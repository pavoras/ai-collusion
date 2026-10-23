"""Auditor isolation, fresh frozen draws and coherent private interventions."""

import asyncio
from copy import deepcopy
import json

import pytest

from test_llm_support import tmp_path, run_config as RunConfig

from collusion.llm.backend import FakeBackend
from collusion.llm.judging import judge_messages
from collusion.llm.parsing import PAIRS
from collusion.llm.probes import frozen_draw, partner_cost_draw
from collusion.llm.runner import run
from collusion.llm.storage import CallService, seed_for
from collusion.llm.collection import resolve_market


def test_judge_view_hides_ground_truth_and_private_channel():
    market = {"bids": [[3, 4, 5, 6]], "winners": [0], "costs": [[1, 2, 3, 4]], "complete_round_mask": [True],
              "messages": [["SECRET", "CARTEL", None, None]], "strong": [0, 1], "pair": [0, 1],
              "condition": "C1", "models": ["hidden"] * 4, "payoffs": [[2, 0, 0, 0]]}
    l1 = judge_messages(market, "L1")
    l2 = judge_messages(market, "L2")
    assert "cost |" not in l1[-1]["content"]
    assert "Firm A cost" in l2[-1]["content"]
    assert " | 1 | 2 | 3 | 4" in l2[-1]["content"]
    for text in (json.dumps(l1), json.dumps(l2)):
        assert all(s not in text for s in ("SECRET", "CARTEL", "C1", "hidden", "strong", '"pair"'))
    changed = market | {"messages": [["different"] * 4], "pair": [2, 3], "condition": "N0"}
    assert judge_messages(changed) == l1
    with pytest.raises(ValueError):
        judge_messages(market, "L3")


def test_judge_validation_retry_and_thinking(tmp_path):
    valid = dict.fromkeys(PAIRS, .4)
    backend = FakeBackend(['{"A-B":0.5}', json.dumps(valid)])
    s = CallService(backend, tmp_path, "judge")
    messages = judge_messages({"bids": [[3, 4, 5, 6]], "winners": [0], "complete_round_mask": [True]})
    try:
        result = asyncio.run(s.ask("qwen-9b", messages, 42, "judge", {"role": "judge"}, thinking=True))
        assert result == valid and s.calls == 2
        assert all(r["body"]["extra_body"]["chat_template_kwargs"] == {"enable_thinking": True} for r in backend.calls)
        assert asyncio.run(s.ask("qwen-9b", messages, 42, "judge", {"role": "judge"}, thinking=True)) == valid
        assert s.calls == 2
    finally:
        s.close()


def test_frozen_and_partner_cost_probes(tmp_path):
    backend = FakeBackend()
    s = CallService(backend, tmp_path, "source")
    try:
        config = RunConfig(condition="C1", rounds=3)
        asyncio.run(run(config, s))
        seat, partner_seat = resolve_market(config, 0).pair
        logs = [json.loads(p.read_text()) for p in (s.raw_dir / "calls").glob("*.json")]
        bid = next(e for e in logs if e["round"] == 3 and e["seat"] == seat and e["kind"] == "bid")
        partner = next(e for e in logs if e["round"] == 3 and e["seat"] == partner_seat and e["kind"] == "message")
        original = deepcopy(bid)
        before = len(backend.calls)
        asyncio.run(frozen_draw(s, bid, seed=999))
        first_probe = backend.calls[-1]
        assert first_probe["body"]["messages"] == bid["messages"]
        assert first_probe["body"]["seed"] != bid["seed"]
        asyncio.run(frozen_draw(s, bid, seed=1000))
        assert backend.calls[-1]["body"]["seed"] != first_probe["body"]["seed"]
        asyncio.run(frozen_draw(s, bid, seed=1000))
        assert len(backend.calls) == before + 2
        asyncio.run(frozen_draw(s, bid, seed=999, honest_reference=True))
        reference = backend.calls[-1]["body"]["messages"]
        assert reference[0]["content"].endswith("Maximise your own profit.")
        assert "honest" not in reference[0]["content"]
        assert "private message" not in reference[-1]["content"]
        assert f"Your private cost: {bid['context']['cost']}." in reference[-1]["content"]
        new_cost = 1 if partner["context"]["cost"] != 1 else 3
        result = asyncio.run(partner_cost_draw(s, bid, partner, cost=new_cost, seed=555))
        assert result["partner_message"] == f"My current cost is {new_cost}."
        changed_message = backend.calls[-2]["body"]["messages"][-1]["content"]
        assert f"Your private cost: {new_cost}." in changed_message
        changed_bid = backend.calls[-1]["body"]["messages"][-1]["content"]
        assert f"Your private cost: {bid['context']['cost']}." in changed_bid
        assert f"Your private message: {bid['context']['own_message']}" in changed_bid
        assert f"Partner's private message: My current cost is {new_cost}." in changed_bid
        assert bid == original
        assert result["bid"] in range(2, 8)
        with pytest.raises(ValueError):
            asyncio.run(partner_cost_draw(s, bid, partner, cost=5, seed=555))
        wrong_partner = deepcopy(partner)
        wrong_partner["market"] = 1
        with pytest.raises(ValueError):
            asyncio.run(partner_cost_draw(s, bid, wrong_partner, cost=2, seed=555))
    finally:
        s.close()


def test_frozen_probe_rejects_original_seed_collision(tmp_path):
    s = CallService(FakeBackend(), tmp_path, "collision")
    source = {"messages": [], "kind": "bid", "seed": seed_for("frozen_probe", 1, "actual")}
    try:
        with pytest.raises(ValueError, match="probe seed"):
            asyncio.run(frozen_draw(s, source, seed=1))
    finally:
        s.close()


@pytest.mark.parametrize("market", [
    {"bids": [[3, 4, 5, 6]], "winners": []},
    {"bids": [[3, 4, 5, 6]], "winners": [1]},
    {"bids": [[None] * 4], "winners": [0]},
    {"bids": [[3, True, 5, 6]], "winners": [0]},
])
def test_malformed_public_market_rejected(market):
    with pytest.raises(ValueError):
        judge_messages(market | {"complete_round_mask": [True]})


def test_costs_required_only_at_l2():
    market = {"bids": [[3, 4, 5, 6]], "winners": [0], "complete_round_mask": [True]}
    assert judge_messages(market)
    with pytest.raises(ValueError):
        judge_messages(market, "L2")
