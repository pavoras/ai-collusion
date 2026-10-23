"""Concurrent N0/P0 data collection with continuously checked operational gates.

No detector, payoff comparison or winner analysis is performed here. A stop
blocks further submissions and drains in-flight requests to preserve replies.
Raw calls and compact market data retain the information for later analysis.
"""

import asyncio
from bisect import insort
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import json
import math
import time

from .backend import BackendError, FakeBackend
from .projection import save_projection, scope_projection
from .runner import RunLock, _all, _market, run_identity, save_manifest
from .storage import BudgetStop, UncertainCall, digest, seed_for, write_json
from .collection import authorize, load_collection, resolve_market
from .reproducibility import record_server_version, write_reproducibility


class PilotStop(BudgetStop):
    """A shared operational gate has stopped submissions across all markets."""


@dataclass(frozen=True)
class PilotLimits:
    max_minutes: float = 75
    max_p95_seconds: float = 60
    warmup_timeout: float = 1200
    gate_round: int = 10

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in (self.max_minutes, self.max_p95_seconds, self.warmup_timeout)) or self.gate_round < 10:
            raise ValueError("positive pilot limits and a gate round of at least 10 required")


def percentile(ordered, q):
    if not ordered:
        return None
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _read_log(path):
    return json.loads(path.read_text(encoding="utf-8"))


class PilotMonitor:
    """Consume only whitelisted operational fields from each durable audit event."""

    def __init__(self, service, strong, limits, progress=None):
        self.service, self.strong, self.limits = service, set(strong), limits
        self.progress = progress or {"wall_seconds": 0., "load_seconds": 0., "warmups": []}
        self.started = time.perf_counter()
        self.load_started = None
        self.reason = None
        self.max_round = 0
        self.attempts = self.responses = self.invalid = self.transport_errors = 0
        self.validation_retries = self.transport_retries = self.cache_hits = 0
        self.prompt_tokens = self.completion_tokens = self.cached_prompt_tokens = 0
        self.usage_missing = self.cached_usage_reported = 0
        self.latencies = []
        self.histograms = {name: {str(b): 0 for b in range(2, 8)} for name in ("strong", "fringe")}
        self.seen_attempts, self.seen_responses, self.seen_bids = set(), set(), set()
        self.warmup_latencies = {}
        paths = list((service.raw_dir / "calls").glob("*.json"))
        # Prefetch bounded batches: Windows per-file access can dominate resume.
        # Only reads run in workers; counter updates remain on the caller thread.
        with ThreadPoolExecutor(max_workers=8) as pool:
            for start in range(0, len(paths), 64):
                for event in pool.map(_read_log, paths[start:start + 64]):
                    self.record(event, evaluate=False)

    @property
    def wall_seconds(self):
        return self.progress["wall_seconds"] + time.perf_counter() - self.started

    @property
    def load_seconds(self):
        return self.progress["load_seconds"] + (time.perf_counter() - self.load_started if self.load_started is not None else 0)

    def fail(self, reason):
        if self.reason is None:
            self.reason = "max_calls" if "max_calls" in reason else reason

    def record(self, event, *, evaluate=True):
        if event.get("purpose") == "warmup":
            if event["response"] is not None and not event["cache_hit"]:
                self.warmup_latencies[event["seed"]] = event["latency"]
            return
        if event.get("condition") not in ("N0", "P0") or event.get("error") == "pending_submission":
            return
        self.max_round = max(self.max_round, event.get("round") or 0)
        if event["cache_hit"]:
            self.cache_hits += 1
        elif event["attempt_id"] not in self.seen_attempts:
            self.seen_attempts.add(event["attempt_id"])
            self.attempts += 1
            self.transport_retries += int(event.get("transport_attempt", 0) > 0)
            self.validation_retries += int(event.get("validation_attempt", 0) > 0 and event.get("transport_attempt", 0) == 0)
            self.transport_errors += int(event["error"] in ("safe_transport_failure", "uncertain_submission"))
            if event["response"] is not None:
                insort(self.latencies, event["latency"])
                self.prompt_tokens += event["prompt_tokens"] or 0
                self.completion_tokens += event["completion_tokens"] or 0
                self.cached_prompt_tokens += event.get("cached_prompt_tokens") or 0
                self.cached_usage_reported += int(event.get("cached_prompt_tokens") is not None)
                self.usage_missing += int(event["prompt_tokens"] is None or event["completion_tokens"] is None)
        if event["response"] is not None:
            if event["request_hash"] not in self.seen_responses:
                self.seen_responses.add(event["request_hash"])
                self.responses += 1
                self.invalid += int(event["parsed_value"] is None)
            key = tuple(event.get(k) for k in ("condition", "market", "round", "seat", "kind"))
            if event["kind"] == "bid" and event["parsed_value"] is not None and key not in self.seen_bids:
                self.seen_bids.add(key)
                firm_type = event.get("firm_type", "strong" if event["seat"] in self.strong else "fringe")
                self.histograms[firm_type][str(event["parsed_value"])] += 1
        if evaluate:
            self.evaluate()

    def evaluate(self):
        if self.wall_seconds >= self.limits.max_minutes * 60:
            self.fail("max_wall_minutes")
        if self.max_round < self.limits.gate_round:
            return
        if self.responses and self.invalid / self.responses > .05:
            self.fail("invalid_answer_rate_above_5_percent")
        if self.attempts and self.transport_errors / self.attempts > .02:
            self.fail("transport_error_rate_above_2_percent")
        for firm_type, counts in self.histograms.items():
            if sum(n > 0 for n in counts.values()) == 1:
                self.fail(f"constant_bid_{firm_type}")
        p95 = percentile(self.latencies, .95)
        if p95 is not None and p95 > self.limits.max_p95_seconds:
            self.fail("p95_latency_above_limit")

    def check(self):
        self.evaluate()
        if self.reason is not None:
            raise PilotStop(self.reason)

    def persist(self):
        write_json(self.service.raw_dir / "pilot_progress.json",
                   {**self.progress, "wall_seconds": self.wall_seconds, "load_seconds": self.load_seconds,
                    "stop_reason": self.reason})

    def report(self, status, calls_before):
        """An explicit whitelist prevents research outcomes entering the pilot report."""
        load = self.load_seconds
        warmups = self.progress["warmups"]
        return {"status": status, "stop_reason": self.reason,
                "measurement_source": "offline_fake_not_endpoint_performance" if isinstance(self.service.backend, FakeBackend) else "live_qwen9b",
                "calls": self.service.calls, "new_calls": self.service.calls - calls_before,
                "market_transport_attempts": self.attempts, "warmup_calls_completed": sum(w["status"] == "complete" for w in warmups),
                "retries": self.validation_retries + self.transport_retries,
                "validation_retries": self.validation_retries, "transport_retries": self.transport_retries,
                "cache_hits": self.cache_hits, "unique_answer_responses": self.responses,
                "invalid_answers": self.invalid, "invalid_answer_rate": self.invalid / self.responses if self.responses else None,
                "transport_errors": self.transport_errors,
                "transport_error_rate": self.transport_errors / self.attempts if self.attempts else None,
                "bid_histogram_llm_only": self.histograms,
                "latency_p50_seconds": percentile(self.latencies, .5), "latency_p95_seconds": percentile(self.latencies, .95),
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "cached_prompt_tokens": self.cached_prompt_tokens if self.cached_usage_reported else None,
                "token_usage_missing_calls": self.usage_missing,
                "cold_start_seconds": warmups[0].get("cold_start_seconds") if warmups else None,
                "wall_seconds": self.wall_seconds, "load_seconds": load,
                "calls_per_hour_under_load": len(self.latencies) * 3600 / load if load > 0 else None,
                "thresholds": {"gate_from_round": self.limits.gate_round, "max_invalid_rate": .05, "max_transport_error_rate": .02,
                               "max_p95_seconds": self.limits.max_p95_seconds, "max_calls": self.service.max_calls,
                               "max_wall_minutes": self.limits.max_minutes},
                "definitions": "Invalid rate counts unique received answers (including validation retries/cache reuse); transport rate counts backend attempts. "
                               "Tokens/latencies/throughput exclude warm-up and cache hits. Histogram includes valid LLM bids only. "
                               "Wall budget persists across resumes, excludes downtime, stops dispatch and drains in-flight calls."}


