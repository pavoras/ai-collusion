from itertools import product

import numpy as np
import pytest

from collusion.games import auction as a


def test_settlement_and_uniform_ties():
    bids = np.array([[3, 3, 5, 6]] * 600)
    costs = np.tile([1, 2, 4, 5], (600, 1))
    winners, payoffs = a.settle(bids, costs, (np.arange(600) + 0.5) / 600)
    assert np.array_equal(np.bincount(winners), [300, 300])
    assert np.array_equal(payoffs.sum(0), [600, 300, 0, 0])
    assert np.all((payoffs != 0).sum(1) <= 1)


def test_cost_ranges_seeds_prefixes_and_history():
    honest = a.play(200, strong=(1, 3), market_index=8)
    cartel = a.play(200, strong=(1, 3), cartel=(2, 3), market_index=8)
    short = a.play(100, strong=(1, 3), cartel=(2, 3), market_index=8)
    assert np.array_equal(honest.costs, cartel.costs)
    assert np.array_equal(short.bids, cartel.bids[:100])
    assert np.array_equal(a.play(200, strong=(1, 3), market_index=8).bids, honest.bids)
    assert not np.array_equal(a.play(200, strong=(1, 3), market_index=9).costs, honest.costs)
    assert set(np.unique(honest.costs[:, [1, 3]])) == {1, 2, 3}
    assert set(np.unique(honest.costs[:, [0, 2]])) == {3, 4, 5}
    previous = np.r_[4, cartel.bids[np.arange(199), cartel.winners[:-1]]]
    assert np.array_equal(previous, cartel.last_winning_bid)
    assert np.array_equal(a.public_bin(previous), cartel.public_state)
    assert cartel.bids.min() >= 2 and cartel.bids.max() <= 7


@pytest.mark.parametrize("pair", [(0, 1), (0, 2), (2, 3), (3, 1)])
def test_cartel_allocates_to_lower_cost_with_strict_cover(pair):
    market = a.play(500, cartel=pair)
    i, j = pair
    designated_i = market.bids[:, i] < market.bids[:, j]
    assert np.all(market.bids[:, i] != market.bids[:, j])
    assert np.all(market.costs[designated_i, i] <= market.costs[designated_i, j])
    assert np.all(market.costs[~designated_i, j] <= market.costs[~designated_i, i])
    assert market.compliant.all()


def test_zero_compliance_is_identical_to_honest():
    honest = a.play(200, reactions=(1, 1, 0, 0))
    cartel = a.play(200, cartel=(0, 1), q=0, reactions=(1, 1, 0, 0))
    assert np.array_equal(cartel.bids, honest.bids)
    assert np.array_equal(cartel.payoffs, honest.payoffs)


def test_expected_profit_matches_exhaustive_tie_calculation():
    rng = np.random.default_rng(4)
    rivals = rng.dirichlet(np.ones(6), size=3)
    brute = np.zeros(6)
    for bids in product(range(2, 8), repeat=3):
        probability = np.prod([rivals[i, b - 2] for i, b in enumerate(bids)])
        for k, own in enumerate(a.BIDS):
            if own <= min(bids):
                brute[k] += probability * (own - 3) / (1 + bids.count(own))
    assert np.allclose(a.expected_profit(3, rivals), brute)
    assert a.best_bid(3, rivals) == a.BIDS[np.argmax(brute)]
    assert a.best_bid(3, rivals, cover=True) == a.BIDS[np.argmax(brute[:5])]


def test_spy_uses_only_victim_cost_and_has_optimal_bid():
    market = a.play(200, spy=(0, 1))
    for t in range(200):
        rivals = [a.honest_distribution([market.costs[t, 1]]),
                  a.honest_distribution([3, 4, 5]), a.honest_distribution([3, 4, 5])]
        assert market.bids[t, 0] == a.best_bid(market.costs[t, 0], rivals)


def test_exact_history_is_primary_and_coarse_history_is_explicit():
    market = a.play(200)
    assert np.array_equal(a.public_history(market), market.last_winning_bid)
    assert np.array_equal(a.public_history(market, "coarse"), a.public_bin(market.last_winning_bid))
    with pytest.raises(ValueError):
        a.public_history(market, "missing")


def test_one_way_sender_keeps_own_cost_policy_and_receiver_uses_joint_objective():
    honest = a.play(200)
    market = a.play(200, one_way=(0, 1))
    assert np.array_equal(honest.costs, market.costs)
    # There is no history response in this condition, so the sender is identical.
    assert np.array_equal(honest.bids[:, 1], market.bids[:, 1])
    assert np.array_equal(a.play(100, one_way=(0, 1)).bids, market.bids[:100])
    assert not np.array_equal(honest.bids[:, 0], market.bids[:, 0])
    for ci, cj in product(range(1, 4), repeat=2):
        mask = (market.costs[:, 0] == ci) & (market.costs[:, 1] == cj)
        expected = a.joint_response(ci, cj, [a.honest_distribution([3, 4, 5])] * 2,
                                    a.honest_distribution([cj]))
        assert np.all(market.bids[mask, 0] == expected)


def test_joint_response_matches_exhaustive_settlement():
    rng = np.random.default_rng(81)
    pmfs = rng.dirichlet(np.ones(6), size=3)
    profits = []
    other = np.array(list(product(a.BIDS, repeat=3)))
    probabilities = np.prod([pmfs[i, other[:, i] - 2] for i in range(3)], axis=0)
    for bid in a.BIDS:
        bids = np.column_stack([np.full(len(other), bid), other])
        # Enumerate twelve tie uniforms: exact for all tie multiplicities 1..4.
        total = np.zeros(len(other))
        for tie in (np.arange(12) + .5) / 12:
            _, payoff = a.settle(bids, np.tile([2, 3, 4, 5], (len(other), 1)), np.full(len(other), tie))
            total += payoff[:, :2].sum(1) / 12
        profits.append(total @ probabilities)
    assert a.joint_response(2, 3, pmfs[1:], pmfs[0]) == a.BIDS[np.argmax(profits)]


@pytest.mark.parametrize("kwargs", [{"q": -1}, {"n_rounds": 0}, {"strong": (0, 0)},
                                   {"cartel": (0, 4)}, {"spy": (0, 1), "cartel": (2, 3)},
                                   {"one_way": (0, 0)}, {"one_way": (0, 1), "spy": (0, 1)}])
def test_invalid_games(kwargs):
    with pytest.raises(ValueError):
        a.play(**kwargs)
