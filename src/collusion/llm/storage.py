"""Durable, fail-closed response cache and persistent per-run call budgets.

SQLite commits a pending request before dispatch and the response before use.
A crash in between leaves a pending request which cannot be resubmitted. This
trades availability for avoiding duplicate billing without server idempotency.
All attempts, including safe transport retries, count against max_calls.
"""

import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .backend import BackendError, Response, RetryableTransportError
from .parsing import parse
from .prompts import VERSION
from .sampling import sampling_for

TOKEN_LIMITS = {"bid": 64, "message": 128, "judge": 12000}


class BudgetStop(Exception):
    """No further backend submissions are authorised by the call cap."""


class SafeRetriesExhausted(BackendError):
    """Every attempt failed before reaching a model server; nothing can have been paid."""


class UncertainCall(Exception):
    """A pending/ambiguous request needs external reconciliation before reuse."""


class PendingElsewhere(UncertainCall):
    """Another process has submitted the identical request and has not finished it yet."""


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def seed_for(*parts):
    """Stable independent streams, unaffected by scheduling or Python hash salt."""
    return int(digest(parts)[:8], 16) % (2**31)


def write_json(path, value):
    """Flush then atomically replace a checkpoint or audit record."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    for retry in range(6):
        try:
            os.replace(temporary, path)
            break
        except PermissionError as error:
            # Windows indexers/virus scanners can briefly deny replacement.
            # Retry only this local operation; never re-dispatch a model call.
            if getattr(error, "winerror", None) not in (5, 32) or retry == 5:
                raise
            time.sleep(.01 * 2**retry)


class CallService:
    """Shared concurrency, bounded safe retries, cache and validation retry."""

    def __init__(self, backend, root, run_id, *, max_calls=1000, concurrency=8,
                 timeout=1200, transport_retries=2, backoff=0.5, pending_wait=None, pending_poll=2.):
        if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in run_id):
            raise ValueError("run_id must contain only letters, numbers, hyphens or underscores")
        if max_calls < 0 or concurrency < 1 or timeout <= 0 or transport_retries < 0 or backoff < 0:
            raise ValueError("invalid budget or transport settings")
        self.backend = backend
        self.root = Path(root)
        self.run_id = run_id
        self.max_calls = max_calls
        self.timeout = timeout
        self.transport_retries = transport_retries
        self.backoff = backoff
        # Seed-paired cells run in parallel processes and share requests: wait for the other process's answer
        # (then a cache hit) instead of failing; a key still pending after this long is treated as uncertain.
        self.pending_wait = timeout if pending_wait is None else pending_wait
        self.pending_poll = pending_poll
        self.semaphore = asyncio.Semaphore(concurrency)
        self.locks = {}
        self.guard = None
        self.observer = None
        self.parse_fenced = False
        self.raw_dir = self.root / "raw" / run_id
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "raw" / "response_cache.sqlite3", isolation_level=None, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS requests (
                key TEXT PRIMARY KEY, request TEXT NOT NULL, state TEXT NOT NULL, response TEXT);
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, key TEXT NOT NULL,
                state TEXT NOT NULL, latency REAL, error TEXT);
            CREATE INDEX IF NOT EXISTS attempts_run ON attempts(run_id);
        """)

    def close(self):
        self.db.close()

    def bind_cohort(self, name, reason):
        """Deviations cannot append to a declared collection directory."""
        if name is None:
            if reason:
                raise ValueError("deviation reason needs a cohort name")
            return
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name) or not reason or not reason.strip():
            raise ValueError("a safe deviation cohort name and nonempty reason are required")
        suffix = "__deviation_" + name
        if self.run_id.endswith(suffix):
            return
        if self.locks:
            raise ValueError("cannot change cohort after using this call service")
        self.run_id += suffix
        self.raw_dir = self.root / "raw" / self.run_id
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @property
    def calls(self):
        return self.db.execute("SELECT count(*) FROM attempts WHERE run_id=?", (self.run_id,)).fetchone()[0]

    def request(self, model, messages, seed, kind, *, thinking=False, max_tokens=None):
        sampling = sampling_for(model, thinking)
        body = {"model": "llm", "messages": messages, **sampling,
                "seed": seed, "max_tokens": max_tokens or TOKEN_LIMITS[kind]}
        return {"model_key": model, "endpoint": self.backend.identity(model), "body": body,
                "prompt_version": VERSION}

    def _claim(self, key, request):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT state,response FROM requests WHERE key=?", (key,)).fetchone()
            if row and row[0] == "complete":
                self.db.execute("COMMIT")
                return None, Response(**json.loads(row[1]))
            if row and row[0] == "pending":
                raise PendingElsewhere(f"request {key}: in flight in another process")
            if row and row[0] == "uncertain":
                raise UncertainCall(f"request {key}: possible prior submission; automatic resubmission blocked")
            if row and row[0] == "rejected":
                raise BackendError("request was previously rejected; change the request/configuration before retrying")
            if self.guard is not None:
                self.guard()
            if self.calls >= self.max_calls:
                raise BudgetStop("persistent max_calls cap reached")
            self.db.execute("INSERT INTO requests VALUES (?,?,?,NULL) ON CONFLICT(key) DO UPDATE SET state='pending'",
                            (key, canonical(request), "pending"))
            cursor = self.db.execute("INSERT INTO attempts(run_id,key,state) VALUES (?,?,'pending')", (self.run_id, key))
            self.db.execute("COMMIT")
            return cursor.lastrowid, None
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    async def _claim_waiting(self, key, request):
        deadline = time.monotonic() + self.pending_wait
        while True:
            try:
                return self._claim(key, request)
            except PendingElsewhere:
                if time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(self.pending_poll)

    def _finish(self, key, attempt, state, latency, response=None, error=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("UPDATE requests SET state=?,response=? WHERE key=?",
                            (state, canonical(asdict(response)) if response is not None else None, key))
            self.db.execute("UPDATE attempts SET state=?,latency=?,error=? WHERE id=?", (state, latency, error, attempt))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _log(self, request, metadata, kind, *, attempt=None, response=None, latency=0, cache_hit=False, error=None):
        value = parse(response.content, kind, self.parse_fenced) if response else None
        entry = {**metadata, "run_id": self.run_id, "kind": kind, "model": request["model_key"], "request": request,
                 "prompt_version": request["prompt_version"],
                 "sampling": {k: v for k, v in request["body"].items() if k not in ("model", "messages", "seed", "max_tokens")},
                 "request_hash": digest(request), "prompt_hash": digest(request["body"]["messages"]),
                 "messages": request["body"]["messages"], "seed": request["body"]["seed"],
                 "attempt_id": attempt, "cache_hit": cache_hit, "latency": latency,
                 "raw_answer": response.content if response else None, "parsed_value": value,
                 "prompt_tokens": response.prompt_tokens if response else None,
                 "completion_tokens": response.completion_tokens if response else None,
                 "cached_prompt_tokens": response.cached_prompt_tokens if response else None,
                 "response": asdict(response) if response else None, "error": error}
        name = f"attempt_{attempt:08d}" if attempt is not None else f"cache_{uuid.uuid4().hex}"
        write_json(self.raw_dir / "calls" / f"{name}.json", entry)
        if self.observer is not None:
            self.observer(entry)

    async def _response(self, request, metadata, kind):
        key = digest(request)
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            for retry in range(self.transport_retries + 1):
                current_metadata = {**metadata, "transport_attempt": retry}
                async with self.semaphore:
                    attempt, cached = await self._claim_waiting(key, request)
                    if cached is not None:
                        self._log(request, current_metadata, kind, response=cached, cache_hit=True)
                        return cached
                    # Retain the observations even if the process dies inside the backend.
                    try:
                        self._log(request, current_metadata, kind, attempt=attempt, error="pending_submission")
                    except OSError:
                        self._finish(key, attempt, "safe_failure", 0., error="audit_write_failed_before_submission")
                        raise
                    started = time.perf_counter()
                    try:
                        response = await asyncio.wait_for(self.backend.complete(request), timeout=self.timeout)
                    except RetryableTransportError:
                        latency = time.perf_counter() - started
                        self._finish(key, attempt, "safe_failure", latency, error="definitely_not_submitted_or_rate_rejected")
                        self._log(request, current_metadata, kind, attempt=attempt, latency=latency, error="safe_transport_failure")
                        if retry == self.transport_retries:
                            raise SafeRetriesExhausted("safe transport retries exhausted") from None
                    except BackendError:
                        latency = time.perf_counter() - started
                        self._finish(key, attempt, "rejected", latency, error="endpoint_rejection")
                        self._log(request, current_metadata, kind, attempt=attempt, latency=latency, error="endpoint_rejection")
                        raise BackendError("endpoint rejected request; see redacted audit status") from None
                    except BaseException as error:
                        latency = time.perf_counter() - started
                        self._finish(key, attempt, "uncertain", latency, error=type(error).__name__)
                        self._log(request, current_metadata, kind, attempt=attempt, latency=latency, error="uncertain_submission")
                        if isinstance(error, (asyncio.CancelledError, KeyboardInterrupt, SystemExit)):
                            raise
                        raise UncertainCall(f"request {key}: reply uncertain; automatic resubmission blocked") from None
                    else:
                        latency = time.perf_counter() - started
                        self._finish(key, attempt, "complete", latency, response=response)
                        self._log(request, current_metadata, kind, attempt=attempt, response=response, latency=latency)
                        return response
                await asyncio.sleep(self.backoff * 2**retry)

    async def ask(self, model, messages, seed, kind, metadata, *, thinking=False, max_tokens=None):
        """One validation retry with a distinct seed; None means no bid/message."""
        request = self.request(model, messages, seed, kind, thinking=thinking, max_tokens=max_tokens)
        return await self.ask_request(request, kind, metadata)

    async def ask_request(self, request, kind, metadata):
        """Preserve a complete frozen request, changing only retry randomness."""
        request = {"prompt_version": VERSION, **request}
        seed = request["body"]["seed"]
        for retry in range(2):
            actual_seed = seed if retry == 0 else seed_for(seed, "validation_retry")
            current = {**request, "body": {**request["body"], "seed": actual_seed}}
            response = await self._response(current, {**metadata, "validation_attempt": retry}, kind)
            value = parse(response.content, kind, self.parse_fenced)
            if value is not None:
                return value
        return None
