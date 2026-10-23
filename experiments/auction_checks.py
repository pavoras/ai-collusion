"""Round-4 checks: .venv/Scripts/python experiments/auction_checks.py [--quick].

Outputs: results/auction_scripted/checks_{full,quick}/. No external calls.
The first 20 markets are the primary analysis; additional independent pools
estimate pooled rejection rates. Pooling is secondary. Thresholds below are
fixed before evaluation; the absence guard is operational, not equivalence.
"""

import argparse
import csv
import json
from itertools import combinations
from pathlib import Path
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

from collusion import measures as m, plotting
from collusion.games import auction as a

SEED = 20261024
ROUNDS = 200
POOL_SIZE = 20
PAIRS = list(combinations(range(4), 2))
CLASSES = ["none", "two-way", "one-way j->i", "one-way i->j", "unclear"]
CONDITIONS = [
    ("honest_iid", "Honest IID", (0, 1), "none", {}),
    ("shared_fine", "Shared history", (0, 1), "none", {"reactions": (1, 1, 1, 1)}),
    ("decoy", "Decoy", (0, 1), "none", {"reactions": (1, 1, 0, 0)}),
    ("cartel_ss", "Cartel S+S", (0, 1), "two-way", {"cartel": (0, 1)}),
    ("cartel_sf", "Cartel S+F", (0, 2), "two-way", {"cartel": (0, 2)}),
    ("cartel_ff", "Cartel F+F", (2, 3), "two-way", {"cartel": (2, 3)}),
    ("spy", "Spy", (0, 1), "one-way j->i", {"spy": (0, 1)}),
    ("one_way_cartel", "One-way cartel", (0, 1), "one-way j->i", {"one_way": (0, 1)}),
]


def write_csv(out, name, rows):
    with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def wilson(hits, total):
    z = norm.ppf(.975)
    centre = (hits / total + z * z / (2 * total)) / (1 + z * z / total)
    radius = z * np.sqrt(hits / total * (1 - hits / total) / total + z * z / (4 * total**2)) / (1 + z * z / total)
    return float(centre - radius), float(centre + radius)


def pool(markets):
    return a.Market(**{field: np.concatenate([getattr(x, field) for x in markets])
                       for field in a.Market.__dataclass_fields__})


def analyse(market, state, n_perm, key, blocks=None):
    history = a.public_history(market, state)
    return [m.symmetric_permutation_test(
        market.bids - 2, None if level == "L1" else list(market.costs.T),
        public_state=history, blocks=blocks, n_perm=n_perm, rng=[SEED, *key, k])
        for k, level in enumerate(["L1", "L2"])]


def classify(result, pair):
    i, j = pair
    return m.classify_leaks(result.leak_p_value[i, j], result.leak_p_value[j, i],
                            result.leak_corrected[i, j], result.leak_corrected[j, i])


def record_results(results, name, pair, truth, state, unit, index):
    l1, l2 = results
    row = {"condition": name, "state": state, "unit": unit, "index": index,
           "pair_i": pair[0], "pair_j": pair[1], "truth": truth}
    for level, result in zip(["L1", "L2"], results):
        scores = m.pair_score(result.net_corrected)
        values = np.array([scores[p] for p in PAIRS])
        winners = [p for p in PAIRS if scores[p] >= values.max() - 1e-12]
        candidates = m.calibrated_pairs(result)
        reported = m.detect_calibrated(result)
        row.update({f"{level}_any_candidate": int(bool(candidates)),
                    f"{level}_reported_any": int(reported is not None),
                    f"{level}_reported_target": int(reported == pair),
                    f"{level}_rank_credit": float((pair in winners) / len(winners)),
                    f"{level}_target_score": float(scores[pair]),
                    f"{level}_top_pairs": ";".join(f"{i}-{j}" for i, j in winners)})
    i, j = pair
    significant = l2.leak_p_value <= .05 / 12
    expected = np.zeros((4, 4), bool)
    if truth != "none":
        expected[i, j] = True
    if truth == "two-way":
        expected[j, i] = True
    off_target = significant & ~expected
    row.update({"p_j_to_i": float(l2.leak_p_value[i, j]),
                "p_i_to_j": float(l2.leak_p_value[j, i]),
                "leak_j_to_i": float(l2.leak_corrected[i, j]),
                "leak_i_to_j": float(l2.leak_corrected[j, i]),
                "action": float(l2.action_corrected[i, j]),
                "detect_j_to_i": int(significant[i, j]), "detect_i_to_j": int(significant[j, i]),
                "detect_either": int(significant[i, j] or significant[j, i]),
                "detect_both": int(significant[i, j] and significant[j, i]),
                "leak_family_alarm": int(np.any(off_target)), "classification": classify(l2, pair)})
    # Also report classification after selecting the unique highest net-score pair.
    # A tie remains unclear; there is no arbitrary pair tie-break.
    values = np.array([m.pair_score(l2.net_corrected)[p] for p in PAIRS])
    top = [p for p in PAIRS if m.pair_score(l2.net_corrected)[p] >= values.max() - 1e-12]
    selected = top[0] if len(top) == 1 else None
    row["selected_pair_correct"] = int(selected == pair)
    row["selected_classification"] = classify(l2, selected) if selected else "unclear"
    if selected is None:
        row["selected_truth"] = "unselected"
    elif selected == pair:
        row["selected_truth"] = truth
    else:
        row["selected_truth"] = "none"
    return row


