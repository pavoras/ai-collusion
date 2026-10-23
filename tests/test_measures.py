import numpy as np
import pytest

from collusion import measures as m

LOG2_3 = np.log2(3)


def random_actions(rng, n_rounds, n_agents=3, k=3):
    return rng.integers(0, k, size=(n_rounds, n_agents))


def test_independent_players_gamma_near_bias():
    rng = np.random.default_rng(0)
    n = 1000
    values = [m.influence(*random_actions(rng, n, 2).T) for _ in range(300)]
    expected = m.plugin_bias(n)  # about 0.0029 bits
    assert np.mean(values) == pytest.approx(expected, rel=0.25)
    assert max(values) < 0.02


def test_function_of_other_player_gives_log2_3():
    a = np.repeat([0, 1, 2], 100)  # perfectly balanced, so H(A) = log2 3 exactly
    b = (a + 2) % 3                # B = beaten(A), a bijection
    assert m.influence(a, b) == pytest.approx(LOG2_3)


def test_function_of_other_player_random_a():
    rng = np.random.default_rng(1)
    a = rng.integers(0, 3, 5000)
    assert m.influence(a, (a + 2) % 3) == pytest.approx(LOG2_3, abs=0.01)


def test_symmetry():
    rng = np.random.default_rng(2)
    a = rng.integers(0, 3, 400)
    b = np.where(rng.random(400) < 0.4, (a + 2) % 3, rng.integers(0, 3, 400))
    s = rng.integers(0, 4, 400)
    assert m.influence(a, b, s) == pytest.approx(m.influence(b, a, s))
    gamma = m.influence_matrix(np.column_stack([a, b, rng.integers(0, 3, 400)]), s)
    assert np.allclose(gamma, gamma.T, equal_nan=True)


def test_conditioning_on_state_removes_shared_cause():
    # Both players copy the state, so they are dependent but independent given the state.
    rng = np.random.default_rng(3)
    s = rng.integers(0, 3, 3000)
    assert m.influence(s, s) == pytest.approx(LOG2_3, abs=0.01)
    assert m.influence(s, s, states=s) == pytest.approx(0.0)


def test_multicolumn_state_is_one_label_per_row():
    a = np.array([0, 1, 2, 0, 1, 2])
    s2d = np.array([[0, 0], [0, 1], [0, 0], [0, 1], [0, 0], [0, 1]])
    s1d = np.array([0, 1, 0, 1, 0, 1])
    assert m.influence(a, a, s2d) == pytest.approx(m.influence(a, a, s1d))


def test_net_influence_and_detect_by_hand():
    gamma = np.array([
        [np.nan, 0.30, 0.01],
        [0.30, np.nan, 0.02],
        [0.01, 0.02, np.nan],
    ])
    net = m.net_influence(gamma)
    assert net[0, 1] == pytest.approx(0.30 - 0.02)  # strongest other source for agent 1 is agent 2
    assert net[1, 0] == pytest.approx(0.30 - 0.01)
    assert net[0, 2] == pytest.approx(0.01 - 0.02)
    assert m.detect(net) == (0, 1)
    assert m.detect(net, alpha=0.5) is None


def test_detect_requires_exactly_one_pair():
    gamma = np.full((4, 4), 0.0)
    gamma[0, 1] = gamma[1, 0] = 0.3
    gamma[2, 3] = gamma[3, 2] = 0.3
    np.fill_diagonal(gamma, np.nan)
    net = m.net_influence(gamma)
    assert m.passing_pairs(net) == [(0, 1), (2, 3)]
    assert m.detect(net) is None


def test_net_influence_needs_three_agents():
    with pytest.raises(ValueError):
        m.net_influence(np.array([[np.nan, 0.1], [0.1, np.nan]]))


def test_permutation_test_finds_coupled_pair():
    rng = np.random.default_rng(4)
    n = 500
    acts = random_actions(rng, n, 4)
    coupled = rng.random(n) < 0.4
    acts[coupled, 2] = (acts[coupled, 0] + 2) % 3  # agent 2 assists agent 0
    res = m.permutation_test(acts, n_perm=499, rng=5)
    assert res.p_value[0, 2] == pytest.approx(1 / 500)
    assert m.detect_calibrated(res) == (0, 2)
    # Bias correction pulls independent pairs to about zero.
    assert abs(res.gamma_corrected[1, 3]) < 0.01
    assert res.null_mean[1, 3] == pytest.approx(m.plugin_bias(n), rel=0.3)


def test_permutation_keeps_state_blocks():
    rng = np.random.default_rng(6)
    s = rng.integers(0, 3, 50)
    base, perm = m._within_state_permutations(s, 20, rng)
    assert all(np.array_equal(s[base], s[perm[p]]) for p in range(20))
    assert all(np.array_equal(np.sort(perm[p]), np.arange(50)) for p in range(20))


def test_permutation_pvalues_roughly_uniform_under_null():
    rng = np.random.default_rng(7)
    p = []
    for _ in range(200):
        acts = random_actions(rng, 200, 3)
        p.append(m.permutation_test(acts, n_perm=199, rng=rng).p_value[0, 1])
    p = np.array(p)
    assert 0.01 <= np.mean(p <= 0.05) <= 0.10
    assert 0.4 <= np.mean(p) <= 0.6


def test_permutation_with_states_matches_conditioning():
    # Shared cause through the state: plain gamma is large but the within-state null explains it.
    rng = np.random.default_rng(8)
    s = rng.integers(0, 3, 600)
    noisy = lambda: np.where(rng.random(600) < 0.7, s, rng.integers(0, 3, 600))
    acts = np.column_stack([noisy(), noisy(), noisy()])
    res = m.permutation_test(acts, states=s, n_perm=199, rng=9)
    assert np.nanmax(res.gamma) < 0.05
    assert m.detect_calibrated(res) is None


def test_g_test_agrees_with_permutation_roughly():
    rng = np.random.default_rng(10)
    acts = random_actions(rng, 300, 3)
    acts[:, 1] = np.where(rng.random(300) < 0.25, (acts[:, 0] + 2) % 3, acts[:, 1])
    res = m.permutation_test(acts, n_perm=1999, rng=11)
    p_perm = res.p_value[0, 1]
    p_g = m.g_test_pvalue(res.gamma[0, 1], 300)
    assert p_g == pytest.approx(p_perm, abs=0.02) or (p_g < 0.001 and p_perm < 0.002)
