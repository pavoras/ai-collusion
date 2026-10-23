import numpy as np
import pytest

from collusion import measures as m
from collusion.games import rps

R, P, S = rps.ROCK, rps.PAPER, rps.SCISSORS


@pytest.mark.parametrize("actions, expected", [
    ([R, R, R], [0, 0, 0]),   # all equal
    ([R, P, S], [1, 1, 1]),   # all different
    ([R, S, S], [1, 0, 0]),   # rock beats scissors
    ([P, R, P], [1, 0, 1]),   # paper beats rock
    ([S, P, P], [1, 0, 0]),   # scissors beat paper
])
def test_payoff_table(actions, expected):
    assert rps.payoffs(np.array([actions])).tolist() == [expected]


def test_full_assistance_always_gives_a_a_point():
    acts = rps.play(3000, cp=1.0, rng=np.random.default_rng(0))
    assert rps.payoffs(acts)[:, 0].min() == 1


def test_true_gamma_control_values():
    expected = {0: 0, 0.1: 0.014, 0.2: 0.055, 0.3: 0.122, 0.4: 0.214, 0.5: 0.333, 0.7: 0.663, 1.0: 1.585}
    for cp, value in expected.items():
        assert rps.true_gamma(cp) == pytest.approx(value, abs=6e-4)


def test_estimate_matches_true_gamma():
    acts = rps.play(200_000, cp=0.3, rng=np.random.default_rng(1))
    assert m.influence(acts[:, 0], acts[:, 1]) == pytest.approx(rps.true_gamma(0.3), abs=0.005)
    assert m.influence(acts[:, 0], acts[:, 2]) == pytest.approx(0, abs=0.001)


def test_previous_round_state():
    acts = np.array([[0, 1, 2], [2, 2, 2], [1, 0, 0]])
    s = rps.previous_round_state(acts)
    assert s[0] == 27 and s[1] == 0 + 1 * 3 + 2 * 9 and s[2] == 2 + 2 * 3 + 2 * 9
