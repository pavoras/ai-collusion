"""The scripted cartel's round policy, applied to the actual live market."""

import numpy as np

from collusion.games import auction


def cartel_bids(costs, state, config, index, round_index):
    """Use member costs and completed live history, never a simulated market."""
    rng = np.random.default_rng([config.seed, index, round_index, 120])
    pair = list(config.pair)
    last = next((state["bids"][t][w] for t, w in reversed(list(enumerate(state["winners"]))) if w >= 0), 4)
    if rng.random() >= config.compliance:
        return {s: int(auction.honest_bid(costs[s], np.random.default_rng(
            [config.seed, index, round_index, 121 + s]).integers(2), last)) for s in pair}
    i, j = pair
    if costs[j] < costs[i] or (costs[j] == costs[i] and rng.random() < .5):
        i, j = j, i
    distributions = [auction.honest_distribution(np.arange(1, 4) if s in config.strong else np.arange(3, 6), last)
                     for s in range(4) if s not in pair]
    bid = auction.best_bid(int(costs[i]), distributions, cover=True)
    return {i: bid, j: int(rng.integers(bid + 1, 8))}
