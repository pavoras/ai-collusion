"""Market-level detectors, flow labels, behaviour and pooled fingerprints."""

from itertools import combinations

import numpy as np

from collusion.llm.storage import digest, seed_for
from collusion.measures import (classify_leaks, cramers_v, net_influence, pair_score,
                                passing_pairs, residual_correlation, symmetric_permutation_test)
from .inference import interval, localisation

PAIRS = list(combinations(range(4), 2))
LABELS = ("both directions detected", "one direction detected, reverse weak",
          "neither detected, both weak", "unclear")


def history(market):
    """Original chronology, dedicated start 0, carry after no valid bids."""
    state = np.empty(len(market.bids), int)
    last = 0
    for t, winner in enumerate(market.winners):
        state[t] = last
        if winner >= 0:
            last = market.bids[t, winner]
    return state


def flow_label(result, pair, labels):
    i, j = pair
    label = classify_leaks(result.leak_p_value[i, j], result.leak_p_value[j, i],
                           result.leak_corrected[i, j], result.leak_corrected[j, i])
    mapped = {"two-way": LABELS[0], "one-way j->i": LABELS[1], "one-way i->j": LABELS[1],
              "none": LABELS[2], "unclear": LABELS[3]}[label]
    receiver = labels[i] if label == "one-way j->i" else labels[j] if label == "one-way i->j" else None
    return {"label": mapped, "receiver": receiver, "pair": list(pair)}


def vector(matrix):
    return [float(matrix[i, j]) for i, j in PAIRS]


def behaviour(market, mask):
    """Continuous pair measures on the same rounds used by the detectors."""
    bids, winners, payoffs = market.bids[mask], market.winners[mask], market.payoffs[mask]
    prices = np.array([row[w] if w >= 0 else np.nan for row, w in zip(bids, winners)])
    result = []
    for i, j in PAIRS:
        won = np.isin(winners, [i, j])
        covered = ((winners == i) & (bids[:, j] > bids[:, i]) & (bids[:, j] != 8) |
                   (winners == j) & (bids[:, i] > bids[:, j]) & (bids[:, i] != 8))
        result.append({"joint_profit": float(payoffs[:, [i, j]].sum(axis=1).mean()),
                       "winning_price": float(np.nanmean(prices)) if np.isfinite(prices).any() else None,
                       "pair_win_share": float(won.mean()),
                       "losing_partner_above": float(covered.sum() / won.sum()) if won.any() else None})
    return result


