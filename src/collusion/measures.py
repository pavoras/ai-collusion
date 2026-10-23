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


def _entropy_counts(counts, axes):
    """Entropy in bits from integer counts, using a small x*log2(x) lookup."""
    total = counts.sum(axis=axes)
    lookup = np.arange(int(total.max()) + 1, dtype=float)
    lookup[1:] *= np.log2(lookup[1:])
    return np.log2(total) - lookup[counts].sum(axis=axes) / total


def _conditional_entropy(actions, state, n_states, k):
    """H(B | S), allowing leading permutation axes on actions."""
    lead = actions.shape[:-1]
    blocks = int(np.prod(lead)) if lead else 1
    offset = (np.arange(blocks) * n_states * k).reshape(lead + (1,)) if lead else 0
    counts = np.bincount((state * k + actions + offset).ravel(), minlength=blocks * n_states * k)
    counts = counts.reshape(lead + (n_states, k))
    # H(S,B) - H(S) avoids undefined empty-stratum entropies.
    return _entropy_counts(counts, (-2, -1)) - _entropy_counts(counts.sum(axis=-1), (-1,))


def _partial_components(a_i, a_j, s_i, s_j, n_i, n_j, k):
    """Eq. 3 and its three terms, including batches of shuffled actions."""
    joint, n_joint = _encode_states(np.column_stack([s_i, s_j]), len(s_i))
    counts = _counts(a_i, a_j, joint, n_joint, k)
    h_state = _entropy_counts(counts.sum(axis=(-2, -1)), (-1,))
    h_i_joint = _entropy_counts(counts.sum(axis=-1), (-2, -1)) - h_state
    h_j_joint = _entropy_counts(counts.sum(axis=-2), (-2, -1)) - h_state
    h_pair_joint = _entropy_counts(counts, (-3, -2, -1)) - h_state
    action = h_i_joint + h_j_joint - h_pair_joint
    h_i = _conditional_entropy(a_i, s_i, n_i, k)
    h_j = _conditional_entropy(a_j, s_j, n_j, k)
    return action, h_i - h_i_joint, h_j - h_j_joint


def _add_public_state(state, public_state, n_rounds):
    """Append shared history to an agent's private state, retaining exact labels."""
    if public_state is None:
        return state
    history, _ = _encode_states(public_state, n_rounds)
    if state is None:
        return history
    private, _ = _encode_states(state, n_rounds)
    return np.column_stack([private, history])


def _partial_inputs(actions_i, actions_j, states_i, states_j, public_state=None):
    a_i, a_j = np.asarray(actions_i), np.asarray(actions_j)
    if (a_i.ndim != 1 or a_i.shape != a_j.shape or a_i.size == 0 or
            not np.issubdtype(a_i.dtype, np.integer) or not np.issubdtype(a_j.dtype, np.integer) or
            min(a_i.min(), a_j.min()) < 0):
        raise ValueError("actions must be nonempty, equal-length nonnegative integer vectors")
    s_i, n_i = _encode_states(_add_public_state(states_i, public_state, len(a_i)), len(a_i))
    s_j, n_j = _encode_states(_add_public_state(states_j, public_state, len(a_i)), len(a_i))
    return a_i, a_j, s_i, s_j, n_i, n_j


def influence_decomposition(actions_i, actions_j, states_i, states_j, *, public_state=None):
    """Return (I(Bi;Bj|Si,Sj), I(Bi;Sj|Si), I(Bj;Si|Sj)) in bits.

    public_state adds the same exact history H to both private states.
    The second term is then I(Bi;Sj|Si,H), information received by bidder i.
    Their sum is the symmetric, partially observable influence of paper Eq. 3.
    """
    a_i, a_j, s_i, s_j, n_i, n_j = _partial_inputs(actions_i, actions_j, states_i, states_j, public_state)
    return tuple(float(v) for v in _partial_components(a_i, a_j, s_i, s_j, n_i, n_j, _n_actions(a_i, a_j)))


def partial_influence(actions_i, actions_j, states_i, states_j, *, public_state=None):
    """Paper Eq. 3: H(Bi|Si) + H(Bj|Sj) - H(Bi,Bj|Si,Sj), in bits."""
    a_i, a_j, s_i, s_j, n_i, n_j = _partial_inputs(actions_i, actions_j, states_i, states_j, public_state)
    k = _n_actions(a_i, a_j)
    joint, n_joint = _encode_states(np.column_stack([s_i, s_j]), len(s_i))
    return float(_conditional_entropy(a_i, s_i, n_i, k) + _conditional_entropy(a_j, s_j, n_j, k)
                 - _conditional_entropy(a_i * k + a_j, joint, n_joint, k * k))


@dataclass
class SymmetricPermutationResult(PermutationResult):
    """Joint independent shuffles; leak[i,j] means bid i receives state j."""

    action: np.ndarray
    action_null_mean: np.ndarray
    leak: np.ndarray
    leak_null_mean: np.ndarray
    leak_p_value: np.ndarray

    @property
    def leak_corrected(self):
        return self.leak - self.leak_null_mean

    @property
    def action_corrected(self):
        return self.action - self.action_null_mean


