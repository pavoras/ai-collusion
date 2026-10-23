import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from collusion.games import auction as a

SPEC = importlib.util.spec_from_file_location("null_validity", Path(__file__).parents[1] / "experiments/null_validity.py")
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


@pytest.mark.parametrize("options, expected", [
    ({}, "0e85dd0851b2b2c2bb72cf07008f4a3ba3a3085e544aa1aa2fcf96f7dd97356e"),
    ({"reactions": (1, 1, 0, 0)}, "a54e7daec878647bebd3ede25e2773561319ef595c95d5dd327f4a743f24cd30"),
    ({"cartel": (0, 1), "q": .5}, "c91ab226dfd28e3159e3456c93f062db858f729f002d6e078aa6e2ce388f3be3"),
    ({"spy": (0, 1)}, "800223f2f1ba399a7ea7aa267854d91c6c83e0d00f46bcde20f4970211dd8f52"),
    ({"one_way": (0, 1)}, "eba1211c158a92c00c538bba1a30a5a18fb2e925fba7b71e1cc9cc025ef22b09"),
])
def test_legacy_outputs_match_pre_change_snapshots(options, expected):
    market = a.play(200, market_index=8, **options)
    fields = ["bids", "costs", "winners", "payoffs", "last_winning_bid", "compliant"]
    digest = hashlib.sha256(b"".join(getattr(market, field).tobytes() for field in fields)).hexdigest()
    assert digest == expected


@pytest.mark.parametrize("variant", study.conditions()[2:])
def test_variants_are_reproducible_and_keep_seed_streams_and_prefixes(variant):
    options = variant["kwargs"]
    market = a.play(60, seed=study.SEED, market_index=3, **options)
    repeat = a.play(60, seed=study.SEED, market_index=3, **options)
    short = a.play(30, seed=study.SEED, market_index=3, **options)
    iid = a.play(60, seed=study.SEED, market_index=3)
    for field in a.Market.__dataclass_fields__:
        assert np.array_equal(getattr(market, field), getattr(repeat, field))
        assert np.array_equal(getattr(short, field), getattr(market, field)[:30])
    assert np.array_equal(market.costs, iid.costs)
    assert market.bids.min() >= 2 and market.bids.max() <= 7
    assert not np.array_equal(market.bids, iid.bids)
    # No policy consumes another seat's randomness: inactive seats retain IID bids.
    if not variant["positive"]:
        inactive = [i for i, p in enumerate(options["policies"]) if p == "none"]
        assert np.array_equal(market.bids[:, inactive], iid.bids[:, inactive])


def test_fixed_history_responses_use_completed_rounds_and_own_profit():
    wins = np.array([0, 1, 1, 1])
    winning = np.array([3, 4, 5, 6])
    bids = np.array([[3, 5, 6, 7], [6, 4, 7, 7], [6, 5, 7, 7], [7, 6, 7, 7]])
    profit = np.array([0, 2, 3, 4])
    def response(policy, **kwargs):
        return a.history_response(policy, winning, bids, wins, profit, seat=1, **kwargs)
    assert response("mean", window=3) == 1
    assert response("mean", window=10) == .5
    assert response("streak") == 1
    assert a.history_response("streak", winning, bids, wins, profit, seat=0) == -1
    assert response("profit") == (9 - 2) / 20
    assert response("rival", rival=2) == 3
    assert response("drift") == 2 * 4 / 200 - 1
    for policy in ["mean", "rival", "streak", "profit"]:
        assert a.history_response(policy, [], np.empty((0, 4)), [], [], seat=0) == 0


def test_mean_ten_bids_can_be_reconstructed_without_current_rival_costs():
    market = a.play(80, policies=("mean",) * 4, history_window=10, market_index=7)
    noise = np.column_stack([np.random.default_rng([20261023, 7, 10 + i]).integers(0, 2, 80)
                             for i in range(4)])
    winning = market.bids[np.arange(80), market.winners]
    for t in range(80):
        offset = np.mean(winning[max(0, t - 10):t]) - 4 if t else 0
        expected = np.clip(np.rint(market.costs[t] + 1 + noise[t] + offset), 2, 7)
        assert np.array_equal(market.bids[t], expected)


def test_cartel_integrates_actual_mean_ten_fringe_policy():
    market = a.play(100, cartel=(0, 1), policies=("none", "none", "mean", "mean"), history_window=10)
    winning = market.bids[np.arange(100), market.winners]
    for t in range(100):
        offset = np.mean(winning[max(0, t - 10):t]) - 4 if t else 0
        i, j = sorted((0, 1), key=lambda seat: market.bids[t, seat])
        rivals = [a.honest_distribution([3, 4, 5], markup=1 + offset)] * 2
        assert market.bids[t, i] == a.best_bid(market.costs[t, i], rivals, cover=True)
        assert market.bids[t, j] > market.bids[t, i]


@pytest.mark.parametrize("options", [
    {"policies": ("unknown",) * 4}, {"policy_strengths": (np.nan,) * 4},
    {"history_window": 0}, {"history_window": 1.5}, {"drift_rounds": 0},
    {"rival_seats": (4, 0, 0, 0)}, {"policies": ("rival",) * 4, "rival_seats": (0, 0, 0, 0)},
])
def test_invalid_new_options(options):
    with pytest.raises(ValueError):
        a.play(**options)


def test_exact_intervals_at_boundaries_and_nominal_count():
    assert study.clopper_pearson(0, 20) == pytest.approx((0, 1 - .025**(1 / 20)))
    assert study.clopper_pearson(20, 20) == pytest.approx((.025**(1 / 20), 1))
    assert study.clopper_pearson(10, 20) == pytest.approx((.2719578496, .7280421504))


def test_market_endpoints_match_existing_calibration_and_direction_family():
    variant = study.conditions()[0]
    row, directions = study.evaluate((0, variant, 0, 239))
    market = a.play(200, seed=study.SEED, market_index=study.MARKET_START)
    from collusion import measures as m
    result = m.symmetric_permutation_test(market.bids - 2, list(market.costs.T),
                                          public_state=market.last_winning_bid, n_perm=239,
                                          rng=[study.SEED, 800, 0, 0, 1])
    assert row["L2_any_candidate"] == bool(m.calibrated_pairs(result))
    assert row["leak_family_alarm"] == np.any(result.leak_p_value <= .05 / 12)
    assert row["classification"] == study.classify(result, (0, 1))
    assert len(directions) == 12
    assert row["mean_abs_bid_change"] == 0
