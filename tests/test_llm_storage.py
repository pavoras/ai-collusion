"""Durable paid-call safety, bounded retries, cache identity and call caps."""

import asyncio
import json

import pytest

from test_llm_support import tmp_path

from collusion.llm.backend import AmbiguousTransportError, BackendError, FakeBackend, RetryableTransportError
from collusion.llm.storage import BudgetStop, CallService, UncertainCall, digest, write_json

MESSAGES = [{"role": "user", "content": 'Answer {"bid": 3}.'}]
META = {"condition": "N0", "market": 0, "round": 1, "seat": 0, "role": "honest"}


def ask(service, seed=10, **kwargs):
    return service.ask("qwen-9b", MESSAGES, seed, "bid", META, **kwargs)


def test_validation_retry_fresh_seed_and_cache(tmp_path):
    backend = FakeBackend(['{"bid":true}', '{"bid":5}'])
    s = CallService(backend, tmp_path, "retry")
    try:
        assert asyncio.run(ask(s)) == 5
        assert len(backend.calls) == 2
        assert backend.calls[0]["body"]["seed"] != backend.calls[1]["body"]["seed"]
        assert asyncio.run(ask(s)) == 5
        assert len(backend.calls) == 2
        entries = [json.loads(p.read_text()) for p in (s.raw_dir / "calls").glob("*.json")]
        assert sum(e["cache_hit"] for e in entries) == 2
        assert any(e["parsed_value"] is None for e in entries)
        assert all(e["messages"] == MESSAGES and e["prompt_hash"] == digest(MESSAGES) for e in entries)
    finally:
        s.close()


def test_two_invalid_answers_return_none(tmp_path):
    s = CallService(FakeBackend(["invalid", '{"bid":8}']), tmp_path, "invalid")
    try:
        assert asyncio.run(ask(s)) is None
        assert s.calls == 2
    finally:
        s.close()


def test_full_request_cache_identity(tmp_path):
    backend = FakeBackend()
    s = CallService(backend, tmp_path, "identity")
    try:
        request = s.request("qwen-9b", MESSAGES, 1, "bid")
        for key, value in [("seed", 2), ("temperature", .9), ("max_tokens", 65), ("messages", MESSAGES * 2),
                           ("extra_body", {"top_k": 21})]:
            changed = dict(request, body=request["body"] | {key: value})
            assert digest(changed) != digest(request)
        assert digest(request | {"endpoint": "fake://other"}) != digest(request)
        assert digest(request | {"model_key": "qwen-4b"}) != digest(request)
        asyncio.run(ask(s))
    finally:
        s.close()
    replacement = FakeBackend()
    resumed = CallService(replacement, tmp_path, "other_run", max_calls=0)
    try:
        assert asyncio.run(ask(resumed)) is not None
        assert resumed.calls == 0 and not replacement.calls
    finally:
        resumed.close()


def test_same_request_concurrent_deduplication(tmp_path):
    backend = FakeBackend(delay=.001)
    s = CallService(backend, tmp_path, "concurrent")

    async def work():
        return await asyncio.gather(*(ask(s) for _ in range(8)))

    try:
        values = asyncio.run(work())
        assert len(set(values)) == 1 and len(backend.calls) == 1
    finally:
        s.close()


def test_safe_transport_retry_and_cap_counting(tmp_path):
    backend = FakeBackend([RetryableTransportError("not sent"), '{"bid":4}'])
    s = CallService(backend, tmp_path, "transport", backoff=0)
    try:
        assert asyncio.run(ask(s)) == 4
        assert len(backend.calls) == s.calls == 2
        assert backend.calls[0] == backend.calls[1]
    finally:
        s.close()


def test_safe_retries_bounded(tmp_path):
    backend = FakeBackend([RetryableTransportError("no") for _ in range(4)])
    s = CallService(backend, tmp_path, "bounded", transport_retries=1, backoff=0)
    try:
        with pytest.raises(BackendError):
            asyncio.run(ask(s))
        assert s.calls == 2
    finally:
        s.close()


@pytest.mark.parametrize("error", [AmbiguousTransportError("possibly billed"), TimeoutError("lost")])
def test_ambiguous_failure_never_resubmitted(tmp_path, error):
    backend = FakeBackend([error, '{"bid":4}'])
    s = CallService(backend, tmp_path, "uncertain", backoff=0)
    try:
        with pytest.raises(UncertainCall):
            asyncio.run(ask(s))
    finally:
        s.close()
    s = CallService(backend, tmp_path, "uncertain")
    try:
        with pytest.raises(UncertainCall):
            asyncio.run(ask(s))
        assert len(backend.calls) == 1
    finally:
        s.close()


