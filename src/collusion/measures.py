"""Pairwise influence, net influence and detection rules.

Implements Bonjour, Aggarwal and Bhargava (UAI 2022), "Information-Theoretic Approach to Detect Collusion in
Multi-Agent Games", for fully observable simultaneous games, where every agent sees the same state s and the
individual influence reduces to a conditional mutual information (their Eq. 6-7):

    gamma(i; j) = I(A_i; A_j | S)        (in bits, plug-in estimate, their Eq. 12-13)

On top of the paper we add a permutation test (shuffle a_i within each state) that gives a p-value and a
bias-corrected gamma per pair, and a detection rule calibrated by those p-values instead of a fixed alpha.

Data layout used throughout:
    actions: int array of shape (n_rounds, n_agents), values in 0..n_actions-1
    states:  int array of shape (n_rounds,) or None (one constant state)
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy import stats

PAPER_ALPHA = 0.05


def _encode_states(states, n_rounds: int) -> tuple[np.ndarray, int]:
    """Map arbitrary state labels to 0..n_states-1."""
    if states is None:
        return np.zeros(n_rounds, dtype=np.int64), 1
    states = np.asarray(states)
    if states.shape[0] != n_rounds:
        raise ValueError(f"states has {states.shape[0]} rows, expected {n_rounds}")
    if states.ndim > 1:
        # Rows of a multi-column state (e.g. last round's joint action) become one label each.
        _, codes = np.unique(states, axis=0, return_inverse=True)
    else:
        _, codes = np.unique(states, return_inverse=True)
    codes = codes.reshape(-1).astype(np.int64)
    return codes, int(codes.max()) + 1


def _n_actions(*arrays: np.ndarray) -> int:
    return int(max(int(a.max()) for a in arrays)) + 1


def _cmi_from_counts(counts: np.ndarray) -> np.ndarray:
    """Plug-in I(X; Y | S) in bits from counts of shape (..., n_states, k_x, k_y)."""
    counts = counts.astype(np.float64)
    n = counts.sum(axis=(-3, -2, -1), keepdims=True)
    n_s = counts.sum(axis=(-2, -1), keepdims=True)
    n_sx = counts.sum(axis=-1, keepdims=True)
    n_sy = counts.sum(axis=-2, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = counts / n * np.log2(counts * n_s / (n_sx * n_sy))
    terms = np.where(counts > 0, terms, 0.0)
    return terms.sum(axis=(-3, -2, -1))


def _counts(a_x: np.ndarray, a_y: np.ndarray, s: np.ndarray, n_states: int, k: int) -> np.ndarray:
    """Contingency table(s) of shape (..., n_states, k, k); a_x may carry leading permutation axes."""
    lead = a_x.shape[:-1]
    n_blocks = int(np.prod(lead)) if lead else 1
    cell = (s * k + a_x) * k + a_y
    offsets = (np.arange(n_blocks) * (n_states * k * k)).reshape(lead + (1,)) if lead else 0
    flat = np.bincount((cell + offsets).ravel(), minlength=n_blocks * n_states * k * k)
    return flat.reshape(lead + (n_states, k, k))


def influence(actions_i, actions_j, states=None, n_actions: int | None = None) -> float:
    """Individual influence gamma(i; j) = I(A_i; A_j | S) in bits (plug-in, no bias correction).

    Symmetric in i and j because the game is simultaneous and fully observable.
    """
    a_i = np.asarray(actions_i, dtype=np.int64)
    a_j = np.asarray(actions_j, dtype=np.int64)
    if a_i.shape != a_j.shape or a_i.ndim != 1:
        raise ValueError("actions_i and actions_j must be 1-D arrays of equal length")
    s, n_states = _encode_states(states, a_i.shape[0])
    k = n_actions or _n_actions(a_i, a_j)
    return float(_cmi_from_counts(_counts(a_i, a_j, s, n_states, k)))


def influence_matrix(actions, states=None, n_actions: int | None = None) -> np.ndarray:
    """Matrix G with G[i, j] = gamma(i; j); the diagonal is NaN."""
    actions = np.asarray(actions, dtype=np.int64)
    n_agents = actions.shape[1]
    s, n_states = _encode_states(states, actions.shape[0])
    k = n_actions or _n_actions(actions)
    gamma = np.full((n_agents, n_agents), np.nan)
    for i, j in combinations(range(n_agents), 2):
        gamma[i, j] = gamma[j, i] = _cmi_from_counts(_counts(actions[:, i], actions[:, j], s, n_states, k))
    return gamma


def net_influence(gamma: np.ndarray) -> np.ndarray:
    """Net influence (paper Eq. 4): Gamma(i; j) = gamma(i; j) - max_{k != i, j} gamma(k; j).

    Needs at least three agents. The diagonal is NaN.
    """
    gamma = np.asarray(gamma, dtype=np.float64)
    n_agents = gamma.shape[0]
    if n_agents < 3:
        raise ValueError("net influence needs at least three agents")
    net = np.full_like(gamma, np.nan)
    for i in range(n_agents):
        for j in range(n_agents):
            if i == j:
                continue
            others = [gamma[k, j] for k in range(n_agents) if k not in (i, j)]
            net[i, j] = gamma[i, j] - max(others)
    return net


def passing_pairs(net: np.ndarray, alpha: float = PAPER_ALPHA) -> list[tuple[int, int]]:
    """Unordered pairs with Gamma(i; j) >= alpha and Gamma(j; i) >= alpha (paper Eq. 5)."""
    n_agents = net.shape[0]
    return [(i, j) for i, j in combinations(range(n_agents), 2) if net[i, j] >= alpha and net[j, i] >= alpha]


def detect(net: np.ndarray, alpha: float = PAPER_ALPHA) -> tuple[int, int] | None:
    """Paper's detector: report a colluding pair only if exactly one pair passes Eq. 5, else None."""
    pairs = passing_pairs(net, alpha)
    return pairs[0] if len(pairs) == 1 else None


