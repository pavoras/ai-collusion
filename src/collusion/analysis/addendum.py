"""Addendum v2.1 matched estimands, placement tests and offline size checks."""

import numpy as np

from .inference import (auc, block_weights, bootstrap_auc, bootstrap_mean, estimate,
                        exact_rate)
from .market import PAIRS

ENDPOINTS = (("L1", "net"), ("L2", "net"), ("L2", "leak"),
             ("L1", "correlation"), ("L2", "correlation"),
             ("L1", "judge:qwen-9b"), ("L2", "judge:qwen-9b"))
TWINS = ("LX", "LY", "LZ")


def holm(p_values):
    """Step-down adjusted p-values, in the original endpoint order."""
    p = np.asarray(p_values, float)
    if p.ndim != 1 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("finite p-values in [0,1] required")
    order = np.argsort(p, kind="stable")
    adjusted = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    result = np.empty_like(p)
    result[order] = adjusted
    return result


def placement_t(cell, twin):
    """Arrays end in [s00, s01, s10, s11]; swapping labels negates T."""
    cell, twin = np.asarray(cell, float), np.asarray(twin, float)
    return .5 * (cell[..., 0] - twin[..., 0] + twin[..., 1] - cell[..., 1])


def label_swap_test(values, *, n_swaps=99999, seed=20261031):
    """Two-sided independent sign flips of complete (index, twin-pair) blocks."""
    values = np.asarray(values, float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or n_swaps < 1:
        raise ValueError("nonempty finite block contrasts and positive swaps required")
    rng = np.random.default_rng(seed)
    observed = float(values.mean())
    exceedances = 0
    for start in range(0, n_swaps, 2000):
        signs = 2 * rng.integers(0, 2, (min(2000, n_swaps - start), len(values))) - 1
        null = (signs * values).mean(axis=1)
        exceedances += int((np.abs(null) >= abs(observed)).sum())
    return {"estimate": observed, "n_blocks": len(values), "n_swaps": n_swaps,
            "seed": seed, "exceedances": exceedances,
            "p_value": (1 + exceedances) / (1 + n_swaps), "two_sided": True,
            "null": "cell/twin labels exchangeable within (index,twin pair)"}


def view(market):
    if market is None or not market["eligible"]:
        return None
    return next((v for v in market["views"] if v["prefix"] == 200 and v["mask"] == "complete"), None)


def scores(market, endpoint):
    v = view(market)
    return v["levels"][endpoint[0]]["scores"].get(endpoint[1]) if v else None


def target(market):
    return PAIRS.index(tuple(sorted(market["assignment"]["designated_pair"])))


def quartet(market, endpoint):
    values = scores(market, endpoint)
    if values is None:
        return None
    roles = market["assignment"]["role_seats"]
    return np.array([values[PAIRS.index(tuple(sorted((roles[s], roles[f]))))]
                     for s in ("strong_0", "strong_1") for f in ("fringe_0", "fringe_1")])


def _market(lookup, cell, index):
    return lookup.get(("registered", cell, index))


def _coverage(indices, selected):
    return {"eligible_indices": list(indices), "contributing_indices": list(selected),
            "eligible_blocks": len(indices), "covered_blocks": len(selected)}


def a1(lookup, *, n_boot=10000, indices=tuple(range(20))):
    """Common eligible N0/SS/NW triplets, with a shared bootstrap per subset."""
    names = ("core.N0", "core.C1-SS", "core.C1-NW")
    triplets = {i: [_market(lookup, c, i) for c in names] for i in indices}
    eligible = [i for i, group in triplets.items() if all(view(m) for m in group)]
    complete = all(m is not None and m.get("observed_rounds", 200) == 200
                   for group in triplets.values() for m in group)

    def estimates(selected, endpoints):
        if not selected:
            return {}
        _, weights = block_weights(selected, n_boot, seed=20261030)
        output = {}
        for endpoint in endpoints:
            if any(scores(m, endpoint) is None for i in selected for m in triplets[i]):
                continue
            values = np.array([[scores(m, endpoint)[target(m)] for m in triplets[i]] for i in selected])
            n0, ss, nw = values.T
            draws = bootstrap_auc(n0, nw, weights) - bootstrap_auc(n0, ss, weights)
            output[":".join(endpoint)] = estimate(auc(n0, nw) - auc(n0, ss), draws)
        return output

    def behaviour_estimates(selected):
        output = {}
        if not selected:
            return output
        _, weights = block_weights(selected, n_boot, seed=20261030)
        for metric in ("joint_profit", "winning_price", "pair_win_share"):
            values = [[view(m)["behaviour"][target(m)][metric] for m in triplets[i]] for i in selected]
            if any(v is None for row in values for v in row):
                output[metric] = None
                continue
            n0, ss, nw = np.array(values).T
            # Additive profit uplift relative to the common N0 cancels in NW minus SS.
            output[metric] = estimate((nw - ss).mean(), bootstrap_mean(nw - ss, weights))
            if metric == "joint_profit":
                denominator = bootstrap_mean(n0, weights)
                with np.errstate(divide="ignore", invalid="ignore"):
                    draws = bootstrap_mean(nw - ss, weights) / denominator
                output["relative_profit_uplift_difference"] = (estimate((nw - ss).mean() / n0.mean(), draws)
                                                                 if n0.mean() else None)
        return output

    endpoints = estimates(eligible, ENDPOINTS[:5])
    judge_subsets = {}
    for endpoint in ENDPOINTS[5:]:
        selected = [i for i in eligible if all(scores(m, endpoint) is not None for m in triplets[i])]
        judge_subsets[endpoint[0]] = {**_coverage(eligible, selected),
                                    "auroc_differences": estimates(selected, (*ENDPOINTS[:5], endpoint)),
                                    "behaviour_NW_minus_SS": behaviour_estimates(selected)}
        endpoints.update(estimates(selected, (endpoint,)))
    return {"status": "complete" if complete else "incomplete or cancelled",
            "seed": 20261030, "n_boot": n_boot, "indices": eligible,
            "excluded_or_uncollected_indices": sorted(set(indices) - set(eligible)),
            "auroc_differences": endpoints, "behaviour_NW_minus_SS": behaviour_estimates(eligible),
            "judge_coverage_and_matched_comparisons": judge_subsets,
            "profit_definition": "Additive N0-referenced joint-profit uplift; also relative difference of mean uplifts."}


def _block_estimate(rows, n_boot):
    """Resample indices together, retaining all twin pairs/endpoints at that index."""
    if not rows:
        return None
    indices, weights = block_weights(range(20), n_boot, seed=20261032)
    sums, counts = np.zeros(20), np.zeros(20)
    for index, value in rows:
        sums[index] += value
        counts[index] += 1
    with np.errstate(divide="ignore", invalid="ignore"):
        draws = (weights @ sums) / (weights @ counts)
    return estimate(sums.sum() / counts.sum(), draws)


def a2(lookup, *, n_boot=10000, n_swaps=99999):
    """Seven placement endpoints with Holm and whole-index bootstrap companions."""
    pairs = {name: {i: (_market(lookup, "lookalike." + name, i),
                       _market(lookup, "lookalike." + name + "-swap", i)) for i in range(20)} for name in TWINS}
    eligible = {name: [i for i, group in blocks.items() if all(view(m) for m in group)]
                for name, blocks in pairs.items()}
    complete = all(m is not None and m.get("observed_rounds", 200) == 200
                   for blocks in pairs.values() for group in blocks.values() for m in group)

    def endpoint_result(endpoint, subsets):
        blocks, interactions, per_pair, coverage = [], [], {}, {}
        for name in TWINS:
            selected = [i for i in subsets[name] if all(scores(m, endpoint) is not None for m in pairs[name][i])]
            local, ds = [], []
            for i in selected:
                original, twin = [quartet(m, endpoint) for m in pairs[name][i]]
                local.append((i, float(placement_t(original, twin))))
                ds.append((i, float(original @ np.array([1, -1, -1, 1]))))
            blocks.extend((i, name, value) for i, value in local)
            interactions.extend(ds)
            per_pair[name] = {"mean_T": _block_estimate(local, n_boot),
                              "D_original_cell": _block_estimate(ds, n_boot)}
            coverage[name] = _coverage(eligible[name], selected)
        # No pooled test after a collection cancellation or a wholly uncovered twin pair.
        test = label_swap_test([v for _, _, v in blocks], n_swaps=n_swaps) if complete and all(
            coverage[n]["covered_blocks"] for n in TWINS) else None
        return {"coverage": coverage, "blocks": [{"index": i, "twin_pair": name, "T": value} for i, name, value in blocks],
                "test": test, "per_twin_pair": per_pair,
                "mean_T": _block_estimate([(i, v) for i, _, v in blocks], n_boot) if complete and all(
                    coverage[n]["covered_blocks"] for n in TWINS) else None,
                "D_original_cells": _block_estimate(interactions, n_boot) if complete and all(
                    coverage[n]["covered_blocks"] for n in TWINS) else None}

    endpoints = {":".join(e): endpoint_result(e, eligible) for e in ENDPOINTS}
    adjusted = holm([endpoints[":".join(e)]["test"]["p_value"] if endpoints[":".join(e)]["test"] else 1
                     for e in ENDPOINTS])
    for endpoint, value in zip(ENDPOINTS, adjusted):
        result = endpoints[":".join(endpoint)]
        result["holm_p_value"] = float(value) if result["test"] else None
        result["holm_reject"] = bool(result["test"] and value <= .05)
    judge_comparisons = {}
    for endpoint in ENDPOINTS[5:]:
        selected = {name: [i for i in eligible[name] if all(scores(m, endpoint) is not None for m in pairs[name][i])]
                    for name in TWINS}
        judge_comparisons[endpoint[0]] = {":".join(e): endpoint_result(e, selected) for e in (*ENDPOINTS[:5], endpoint)}
    candidates = {}
    for endpoint in ENDPOINTS[:3]:
        counts = {kind: [0, 0] for kind in ("same_model", "different_model")}
        for name in TWINS:
            for i in eligible[name]:
                for market in pairs[name][i]:
                    choices = view(market)["levels"][endpoint[0]].get("candidates", {}).get(endpoint[1])
                    if choices is None:
                        continue
                    models = market["assignment"]["model_to_seat"]
                    for k, (a, b) in enumerate(PAIRS):
                        count = counts["same_model" if models[a] == models[b] else "different_model"]
                        count[0] += int(k in choices)
                        count[1] += 1
        candidates[":".join(endpoint)] = {kind: {"hits": v[0], "pair_opportunities": v[1],
            "rate": v[0] / v[1] if v[1] else None} for kind, v in counts.items()}
    return {"status": "complete" if complete else "incomplete or cancelled; pooled tests withheld",
            "bootstrap_seed": 20261032, "n_boot": n_boot, "swap_seed": 20261031, "n_swaps": n_swaps,
            "endpoints": endpoints, "judge_coverage_and_matched_comparisons": judge_comparisons,
            "candidate_rates": candidates, "candidate_rate_note": "All six pairs; descriptive pair opportunities, no iid intervals.",
            "interpretation": "Positive net contrast with a leak interval containing zero is unresolved differential leak; "
                              "it establishes neither equivalence, calibration, nor a sameness mechanism."}


def analyze_addendum(lookup, manifest, *, n_boot=10000):
    if manifest.get("manifest_version") != "collection_v2":
        return {"status": "not declared by this manifest"}
    return {"specification": "docs/PREREG.md Addendum v2.1", "A1": a1(lookup, n_boot=n_boot),
            "A2": a2(lookup, n_boot=n_boot),
            "A3": {"indices": list(range(20)), "analysis": "Merged breadth cells in all_cells; no 10-market selection."}}


def placement_size_check(repetitions=1000, *, n_swaps=1999, seed=20261033):
    """Exchangeable fake cell/twin scores; seven correlated endpoints, no LLM data."""
    rng = np.random.default_rng(seed)
    hits = np.zeros(7, int)
    family_hits = 0
    swap_rng = np.random.default_rng(20261031)
    signs = 2 * swap_rng.integers(0, 2, (n_swaps, 60)) - 1
    for repetition in range(repetitions):
        cell = rng.normal(size=(60, 4, 7))
        twin = rng.normal(size=(60, 4, 7))
        values = .5 * (cell[:, 0] - twin[:, 0] + twin[:, 1] - cell[:, 1])
        exceedances = np.zeros(7, int)
        for start in range(0, n_swaps, 2000):
            null = signs[start:start + 2000] @ values / 60
            exceedances += (np.abs(null) >= np.abs(values.mean(axis=0))).sum(axis=0)
        p = (1 + exceedances) / (1 + n_swaps)
        hits += p <= .05
        family_hits += bool((holm(p) <= .05).any())
    return {"data_kind": "scripted exchangeable cell/twin Gaussian scores", "seed": seed,
            "test_seed": 20261031, "n_swaps": n_swaps, "repetitions": repetitions,
            "endpoint_size": [exact_rate(h, repetitions) for h in hits],
            "Holm_family_size": exact_rate(family_hits, repetitions)}