def test_timeout_is_uncertain(tmp_path):
    backend = FakeBackend(delay=.05)
    s = CallService(backend, tmp_path, "timeout", timeout=.001)
    try:
        with pytest.raises(UncertainCall):
            asyncio.run(ask(s))
        assert len(backend.calls) == 1
    finally:
        s.close()


def test_crash_pending_ledger_blocks_dispatch(tmp_path):
    backend = FakeBackend()
    s = CallService(backend, tmp_path, "crash")
    request = s.request("qwen-9b", MESSAGES, 10, "bid")
    s._claim(digest(request), request)
    s.close()
    s = CallService(backend, tmp_path, "crash", pending_wait=.05, pending_poll=.01)
    try:
        with pytest.raises(UncertainCall):
            asyncio.run(ask(s))
        assert not backend.calls
        assert s.calls == 1
    finally:
        s.close()


def test_persistent_budget_and_concurrency(tmp_path):
    backend = FakeBackend(delay=.001)
    s = CallService(backend, tmp_path, "cap", max_calls=3, concurrency=2)

    async def work():
        return await asyncio.gather(*(ask(s, i) for i in range(8)), return_exceptions=True)

    try:
        values = asyncio.run(work())
        assert sum(isinstance(v, BudgetStop) for v in values) == 5
        assert backend.peak_active <= 2
        assert s.calls == len(backend.calls) == 3
    finally:
        s.close()
    s = CallService(backend, tmp_path, "cap", max_calls=3)
    try:
        with pytest.raises(BudgetStop):
            asyncio.run(ask(s, 100))
        assert len(backend.calls) == 3
    finally:
        s.close()


def test_rejected_request_not_repeated(tmp_path):
    backend = FakeBackend([BackendError("secret details must never be logged")])
    s = CallService(backend, tmp_path, "reject")
    try:
        for _ in range(2):
            with pytest.raises(BackendError):
                asyncio.run(ask(s))
        assert len(backend.calls) == 1
        assert "secret details" not in next((s.raw_dir / "calls").glob("*.json")).read_text()
    finally:
        s.close()


def test_independent_services_do_not_both_submit_same_request(tmp_path):
    backend = FakeBackend(delay=.01)
    a = CallService(backend, tmp_path, "first", pending_poll=.005)
    b = CallService(backend, tmp_path, "second", pending_poll=.005)

    async def work():
        return await asyncio.gather(ask(a), ask(b), return_exceptions=True)

    try:
        values = asyncio.run(work())
        assert len(backend.calls) == 1
        assert values[0] == values[1] and not isinstance(values[0], Exception)
        assert a.calls + b.calls == 1
    finally:
        a.close()
        b.close()


def test_transient_windows_checkpoint_replace_is_retried_locally(tmp_path, monkeypatch):
    from collusion.llm import storage
    target = tmp_path / "checkpoint.json"
    write_json(target, {"round": 1})
    original_replace = storage.os.replace
    attempts = []

    def flaky(source, destination):
        attempts.append(source)
        if len(attempts) <= 2:
            error = PermissionError("simulated Windows sharing conflict")
            error.winerror = 5
            raise error
        original_replace(source, destination)

    monkeypatch.setattr(storage.os, "replace", flaky)
    monkeypatch.setattr(storage.time, "sleep", lambda _: None)
    write_json(target, {"round": 2})
    assert json.loads(target.read_text()) == {"round": 2}
    assert len(attempts) == 3


def test_request_pending_in_another_process_is_awaited(tmp_path):
    backend = FakeBackend(['{"bid":4}'])
    other = CallService(backend, tmp_path, "other")
    s = CallService(backend, tmp_path, "waiting", pending_wait=5, pending_poll=.01)
    request = s.request("qwen-9b", MESSAGES, 10, "bid")
    key = digest(request)
    attempt, _ = other._claim(key, request)

    async def work():
        waiting = asyncio.create_task(ask(s))
        await asyncio.sleep(.05)
        assert not waiting.done()
        other._finish(key, attempt, "complete", 0., response=await backend.complete(request))
        return await waiting

    try:
        assert asyncio.run(work()) == 4
        assert len(backend.calls) == 1
        assert s.calls == 0
    finally:
        s.close()
        other.close()