def pair_rows(result, name, state, unit, index):
    return [{"condition": name, "state": state, "unit": unit, "index": index,
             "receiver": i, "source": j, "raw_leak": float(result.leak[i, j]),
             "null_mean": float(result.leak_null_mean[i, j]),
             "corrected_leak": float(result.leak_corrected[i, j]),
             "p_value": float(result.leak_p_value[i, j]),
             "significant_bonferroni12": int(result.leak_p_value[i, j] <= .05 / 12)}
            for i in range(4) for j in range(4) if i != j]


def terms_from_tables(tables):
    """Three Eq. 3 terms from (..., H, Ci, Cj, Bi, Bj) count tables."""
    lead = tables.shape[:-5]
    action = m._cmi_from_counts(tables.reshape(lead + (54, 6, 6)))
    incoming = tables.sum(axis=-1).swapaxes(-1, -2).reshape(lead + (18, 6, 3))
    outgoing = np.moveaxis(tables.sum(axis=-2), -3, -1).reshape(lead + (18, 6, 3))
    return np.stack([action, m._cmi_from_counts(incoming), m._cmi_from_counts(outgoing)], axis=-1)


def fingerprint_tables(market, pair, n_perm, key):
    """Within-market sufficient tables for a blocked symmetric permutation null."""
    i, j = pair
    ci, cj = market.costs[:, i] - (1 if i < 2 else 3), market.costs[:, j] - (1 if j < 2 else 3)
    h = market.last_winning_bid - 2
    joint = h * 9 + ci * 3 + cj
    bids = market.bids[:, [i, j]] - 2
    rng = np.random.default_rng([SEED, 700, *key])
    draws = []
    for cost, bid in zip([ci, cj], bids.T):
        base, perm = m._within_state_permutations(h * 3 + cost, n_perm, rng)
        shuffled = np.empty((n_perm, ROUNDS), int)
        shuffled[:, base] = bid[perm]
        draws.append(shuffled)
    observed = m._counts(bids[:, 0], bids[:, 1], joint, 54, 6).reshape(6, 3, 3, 6, 6)
    null = m._counts(*draws, joint, 54, 6).reshape(n_perm, 6, 3, 3, 6, 6)
    return observed, null


def bootstrap_fingerprint(markets, pair, point, n_boot, n_perm, condition_index):
    """Resample whole markets and recompute pooled plug-in terms and null bias.

    Null tables retain market blocks and own-cost/history strata. Recentring
    at the endpoint estimate removes the independent Monte Carlo offset of
    the smaller bootstrap null; no round bootstrap or averaging of market MI.
    """
    tables = [fingerprint_tables(x, pair, n_perm, [condition_index, k]) for k, x in enumerate(markets)]
    observed = np.array([t[0] for t in tables], dtype=np.int32)
    null = np.array([t[1] for t in tables], dtype=np.int32)
    base = terms_from_tables(observed.sum(0)) - terms_from_tables(null.sum(0)).mean(0)
    rng = np.random.default_rng([SEED, 701, condition_index])
    weights = rng.multinomial(len(markets), np.full(len(markets), 1 / len(markets)), size=n_boot)
    values = []
    for start in range(0, n_boot, 8):
        w = weights[start:start + 8]
        obs = np.tensordot(w, observed, axes=(1, 0))
        permuted = np.tensordot(w, null, axes=(1, 0))
        corrected = terms_from_tables(obs) - terms_from_tables(permuted).mean(axis=1)
        values.extend(corrected - base + point)
    values = np.array(values)
    low, high = np.quantile(values, [.025, .975], axis=0)
    return low, high, values


