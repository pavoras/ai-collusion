"""Operational gates, blinded reporting, warm-up barriers and pilot resume."""

import asyncio
from dataclasses import replace
import json
import re

import pytest

from test_llm_support import tmp_path, run_config as RunConfig
from collusion.llm.backend import FakeBackend, RetryableTransportError
from collusion.llm import pilot
from collusion.llm.pilot import PilotLimits, run_pilot
from collusion.llm.projection import scope_projection
from collusion.llm.prompts import VERSION
from collusion.llm.storage import CallService


@pytest.fixture(autouse=True)
def no_unit_test_figures(monkeypatch):
    monkeypatch.setattr(pilot, "plot_operations", lambda *args: None)


class ChangingBackend(FakeBackend):
    def __init__(self, mode=None, delay=0):
        super().__init__(delay=delay)
        self.mode, self.ready = mode, False
        self.failed = set()

    async def complete(self, request):
        text = request["body"]["messages"][-1]["content"]
        match = re.match(r"Round (\d+)\.", text)
        if match:
            assert self.ready, "markets must not start before the warm-up reply"
        response = await super().complete(request)
        response.cached_prompt_tokens = 7
        if not match:
            self.ready = True
            return response
        round_number = int(match[1])
        if self.mode == "invalid" and round_number >= 4:
            response.content = "invalid"
        if self.mode == "constant" and "Your cost range is {1, 2, 3}" in request["body"]["messages"][0]["content"]:
            response.content = '{"bid": 4}'
        if self.mode == "transport" and round_number >= 10:
            key = request["body"]["seed"]
            if key not in self.failed:
                self.failed.add(key)
                raise RetryableTransportError("not submitted")
        response.raw["content"] = response.content
        return response


def collect(root, backend=None, *, run_id="pilot", config=None, max_calls=1000, limits=None):
    backend = backend or ChangingBackend()
    # A resumed process still has to warm up; ready is set by its warm-up request.
    s = CallService(backend, root, run_id, max_calls=max_calls, concurrency=128, backoff=0)
    try:
        report, projection = asyncio.run(run_pilot(config or RunConfig(rounds=12), s,
            limits=limits or PilotLimits(max_p95_seconds=1000)))
        return report, projection, backend
    finally:
        s.close()


def test_warmup_then_all_40_markets_concurrent_and_blinded(tmp_path):
    config = RunConfig(rounds=2, markets=20)
    report, projection, backend = collect(tmp_path, ChangingBackend(delay=.001), config=config)
    assert report["status"] == "complete" and report["warmup_calls_completed"] == 1
    assert 80 < backend.peak_active <= 120
    assert report["cold_start_seconds"] > 0
    assert report["cached_prompt_tokens"] == 7 * (report["market_transport_attempts"] - report["transport_errors"])
    assert report["calls_per_hour_under_load"] > 0
    assert len(list((tmp_path / "llm/pilot__deviation_tests/N0").glob("market_*.json"))) == 20
    assert len(list((tmp_path / "llm/pilot__deviation_tests/P0").glob("market_*.json"))) == 20
    text = json.dumps(report).lower()
    for forbidden in ("detector", "gamma", "net_influence", "profit", "payoff", "winner", "cartel_outcome", "auroc"):
        assert forbidden not in text
    assert projection["measurement_source"] == "offline_fake_not_endpoint_performance"
    calls = [json.loads(p.read_text()) for p in (tmp_path / "raw/pilot__deviation_tests/calls").glob("*.json")]
    assert all(e["prompt_version"] == e["request"]["prompt_version"] == VERSION for e in calls)
    assert all(e["sampling"]["temperature"] == .7 for e in calls)


@pytest.mark.parametrize("mode,reason", [("invalid", "invalid_answer_rate_above_5_percent"),
                                          ("constant", "constant_bid_strong"),
                                          ("transport", "transport_error_rate_above_2_percent")])
def test_continuous_abort_gates_start_at_round_10(tmp_path, mode, reason):
    report, _, backend = collect(tmp_path, ChangingBackend(mode), config=RunConfig(rounds=20))
    assert report["status"] == "stopped" and report["stop_reason"] == reason
    assert report["calls"] < 121
    logs = [json.loads(p.read_text()) for p in (tmp_path / "raw/pilot__deviation_tests/calls").glob("*.json")]
    assert max(e["round"] or 0 for e in logs) >= 10
    assert all(json.loads(p.read_text())["planned_rounds"] == 20 for p in (tmp_path / "llm/pilot__deviation_tests").glob("*/market_*.json"))


def test_latency_gate_excludes_warmup_and_starts_at_10(tmp_path):
    report, _, _ = collect(tmp_path, ChangingBackend(delay=.002), config=RunConfig(rounds=20),
                           limits=PilotLimits(max_p95_seconds=.001))
    assert report["status"] == "stopped" and report["stop_reason"] == "p95_latency_above_limit"


