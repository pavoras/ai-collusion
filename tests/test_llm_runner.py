"""Pairing, interruption recovery, no-bid settlement and mixed populations."""

import asyncio
from dataclasses import replace
import json

import numpy as np
import pytest

from test_llm_support import tmp_path, run_config as RunConfig

from collusion.games import auction
from collusion.llm.backend import FakeBackend
from collusion.llm.runner import context_for, market_randomness, run
from collusion.llm.storage import CallService, seed_for
from collusion.llm.collection import resolve_market


def execute(root, run_id, config, **kwargs):
    backend = FakeBackend()
    s = CallService(backend, root, run_id, **kwargs)
    try:
        states = asyncio.run(run(config, s))
        return states, len(backend.calls)
    finally:
        s.close()


def test_cost_and_tie_pairing_matches_scripted():
    config = RunConfig(rounds=20)
    costs, ties = market_randomness(config, 5)
    scripted = auction.play(20, market_index=5, seed=config.seed, strong=resolve_market(config, 5).strong)
    np.testing.assert_array_equal(costs, scripted.costs)
    for condition, models in [("C1", ("x",) * 4), ("E1", ("a", "b", "c", "d"))]:
        changed = replace(config, condition=condition, models=models)
        paired_costs, paired_ties = market_randomness(changed, 5)
        np.testing.assert_array_equal(costs, paired_costs)
        np.testing.assert_array_equal(ties, paired_ties)
    different, _ = market_randomness(config, 6)
    assert not np.array_equal(costs, different)
    assert seed_for(config.seed, 5, 3, 0, "bid") != seed_for(config.seed, 5, 3, 1, "bid")