async def _warmup(service, monitor, config):
    warmups = monitor.progress["warmups"]
    if not warmups or warmups[-1]["status"] == "complete":
        warmups.append({"seed": seed_for(config.seed, service.run_id, "pilot_warmup", len(warmups)), "status": "pending"})
    warmup = warmups[-1]
    monitor.persist()
    prompt = f"Warm-up {service.run_id}, session {len(warmups) - 1}.\n" + 'Reply only with JSON {"bid": 2}.'
    request = service.request("qwen-9b", [{"role": "user", "content": prompt}],
                              warmup["seed"], "bid")
    previous = service.db.execute("SELECT state FROM requests WHERE key=?", (digest(request),)).fetchone()
    if previous and previous[0] == "complete":
        # Recover a reply committed before a crash, then actually check readiness
        # with one new warm-up. Never treat a cached reply as endpoint readiness.
        warmup.update(status="complete", cold_start_seconds=monitor.warmup_latencies.get(warmup["seed"]))
        monitor.persist()
        return await _warmup(service, monitor, config)
    saved_timeout, saved_retries = service.timeout, service.transport_retries
    backend_timeout = getattr(service.backend, "timeout", None)
    try:
        service.timeout, service.transport_retries = monitor.limits.warmup_timeout, 0
        if backend_timeout is not None:
            service.backend.timeout = monitor.limits.warmup_timeout
        await service._response(request, {"condition": "warmup", "market": None, "round": None, "seat": None,
                                         "role": "warmup", "purpose": "warmup"}, "bid")
        await record_server_version(service, "qwen-9b")
        warmup.update(status="complete", cold_start_seconds=monitor.warmup_latencies.get(warmup["seed"]))
        monitor.persist()
    finally:
        service.timeout, service.transport_retries = saved_timeout, saved_retries
        if backend_timeout is not None:
            service.backend.timeout = backend_timeout


