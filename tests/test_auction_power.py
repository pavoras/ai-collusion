"""Tiny market grid and paired AUROC resampling checks."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from collusion.measures import auroc
from collusion.games.auction import play

spec = importlib.util.spec_from_file_location(
    "auction_power", Path(__file__).parents[1] / "experiments/auction_power.py")
power = importlib.util.module_from_spec(spec)
spec.loader.exec_module(power)


def test_resampling_is_seeded_and_matches_rank_auc_with_ties():
    negative, positive = np.array([0., 1., 1., 2.]), np.array([1., 1., 2., 3.])
    values, draws = power.resample_auc(negative, positive, 10, 27, 42)
    again, same = power.resample_auc(negative, positive, 10, 27, 42)
    assert np.array_equal(values, again)
    assert np.array_equal(draws, same)
    for value, index in zip(values, draws):
        assert value == pytest.approx(auroc(np.r_[np.zeros(10), np.ones(10)],
                                            np.r_[negative[index], positive[index]]))
    assert not np.array_equal(draws, power.resample_auc(negative, positive, 10, 27, 43)[1])


def test_tiny_grid_runs_and_summarises_both_populations():
    cells = [(population, 20, condition, "all" if condition == "N0" else "strong_strong",
              0.0 if condition == "N0" else .5)
             for population in power.POPULATIONS for condition in ("N0", "cartel")]
    rows = [row for cell in cells for row in power.simulate_cell((cell, 2, 239))]
    aucs, leaks, alarms = power.summarise(rows, cells, 2, 20)
    assert len(aucs) == 2 * 2 * len(power.NS)
    assert len(leaks) == 2 * len(power.NS)
    assert {r["population"] for r in aucs} == set(power.POPULATIONS)
    assert all(0 <= r["auc_low"] <= r["auc_median"] <= r["auc_high"] <= 1 for r in aucs)
    assert all(r["n_observed"] == 2 for r in alarms)
    assert all(r["leak_class"] == "unobservable" for r in rows if r["level"] == "L1")


def test_grid_and_exact_false_alarm_boundary():
    cells = power.grid()
    assert len(cells) == 74
    assert all(c[1] == 200 for c in cells if c[3] == "fringe_fringe")
    assert {c[4] for c in cells if c[2] == "spy"} == {.5, 1.0}
    assert power.exact_interval(0, 10)[1] > .2
    assert power.exact_interval(0, 20)[1] < .2
    assert power.exact_interval(0, 40)[1] < .2


@pytest.mark.parametrize("reactions", list(power.POPULATIONS.values()))
@pytest.mark.parametrize("q", [0., 1.])
def test_local_spy_compliance_endpoints_match_public_auction(reactions, q):
    for index in (0, 3):
        expected = play(200, seed=power.SEED, market_index=index, reactions=reactions,
                        **({"spy": (0, 1)} if q else {}))
        actual = power.partial_spy(200, index, q, reactions)
        for field in ("bids", "costs", "winners", "payoffs", "last_winning_bid", "public_state"):
            assert np.array_equal(getattr(actual, field), getattr(expected, field))


def test_partial_spy_reverts_to_own_policy_and_preserves_adaptive_history():
    market = power.partial_spy(200, 7, .5, power.POPULATIONS["shared_fine"])
    baseline = play(200, seed=power.SEED, market_index=7)
    noise = baseline.bids - baseline.costs - 1
    honest = np.clip(market.costs + 1 + noise + (market.last_winning_bid[:, None] - 4), 2, 7)
    assert .35 < market.compliant.mean() < .65
    assert np.array_equal(market.bids[~market.compliant], honest[~market.compliant])
    assert np.array_equal(market.bids[:, 1:], honest[:, 1:])
    assert np.array_equal(market.last_winning_bid[1:], market.bids[np.arange(199), market.winners[:-1]])
