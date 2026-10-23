"""Check pooled sufficient tables against the independent public measure API."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from collusion import measures as m
from collusion.games import auction as a

spec = importlib.util.spec_from_file_location("auction_checks", Path(__file__).parents[1] / "experiments/auction_checks.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


@pytest.mark.parametrize("pair", [(0, 1), (0, 2), (2, 3)])
def test_fingerprint_count_terms_match_eq3_api_and_cluster_weights(pair):
    markets = [a.play(200, cartel=pair, market_index=k) for k in range(3)]
    tables = [checks.fingerprint_tables(market, pair, 5, [k])[0] for k, market in enumerate(markets)]
    weights = np.array([2, 0, 1])
    weighted = np.tensordot(weights, tables, axes=(0, 0))
    repeated = checks.pool([markets[0], markets[0], markets[2]])
    i, j = pair
    expected = m.influence_decomposition(repeated.bids[:, i] - 2, repeated.bids[:, j] - 2,
                                         repeated.costs[:, i], repeated.costs[:, j],
                                         public_state=repeated.last_winning_bid)
    assert checks.terms_from_tables(weighted) == pytest.approx(expected, abs=1e-12)
    batch = checks.terms_from_tables(np.array([weighted, weighted]))
    assert batch.shape == (2, 3)
    assert batch[1] == pytest.approx(expected, abs=1e-12)


def test_fingerprint_null_preserves_own_cost_history_marginals():
    market = a.play(200, cartel=(0, 1))
    observed, null = checks.fingerprint_tables(market, (0, 1), 19, [50])
    # Sum out the rival cost and bid to obtain own (H, cost, bid) margins.
    assert np.all(null.sum(axis=(-1, -3)) == observed.sum(axis=(-1, -3)))
    assert np.all(null.sum(axis=(-2, -4)) == observed.sum(axis=(-2, -4)))
    assert np.all(null.sum(axis=(-1, -2)) == observed.sum(axis=(-1, -2)))


def test_symmetric_null_and_count_table_corrections_agree_in_expectation():
    market = a.play(200, cartel=(0, 1))
    observed, null = checks.fingerprint_tables(market, (0, 1), 999, [60])
    table_estimate = checks.terms_from_tables(observed) - checks.terms_from_tables(null).mean(0)
    result = m.symmetric_permutation_test(market.bids[:, :2] - 2, list(market.costs[:, :2].T),
                                          public_state=market.last_winning_bid, n_perm=999, rng=61)
    direct = [result.action_corrected[0, 1], result.leak_corrected[0, 1], result.leak_corrected[1, 0]]
    assert table_estimate == pytest.approx(direct, abs=.015)
