"""Round 8: honest adaptive policies under the exact-H permutation null.

Run with .venv/Scripts/python experiments/null_validity.py [--quick]
or --markets 200 --workers 4 for tighter market-level rates. No external calls.
The first 20 markets are also reported separately in a larger run.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import beta

from collusion import measures as m, plotting
from collusion.games import auction as a

SEED = 20261028
ROUNDS = 200
MARKET_START = 80000
CLASSES = ["none", "two-way", "one-way j->i", "one-way i->j", "unclear"]
METRICS = ["L1_any_candidate", "L2_any_candidate", "leak_family_alarm"]


def conditions():
    """Fixed moderate/strong policies, with the strong pair as the decoy."""
    rows = [{"name": "iid", "label": "IID", "kwargs": {}, "positive": False},
            {"name": "last_exact", "label": "Last bid (old)",
             "kwargs": {"reactions": (1, 1, 1, 1)}, "positive": False}]
    policies = [
        ("mean3", "Mean 3, all", ("mean",) * 4, {"history_window": 3}),
        ("mean10", "Mean 10, all", ("mean",) * 4, {"history_window": 10}),
        ("streak", "Own streak, all", ("streak",) * 4, {}),
        ("profit", "Own profit, all", ("profit",) * 4, {}),
        ("rival", "Last rival, ring", ("rival",) * 4, {"rival_seats": (1, 2, 3, 0)}),
        ("drift", "Slow drift, all", ("drift",) * 4, {}),
        ("decoy_mean3", "Mean 3, pair", ("mean", "mean", "none", "none"), {"history_window": 3}),
        ("decoy_mean10", "Mean 10, pair", ("mean", "mean", "none", "none"), {"history_window": 10}),
        ("decoy_rival", "Same rival, pair", ("rival", "rival", "none", "none"),
         {"rival_seats": (2, 2, 0, 0)}),
    ]
    for name, label, policy, extra in policies:
        for strength in [1, 2]:
            rows.append({"name": f"{name}_{strength}", "label": f"{label} x{strength}",
                         "kwargs": {"policies": policy, "policy_strengths": (strength,) * 4, **extra},
                         "positive": False})
    rows.append({"name": "cartel_mean10", "label": "Cartel q=.5 / mean 10",
                 "kwargs": {"cartel": (0, 1), "q": .5, "history_window": 10,
                            "policies": ("none", "none", "mean", "mean")}, "positive": True})
    return rows


def clopper_pearson(hits, total, level=.95):
    """Exact two-sided binomial interval, including zero/all boundaries."""
    tail = (1 - level) / 2
    low = 0.0 if hits == 0 else beta.ppf(tail, hits, total - hits + 1)
    high = 1.0 if hits == total else beta.ppf(1 - tail, hits + 1, total - hits)
    return float(low), float(high)


def classify(result, pair):
    i, j = pair
    return m.classify_leaks(result.leak_p_value[i, j], result.leak_p_value[j, i],
                            result.leak_corrected[i, j], result.leak_corrected[j, i])


def evaluate(task):
    """One independent market, with the Round-4 symmetric null/settings."""
    condition_index, condition, index, n_perm = task
    market = a.play(ROUNDS, seed=SEED, market_index=MARKET_START + index, **condition["kwargs"])
    results = [m.symmetric_permutation_test(
        market.bids - 2, state, public_state=a.public_history(market), n_perm=n_perm,
        rng=[SEED, 800, condition_index, index, level])
        for level, state in enumerate([None, list(market.costs.T)])]
    row = {"condition": condition["name"], "index": index, "positive": condition["positive"]}
    for level, result in zip(["L1", "L2"], results):
        candidates = m.calibrated_pairs(result)
        row.update({f"{level}_any_candidate": int(bool(candidates)),
                    f"{level}_reported_any": int(m.detect_calibrated(result) is not None),
                    f"{level}_reported_target": int(m.detect_calibrated(result) == (0, 1)),
                    f"{level}_target_candidate": int((0, 1) in candidates),
                    f"{level}_target_p": float(result.p_value[0, 1]),
                    f"{level}_target_score": float(m.pair_score(result.net_corrected)[0, 1])})
    l2 = results[1]
    significant = l2.leak_p_value <= .05 / 12
    off_target = significant.copy()
    if condition["positive"]:
        off_target[0, 1] = off_target[1, 0] = False
    row.update({"leak_family_alarm": int(significant.any()),
                "off_target_leak_alarm": int(off_target.any()),
                "detect_either": int(significant[0, 1] or significant[1, 0]),
                "detect_both": int(significant[0, 1] and significant[1, 0]),
                "classification": classify(l2, (0, 1)),
                "honest_pair_classification": classify(l2, (2, 3)),
                "action_corrected": float(l2.action_corrected[0, 1]),
                "incoming_corrected": float(l2.leak_corrected[0, 1]),
                "outgoing_corrected": float(l2.leak_corrected[1, 0]),
                "compliant_rounds": int(market.compliant.sum()),
                "winning_bid_mean": float(market.bids[np.arange(ROUNDS), market.winners].mean()),
                "bid_boundary_fraction": float(np.isin(market.bids, [2, 7]).mean())})
    # Compare bids with the original IID policy using identical own-cost/noise draws.
    noise = np.column_stack([np.random.default_rng([SEED, MARKET_START + index, 10 + i]).integers(0, 2, ROUNDS)
                             for i in range(4)])
    honest = [i for i in range(4) if not condition["positive"] or i not in (0, 1)]
    delta = market.bids[:, honest] - a.honest_bid(market.costs[:, honest], noise[:, honest])
    row["mean_abs_bid_change"] = float(np.abs(delta).mean())
    row["fraction_bids_changed"] = float((delta != 0).mean())
    directions = [{"condition": condition["name"], "index": index, "receiver": i, "source": j,
                   "p_value": float(l2.leak_p_value[i, j]),
                   "leak_corrected": float(l2.leak_corrected[i, j]),
                   "action_corrected": float(l2.action_corrected[i, j]),
                   "significant": int(significant[i, j])}
                  for i in range(4) for j in range(4) if i != j]
    return row, directions


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows, variants):
    rates, classes, effects = [], [], []
    endpoints = METRICS + ["L1_reported_any", "L2_reported_any", "L1_reported_target", "L2_reported_target",
                           "detect_either", "detect_both", "off_target_leak_alarm"]
    n = max(r["index"] for r in rows) + 1
    for count in sorted({min(20, n), n}):
        for variant in variants:
            subset = [r for r in rows if r["condition"] == variant["name"] and r["index"] < count]
            base = {"condition": variant["name"], "markets": count, "positive": variant["positive"]}
            for metric in endpoints:
                hits = sum(r[metric] for r in subset)
                low, high = clopper_pearson(hits, count)
                rates.append({**base, "statistic": metric, "hits": hits, "rate": hits / count,
                              "ci_low": low, "ci_high": high,
                              "lower_exceeds_05": low > .05})
            for pair in ["classification", "honest_pair_classification"]:
                for label in CLASSES:
                    hits = sum(r[pair] == label for r in subset)
                    low, high = clopper_pearson(hits, count)
                    classes.append({**base, "pair": "0-1" if pair == "classification" else "2-3",
                                    "label": label, "hits": hits, "rate": hits / count,
                                    "ci_low": low, "ci_high": high})
            fields = ["action_corrected", "incoming_corrected", "outgoing_corrected",
                      "mean_abs_bid_change", "fraction_bids_changed", "bid_boundary_fraction",
                      "winning_bid_mean", "compliant_rounds"]
            effects.append({**base, **{field: float(np.mean([r[field] for r in subset])) for field in fields}})
    return rates, classes, effects


def plot_rates(out, rates, variants, count):
    """One compact interval plot, with a shared axis and 5% reference."""
    plotting.apply_style()
    nulls = [v for v in variants if not v["positive"]]
    fig, ax = plt.subplots(figsize=(8, 6.6), layout="constrained")
    for offset, metric, label, color in zip([-.22, 0, .22], METRICS,
                                          ["L1 calibrated", "L2 Eq. 3 calibrated", "Leak family (12)"],
                                          [plotting.BLUE, plotting.ORANGE, plotting.AQUA]):
        selected = [next(r for r in rates if r["condition"] == v["name"] and
                         r["markets"] == count and r["statistic"] == metric) for v in nulls]
        point = np.array([r["rate"] for r in selected]) * 100
        low = point - np.array([r["ci_low"] for r in selected]) * 100
        high = np.array([r["ci_high"] for r in selected]) * 100 - point
        ax.errorbar(point, np.arange(len(nulls)) + offset, xerr=[low, high], fmt="o",
                    capsize=2, color=color, label=label, markersize=3, elinewidth=.8)
    ax.axvline(5, color=plotting.TEXT_MUTED, linestyle="--", linewidth=1, label="5% nominal")
    ax.set(yticks=np.arange(len(nulls)), yticklabels=[v["label"] for v in nulls],
           xlabel="Markets with any false alarm (%) / exact 95% intervals", xlim=(-1, 101),
           title=f"Exact last winning bid H; {count} markets x 200 rounds per variant")
    ax.invert_yaxis()
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.10), ncol=2, fontsize=8)
    fig.savefig(out / "false_alarm_rates.png")
    fig.savefig(out / "false_alarm_rates.pdf")
    plt.close(fig)


def report(out, rates, classes, effects, variants, config, elapsed):
    """Keep both the primary and extension tables reviewable alongside CSVs."""
    lines = ["# Round 8: adaptive honest-bidder null validity", "",
             f"Runtime: {elapsed:.2f} seconds. Seed {SEED}; {config['n_perm']} symmetric permutations; "
             f"{config['markets']} markets per condition x 200 rounds. Workers: {config['workers']}.", "",
             "H is the exact pre-round winning bid (initial 4). L1/L2 count any calibrated candidate "
             "(Bonferroni .05/6 and mutual positive corrected net influence); unique reports are also in rates.csv. "
             "Leak family means any of 12 directions at .05/12. Intervals are exact, pointwise 95% "
             "Clopper-Pearson intervals across independent markets; conditions use paired cost/noise seeds.", "",
             "Strength 1 is moderate; strength 2 doubles it. Mean-k adds s*(past mean - 4), using available "
             "completed rounds, initially zero. Rival adds s*(fixed rival's last bid - 4), initially zero. "
             "These use the same coefficient as the existing shared-history reaction (s=1). "
             "Streak adds s*(signed consecutive wins/losses capped at 3)/3. Profit adds "
             "s*clip((own cumulative profit - .5*t)/20,-1,1). Drift adds s*clip(2*t/200-1,-1,1). "
             "All are added before nearest-even integer rounding and clipping to [2,7]. "
             "All-firm policies affect four firms; pair policies affect only strong seats 0/1. "
             "Rival ring follows 1/2/3/0; same-rival pair both follow seat 2. "
             "No honest bid observes a rival's current cost. The positive control has strong cartel 0/1, "
             "q=.5, and honest fringe 2/3 using mean-10 at strength 1; cartel best bids integrate the "
             "fringe's actual pre-round policy.", ""]
    for count in sorted({r["markets"] for r in rates}):
        lines.extend([f"## {count} markets", "", "Counts / markets [95% CI in percent]. "
                      "In the positive row these are detections, not false alarms.", "",
                      "| Variant | L1 | L2 | Leak family | Pair 0/1 labels: none / two-way / j->i / i->j / unclear |",
                      "|---|---|---|---|---|"])
        for variant in variants:
            cells = []
            for metric in METRICS:
                r = next(r for r in rates if r["condition"] == variant["name"] and
                         r["markets"] == count and r["statistic"] == metric)
                cells.append(f"{r['hits']}/{count} [{100*r['ci_low']:.1f}, {100*r['ci_high']:.1f}]")
            labels = [next(r["hits"] for r in classes if r["condition"] == variant["name"] and
                           r["markets"] == count and r["pair"] == "0-1" and r["label"] == label)
                      for label in CLASSES]
            lines.append(f"| {variant['label']} | " + " | ".join(cells) + " | " +
                         " / ".join(map(str, labels)) + " |")
    count = config["markets"]
    lines.extend(["", "## Positive control", "",
                  "The following endpoints test the actual cartel 0/1; the off-target family excludes "
                  "its two true directions. Counts and exact 95% intervals:", "",
                  "| Markets | Endpoint | Hits | Rate (%) | 95% CI (%) |", "|---|---|---|---|---|"])
    for r in rates:
        if r["positive"] and r["statistic"] in ["L1_reported_target", "L2_reported_target",
                                                "detect_either", "detect_both", "off_target_leak_alarm"]:
            lines.append(f"| {r['markets']} | {r['statistic']} | {r['hits']} | {100*r['rate']:.1f} | "
                         f"[{100*r['ci_low']:.1f}, {100*r['ci_high']:.1f}] |")
    lines.extend(["", "The honest fringe pair 2/3 has these classification counts "
                  "(none / two-way / j->i / i->j / unclear):"])
    for n in sorted({r["markets"] for r in classes}):
        labels = [next(r["hits"] for r in classes if r["positive"] and r["markets"] == n and
                       r["pair"] == "2-3" and r["label"] == label) for label in CLASSES]
        lines.append(f"- {n} markets: " + " / ".join(map(str, labels)))
    lines.extend(["", "## Observed inflation", "",
                  "A lower 95% interval bound above 5% is evidence of inflation for that row, "
                  "without adjustment across the many variants/endpoints. A bound below 5% does not prove validity."])
    for metric in METRICS:
        failures = [r["condition"] for r in rates if not r["positive"] and r["markets"] == count and
                    r["statistic"] == metric and r["lower_exceeds_05"]]
        lines.append(f"- {metric}: " + (", ".join(failures) if failures else "no lower bound above 5%"))
    lines.extend(["", "## Corrected target action term and realised bid changes", "",
                  "Means across markets; changes compare the actual honest bids with the original IID policy "
                  "using identical costs/noise. Positive control changes refer only to its honest fringe.", "",
                  "| Variant | Action (bits) | Incoming leak (bits) | Outgoing leak (bits) | Mean absolute bid change | Bids changed (%) | Boundary bids (%) |",
                  "|---|---|---|---|---|---|---|"])
    for e in effects:
        if e["markets"] == count:
            lines.append(f"| {e['condition']} | {e['action_corrected']:.4f} | {e['incoming_corrected']:.4f} | "
                         f"{e['outgoing_corrected']:.4f} | {e['mean_abs_bid_change']:.3f} | "
                         f"{100*e['fraction_bids_changed']:.1f} | {100*e['bid_boundary_fraction']:.1f} |")
    lines.extend(["", "## Limitations", "",
                  "Scripted stress tests cannot establish exchangeability for arbitrary LLM policies. "
                  "Current costs are independently redrawn, so honest history-only policies have no population "
                  "current-cost information flow; trajectory permutation p-values still need not be valid. "
                  "Adaptive H depends on earlier bids and costs. Even a clean leak result is empirical, not a "
                  "finite-sample guarantee. Saturation at bid bounds can suppress variation, especially for "
                  "strong reactions. Like the existing shared-history policy, these policies can bid below "
                  "own cost; they are dependence stress tests, not optimal-bidding models. "
                  "Absence labels use the existing p>=.2 and corrected leak<=.05 bits guard, "
                  "which is not an equivalence test. Label intervals, unique reports, all directional p-values "
                  "and effects are in the CSVs. A two-way label alone is not proof of collusion.", ""])
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main(quick=False, markets=None, workers=1):
    started = time.perf_counter()
    count = markets if markets is not None else (4 if quick else 20)
    if count < 1 or workers < 1:
        raise ValueError("positive market and worker counts required")
    variants = conditions()
    out = Path("results/null_validity") / ("quick" if quick else f"markets_{count}")
    out.mkdir(parents=True, exist_ok=True)
    config = {"seed": SEED, "rounds": ROUNDS, "market_start": MARKET_START, "markets": count,
              "n_perm": 239 if quick else 999, "workers": workers, "quick": quick,
              "conditions": variants, "state": "exact", "pair_level": .05 / 6,
              "direction_level": .05 / 12, "absence_p": .2, "absence_bits": .05}
    (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    tasks = [(k, v, index, config["n_perm"]) for k, v in enumerate(variants) for index in range(count)]
    rows, directions = [], []
    executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        evaluated = executor.map(evaluate, tasks) if executor else map(evaluate, tasks)
        for row, detail in evaluated:
            rows.append(row)
            directions.extend(detail)
            if row["index"] == count - 1:
                write_csv(out / "markets.csv", rows)
                write_csv(out / "directions.csv", directions)
                print(f"{row['condition']}: {count} markets complete ({time.perf_counter()-started:.1f}s)", flush=True)
    finally:
        if executor:
            executor.shutdown()
    rates, classes, effects = summarize(rows, variants)
    for name, data in [("rates", rates), ("classifications", classes), ("effects", effects)]:
        write_csv(out / f"{name}.csv", data)
    plot_rates(out, rates, variants, count)
    elapsed = time.perf_counter() - started
    summary = {"config": config, "elapsed_seconds": elapsed,
               "inflation": [r for r in rates if not r["positive"] and r["lower_exceeds_05"] and
                             r["statistic"] in METRICS],
               "positive": [r for r in rates if r["positive"]]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report(out, rates, classes, effects, variants, config, elapsed)
    print(f"Finished in {elapsed:.2f}s. Artifacts: {out}", flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--markets", type=int)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    main(args.quick, args.markets, args.workers)
