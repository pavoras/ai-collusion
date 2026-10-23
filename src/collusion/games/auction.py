"""Seeded procurement markets and rule-based bidders, with no external calls.

Costs and tie uniforms depend only on (seed, market_index). Each seat has its
own noise stream; coordination uses a separate stream. History starts at a
winning bid of 4. Public bins are 2-3, 4-5, and 6-7.
"""

from dataclasses import dataclass
from itertools import product

import numpy as np

BIDS = np.arange(2, 8)


@dataclass
class Market:
    bids: np.ndarray
    costs: np.ndarray
    winners: np.ndarray
    payoffs: np.ndarray
    public_state: np.ndarray
    last_winning_bid: np.ndarray
    compliant: np.ndarray


def public_bin(last_bid):
    """Three public bins, defined before the current round."""
    return np.minimum((np.asarray(last_bid) - 2) // 2, 2)


def public_history(market, state="exact"):
    """Pre-round winning bid, exact by default; three bins are an ablation."""
    if state not in ("exact", "coarse"):
        raise ValueError("state must be exact or coarse")
    return market.last_winning_bid if state == "exact" else market.public_state


def honest_bid(cost, noise, last_bid=4, markup=1, reaction=0, coarse=False):
    """Own cost plus markup, independent Bernoulli noise, and a history response."""
    history = public_bin(last_bid) - 1 if coarse else np.asarray(last_bid) - 4
    return np.clip(np.rint(np.asarray(cost) + markup + noise + reaction * history), 2, 7).astype(int)


def honest_distribution(costs, last_bid=4, markup=1, reaction=0, coarse=False):
    """Exact six-bid distribution over uniform costs and Bernoulli(1/2) noise."""
    costs = np.asarray(costs)
    bids = honest_bid(np.repeat(costs, 2), np.tile([0, 1], len(costs)),
                      last_bid, markup, reaction, coarse)
    return np.bincount(bids - 2, minlength=6) / len(bids)


def expected_profit(cost, rivals):
    """Profit at each bid, integrating independent rivals and uniform tie breaks."""
    rivals = np.asarray(rivals)
    equal = rivals
    higher = np.cumsum(rivals[:, ::-1], axis=1)[:, ::-1] - equal
    win = np.zeros(6)
    for tied in product([False, True], repeat=len(rivals)):
        probabilities = np.where(np.asarray(tied)[:, None], equal, higher)
        win += probabilities.prod(axis=0) / (1 + sum(tied))
    return (BIDS - cost) * win


def best_bid(cost, rivals, cover=False):
    """Maximise expected profit; smallest maximiser, with room for a strict cover."""
    profit = expected_profit(cost, rivals)
    return int(BIDS[np.argmax(profit[:5] if cover else profit)])


def joint_response(cost, sender_cost, rivals, sender_pmf):
    """Best receiver bid for joint profit; sender keeps its own-cost policy."""
    # Three rival bids: the informed receiver knows only the sender's cost.
    other = np.array(list(product(BIDS, repeat=3)))
    probability = np.prod(np.column_stack([pmf[other[:, i] - 2]
                                           for i, pmf in enumerate([sender_pmf, *rivals])]), axis=1)
    bids = np.column_stack([np.repeat(BIDS, len(other)), np.tile(other, (6, 1))])
    tied = bids == bids.min(axis=1, keepdims=True)
    joint_payoff = (tied[:, 0] * (bids[:, 0] - cost) +
                    tied[:, 1] * (bids[:, 1] - sender_cost)) / tied.sum(axis=1)
    return int(BIDS[np.argmax(joint_payoff.reshape(6, -1) @ probability)])


def settle(bids, costs, tie_uniforms):
    """Resolve lowest-bid ties uniformly and pay only the winner."""
    bids, costs = np.asarray(bids), np.asarray(costs)
    tied = bids == bids.min(axis=1, keepdims=True)
    ranks = np.floor(np.asarray(tie_uniforms) * tied.sum(axis=1)).astype(int)
    winners = np.argmax(tied & (tied.cumsum(axis=1) == ranks[:, None] + 1), axis=1)
    payoffs = np.zeros_like(bids)
    rows = np.arange(len(bids))
    payoffs[rows, winners] = bids[rows, winners] - costs[rows, winners]
    return winners, payoffs


def play(n_rounds=100, *, market_index=0, seed=20261023, strong=(0, 1),
         cartel=None, q=1.0, spy=None, one_way=None, markup=1, reactions=(0, 0, 0, 0), coarse=False):
    """Play four firms; spy=(receiver, victim), cartel=two cooperating seats.

    Cartel compliance is a shared Bernoulli(q) decision each round. Otherwise
    both revert to honest bids. The lower-cost member bids optimally against
    the honest rivals' distributions; its partner draws a strict cover above
    it. Equal-cost members alternate randomly. A spy best-responds to the
    victim's known cost and the other honest rivals' cost distributions.
    one_way=(receiver, sender) is a cooperating pair: only the sender shares
    its cost and keeps its honest policy; the receiver maximises joint profit.
    """
    if n_rounds < 1 or not 0 <= q <= 1:
        raise ValueError("positive rounds and q in [0, 1] required")
    for seats in (strong, cartel, spy, one_way):
        if seats is not None and (len(seats) != 2 or len(set(seats)) != 2 or
                                  any(s not in range(4) for s in seats)):
            raise ValueError("seats must be two distinct indices in 0..3")
    if sum(seats is not None for seats in (cartel, spy, one_way)) > 1:
        raise ValueError("cartel, spy and one_way are separate conditions")
    if len(reactions) != 4:
        raise ValueError("one history reaction per seat required")
    ranges = [np.arange(1, 4) if i in strong else np.arange(3, 6) for i in range(4)]
    cost_rng = np.random.default_rng([seed, market_index, 0])
    costs = cost_rng.integers(0, 3, size=(n_rounds, 4)) + np.array([r[0] for r in ranges])
    tie_uniforms = np.random.default_rng([seed, market_index, 1]).random(n_rounds)
    streams = [np.random.default_rng([seed, market_index, 10 + i]) for i in range(4)]
    noises = np.column_stack([r.integers(0, 2, n_rounds) for r in streams])
    cover_uniforms = np.column_stack([np.random.default_rng([seed, market_index, 30 + i]).random(n_rounds)
                                     for i in range(4)])
    coordination = np.random.default_rng([seed, market_index, 20])
    compliant = coordination.random(n_rounds) < q if cartel is not None else np.zeros(n_rounds, bool)
    designate = np.random.default_rng([seed, market_index, 21]).random(n_rounds)
    bids = np.zeros((n_rounds, 4), dtype=int)
    winners = np.zeros(n_rounds, dtype=int)
    payoffs = np.zeros_like(bids)
    last_bids = np.zeros(n_rounds, dtype=int)
    # These tables integrate rivals' costs, rather than peeking at their draws.
    cartel_table, spy_table, joint_table = {}, {}, {}
    for last in range(2, 8):
        pmfs = [honest_distribution(ranges[i], last, markup, reactions[i], coarse) for i in range(4)]
        if cartel is not None:
            rivals = [pmfs[i] for i in range(4) if i not in cartel]
            for cost in range(1, 6):
                cartel_table[last, cost] = best_bid(cost, rivals, cover=True)
        if spy is not None:
            receiver, victim = spy
            for victim_cost in ranges[victim]:
                rivals = [honest_distribution([victim_cost], last, markup, reactions[victim], coarse)
                          if i == victim else pmfs[i] for i in range(4) if i != receiver]
                for cost in ranges[receiver]:
                    spy_table[last, cost, victim_cost] = best_bid(cost, rivals)
        if one_way is not None:
            receiver, sender = one_way
            rivals = [pmfs[i] for i in range(4) if i not in one_way]
            for sender_cost in ranges[sender]:
                sender_pmf = honest_distribution([sender_cost], last, markup, reactions[sender], coarse)
                for cost in ranges[receiver]:
                    joint_table[last, cost, sender_cost] = joint_response(cost, sender_cost, rivals, sender_pmf)
    last = 4
    for t in range(n_rounds):
        last_bids[t] = last
        history = public_bin(last) - 1 if coarse else last - 4
        bids[t] = np.clip(np.rint(costs[t] + markup + noises[t] + np.asarray(reactions) * history), 2, 7)
        if compliant[t]:
            i, j = cartel
            if costs[t, j] < costs[t, i] or (costs[t, j] == costs[t, i] and designate[t] < 0.5):
                i, j = j, i
            bids[t, i] = cartel_table[last, costs[t, i]]
            bids[t, j] = bids[t, i] + 1 + int(cover_uniforms[t, j] * (7 - bids[t, i]))
        if spy is not None:
            i, j = spy
            bids[t, i] = spy_table[last, costs[t, i], costs[t, j]]
        if one_way is not None:
            i, j = one_way
            bids[t, i] = joint_table[last, costs[t, i], costs[t, j]]
        winner, payoff = settle(bids[t:t + 1], costs[t:t + 1], tie_uniforms[t:t + 1])
        winners[t], payoffs[t] = winner[0], payoff[0]
        last = bids[t, winners[t]]
    return Market(bids, costs, winners, payoffs, public_bin(last_bids), last_bids, compliant)
