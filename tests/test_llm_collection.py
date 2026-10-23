"""Declared collection, balanced assignments, live controls and blinded judging."""

import asyncio
from collections import Counter
from dataclasses import replace
from itertools import combinations
import json

import numpy as np
import pytest

from test_llm_support import tmp_path, run_config
from collusion.games import auction
from collusion.llm.backend import FakeBackend
from collusion.llm.collection import (ROLES, assignment_for, authorize, authorize_judge, authorize_probe,
                                     collection_hash, indices_for, load_collection, resolve_market)
from collusion.llm.judging import judge_market, judge_messages
from collusion.llm.parsing import PAIRS
from collusion.llm.prompts import ROLE_TEXTS, VERSION
from collusion.llm.reproducibility import cloud_settings, record_server_version, text_hash
from collusion.llm.runner import RunConfig, context_for, market_randomness, role_for, run
from collusion.llm.scripted import cartel_bids
from collusion.llm.storage import CallService


def test_balanced_seats_and_displayed_labels():
    assignments = [assignment_for(i, ("qwen-9b",) * 4) for i in range(20)]
    seats = Counter(tuple(a["strong_seats"]) for a in assignments)
    labels = Counter(tuple(sorted(a["labels_by_seat"][s] for s in a["strong_seats"])) for a in assignments)
    assert set(seats) == set(combinations(range(4), 2))
    assert sorted(seats.values()) == sorted(labels.values()) == [3, 3, 3, 3, 4, 4]
    assert [sum(s in a["strong_seats"] for a in assignments) for s in range(4)] == [10] * 4
    for label in ("Firm A", "Firm B", "Firm C", "Firm D"):
        assert sum(label in [a["labels_by_seat"][s] for s in a["strong_seats"]] for a in assignments) == 10
    assert assignments == [assignment_for(i, ("qwen-9b",) * 4) for i in range(20)]
    assert assignments != [assignment_for(i, ("qwen-9b",) * 4, seed=1) for i in range(20)]


@pytest.mark.parametrize("control,treatment", [("core.N0", "core.C1-SS"), ("mixed.D", "mixed.C1-XX"),
                                                ("mixed.H-XYZZ", "mixed.C1-XY")])
def test_matching_models_follow_strength_roles(control, treatment):
    manifest = load_collection()
    entries = {e["id"]: e for e in manifest["entries"]}
    configurations = [RunConfig(condition=entries[key]["condition"], entry_id=key,
                                models=tuple(entries[key]["models_by_role"][r] for r in ROLES))
                      for key in (control, treatment)]
    for index in range(20):
        a, b = [resolve_market(c, index) for c in configurations]
        assert a.assignment == b.assignment
        assert a.models == b.models and a.labels == b.labels and a.strong == b.strong
        for role, seat in a.assignment["role_seats"].items():
            assert a.models[seat] == entries[control]["models_by_role"][role]
        np.testing.assert_array_equal(market_randomness(a, index)[0], market_randomness(b, index)[0])
    assert entries[treatment]["matched_control"] == control


@pytest.mark.parametrize("position,strong_members", [("strong_strong", 2), ("strong_fringe", 1), ("fringe_fringe", 0)])
def test_strength_relative_cartels_and_spy(position, strong_members):
    for index in range(20):
        c = resolve_market(RunConfig(condition="C1", cartel_position=position), index)
        assert len(set(c.pair) & set(c.strong)) == strong_members
        assert {s for s in range(4) if role_for(c, s) == "cartel_channel"} == set(c.pair)
        spy = resolve_market(RunConfig(condition="E1"), index)
        assert set(spy.pair) == set(spy.strong)
        assert spy.pair[0] == spy.assignment["spy_receiver"]
        costs, _ = market_randomness(spy, index)
        context = context_for(spy, {"bids": [], "winners": [], "payoffs": []}, costs, 0, spy.pair[0])
        assert context.victim == spy.pair[1] and context.leaked_cost == costs[0, spy.pair[1]]


