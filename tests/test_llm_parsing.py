"""Strict decisions and six independent pair probabilities."""

import json

import pytest

from collusion.llm.parsing import PAIRS, parse


@pytest.mark.parametrize("bid", range(2, 8))
def test_bid_valid(bid):
    assert parse(json.dumps({"bid": bid}), "bid") == bid


@pytest.mark.parametrize("text", ['{"bid":1}', '{"bid":8}', '{"bid":true}', '{"bid":"3"}',
                                  '{"bid":3.0}', '{"bid":3,"extra":0}', '{"bid":3,"bid":4}',
                                  'prefix {"bid":3}', '```json\n{"bid":3}\n```', 'null', '[]', '{}',
                                  '{"bid":NaN}', '{"bid":Infinity}', ''])
def test_bid_invalid(text):
    assert parse(text, "bid") is None


def test_message_limits():
    assert parse(json.dumps({"message": "one " * 40}), "message") is not None
    for value in ["one " * 41, "", "   ", 3, False, None]:
        assert parse(json.dumps({"message": value}), "message") is None
    assert parse('{"message":"hello", "bid":4}', "message") is None


def test_judge_probabilities_are_not_a_distribution():
    values = dict(zip(PAIRS, [0, 1, .2, .9, .8, .7]))
    assert parse(json.dumps(values), "judge") == values


@pytest.mark.parametrize("value", [True, "0.5", -0.1, 1.01, float("nan"), float("inf"), None])
def test_judge_invalid_probability(value):
    values = dict.fromkeys(PAIRS, .1)
    values["A-B"] = value
    assert parse(json.dumps(values), "judge") is None


def test_judge_missing_extra_duplicate_keys():
    values = dict.fromkeys(PAIRS, .2)
    for invalid in [{k: v for k, v in values.items() if k != "A-B"}, values | {"B-A": .2}]:
        assert parse(json.dumps(invalid), "judge") is None
    text = json.dumps(values)[:-1] + ', "A-B": 0.4}'
    assert parse(text, "judge") is None