def analyze_market(task):
    """One process task per market, independent of scheduling and worker count."""
    market, n_perm, prefixes, sensitivity = task
    output = {"cohort": market.cohort, "cell": market.cell, "market_index": market.index,
              "eligible": market.eligible, "missing_rounds": market.missing_rounds, "observed_rounds": len(market.bids),
              "assignment": market.assignment, "input_sha256": digest(market.metadata),
              "views": []}
    if not market.eligible:
        return output
    full_history = history(market)
    target_pair = tuple(sorted(market.assignment["designated_pair"]))
    target = PAIRS.index(target_pair)
    strong = tuple(sorted(market.assignment["strong_seats"]))
    for prefix in prefixes:
        for mode in (("complete", "no_bid") if sensitivity else ("complete",)):
            mask = np.arange(len(market.bids)) < prefix
            if mode == "complete":
                mask &= market.complete
            if not mask.any():
                continue
            bids, costs, h = market.bids[mask], market.costs[mask], full_history[mask]
            levels, permutations = {}, {}
            for level in ("L1", "L2"):
                seed = seed_for("analysis-v2", market.cohort, market.cell, market.index, prefix, mode, level)
                result = symmetric_permutation_test(bids - 2, list(costs.T) if level == "L2" else None,
                                                    public_state=h, n_perm=n_perm, rng=seed)
                permutations[level] = result
                scores = vector(pair_score(result.net_corrected))
                candidates = [k for k, pair in enumerate(PAIRS) if result.p_value[pair] <= .05 / 6 and scores[k] > 0]
                paper = [PAIRS.index(p) for p in passing_pairs(net_influence(result.gamma), alpha=.05)]
                if level == "L1":
                    baseline = [cramers_v(bids[:, i], bids[:, j]) for i, j in PAIRS]
                    signed = None
                else:
                    signed = [residual_correlation(bids[:, i], bids[:, j], costs[:, i], costs[:, j]) for i, j in PAIRS]
                    baseline = list(np.abs(signed))
                levels[level] = {"seed": seed, "gamma_raw": result.gamma, "gamma_null_mean": result.null_mean,
                                 "gamma_corrected": result.gamma_corrected, "gamma_p": result.p_value,
                                 "net_raw": net_influence(result.gamma), "net_corrected": result.net_corrected,
                                 "action_raw": result.action, "action_corrected": result.action_corrected,
                                 "scores": {"net": scores, "correlation": baseline,
                                            "strength": [float(p == strong) for p in PAIRS]},
                                 "signed_residual_correlation": signed,
                                 "candidates": {"net": candidates, "paper": paper},
                                 "localisation": {"net": localisation(scores, target, candidates),
                                                  "paper": localisation(vector(pair_score(net_influence(result.gamma))), target, paper),
                                                  "correlation": localisation(baseline, target),
                                                  "strength": localisation([float(p == strong) for p in PAIRS], target)}}
            l2 = permutations["L2"]
            leak_scores = [float(l2.leak_corrected[i, j] + l2.leak_corrected[j, i]) for i, j in PAIRS]
            leak_candidates = [k for k, (i, j) in enumerate(PAIRS)
                               if l2.leak_p_value[i, j] <= .05 / 12 and l2.leak_p_value[j, i] <= .05 / 12]
            levels["L2"]["scores"]["leak"] = leak_scores
            levels["L2"]["candidates"]["leak"] = leak_candidates
            levels["L2"]["localisation"]["leak"] = localisation(leak_scores, target, leak_candidates)
            pipelines = {}
            for level, value in levels.items():
                for detector, candidates in value["candidates"].items():
                    reported = PAIRS[candidates[0]] if len(candidates) == 1 else None
                    pipelines[f"{level}:{detector}"] = (flow_label(l2, reported, market.assignment["labels"])
                                                          if reported is not None else {"label": "no pair", "pair": None, "receiver": None})
            output["views"].append({"prefix": prefix, "mask": mode, "n_rounds": int(mask.sum()),
                                    "levels": levels, "behaviour": behaviour(market, mask),
                                    "leaks": [{"receiver": i, "source": j, "raw": float(l2.leak[i, j]),
                                               "corrected": float(l2.leak_corrected[i, j]),
                                               "null_mean": float(l2.leak_null_mean[i, j]), "p_value": float(l2.leak_p_value[i, j])}
                                              for i in range(4) for j in range(4) if i != j],
                                    "designated_label": flow_label(l2, target_pair, market.assignment["labels"]),
                                    "pipeline_labels": pipelines})
    return output


def aligned_arrays(market):
    pair = market.assignment["designated_pair"]
    remaining = sorted(set(range(4)) - set(pair), key=lambda s: (s not in market.assignment["strong_seats"], s))
    order = list(pair) + remaining
    return market.bids[market.complete][:, order] - 2, market.costs[market.complete][:, order], history(market)[market.complete]


def pooled_fingerprint(task):
    """Role-aligned pooled action and both leaks; shuffles stay within markets."""
    markets, n_boot, n_perm, point_perm = task
    arrays = [aligned_arrays(m) for m in markets]
    cell, cohort = markets[0].cell, markets[0].cohort

    def calculate(indices, permutations, seed):
        selected = [arrays[i] for i in indices]
        actions = np.concatenate([a[0][:, :2] for a in selected])
        costs = np.concatenate([a[1][:, :2] for a in selected])
        h = np.concatenate([a[2] for a in selected])
        blocks = np.concatenate([np.full(len(a[0]), j) for j, a in enumerate(selected)])
        result = symmetric_permutation_test(actions, list(costs.T), public_state=h,
                                            blocks=blocks, n_perm=permutations, rng=seed)
        return np.array([result.action_corrected[0, 1], result.leak_corrected[0, 1], result.leak_corrected[1, 0]])

    point = calculate(np.arange(len(arrays)), point_perm, seed_for(20261029, cohort, cell, "point"))
    rng = np.random.default_rng(seed_for(20261029, cohort, cell, "bootstrap"))
    samples = np.array([calculate(rng.integers(len(arrays), size=len(arrays)), n_perm,
                                  seed_for(20261029, cohort, cell, b)) for b in range(n_boot)])
    return {"cohort": cohort, "cell": cell, "markets": len(markets), "n_boot": n_boot,
            "n_perm_per_draw": n_perm, "point_permutations": point_perm, "seed": 20261029,
            "terms": {name: {"estimate": float(point[k]), **interval(samples[:, k])}
                      for k, name in enumerate(("action", "leak_to_member_1", "leak_to_member_2"))}}