@pytest.mark.parametrize("settings", [dict(rounds=300), dict(market_start=40), dict(seed=4),
    dict(condition="M2"), dict(models=("gemma-12b",) * 4, condition="E1"), dict(compliance=.5)])
def test_undeclared_run_rejected_before_backend(tmp_path, settings):
    backend = FakeBackend()
    service = CallService(backend, tmp_path, "refused")
    try:
        with pytest.raises(ValueError):
            asyncio.run(run(RunConfig(**settings), service))
        assert not backend.calls and service.calls == 0
    finally:
        service.close()


def test_manifest_placeholders_and_all_scope_cells():
    m = load_collection()
    assert m["parameters"]["core_markets"] == {"value": 20, "status": "declared"} and m["parameters"]["core_n0_markets"]["value"] == 40
    assert m["parameters"]["breadth_markets"]["value"] == 10
    auctions = [e for e in m["entries"] if e["phase"] == "auction"]
    assert len(auctions) == 21 and sum(len(indices_for(m, e)) for e in auctions) == 300  # B0: core.N0 has 40 markets
    assert m["pilot_entries"] == ["core.N0", "core.P0"]
    for entry in auctions:
        config = RunConfig(condition=entry["condition"], entry_id=entry["id"], cartel_position=entry["position"],
                           models=tuple(entry["models_by_role"][r] for r in ROLES))
        assert authorize(config)[1] == entry
        assert entry["execution_order"] > 0 and entry["cancellation_priority"] >= 0


def test_deviation_requires_reason_and_uses_separate_directory(tmp_path):
    service = CallService(FakeBackend(), tmp_path, "explore")
    try:
        with pytest.raises(ValueError, match="reason"):
            asyncio.run(run(RunConfig(rounds=1, deviation_cohort="scratch"), service))
        config = RunConfig(rounds=1, deviation_cohort="scratch", deviation_reason="Offline sensitivity check")
        state = asyncio.run(run(config, service))[0]
        assert service.run_id == "explore__deviation_scratch"
        assert (tmp_path / "llm/explore__deviation_scratch/market_00000.json").exists()
        assert not (tmp_path / "llm/explore/market_00000.json").exists()
        assert state["metadata"]["deviation_reason"] == "Offline sensitivity check"
    finally:
        service.close()


def test_declared_extension_and_new_indices_match_full_run(tmp_path):
    m = load_collection()
    m["parameters"]["rounds"]["value"] = 2
    m["parameters"]["core_markets"]["value"] = 40
    entry = next(e for e in m["entries"] if e["id"] == "core.N0")
    entry["allowed_round_extensions"] = [3]
    path = tmp_path / "declared.json"
    path.write_text(json.dumps(m))
    config = RunConfig(rounds=2, entry_id="core.N0", collection_manifest=str(path))
    service = CallService(FakeBackend(), tmp_path, "declared")
    reference = CallService(FakeBackend(), tmp_path / "reference", "full")
    try:
        short = asyncio.run(run(config, service))[0]
        grown = asyncio.run(run(replace(config, rounds=3), service))[0]
        full = asyncio.run(run(replace(config, rounds=3), reference))[0]
        assert short["costs"] == grown["costs"][:2] and grown == full
        assert grown["metadata"]["assignment"] == short["metadata"]["assignment"]
        added = asyncio.run(run(replace(config, rounds=3, market_start=20), service))[0]
        assert added["market_index"] == 20
        before = service.calls
        with pytest.raises(ValueError):
            asyncio.run(run(replace(config, rounds=4), service))
        assert service.calls == before
    finally:
        service.close()
        reference.close()