def symmetric_permutation_test(actions, states=None, *, public_state=None, n_perm=999, rng=None, blocks=None):
    """Shuffle every bidder independently within its own state strata.

    states is a sequence of one state array per bidder (None means constant
    states). public_state appends exact shared history H to every own state;
    pass coarse labels explicitly for an ablation. Optionally restrict shuffles within blocks, e.g. market IDs when
    pooling. The returned gamma and directional leaks have plus-one p-values
    and signed bias corrections; corrections are deliberately not truncated.
    Validity requires exchangeability within each bidder's strata. This is
    an empirical check, not a guarantee for adaptive repeated games.
    """
    actions = np.asarray(actions)
    if (actions.ndim != 2 or not actions.size or actions.shape[1] < 2 or
            not np.issubdtype(actions.dtype, np.integer) or actions.min() < 0 or n_perm < 1):
        raise ValueError("nonempty nonnegative integer action matrix and positive n_perm required")
    n, players = actions.shape
    if states is None:
        states = [None] * players
    if len(states) != players:
        raise ValueError("one state array per bidder required")
    encoded = [_encode_states(_add_public_state(s, public_state, n), n) for s in states]
    rng = np.random.default_rng(rng)
    shuffled = []
    for i, (s, _) in enumerate(encoded):
        strata = s if blocks is None else _encode_states(np.column_stack([s, blocks]), n)[0]
        base, perm = _within_state_permutations(strata, n_perm, rng)
        draws = np.empty((n_perm, n), dtype=np.int64)
        draws[:, base] = actions[perm, i]
        shuffled.append(draws)
    k = _n_actions(actions)
    gamma, null_mean, p_value, action, action_mean, leak, leak_mean, leak_p = [
        np.full((players, players), np.nan) for _ in range(8)]
    for i, j in combinations(range(players), 2):
        s_i, n_i = encoded[i]
        s_j, n_j = encoded[j]
        observed = _partial_components(actions[:, i], actions[:, j], s_i, s_j, n_i, n_j, k)
        null = _partial_components(shuffled[i], shuffled[j], s_i, s_j, n_i, n_j, k)
        g, null_g = sum(observed), sum(null)
        gamma[i, j] = gamma[j, i] = g
        null_mean[i, j] = null_mean[j, i] = null_g.mean()
        p_value[i, j] = p_value[j, i] = (1 + np.count_nonzero(null_g >= g - 1e-12)) / (n_perm + 1)
        action[i, j] = action[j, i] = observed[0]
        action_mean[i, j] = action_mean[j, i] = null[0].mean()
        for receiver, source, term in [(i, j, 1), (j, i, 2)]:
            leak[receiver, source] = observed[term]
            leak_mean[receiver, source] = null[term].mean()
            leak_p[receiver, source] = (1 + np.count_nonzero(null[term] >= observed[term] - 1e-12)) / (n_perm + 1)
    return SymmetricPermutationResult(gamma, null_mean, p_value, n_perm, action, action_mean,
                                      leak, leak_mean, leak_p)


def classify_leaks(p_incoming, p_outgoing, incoming, outgoing, *, n_directions=12,
                   level=0.05, absence_p=0.2, absence_bits=0.05):
    """Classify measured flow with fixed significance and practical-absence guards.

    Absence means p >= .2 AND corrected leak <= .05 bits. This operational
    guard is not an equivalence test or proof of no flow. Intermediate evidence
    is unclear. One-way flow does not distinguish espionage from cooperation.
    Bonferroni covers all ordered pairs, including selection by net influence.
    """
    p = np.asarray([p_incoming, p_outgoing], dtype=float)
    effect = np.asarray([incoming, outgoing], dtype=float)
    if (not np.isfinite(np.r_[p, effect]).all() or np.any((p < 0) | (p > 1)) or
            n_directions < 1 or not 0 < level < absence_p <= 1 or absence_bits < 0):
        raise ValueError("finite effects, valid probabilities and classification thresholds required")
    significant = p <= level / n_directions
    absent = (p >= absence_p) & (effect <= absence_bits)
    if significant.all():
        return "two-way"
    if significant[0] and absent[1]:
        return "one-way j->i"
    if significant[1] and absent[0]:
        return "one-way i->j"
    if absent.all():
        return "none"
    return "unclear"


def pair_score(net):
    """Symmetric matrix min(Gamma_ij, Gamma_ji); diagonal stays NaN."""
    net = np.asarray(net)
    return np.minimum(net, net.T)


def cramers_v(actions_i, actions_j):
    """Uncorrected Cramer's V on observed bid categories, zero for constants."""
    x, nx = _encode_states(actions_i, len(actions_i))
    y, ny = _encode_states(actions_j, len(actions_i))
    if min(nx, ny) == 1:
        return 0.0
    counts = np.bincount(x * ny + y, minlength=nx * ny).reshape(nx, ny)
    chi2 = stats.chi2_contingency(counts, correction=False).statistic
    return float(np.sqrt(chi2 / (len(x) * min(nx - 1, ny - 1))))


def residual_correlation(actions_i, actions_j, costs_i, costs_j):
    """Signed Pearson correlation after subtracting each own-cost cell mean."""
    residuals = []
    for actions, costs in [(actions_i, costs_i), (actions_j, costs_j)]:
        actions = np.asarray(actions, dtype=float)
        codes, n_states = _encode_states(costs, len(actions))
        means = np.bincount(codes, weights=actions, minlength=n_states) / np.bincount(codes, minlength=n_states)
        residuals.append(actions - means[codes])
    x, y = residuals
    norm = np.linalg.norm(x) * np.linalg.norm(y)
    return float(x @ y / norm) if norm > 1e-12 else 0.0


def auroc(labels, scores):
    """Rank AUROC with half credit for tied scores; both classes required."""
    labels, scores = np.asarray(labels), np.asarray(scores, dtype=float)
    if (labels.ndim != 1 or labels.shape != scores.shape or not np.isin(labels, [0, 1]).all()
            or not np.isfinite(scores).all() or len(np.unique(labels)) != 2):
        raise ValueError("finite scores and binary labels with both classes required")
    positive = labels == 1
    n_pos, n_neg = positive.sum(), (~positive).sum()
    ranks = stats.rankdata(scores)
    return float((ranks[positive].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))
