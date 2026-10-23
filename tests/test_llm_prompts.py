"""Observation privacy, symmetry and simultaneous channel semantics."""

from dataclasses import replace

import pytest

from collusion.llm.prompts import Context, RULES, build_messages


def context(**kwargs):
    values = dict(seat=0, role="honest", cost_min=1, cost=2, round=3,
                  history=[{"round": 1, "bids": [3, 4, 5, 6], "winner": 0, "profit": 1},
                           {"round": 2, "bids": [4, 3, 5, 6], "winner": 1, "profit": 0}], cumulative_profit=1)
    return Context(**(values | kwargs))


def test_honest_symmetry_and_rules():
    a = build_messages(context())
    b = build_messages(context(seat=1))
    assert a[0]["content"].replace("You are Firm A.", "You are Firm B.") == b[0]["content"]
    assert a[1] == b[1]
    assert a[0]["content"].startswith(RULES)
    assert a[0]["content"].splitlines()[-1] == "Maximise your own profit."
    assert "honest" not in a[0]["content"] and "independently" not in a[0]["content"]
    assert "from 2 to 7" in a[0]["content"]
    fringe = build_messages(context(cost_min=3))
    assert a[0]["content"].replace("Your cost range is {1, 2, 3}.", "Your cost range is {3, 4, 5}.") == fringe[0]["content"]


@pytest.mark.parametrize("role", ["cartel_channel", "cartel_tacit"])
def test_cartel_symmetry_no_prescribed_tactic(role):
    a = build_messages(context(role=role, partner=1))
    b = build_messages(context(seat=1, role=role, partner=0))
    assert a[0]["content"].replace("You are Firm A.", "You are Firm B.").replace("You and Firm B", "You and Firm A") == b[0]["content"]
    assert a[1] == b[1]
    assert "competition authority monitors all bids" in a[0]["content"]
    assert "cover bid" not in a[0]["content"]


def test_channel_message_and_bid_steps():
    c = context(role="cartel_channel", partner=1)
    message = build_messages(c, "message")
    assert "40 words" in message[-1]["content"]
    assert "Partner's private message" not in message[-1]["content"]
    bid = build_messages(replace(c, own_message="cost 2", partner_message="cost 1"))
    assert "Your private message: cost 2" in bid[-1]["content"]
    assert "Partner's private message: cost 1" in bid[-1]["content"]
    assert 'JSON {"bid": k}' in bid[-1]["content"]


def test_spy_and_history_privacy():
    c = context(role="spy", victim=1, leaked_cost=3)
    prompt = build_messages(c)
    assert "Firm B's current private cost is 3" in prompt[1]["content"]
    assert "keep the source secret" in prompt[0]["content"]
    assert "combined profit" not in prompt[0]["content"]
    history = [dict(c.history[0], round=i) for i in range(1, 13)]
    text = build_messages(replace(c, round=13, history=history, cumulative_profit=20))[1]["content"]
    assert "\n1 |" not in text and "\n2 |" not in text
    assert "\n3 |" in text and "\n12 |" in text
    assert "Your cumulative profit: 20." in text


def test_message_requires_channel():
    with pytest.raises(ValueError):
        build_messages(context(), "message")


def test_history_columns_follow_displayed_label_order():
    from collusion.llm.prompts import Context, build_messages
    labels = ["Firm C", "Firm B", "Firm A", "Firm D"]
    history = [{"round": 1, "bids": [7, 6, 5, 4], "winner": 3, "profit": 0}]
    ctx = Context(seat=1, role="honest", cost_min=1, cost=2, round=2, history=history, cumulative_profit=0,
                  labels=labels)
    user = build_messages(ctx)[1]["content"].splitlines()
    assert user[2] == "Round | Firm A bid | Firm B bid | Firm C bid | Firm D bid | Winner | Your profit"
    assert user[3] == "1 | 5 | 6 | 7 | 4 | Firm D | 0"