async def run_pilot(config, service, *, limits=None, market_concurrency=None, probe_calls=None, judge_work_factor=10):
    """Warm up once, then run both conditions together without inspecting outcomes."""
    if config.models != ("qwen-9b",) * 4 or config.condition != "N0":
        raise ValueError("pilot requires the single qwen-9b endpoint and an N0 base configuration")
    slots = 2 * config.markets if market_concurrency is None else market_concurrency
    if slots < 1:
        raise ValueError("market concurrency must be positive")
    manifest = load_collection(config.collection_manifest)
    probe_calls = manifest["parameters"]["probe_calls"]["value"] if probe_calls is None else probe_calls
    if probe_calls < 0 or not math.isfinite(judge_work_factor) or judge_work_factor <= 0:
        raise ValueError("nonnegative probe calls and a finite positive judge work factor required")
    entries = {e["id"]: e for e in manifest["entries"]}
    cells = [entries[key] for key in manifest["pilot_entries"]]
    if [(e["condition"], e["models_by_role"]) for e in cells] != [
            (c, dict(zip(("strong_0", "strong_1", "fringe_0", "fringe_1"), ("qwen-9b",) * 4))) for c in ("N0", "P0")]:
        raise ValueError("manifest pilot must declare qwen-9b N0 and P0")
    configs = [replace(config, condition=e["condition"], entry_id=e["id"], cartel_position=e["position"]) for e in cells]
    for c in configs:
        authorize(c)
    service.bind_cohort(config.deviation_cohort, config.deviation_reason)
    out = service.root / "llm" / service.run_id
    out.mkdir(parents=True, exist_ok=True)
    with RunLock(service.raw_dir / "run.lock"):
        save_manifest(service.raw_dir / "config.json", {"mode": "pilot", "conditions": [run_identity(c, service) for c in configs]},
                      config.rounds, range(config.market_start, config.market_start + config.markets))
        write_reproducibility(service, config, manifest["pilot_entries"], warmup_timeout=(limits or PilotLimits()).warmup_timeout)
        progress_path = service.raw_dir / "pilot_progress.json"
        progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else None
        monitor = PilotMonitor(service, config.strong, limits or PilotLimits(), progress)
        service.guard, service.observer = monitor.check, monitor.record
        calls_before = service.calls
        done = asyncio.Event()

        async def watchdog():
            while not done.is_set():
                monitor.evaluate()
                monitor.persist()
                try:
                    await asyncio.wait_for(done.wait(), .25)
                except TimeoutError:
                    pass

        watcher = asyncio.create_task(watchdog())
        states = []
        try:
            paths = [out / c.condition / f"market_{i:05d}.json" for c in configs
                     for i in range(config.market_start, config.market_start + config.markets)]
            complete = all(p.exists() and len(json.loads(p.read_text(encoding="utf-8"))["bids"]) == config.rounds for p in paths)
            if not complete:
                monitor.check()
                await _warmup(service, monitor, config)
            monitor.load_started = time.perf_counter()
            semaphore = asyncio.Semaphore(slots)

            async def play(c, index):
                async with semaphore:
                    try:
                        return await _market(resolve_market(c, index, manifest), service, index, out / c.condition, monitor)
                    except Exception as error:
                        monitor.fail("checkpoint_io_error" if isinstance(error, OSError) else "market_error")
                        raise

            states = await _all([play(c, i) for c in configs
                                 for i in range(config.market_start, config.market_start + config.markets)])
        except (BudgetStop, UncertainCall, BackendError) as error:
            monitor.fail(str(error) if isinstance(error, BudgetStop) else type(error).__name__)
        except OSError:
            monitor.fail("checkpoint_io_error")
        finally:
            done.set()
            await watcher
            monitor.persist()
            service.guard = service.observer = None
        status = "complete" if states and all(s["status"] == "complete" for s in states) and monitor.reason is None else "stopped"
        report = monitor.report(status, calls_before)
        write_json(out / "pilot_report.json", report)
        projection = scope_projection(report["calls_per_hour_under_load"], fake=isinstance(service.backend, FakeBackend),
                                      probe_calls=probe_calls, judge_work_factor=judge_work_factor, manifest=manifest)
        save_projection(out, projection)
        plot_operations(out, report)
        return report, projection


def plot_operations(out, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from collusion import plotting

    plotting.apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(8, 3), layout="constrained")
    for ax, firm_type, color in zip(axes, ("strong", "fringe"), (plotting.BLUE, plotting.AQUA)):
        counts = report["bid_histogram_llm_only"][firm_type]
        ax.bar(list(counts), list(counts.values()), color=color, label=f"{firm_type.capitalize()} LLM firms")
        ax.set(xlabel="Bid", ylabel="Count")
        ax.legend()
    fig.savefig(out / "operations.png")
    plt.close(fig)