def test_p0_uses_actual_costs_and_live_history(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("separately simulated auction is forbidden")
    monkeypatch.setattr(auction, "play", forbidden)
    original = auction.honest_distribution
    observed_history = []

    def distribution(costs, last, *args, **kwargs):
        observed_history.append(last)
        return original(costs, last, *args, **kwargs)

    monkeypatch.setattr(auction, "honest_distribution", distribution)
    config = run_config(condition="P0", rounds=4)
    service = CallService(FakeBackend(), tmp_path, "live")
    try:
        state = asyncio.run(run(config, service))[0]
        pair = resolve_market(config, 0).pair
        expected_history = [4] + [state["bids"][t][state["winners"][t]] for t in range(3)]
        assert observed_history == [last for last in expected_history for _ in range(2)]
        for costs, bids in zip(state["costs"], state["bids"]):
            i, j = pair
            if costs[i] != costs[j]:
                assert (bids[i] < bids[j]) == (costs[i] < costs[j])
        c = resolve_market(config, 0)
        costs = [4] * 4
        costs[pair[0]], costs[pair[1]] = 1, 3
        first = cartel_bids(costs, {"bids": [], "winners": []}, c, 0, 0)
        costs[pair[0]], costs[pair[1]] = 3, 1
        second = cartel_bids(costs, {"bids": [], "winners": []}, c, 0, 0)
        assert first[pair[0]] < first[pair[1]] and second[pair[1]] < second[pair[0]]
    finally:
        service.close()


def masked_market():
    return {"market_index": 0, "bids": [[7, 2, 6, 5], [None, 3, 4, 5], [3, 4, 5, 6]], "winners": [1, 1, 0],
            "costs": [[1, 2, 3, 4], [5, 5, 5, 5], [2, 3, 4, 5]], "complete_round_mask": [True, False, True],
            "messages": ["SECRET"], "condition": "C1", "models": ["hidden-model"], "role": "spy",
            "filename": "secret.json", "metadata": {"assignment": {"labels_by_seat": ["Firm D", "Firm A", "Firm C", "Firm B"]}}}


def test_judge_exact_mask_original_numbers_and_only_allowed_observations():
    market = masked_market()
    for level in ("L1", "L2"):
        messages = judge_messages(market, level)
        text = json.dumps(messages)
        assert all(v not in text for v in ("SECRET", "C1", "hidden-model", "spy", "secret.json", "metadata", "condition"))
        assert "\n1 | 2 | 5 | 6 | 7 | Firm A" in messages[1]["content"]
        assert "\n2 |" not in messages[1]["content"] and "\n3 |" in messages[1]["content"]
        if level == "L2":
            assert " | 2 | 4 | 3 | 1" in messages[1]["content"]
        changed = market | {"messages": ["different"], "condition": "N0", "filename": "other.json", "models": []}
        assert judge_messages(changed, level) == messages
    with pytest.raises(ValueError, match="mask"):
        judge_messages(market | {"complete_round_mask": [True] * 3})


@pytest.mark.parametrize("answers,status,calls", [([json.dumps(dict.fromkeys(PAIRS, .8))], "complete", 1),
                                                  (["invalid"] * 3, "failed", 2)])
def test_judge_raw_scores_and_fixed_failure_policy(tmp_path, answers, status, calls):
    backend = FakeBackend(answers)
    service = CallService(backend, tmp_path, "judge")
    try:
        result = asyncio.run(judge_market(service, masked_market(), "qwen-9b", 2, "L1"))
        assert result["status"] == status and service.calls == calls
        if status == "complete":
            assert result["pair_scores"] == dict.fromkeys(PAIRS, .8) == result["probabilities"]
        else:
            assert result["failure"] == "invalid_judge_json" and result["pair_scores"] is None
        empty = {"market_index": 1, "bids": [[None] * 4], "winners": [-1], "complete_round_mask": [False]}
        assert asyncio.run(judge_market(service, empty, "qwen-9b", 3, "L1"))["failure"] == "no_complete_rounds"
        assert service.calls == calls
    finally:
        service.close()


def test_run_reproducibility_metadata_complete(tmp_path):
    service = CallService(FakeBackend(), tmp_path, "metadata")
    try:
        config = run_config(rounds=1)
        state = asyncio.run(run(config, service))[0]
        record = json.loads((service.raw_dir / "reproducibility.json").read_text())
        data = record["static"]
        assert data["manifest_hash"] == collection_hash(load_collection())
        assert data["prompt_template"]["version"] == VERSION
        assert data["prompt_template"]["sha256"] == text_hash(data["prompt_template"]["text"])
        assert data["role_texts"]["honest"]["text"] == ROLE_TEXTS["honest"]
        assert all(v["sha256"] == text_hash(v["text"]) for v in data["role_texts"].values())
        assert len(data["sampling_table"]) == 6 and data["token_limits"] == {"bid": 64, "message": 128, "judge": 12000}
        assert data["thinking_flags"]["qwen-9b"] == {"bidder": False, "judge": True}
        assert data["retry_policy"]["validation_attempts"] == 2
        assert data["seed_derivation"]["run_seed"] == config.seed
        assert len(data["packages"]["pip_freeze_sha256"]) == 64 and data["packages"]["versions"]["numpy"]
        model = data["models"]["qwen-9b"]
        assert len(model["revision"]) == 40 and model["repo"] and model["gpu"] == "L40S"
        assert model["max_model_len"] == 8192 and model["max_num_seqs"] == 128
        assert record["vllm_runtime"]["qwen-9b"]["version"] == cloud_settings()["vllm_version"]
        assert state["metadata"]["assignment"] == assignment_for(0, config.models)
    finally:
        service.close()


def test_judge_declared_scope_requires_matching_manifest():
    m = load_collection()
    market = masked_market() | {"planned_rounds": 200, "metadata": {"collection_entry": "core.N0", "manifest_hash": collection_hash(m)}}
    assert authorize_judge(m, market, "qwen-9b", "L1")["id"] == "judge.qwen9b"
    assert authorize_judge(m, market, "gemma-12b", "L2")["id"] == "judge.gemma12b"
    for changed in (market | {"market_index": 40}, market | {"planned_rounds": 300}, market | {"metadata": {}}):
        with pytest.raises(ValueError):
            authorize_judge(m, changed, "qwen-9b", "L1")
    with pytest.raises(ValueError):
        authorize_judge(m, market | {"market_index": 10}, "gemma-12b", "L1")


def test_runtime_version_record_and_config_fallback(tmp_path, monkeypatch):
    service = CallService(FakeBackend(), tmp_path, "runtime")
    try:
        asyncio.run(run(run_config(rounds=1), service))
        asyncio.run(record_server_version(service, "qwen-9b"))
        path = service.raw_dir / "reproducibility.json"
        assert json.loads(path.read_text())["vllm_runtime"]["qwen-9b"]["probe_status"] == "offline_fake"
        async def version(model):
            return "0.31.reported"
        monkeypatch.setattr(service.backend, "server_version", version)
        asyncio.run(record_server_version(service, "qwen-9b"))
        runtime = json.loads(path.read_text())["vllm_runtime"]["qwen-9b"]
        assert runtime == {"version": "0.31.reported", "source": "server GET /version", "probe_status": "reported"}
    finally:
        service.close()


def test_cli_declared_entry_defaults_and_deviation_segregation(tmp_path):
    from experiments.run_llm import main, parser
    args = parser().parse_args(["--run", "cli", "--results", str(tmp_path), "--dry-run", "--entry", "mixed.H-XYZZ",
                                "--quick", "--deviation-cohort", "offline", "--deviation-reason", "CLI integration test"])
    assert asyncio.run(main(args)) == 0
    path = tmp_path / "llm/cli__deviation_offline/market_00000.json"
    state = json.loads(path.read_text())
    assert list(state["metadata"]["assignment"]["models_by_role"].values()) == ["qwen-9b", "gemma-12b", "ministral-8b", "ministral-8b"]
    refused = parser().parse_args(["--run", "refuse", "--results", str(tmp_path), "--dry-run", "--quick"])
    with pytest.raises(ValueError, match="undeclared"):
        asyncio.run(main(refused))
    assert not (tmp_path / "raw/refuse/calls").exists()


def test_judge_cli_records_raw_scores_and_metadata(tmp_path):
    import argparse
    from experiments.judge import main
    from collusion.llm.cli import add_backend_args
    market = masked_market() | {"status": "complete"}
    path = tmp_path / "market.json"
    path.write_text(json.dumps(market))
    parser = argparse.ArgumentParser()
    add_backend_args(parser)
    args = parser.parse_args(["--run", "audit", "--results", str(tmp_path), "--dry-run", "--deviation-cohort", "test",
                              "--deviation-reason", "Offline judge integration"])
    args.market, args.model, args.level = str(path), "qwen-9b", "L2"
    assert asyncio.run(main(args)) == 0
    result = json.loads((tmp_path / "llm/audit__deviation_test/judge.json").read_text())
    assert result["pair_scores"] == result["probabilities"] == dict.fromkeys(PAIRS, .1)
    metadata = json.loads((tmp_path / "raw/audit__deviation_test/reproducibility.json").read_text())["static"]
    assert "def judge_messages" in metadata["prompt_template"]["text"]
    assert metadata["models"]["qwen-9b"]["max_model_len"] == 32768


def test_declared_probe_grid_and_single_message_shared_by_five_bids(tmp_path):
    from experiments.run_llm import main, parser
    m = load_collection()
    m["parameters"]["rounds"]["value"] = 3
    probe = next(e for e in m["entries"] if e["id"] == "core.probes")
    assert probe["context_rounds"] == list(range(110, 201, 10))
    assert probe["bid_draws_per_cost"] == 5 and probe["message_draws_per_cost"] == 1
    assert m["parameters"]["probe_calls"]["value"] == 10 * 10 * 2 * 3 * 6
    probe["context_rounds"] = [3]
    collection = tmp_path / "collection.json"
    collection.write_text(json.dumps(m))
    config = RunConfig(condition="C1", entry_id="core.C1-SS", rounds=3, collection_manifest=str(collection))
    backend = FakeBackend()
    service = CallService(backend, tmp_path, "source")
    try:
        asyncio.run(run(config, service))
        paths = list((service.raw_dir / "calls").glob("*.json"))
        records = [(p, json.loads(p.read_text())) for p in paths]
        seat, partner_seat = resolve_market(config, 0).pair
        source_path, source = next((p, e) for p, e in records if e["round"] == 3 and e["seat"] == seat and e["kind"] == "bid")
        partner_path, partner = next((p, e) for p, e in records if e["round"] == 3 and e["seat"] == partner_seat and e["kind"] == "message")
        probe_config = replace(config, entry_id="core.probes")
        assert authorize_probe(probe_config, source, partner, "partner-cost", 2, 5)["id"] == "core.probes"
        for kind, cost, draws in [("honest", 2, 5), ("partner-cost", 4, 5), ("partner-cost", 2, 6)]:
            with pytest.raises(ValueError, match="undeclared"):
                authorize_probe(probe_config, source, partner, kind, cost, draws)
        with pytest.raises(ValueError, match="undeclared"):
            authorize_probe(probe_config, source | {"round": 2}, partner, "partner-cost", 2, 5)
    finally:
        service.close()
    args = parser().parse_args(["--run", "probe", "--results", str(tmp_path), "--entry", "core.probes", "--dry-run",
        "--collection-manifest", str(collection), "--probe", "partner-cost", "--source-call", str(source_path),
        "--partner-call", str(partner_path), "--partner-cost", "2", "--probe-draws", "5"])
    assert asyncio.run(main(args)) == 0
    logs = [json.loads(p.read_text()) for p in (tmp_path / "raw/probe/calls").glob("*.json")]
    paid = [e for e in logs if not e["cache_hit"]]
    assert len(paid) == 6
    assert sum(e["kind"] == "message" for e in paid) == 1
    assert len({e["seed"] for e in paid if e["kind"] == "bid"}) == 5
    assert len({e["context"]["partner_message"] for e in paid if e["kind"] == "bid"}) == 1