def rate_summary(rows):
    summaries = []
    fields = ["detect_j_to_i", "detect_i_to_j", "detect_either", "detect_both", "leak_family_alarm",
              "L1_any_candidate", "L2_any_candidate", "L1_reported_target", "L2_reported_target",
              "L1_rank_credit", "L2_rank_credit"]
    for name, _, _, _, _ in CONDITIONS:
        for state in ["exact", "coarse"]:
            for unit in ["market", "pool20"]:
                subset = [r for r in rows if (r["condition"], r["state"], r["unit"]) == (name, state, unit)]
                if not subset:
                    continue
                summary = {"condition": name, "state": state, "unit": unit, "n_units": len(subset)}
                for field in fields:
                    hits = sum(r[field] for r in subset)
                    summary[field] = hits / len(subset)
                    if "credit" not in field:
                        low, high = wilson(hits, len(subset))
                        summary[field + "_hits"] = hits
                        summary[field + "_ci_low"] = low
                        summary[field + "_ci_high"] = high
                summaries.append(summary)
    return summaries


def confusion(rows, unit, selected=False):
    matrix = []
    for name, _, _, truth, _ in CONDITIONS:
        subset = [r for r in rows if r["condition"] == name and r["state"] == "exact" and r["unit"] == unit]
        field = "selected_classification" if selected else "classification"
        matrix.append({"condition": name, "truth": truth, "n_units": len(subset),
                       **{label: sum(r[field] == label for r in subset) for label in CLASSES}})
    return matrix


def plot_results(out, fingerprints, rates):
    plotting.apply_style()
    fig, ax = plt.subplots(figsize=(3.5, 4.5), layout="constrained")
    names = [x[0] for x in CONDITIONS]
    for k, (term, label, color) in enumerate(zip(
            ["action", "leak_j_to_i", "leak_i_to_j"],
            [r"Action $I(B_i;B_j\mid C_i,C_j,H)$", r"Leak $j\to i$", r"Leak $i\to j$"],
            [plotting.BLUE, plotting.ORANGE, plotting.AQUA])):
        selected = [next(r for r in fingerprints if r["condition"] == name and r["term"] == term) for name in names]
        values = np.array([r["estimate"] for r in selected])
        y = np.arange(len(names)) + (k - 1) * .24
        ax.barh(y, values, height=.22, color=color, label=label)
        # CI endpoints can both lie on one side of the point; draw them directly.
        ax.hlines(y, [r["ci_low"] for r in selected], [r["ci_high"] for r in selected], color=plotting.TEXT, linewidth=.7)
        for row, yy in zip(selected, y):
            ax.vlines([row["ci_low"], row["ci_high"]], yy - .06, yy + .06, color=plotting.TEXT, linewidth=.7)
    ax.axvline(0, color=plotting.TEXT_MUTED, linewidth=.6)
    ax.set(yticks=np.arange(len(names)), yticklabels=[x[1] for x in CONDITIONS],
           xlabel="Permutation-corrected information [bits]")
    ax.tick_params(labelsize=7)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(.42, -.14), ncol=1, fontsize=7)
    for extension in ["png", "pdf"]:
        fig.savefig(out / f"fingerprint_v2.{extension}")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 3.0), layout="constrained")
    names = ["honest_iid", "shared_fine", "decoy"]
    for k, (state, level, color, marker) in enumerate([
            ("coarse", "L1", plotting.BLUE, "o"), ("exact", "L1", plotting.BLUE, "s"),
            ("coarse", "L2", plotting.ORANGE, "o"), ("exact", "L2", plotting.ORANGE, "s")]):
        selected = [next(r for r in rates if r["condition"] == name and r["state"] == state and r["unit"] == "market") for name in names]
        field = level + "_any_candidate"
        values = np.array([r[field] for r in selected])
        ax.errorbar(np.arange(3) + (k - 1.5) * .12, values,
                    yerr=[values - [r[field + "_ci_low"] for r in selected],
                          np.array([r[field + "_ci_high"] for r in selected]) - values],
                    fmt=marker, color=color, capsize=2, label=f"{level}, {state}")
    ax.axhline(.05, color=plotting.AQUA, linestyle=":", label="Nominal family level")
    ax.set(xticks=np.arange(3), xticklabels=["Honest IID", "Shared fine history", "Decoy"],
           ylabel="Any candidate / market (95% Wilson CI)", ylim=(-.025, 1.025))
    ax.legend(fontsize=7, loc="upper left", ncol=2)
    fig.savefig(out / "false_alarms_v2.png")
    plt.close(fig)


