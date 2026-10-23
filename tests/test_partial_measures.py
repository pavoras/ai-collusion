import numpy as np
import pytest

from collusion import measures as m


def test_eq3_decomposition_matches_direct_probability_formula():
    rng = np.random.default_rng(1)
    si, sj = rng.integers(0, 3, (2, 700))
    ai = (si + sj + rng.integers(0, 2, 700)) % 4
    aj = (sj + rng.integers(0, 2, 700)) % 3
    direct = 0.0
    for x, y, u, v in set(zip(ai, aj, si, sj)):
        cell = (ai == x) & (aj == y) & (si == u) & (sj == v)
        joint = (si == u) & (sj == v)
        pi = np.mean(ai[si == u] == x)
        pj = np.mean(aj[sj == v] == y)
        direct += np.mean(cell) * np.log2(cell.sum() / joint.sum() / (pi * pj))
    parts = m.influence_decomposition(ai, aj, si, sj)
    assert sum(parts) == pytest.approx(direct, abs=1e-12)
    assert m.partial_influence(ai, aj, si, sj) == pytest.approx(direct, abs=1e-12)
    assert m.partial_influence(aj, ai, sj, si) == pytest.approx(direct)
    assert parts[1] > parts[2] + 0.1


def test_shared_state_reduces_to_fully_observable_influence():
    rng = np.random.default_rng(2)
    ai, aj, state = rng.integers(0, 3, (3, 200))
    assert m.partial_influence(ai, aj, state, state) == pytest.approx(m.influence(ai, aj, state))
    action, li, lj = m.influence_decomposition(ai, aj, state, state)
    assert action == pytest.approx(m.influence(ai, aj, state))
    assert li == pytest.approx(0) and lj == pytest.approx(0)


def test_one_way_leak_names_receiver_not_victim():
    si, sj = np.tile(np.array([[0, 0], [0, 1], [1, 0], [1, 1]]).T, 100)
    actions = np.column_stack([sj, sj, si])
    result = m.symmetric_permutation_test(actions, [si, sj, si], n_perm=199, rng=3)
    assert result.leak[0, 1] == pytest.approx(1)
    assert result.leak[1, 0] == pytest.approx(0)
    assert result.leak_p_value[0, 1] == pytest.approx(1 / 200)
    assert result.leak_p_value[1, 0] == pytest.approx(1)
    assert result.leak_corrected[0, 1] > 0.98
    assert np.allclose(result.gamma, result.gamma.T, equal_nan=True)
    assert np.allclose(result.gamma, result.action + result.leak + result.leak.T, equal_nan=True)
    assert np.allclose(result.gamma_corrected,
                       result.action_corrected + result.leak_corrected + result.leak_corrected.T, equal_nan=True)


def test_two_way_exchange_has_two_leaks_and_no_conditional_action_term():
    si, sj = np.tile(np.array([[0, 0], [0, 1], [1, 0], [1, 1]]).T, 100)
    action, incoming, outgoing = m.influence_decomposition(sj, si, si, sj)
    assert action == pytest.approx(0)
    assert incoming == pytest.approx(1)
    assert outgoing == pytest.approx(1)
    assert m.partial_influence(sj, si, si, sj) == pytest.approx(2)


def test_own_state_determinism_is_preserved_by_symmetric_null():
    rng = np.random.default_rng(4)
    states = rng.integers(0, 3, (3, 500))
    result = m.symmetric_permutation_test(states.T.copy(), list(states), n_perm=39, rng=5)
    off = ~np.eye(3, dtype=bool)
    assert np.allclose(result.p_value[off], 1)
    assert np.allclose(result.leak_p_value[off], 1)
    assert np.allclose(result.gamma_corrected[off], 0)


def test_each_bidder_is_shuffled_independently():
    rng = np.random.default_rng(40)
    actions = rng.integers(0, 3, (400, 4))
    actions[:, 1] = actions[:, 0]
    result = m.symmetric_permutation_test(actions, n_perm=199, rng=41)
    assert result.p_value[0, 1] == pytest.approx(1 / 200)
    assert result.gamma_corrected[0, 1] > 1.5
    assert m.detect_calibrated(result) == (0, 1)


def test_symmetric_null_reproducibility_blocks_and_multicolumn_states():
    rng = np.random.default_rng(6)
    actions = rng.integers(0, 3, (150, 3))
    states = [rng.integers(0, 2, (150, 2)) for _ in range(3)]
    r1 = m.symmetric_permutation_test(actions, states, n_perm=39, rng=7)
    r2 = m.symmetric_permutation_test(actions, states, n_perm=39, rng=7)
    assert np.allclose(r1.null_mean, r2.null_mean, equal_nan=True)
    # Singleton shuffle blocks cannot move any observation.
    locked = m.symmetric_permutation_test(actions, states, blocks=np.arange(150), n_perm=19, rng=8)
    assert np.allclose(locked.p_value[~np.eye(3, dtype=bool)], 1)
    assert np.allclose(locked.gamma_corrected[~np.eye(3, dtype=bool)], 0)


def test_symmetric_null_calibration_on_iid_independent_bidders():
    rng = np.random.default_rng(9)
    pvalues, corrected = [], []
    for _ in range(100):
        states = rng.integers(0, 2, (3, 120))
        actions = (states.T + rng.integers(0, 2, (120, 3))) % 3
        result = m.symmetric_permutation_test(actions, list(states), n_perm=99, rng=rng)
        pvalues.append(result.p_value[0, 1])
        corrected.append(result.gamma_corrected[0, 1])
    assert 0.01 <= np.mean(np.array(pvalues) <= 0.05) <= 0.12
    assert abs(np.mean(corrected)) < 0.02


def test_pair_score_uses_weaker_direction():
    net = np.array([[np.nan, .2, -.1], [.1, np.nan, .3], [.4, -.2, np.nan]])
    assert m.pair_score(net)[0, 1] == pytest.approx(.1)
    assert m.pair_score(net)[0, 2] == pytest.approx(-.1)
    assert np.isnan(m.pair_score(net).diagonal()).all()


def test_cramers_v_and_residual_correlation():
    x = np.tile([0, 0, 1, 1], 100)
    y = np.tile([0, 1, 0, 1], 100)
    assert m.cramers_v(x, x) == pytest.approx(1)
    assert m.cramers_v(x, y) == pytest.approx(0)
    assert m.cramers_v(x, x * 0) == pytest.approx(0)
    assert m.residual_correlation(2 * x + y, 3 * x + y, x, x) == pytest.approx(1)
    assert m.residual_correlation(x, x, x, x) == pytest.approx(0)


def test_auroc_ties_perfect_reversed_and_invalid():
    assert m.auroc([0, 1], [1, 1]) == pytest.approx(.5)
    assert m.auroc([0, 1, 0, 1], [0, 1, 0, 2]) == pytest.approx(1)
    assert m.auroc([0, 1], [1, 0]) == pytest.approx(0)
    with pytest.raises(ValueError):
        m.auroc([1, 1], [0, 1])
    with pytest.raises(ValueError):
        m.auroc([0, 1], [0, np.nan])


@pytest.mark.parametrize("actions,kwargs", [(np.zeros((0, 3), int), {}),
                                        (np.zeros((10, 3)), {}),
                                        (-np.ones((10, 3), int), {}),
                                        (np.zeros((10, 3), int), {"n_perm": 0}),
                                        (np.zeros((10, 3), int), {"states": [None]})])
def test_invalid_symmetric_inputs(actions, kwargs):
    with pytest.raises(ValueError):
        m.symmetric_permutation_test(actions, **kwargs)