@dataclass
class PermutationResult:
    gamma: np.ndarray            # observed gamma(i; j), bits
    null_mean: np.ndarray        # mean of gamma under within-state shuffles of a_i
    p_value: np.ndarray          # (1 + #{null >= observed}) / (1 + n_perm)
    n_perm: int

    @property
    def gamma_corrected(self) -> np.ndarray:
        """Bias-corrected gamma: observed minus the mean of its permutation null."""
        return self.gamma - self.null_mean

    @property
    def net_corrected(self) -> np.ndarray:
        return net_influence(self.gamma_corrected)


def _within_state_permutations(s: np.ndarray, n_perm: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Return (base, perm) with s[base] == s[perm[p]] and perm[p] shuffled inside each state block."""
    n = s.shape[0]
    base = np.argsort(s, kind="stable")
    keys = rng.random((n_perm, n))
    perm = np.lexsort((keys, np.broadcast_to(s, (n_perm, n))), axis=-1)
    return base, perm


def permutation_test(
    actions,
    states=None,
    n_perm: int = 999,
    rng: np.random.Generator | int | None = None,
    n_actions: int | None = None,
) -> PermutationResult:
    """Permutation null for every pair: shuffle a_i across rounds within each state, keep a_j fixed.

    This keeps both marginals per state and breaks only the dependence between i and j. Since gamma is
    symmetric here, one test per unordered pair is enough.
    """
    rng = np.random.default_rng(rng)
    actions = np.asarray(actions, dtype=np.int64)
    n_rounds, n_agents = actions.shape
    s, n_states = _encode_states(states, n_rounds)
    k = n_actions or _n_actions(actions)
    base, perm = _within_state_permutations(s, n_perm, rng)

    gamma = np.full((n_agents, n_agents), np.nan)
    null_mean = np.full_like(gamma, np.nan)
    p_value = np.full_like(gamma, np.nan)
    for i, j in combinations(range(n_agents), 2):
        a_i, a_j = actions[:, i], actions[:, j]
        observed = _cmi_from_counts(_counts(a_i, a_j, s, n_states, k))
        shuffled = np.empty((n_perm, n_rounds), dtype=np.int64)
        shuffled[:, base] = a_i[perm]
        null = _cmi_from_counts(_counts(shuffled, a_j, s, n_states, k))
        # Small tolerance so that ties from floating-point noise count as "as extreme".
        exceed = np.count_nonzero(null >= observed - 1e-12)
        gamma[i, j] = gamma[j, i] = observed
        null_mean[i, j] = null_mean[j, i] = null.mean()
        p_value[i, j] = p_value[j, i] = (1 + exceed) / (1 + n_perm)
    return PermutationResult(gamma=gamma, null_mean=null_mean, p_value=p_value, n_perm=n_perm)


def calibrated_pairs(result: PermutationResult, level: float = 0.05) -> list[tuple[int, int]]:
    """Pairs that pass the permutation-calibrated rule.

    A pair (i, j) passes if its gamma is significant after Bonferroni over all pairs (p <= level / m) and,
    on bias-corrected gamma, each is the other's strongest partner: Gamma_c(i; j) > 0 and Gamma_c(j; i) > 0.
    The false-alarm rate is at most `level` only if the within-state shuffle is a valid null, i.e. each action
    depends on nothing but the given state. Coarse states and adaptive histories can break this; check on
    simulated data before relying on it.
    """
    n_agents = result.gamma.shape[0]
    m = n_agents * (n_agents - 1) // 2
    net = result.net_corrected
    return [
        (i, j)
        for i, j in combinations(range(n_agents), 2)
        if result.p_value[i, j] <= level / m and net[i, j] > 0 and net[j, i] > 0
    ]


def detect_calibrated(result: PermutationResult, level: float = 0.05) -> tuple[int, int] | None:
    """Calibrated detector: report a pair only if exactly one pair passes `calibrated_pairs`."""
    pairs = calibrated_pairs(result, level)
    return pairs[0] if len(pairs) == 1 else None


def plugin_bias(n_rounds: int, k_i: int = 3, k_j: int = 3, n_states: int = 1) -> float:
    """First-order bias of plug-in I(A_i; A_j | S) under independence, in bits (Miller-Madow style)."""
    return n_states * (k_i - 1) * (k_j - 1) / (2 * n_rounds * np.log(2))


def g_test_pvalue(gamma: float, n_rounds: int, k_i: int = 3, k_j: int = 3, n_states: int = 1) -> float:
    """Asymptotic p-value: 2 N ln(2) * gamma ~ chi2 with n_states * (k_i - 1) * (k_j - 1) degrees of freedom."""
    dof = n_states * (k_i - 1) * (k_j - 1)
    return float(stats.chi2.sf(2 * n_rounds * np.log(2) * gamma, dof))