def main(quick=False):
    out = Path("results/auction_scripted") / ("checks_quick" if quick else "checks_full")
    out.mkdir(parents=True, exist_ok=True)
    config = {"seed": SEED, "quick": quick, "rounds": ROUNDS,
              "primary_markets": 4 if quick else 20, "pool_size": POOL_SIZE,
              "independent_pools": 2 if quick else 20, "n_perm": 239 if quick else 999,
              "bootstrap_markets": 39 if quick else 399, "bootstrap_n_perm": 39 if quick else 99,
              "market_index_start": 40000, "strong_seats": [0, 1],
              "conditions": [{"name": name, "pair": pair, "assigned_flow": truth, "kwargs": kwargs}
                             for name, _, pair, truth, kwargs in CONDITIONS],
              "primary_state": "exact pre-round winning bid H, initial value 4",
              "ablation_state": "three bins: 2-3, 4-5, 6-7",
              "L1": "I(Bi;Bj|H); net ranks all six pairs, min of two net directions",
              "L2": "Eq3, own states (Ci,H); leaks I(Bi;Cj|Ci,H)",
              "null": "shuffle all bidders independently within (own cost,H), or H for L1; block by market in pools",
              "significance": {"family_level": .05, "net_pairs": 6, "leak_directions": 12},
              "classifier": {"significant_p": .05 / 12, "absence_min_p": .2, "absence_max_corrected_bits": .05,
                             "rule": "both significant: two-way; one significant and reverse absent: one-way with direction; both absent: none; otherwise unclear",
                             "justification": "5% family error over 12 directions; .2 guard requires weak null evidence, .05 bits is a fixed small practical margin (paper alpha scale); neither is fitted on these evaluations",
                             "warning": "absence is an operational guard, not a confidence bound or equivalence test; one-way labels cannot infer intent"},
              "pool_rate_design": "independent pools; primary markets are a prefix of the first pool, paired costs/tie streams across conditions",
              "fingerprint_ci": "95% percentile bootstrap of whole primary markets, recomputing pooled MI and blocked null correction; common null draws, recentered to full-permutation point estimate",
              "ranking_ties": "fractional top-rank credit; selected flow unclear on a tie",
              "limitations": ["adaptive history may invalidate exchangeability, even with exact H",
                              "20 primary markets give coarse rates and wide Wilson intervals",
                              "pooled mechanism power is secondary and uses additional independent markets",
                              "assigned two-way protocol does not imply both bids actually respond at every position",
                              "practical absence guard is heuristic; no claim of equivalence or causal intent",
                              "bootstrap null uses fewer permutations than endpoint tests; Monte Carlo CI error remains"]}
    # Persist the full analysis specification before generating any evaluation market.
    (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    started = time.perf_counter()
    rows, directions, raw, fingerprints, boot_rows, pooled_points, occupancy = [], [], [], [], [], [], []
    for condition_index, (name, _, pair, truth, kwargs) in enumerate(CONDITIONS):
        primary = []
        for group in range(config["independent_pools"]):
            markets = [a.play(ROUNDS, seed=SEED, market_index=40000 + group * POOL_SIZE + k, **kwargs)
                       for k in range(POOL_SIZE)]
            if group == 0:
                primary = markets[:config["primary_markets"]]
                for k, market in enumerate(primary):
                    for t in range(ROUNDS):
                        raw.append({"condition": name, "market": k, "round": t,
                                    "history": int(market.last_winning_bid[t]), "winner": int(market.winners[t]),
                                    **{f"cost_{i}": int(market.costs[t, i]) for i in range(4)},
                                    **{f"bid_{i}": int(market.bids[t, i]) for i in range(4)}})
                    for state_index, state in enumerate(["exact", "coarse"]):
                        results = analyse(market, state, config["n_perm"], [condition_index, k, state_index])
                        rows.append(record_results(results, name, pair, truth, state, "market", k))
                        directions.extend(pair_rows(results[1], name, state, "market", k))
                    h = market.last_winning_bid
                    for i, j in [pair]:
                        state = np.column_stack([h, market.costs[:, i], market.costs[:, j]])
                        _, counts = np.unique(state, axis=0, return_counts=True)
                        occupancy.append({"condition": name, "market": k, "joint_states": len(counts),
                                          "min_state_count": int(counts.min()), "median_state_count": float(np.median(counts)),
                                          "fraction_states_below5": float(np.mean(counts < 5))})
            combined = pool(markets)
            results = analyse(combined, "exact", config["n_perm"], [condition_index, 1000 + group],
                              blocks=np.repeat(np.arange(POOL_SIZE), ROUNDS))
            row = record_results(results, name, pair, truth, "exact", "pool20", group)
            rows.append(row)
            directions.extend(pair_rows(results[1], name, "exact", "pool20", group))
            if group == 0:
                # Full run: figure and primary pool share the same 20 markets.
                if len(primary) != POOL_SIZE:
                    fig_results = analyse(pool(primary), "exact", config["n_perm"], [condition_index, 2000],
                                          blocks=np.repeat(np.arange(len(primary)), ROUNDS))
                    fig_row = record_results(fig_results, name, pair, truth, "exact", "fingerprint", 0)
                else:
                    fig_row = row
                pooled_points.append(row)
                point = np.array([fig_row["action"], fig_row["leak_j_to_i"], fig_row["leak_i_to_j"]])
                low, high, values = bootstrap_fingerprint(primary, pair, point, config["bootstrap_markets"],
                                                         config["bootstrap_n_perm"], condition_index)
                for term, estimate, lo, hi in zip(["action", "leak_j_to_i", "leak_i_to_j"], point, low, high):
                    fingerprints.append({"condition": name, "pair_i": pair[0], "pair_j": pair[1], "term": term,
                                         "markets": len(primary), "estimate": float(estimate),
                                         "ci_low": float(lo), "ci_high": float(hi)})
                for b, value in enumerate(values):
                    boot_rows.append({"condition": name, "replicate": b, "action": float(value[0]),
                                      "leak_j_to_i": float(value[1]), "leak_i_to_j": float(value[2])})
            if (group + 1) % 5 == 0 or quick:
                print(f"{name}: {group + 1}/{config['independent_pools']} independent pools complete", flush=True)
        # Keep partial results inspectable during the full run.
        write_csv(out, "market_and_pool_results", rows)
        write_csv(out, "directional_tests", directions)
        print(f"{name}: primary markets and fingerprint complete", flush=True)
    rates = rate_summary(rows)
    market_confusion = confusion(rows, "market")
    pool_confusion = confusion(rows, "pool20")
    selected_confusion = confusion(rows, "market", selected=True)
    for filename, data in [("rates", rates), ("primary_rounds", raw), ("fingerprints_v2", fingerprints),
                           ("fingerprint_bootstrap", boot_rows), ("occupancy", occupancy),
                           ("confusion_market", market_confusion), ("confusion_pool20", pool_confusion),
                           ("confusion_selected_market", selected_confusion)]:
        write_csv(out, filename, data)
    plot_results(out, fingerprints, rates)
    summary = {"mode": "quick" if quick else "full", "config": config,
               "false_alarms": [r for r in rates if r["condition"] in ["honest_iid", "shared_fine", "decoy"] and r["unit"] == "market"],
               "leak_power": [r for r in rates if r["state"] == "exact"],
               "confusion_market": market_confusion, "confusion_pool20": pool_confusion,
               "confusion_selected_market": selected_confusion,
               "first_pool_results": pooled_points, "fingerprint": fingerprints,
               "elapsed_seconds": time.perf_counter() - started}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Artifacts: {out}", flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    main(parser.parse_args().quick)
