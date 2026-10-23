"""Three-player Rock-Paper-Scissors with a scripted assistant (Bonjour et al. 2022, Section 5.1).

Moves: 0 = rock, 1 = paper, 2 = scissors. Payoffs per round: all three moves equal -> everybody 0; all three
different -> everybody 1; two distinct moves -> every player with the winning move gets 1.

Player A (index 0) and C (index 2) play uniformly at random. Player B (index 1) assists A: with probability `cp`
("collusion probability") it plays the move that A beats, which guarantees A a point whatever C plays; otherwise
it plays uniformly at random.
"""

from __future__ import annotations

import numpy as np

ROCK, PAPER, SCISSORS = 0, 1, 2


def beaten_by(move: np.ndarray) -> np.ndarray:
    """The move that `move` beats: rock beats scissors, paper beats rock, scissors beat paper."""
    return (np.asarray(move) + 2) % 3


def payoffs(actions: np.ndarray) -> np.ndarray:
    """Per-round payoffs, shape (n_rounds, n_players), for any number of players."""
    actions = np.asarray(actions)
    present = np.stack([(actions == m).any(axis=1) for m in range(3)], axis=1)
    n_distinct = present.sum(axis=1)
    pay = np.zeros(actions.shape, dtype=np.int64)
    pay[n_distinct == 3] = 1
    two = n_distinct == 2
    for winner in range(3):
        loser = int(beaten_by(winner))
        rows = two & present[:, winner] & present[:, loser]
        pay[rows] = (actions[rows] == winner).astype(np.int64)
    return pay


def play(n_rounds: int, cp: float, rng: np.random.Generator, n_players: int = 3) -> np.ndarray:
    """Actions of shape (n_rounds, n_players): player 1 assists player 0 with probability cp, others random."""
    actions = rng.integers(0, 3, size=(n_rounds, n_players))
    assist = rng.random(n_rounds) < cp
    actions[assist, 1] = beaten_by(actions[assist, 0])
    return actions


def previous_round_state(actions: np.ndarray) -> np.ndarray:
    """State = last round's joint action as one integer (first round gets its own label)."""
    n_rounds, n_players = actions.shape
    codes = (actions * 3 ** np.arange(n_players)).sum(axis=1)
    return np.concatenate([[3 ** n_players], codes[:-1]])


def true_gamma(cp: float) -> float:
    """Exact gamma(A; B) in bits: P(B = beaten(A)) = cp + (1 - cp)/3, the other two moves share the rest."""
    q = cp + (1 - cp) / 3
    r = (1 - q) / 2
    h = -q * np.log2(q) - (2 * r * np.log2(r) if r > 0 else 0.0)
    return float(np.log2(3) - h)