def test_budget_stop_resume_extension_and_new_indices(tmp_path):
    config = RunConfig(rounds=3)
    stopped, _, _ = collect(tmp_path, config=config, max_calls=8)
    assert stopped["stop_reason"] == "max_calls" and stopped["calls"] == 8
    resumed, _, _ = collect(tmp_path, config=config, max_calls=100)
    assert resumed["status"] == "complete"
    before = resumed["calls"]
    repeated, _, _ = collect(tmp_path, config=config, max_calls=100)
    assert repeated["new_calls"] == 0 and repeated["calls"] == before
    old = json.loads((tmp_path / "llm/pilot__deviation_tests/N0/market_00000.json").read_text())
    extended, _, _ = collect(tmp_path, config=replace(config, rounds=5), max_calls=200)
    assert extended["status"] == "complete"
    grown = json.loads((tmp_path / "llm/pilot__deviation_tests/N0/market_00000.json").read_text())
    assert grown["costs"][:3] == old["costs"] and grown["bids"][:3] == old["bids"]
    appended, _, _ = collect(tmp_path, config=replace(config, rounds=5, market_start=20), max_calls=200)
    assert appended["status"] == "complete"
    assert (tmp_path / "llm/pilot__deviation_tests/N0/market_00020.json").is_file()
    assert (tmp_path / "llm/pilot__deviation_tests/P0/market_00020.json").is_file()


def test_wall_budget_persists_and_prevents_new_submissions(tmp_path):
    limits = PilotLimits(max_minutes=.001, max_p95_seconds=1000)
    report, _, _ = collect(tmp_path, ChangingBackend(delay=.01), config=RunConfig(rounds=30), limits=limits)
    assert report["status"] == "stopped" and report["stop_reason"] == "max_wall_minutes"
    again, _, _ = collect(tmp_path, config=RunConfig(rounds=30), limits=limits)
    assert again["new_calls"] == 0 and again["calls"] == report["calls"]


def test_completed_warmup_after_crash_is_recovered_without_false_readiness(tmp_path):
    config = RunConfig(rounds=2)
    first, _, _ = collect(tmp_path, config=config)
    path = tmp_path / "raw/pilot__deviation_tests/pilot_progress.json"
    progress = json.loads(path.read_text())
    progress["warmups"][-1]["status"] = "pending"
    path.write_text(json.dumps(progress))
    report, _, _ = collect(tmp_path, config=replace(config, rounds=3))
    assert report["status"] == "complete" and report["warmup_calls_completed"] == 2
    assert report["calls"] > first["calls"]


def test_different_run_ids_use_fresh_warmups(tmp_path):
    collect(tmp_path, config=RunConfig(rounds=2), run_id="first")
    report, _, backend = collect(tmp_path, config=RunConfig(rounds=2), run_id="second")
    assert report["status"] == "complete" and backend.ready
    assert len(backend.calls) == 1  # Market requests are shared, readiness is measured afresh.


def test_persistent_checkpoint_error_stops_new_submissions_and_resumes(tmp_path, monkeypatch):
    from collusion.llm import runner
    original_write = runner.write_json

    def fail_checkpoint(path, value):
        if path.name.startswith("market_") and value["bids"]:
            raise OSError("simulated checkpoint write failure")
        original_write(path, value)

    monkeypatch.setattr(runner, "write_json", fail_checkpoint)
    report, _, _ = collect(tmp_path, config=RunConfig(rounds=3))
    assert report["status"] == "stopped" and report["stop_reason"] == "checkpoint_io_error"
    before = report["calls"]
    monkeypatch.setattr(runner, "write_json", original_write)
    resumed, _, _ = collect(tmp_path, config=RunConfig(rounds=3))
    assert resumed["status"] == "complete"
    assert resumed["calls"] - before < 18


def test_projection_covers_scope_and_marks_unmeasured_assumptions():
    projection = scope_projection(3600)
    assert projection["total_calls"] == 288220  # B0 incl. core.N0 markets 20-39
    for block, expected in [("core", 144000), ("labs", 40000), ("sizes", 60000), ("mixed", 40000)]:
        assert sum(r["calls"] for r in projection["rows"] if r["block"] == block) == expected
    qwen = next(r for r in projection["rows"] if r["block"] == "core" and r["condition"] == "N0")
    assert qwen["projected_gpu_hours"] == 32000 / 3600
    assert qwen["projected_usd"] == 32000 / 3600 * 1.95
    gemma = next(r for r in projection["rows"] if r["block"] == "labs" and r["model"] == "gemma-12b")
    assert gemma["time_scale_vs_qwen9_bidder"] == 12 / 9 and gemma["basis"] == "scaled assumption"
    assert all(r["usd_per_gpu_hour"] == (1.1 if r["gpu"] == "A10" else 1.95) for r in projection["rows"])
    assert scope_projection(None)["total_projected_usd"] is None


@pytest.mark.parametrize("settings", [{"market_concurrency": 0}, {"probe_calls": -1}, {"judge_work_factor": float("nan")}])
def test_invalid_pilot_configuration_rejected_before_any_submission(tmp_path, settings):
    backend = FakeBackend()
    service = CallService(backend, tmp_path, "invalid_config")
    try:
        with pytest.raises(ValueError):
            asyncio.run(run_pilot(RunConfig(rounds=2), service, **settings))
        assert not backend.calls and service.calls == 0
    finally:
        service.close()
