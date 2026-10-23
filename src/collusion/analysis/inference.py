"""Matched inference, tie-aware ranks and exact binomial intervals."""

import numpy as np
from scipy.stats import beta, rankdata

from collusion.measures import auroc


def auc(negative, positive):
    """AUROC with half credit for ties."""
    negative, positive = np.asarray(negative), np.asarray(positive)
    return auroc(np.r_[np.zeros(len(negative)), np.ones(len(positive))],
                 np.r_[negative, positive])


def primary_test(negative, positive, *, indices=None, n_swaps=99999, seed=20261027):
    """Independent within-block swaps; rank sums avoid quadratic comparisons."""
    negative, positive = np.asarray(negative, float), np.asarray(positive, float)
    if negative.ndim != 1 or negative.shape != positive.shape or not len(negative):
        raise ValueError("equal nonempty matched score vectors required")
    observed = auc(negative, positive)
    n = len(negative)
    ranks = rankdata(np.r_[negative, positive])
    rng = np.random.default_rng(seed)
    exceed = 0
    for start in range(0, n_swaps, 2000):
        swaps = rng.integers(0, 2, (min(2000, n_swaps - start), n))
        sums = np.where(swaps, ranks[:n], ranks[n:]).sum(axis=1)
        null = (sums - n * (n + 1) / 2) / n**2
        exceed += int(np.count_nonzero(null >= observed))
    p = (1 + exceed) / (1 + n_swaps)
    return {"status": "available", "model": "qwen-9b", "treatment": "C1-SS",
            "control": "N0", "level": "L2", "detector": "net", "prefix": 200,
            "mask": "complete", "n_blocks": n, "market_indices": list(range(n)) if indices is None else list(indices),
            "auroc": observed, "exceedances": exceed, "n_swaps": n_swaps,
            "seed": seed, "p_value": p, "reject": bool(observed > .5 and p <= .05),
            "null": "within-block condition-label exchangeability"}


def interval(values):
    """Pointwise percentile interval, retaining empty draws as missing."""
    values = np.asarray(values, float)
    finite = values[np.isfinite(values)]
    return {"low": float(np.quantile(finite, .025)) if len(finite) else None,
            "high": float(np.quantile(finite, .975)) if len(finite) else None,
            "valid_draws": len(finite), "empty_draws": len(values) - len(finite)}


def estimate(point, draws):
    return {"estimate": float(point), **interval(draws)}


def exact_rate(hits, total):
    """Count and two-sided 95% Clopper-Pearson interval."""
    return {"hits": int(hits), "total": int(total),
            "estimate": float(hits / total) if total else None,
            "low": float(beta.ppf(.025, hits, total - hits + 1)) if hits else (0.0 if total else None),
            "high": float(beta.ppf(.975, hits + 1, total - hits)) if hits < total else (1.0 if total else None)}


def localisation(scores, target, candidates=None):
    """Fractional top-1 and reciprocal average rank, plus unique decisions."""
    scores = np.asarray(scores, float)
    ranks = rankdata(-scores, method="average")
    top = scores == scores.max()
    unique = candidates[0] if candidates is not None and len(candidates) == 1 else None
    return {"top1": float(top[target] / top.sum()), "mrr": float(1 / ranks[target]),
            "correct_unique": float(unique == target) if candidates is not None else None,
            "wrong_pair": float(unique is not None and unique != target) if candidates is not None else None,
            "abstention": float(unique is None) if candidates is not None else None}


def bootstrap_auc(negative, positive, weights):
    """All-pairs AUROC for shared whole-block bootstrap multiplicities."""
    negative, positive = np.asarray(negative), np.asarray(positive)
    comparison = (positive[:, None] > negative).astype(float) + .5 * (positive[:, None] == negative)
    counts = weights.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.einsum("bi,ij,bj->b", weights, comparison, weights, optimize=True) / counts**2


def bootstrap_mean(values, weights):
    values = np.asarray(values, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return weights @ values / weights.sum(axis=1)


def block_weights(indices, n_boot=10000, seed=20261028):
    """One union-index draw shared by every condition/detector in a cohort."""
    indices = sorted(set(indices))
    rng = np.random.default_rng(seed)
    draws = rng.integers(len(indices), size=(n_boot, len(indices)))
    weights = np.zeros((n_boot, len(indices)), int)
    np.add.at(weights, (np.arange(n_boot)[:, None], draws), 1)
    return indices, weights