@pytest.mark.parametrize("condition,per_round", [("N0", 4), ("D", 4), ("C1", 6), ("M2", 6), ("C2", 4), ("E1", 4), ("P0", 2)])
def test_all_condition_call_counts_and_outputs(tmp_path, condition, per_round):
    config = RunConfig(condition=condition, rounds=3)
    states, calls = execute(tmp_path, condition, config)
    state = states[0]
    assert state["status"] == "complete"
    assert len(state["bids"]) == 3
    assert calls == per_round * 3
    for key in ["bids", "costs", "payoffs", "messages", "invalid", "message_invalid"]:
        assert np.shape(state[key]) == (3, 4)
    assert all(2 <= b <= 7 for row in state["bids"] for b in row)
    assert not np.any(state["invalid"])
    records = [json.loads(p.read_text()) for p in (tmp_path / "raw" / (condition + "__deviation_tests") / "calls").glob("*.json")]
    assert all(e["response"]["raw"]["offline"] for e in records)
    assert all(e["request"]["body"]["temperature"] == .7 for e in records)
    assert all(e["request"]["body"]["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False} for e in records)
    if condition in ("C1", "M2"):
        pair = resolve_market(config, 0).pair
        assert all(all(bool(value) == (seat in pair) for seat, value in enumerate(row)) for row in state["messages"])
        for entry in records:
            if entry["kind"] == "message":
                assert entry["context"]["partner_message"] is None
                assert entry["context"]["own_message"] is None
            elif entry["role"] == "cartel_channel":
                assert entry["context"]["partner_message"] is not None
                assert entry["context"]["own_message"] is not None
    assert state["complete_round_mask"] == [True] * 3


def test_retry_to_no_bid_and_all_missing_settlement(tmp_path):
    s = CallService(FakeBackend(["invalid"] * 8), tmp_path, "no_bid")
    try:
        state = asyncio.run(run(RunConfig(rounds=1), s))[0]
        assert state["bids"] == [[None] * 4]
        assert state["winners"] == [-1]
        assert state["payoffs"] == [[0] * 4]
        assert state["invalid"] == [[True] * 4]
        assert s.calls == 8
    finally:
        s.close()


def test_partial_no_bid_cannot_win(tmp_path):
    class OneInvalid(FakeBackend):
        async def complete(self, request):
            result = await super().complete(request)
            if "You are Firm A." in request["body"]["messages"][0]["content"]:
                result.content = "invalid"
            return result

    s = CallService(OneInvalid(), tmp_path, "partial_invalid")
    try:
        state = asyncio.run(run(RunConfig(rounds=2), s))[0]
        seat = state["metadata"]["assignment"]["labels_by_seat"].index("Firm A")
        assert all(row[seat] is None for row in state["bids"])
        assert all(w != seat for w in state["winners"])
        assert all(row[seat] == 0 for row in state["payoffs"])
        assert state["complete_round_mask"] == [False, False]
    finally:
        s.close()


def test_resume_partial_round_without_repaying(tmp_path):
    config = RunConfig(condition="C1", rounds=3)
    states, calls = execute(tmp_path, "resume", config, max_calls=9)
    assert calls == 9
    assert states[0]["status"] == "budget_stop" and len(states[0]["bids"]) == 1
    resumed, new_calls = execute(tmp_path, "resume", config, max_calls=18)
    assert resumed[0]["status"] == "complete"
    assert new_calls == 9
    reference, full_calls = execute(tmp_path / "reference", "full", config)
    assert full_calls == 18 and resumed == reference
    again, new_calls = execute(tmp_path, "resume", config, max_calls=18)
    assert new_calls == 0 and again == resumed


def test_crash_after_responses_before_checkpoint(tmp_path, monkeypatch):
    from collusion.llm import runner
    config = RunConfig(rounds=2)
    real_write = runner.write_json

    def crash(path, value):
        if path.name.startswith("market_") and value["bids"]:
            raise RuntimeError("simulated checkpoint interruption")
        return real_write(path, value)

    monkeypatch.setattr(runner, "write_json", crash)
    s = CallService(FakeBackend(), tmp_path, "crash_round")
    try:
        with pytest.raises(RuntimeError, match="checkpoint interruption"):
            asyncio.run(run(config, s))
        assert s.calls == 4
    finally:
        s.close()
    monkeypatch.setattr(runner, "write_json", real_write)
    resumed, calls = execute(tmp_path, "crash_round", config)
    assert calls == 4 and resumed[0]["status"] == "complete"


def test_config_change_blocked_before_new_calls(tmp_path):
    config = RunConfig(rounds=1)
    execute(tmp_path, "immutable", config)
    backend = FakeBackend()
    s = CallService(backend, tmp_path, "immutable")
    try:
        with pytest.raises(ValueError, match="configuration changed"):
            asyncio.run(run(replace(config, cartel_position="fringe_fringe"), s))
        assert not backend.calls
    finally:
        s.close()


def test_mixed_models_seats_and_spy(tmp_path):
    config = RunConfig(condition="E1", models=("qwen-9b", "gemma-12b", "ministral-8b", "qwen-4b"),
                       rounds=2, markets=3)
    backend = FakeBackend(delay=.001)
    s = CallService(backend, tmp_path, "mixed", concurrency=3)
    try:
        states = asyncio.run(run(config, s, market_concurrency=3))
        assert len(states) == 3 and s.calls == 24
        assert 1 < backend.peak_active <= 3
        records = [json.loads(p.read_text()) for p in (s.raw_dir / "calls").glob("*.json")]
        for e in records:
            assignment = states[e["market"]]["metadata"]["assignment"]
            assert e["model"] == assignment["models_by_seat"][e["seat"]]
            if e["role"] == "spy":
                victim = assignment["spy_victim"]
                assert e["seat"] == assignment["spy_receiver"] and e["context"]["victim"] == victim
                state = states[e["market"]]
                assert e["context"]["leaked_cost"] == state["costs"][e["round"] - 1][victim]
            else:
                assert "Informant:" not in e["messages"][-1]["content"]
    finally:
        s.close()


def test_context_cumulative_and_ten_round_window():
    config = RunConfig(rounds=15)
    state = {"bids": [[2, 3, 4, 5]] * 14, "winners": [0] * 14, "payoffs": [[1, 0, 0, 0]] * 14}
    costs, _ = market_randomness(config, 0)
    context = context_for(config, state, costs, 14, 0)
    assert len(context.history) == 10
    assert context.history[0]["round"] == 5 and context.history[-1]["round"] == 14
    assert context.cumulative_profit == 14
