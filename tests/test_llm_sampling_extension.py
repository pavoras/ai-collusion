"""Vendor recipes, prompt-version cache isolation, and append-only games."""

import asyncio
from dataclasses import replace
import json

import numpy as np
import pytest

from test_llm_support import tmp_path, run_config as RunConfig
from collusion.llm.backend import FakeBackend
from collusion.llm.parsing import parse
from collusion.llm.prompts import VERSION
from collusion.llm.runner import market_randomness, run
from collusion.llm.sampling import MODEL_CONFIG, sampling_for
from collusion.llm.storage import CallService, digest


@pytest.mark.parametrize("model", MODEL_CONFIG)
@pytest.mark.parametrize("thinking", [False, True])
def test_vendor_recipes(model, thinking):
    settings = sampling_for(model, thinking)
    if model.startswith("qwen"):
        extra = {"top_k": 20, "min_p": 0., "chat_template_kwargs": {"enable_thinking": thinking}}
        if not thinking:
            extra["repetition_penalty"] = 1.
        assert settings == {"temperature": 1. if thinking else .7, "top_p": .95 if thinking else .8,
                            "presence_penalty": 1.5, "extra_body": extra}
    elif model.startswith("gemma"):
        assert settings == {"temperature": 1., "top_p": .95, "extra_body": {
            "top_k": 64, "chat_template_kwargs": {"enable_thinking": thinking}}}
    else:
        assert settings == {"temperature": .15}
    settings["temperature"] = 999
    assert sampling_for(model, thinking)["temperature"] != 999


def test_prompt_version_is_logged_and_separates_cache(tmp_path):
    backend = FakeBackend()
    s = CallService(backend, tmp_path, "version")
    messages = [{"role": "user", "content": 'Reply {"bid": 3}.'}]
    try:
        request = s.request("qwen-9b", messages, 1, "bid")
        assert request["prompt_version"] == VERSION == 4
        changed = request | {"prompt_version": VERSION + 1}
        assert digest(changed) != digest(request)
        asyncio.run(s.ask_request(request, "bid", {}))
        asyncio.run(s.ask_request(changed, "bid", {}))
        asyncio.run(s.ask_request(changed, "bid", {}))
        assert len(backend.calls) == 2
        logs = [json.loads(p.read_text()) for p in (s.raw_dir / "calls").glob("*.json")]
        assert all(e["prompt_version"] == e["request"]["prompt_version"] for e in logs)
        assert all(e["sampling"] == sampling_for("qwen-9b") for e in logs)
    finally:
        s.close()


@pytest.mark.parametrize("prefix", ["<think>\n</think>\n", "[unused94]thought\n[unused95]\n"])
def test_empty_thought_block_is_not_an_invalid_answer(prefix):
    assert parse(prefix + '{"bid": 4}', "bid") == 4
    assert parse(prefix + '{"message":"cost 3"}', "message") == "cost 3"
    assert parse('<think>reasoning</think>{"bid":4}', "bid") is None


@pytest.mark.parametrize("condition", ["N0", "P0"])
def test_market_extension_and_new_indices_match_uninterrupted(tmp_path, condition):
    config = RunConfig(condition=condition, rounds=3, compliance=.5)
    s = CallService(FakeBackend(), tmp_path, "extend")
    try:
        initial = asyncio.run(run(config, s))[0]
        before = s.calls
        grown = replace(config, rounds=5)
        extended = asyncio.run(run(grown, s))[0]
        assert extended["costs"][:3] == initial["costs"]
        assert extended["bids"][:3] == initial["bids"]
        assert s.calls - before == (8 if condition == "N0" else 4)
        reference = CallService(FakeBackend(), tmp_path / "reference", "full")
        try:
            uninterrupted = asyncio.run(run(grown, reference))[0]
            assert extended == uninterrupted
        finally:
            reference.close()
        asyncio.run(run(replace(grown, market_start=20, markets=2), s))
        assert json.loads((tmp_path / "llm/extend__deviation_tests/market_00000.json").read_text()) == extended
        manifest = json.loads((s.raw_dir / "config.json").read_text())
        assert manifest["market_indices"] == [0, 20, 21]
        with pytest.raises(ValueError, match="cannot decrease"):
            asyncio.run(run(config, s))
    finally:
        s.close()


def test_200_to_300_preserves_all_costs_and_tie_prefixes():
    short = RunConfig(rounds=200)
    for index in (0, 19, 20, 39):
        costs, ties = market_randomness(short, index)
        grown_costs, grown_ties = market_randomness(replace(short, rounds=300), index)
        np.testing.assert_array_equal(costs, grown_costs[:200])
        np.testing.assert_array_equal(ties, grown_ties[:200])
