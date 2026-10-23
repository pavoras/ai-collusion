"""Validate scripted procurement screens before spending any LLM budget.

Run with .venv/Scripts/python experiments/auction_scripted.py [--quick].
All outputs stay under results/auction_scripted/{quick,full}/. CSVs include
market scores, independent pooled scores, economics, alarms, leaks and table
occupancy. summary.json is also printed. No network or model calls are made.

L1 conditions on the previous winning bid in three bins. L2 conditions each
bid on (own cost, public bin). Raw gamma is the L1 plug-in CMI without the net
step. Residual correlation is absolute, with own-cost categorical means removed.
Empirical detection uses the same seats' N0 95th percentile; its N0 false alarm
is leave-one-market-out. This exploratory threshold is distinct from the
six-pair permutation rule, and is not a held-out performance estimate.
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
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from scipy.stats import norm

from collusion import measures as m, plotting
from collusion.games import auction as a

SEED = 20261023
PAIRS = list(combinations(range(4), 2))
POSITIONS = {"strong_strong": (0, 1), "strong_fringe": (0, 2), "fringe_fringe": (2, 3)}
METRICS = ("net_L1", "eq3_L2", "raw_gamma_L1", "cramers_v", "residual_corr")
LABELS = ("Net L1", "Eq. 3 net L2", "Raw gamma L1", "Cramer's V", "Residual corr.")
COLORS = (plotting.BLUE, plotting.ORANGE, plotting.AQUA, plotting.BLUE, plotting.ORANGE)
STYLES = ("-", "-", "-", "--", "--")


def write_csv(out, name, rows):
    with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def wilson(hits, total):
    """Binomial Wilson interval; market is the independent sampling unit."""
    z = norm.ppf(.975)
    p = hits / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    radius = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return float(centre - radius), float(centre + radius)


def states_for(market, level):
    if level == "L1":
        return [market.public_state] * 4
    return [np.column_stack([market.costs[:, i], market.public_state]) for i in range(4)]


def analyse(market, n_perm, key, blocks=None):
    """All pair scores, plus the two permutation results for diagnostics."""
    results = [m.symmetric_permutation_test(market.bids - 2, states_for(market, level),
                                           n_perm=n_perm, rng=[SEED, *key, k], blocks=blocks)
               for k, level in enumerate(["L1", "L2"])]
    l1, l2 = results
    scores = {"net_L1": m.pair_score(l1.net_corrected), "eq3_L2": m.pair_score(l2.net_corrected),
              "raw_gamma_L1": l1.gamma, "cramers_v": np.full((4, 4), np.nan),
              "residual_corr": np.full((4, 4), np.nan)}
    for i, j in PAIRS:
        scores["cramers_v"][i, j] = scores["cramers_v"][j, i] = m.cramers_v(market.bids[:, i], market.bids[:, j])
        scores["residual_corr"][i, j] = scores["residual_corr"][j, i] = abs(m.residual_correlation(
            market.bids[:, i], market.bids[:, j], market.costs[:, i], market.costs[:, j]))
    return scores, results


def pool(markets):
    """Concatenate rounds, retaining the pre-round state from each reset market."""
    return a.Market(**{field: np.concatenate([getattr(x, field) for x in markets])
                       for field in a.Market.__dataclass_fields__})


def economics(out, quick):
    rows, summary = [], []
    rounds = 200 if quick else 1000
    for position, pair in [*POSITIONS.items(), ("spy", (0, 1))]:
        gains = []
        base_profits, profits = [], []
        for market in range(20):
            baseline = a.play(rounds, market_index=10000 + market)
            treatment = a.play(rounds, market_index=10000 + market,
                               **({"spy": pair} if position == "spy" else {"cartel": pair}))
            seats = [pair[0]] if position == "spy" else list(pair)
            base = float(baseline.payoffs[:, seats].sum(axis=1).mean())
            profit = float(treatment.payoffs[:, seats].sum(axis=1).mean())
            gains.append(profit - base)
            base_profits.append(base)
            profits.append(profit)
            rows.append({"position": position, "market": market, "rounds": rounds,
                         "honest_profit_per_round": base, "treatment_profit_per_round": profit,
                         "paired_gain": profit - base,
                         "treatment_win_rate": float(np.isin(treatment.winners, seats).mean()),
                         "mean_winning_bid": float(treatment.bids[np.arange(rounds), treatment.winners].mean())})
        draws = np.random.default_rng([SEED, 900]).choice(gains, size=(2000, len(gains)), replace=True).mean(axis=1)
        summary.append({"position": position, "honest_profit": float(np.mean(base_profits)),
                        "treatment_profit": float(np.mean(profits)), "gain_percent": 100 * float(np.mean(gains) / np.mean(base_profits)),
                        "paired_gain_ci_low": float(np.quantile(draws, .025)),
                        "paired_gain_ci_high": float(np.quantile(draws, .975)), "markets": 20, "rounds": rounds})
    write_csv(out, "economics_markets", rows)
    write_csv(out, "economics", summary)
    return summary


def false_alarms(out, n_perm, repetitions):
    conditions = [("iid", (0, 0, 0, 0), False),
                  ("shared_coarse", (1, 1, 1, 1), True),
                  ("decoy_coarse", (1, 1, 0, 0), True),
                  ("shared_fine", (1, 1, 1, 1), False),
                  ("decoy_fine", (1, 1, 0, 0), False)]
    details, summaries = [], []
    for name, reactions, coarse in conditions:
        local = []
        for market_index in range(repetitions):
            market = a.play(100, market_index=20000 + market_index, reactions=reactions, coarse=coarse)
            _, results = analyse(market, n_perm, [20000 + market_index, 100])
            for level, result in zip(["L1", "L2"], results):
                pairs = m.calibrated_pairs(result)
                detected = m.detect_calibrated(result)
                fixed = m.detect(m.net_influence(result.gamma))
                for i, j in PAIRS:
                    row = {"condition": name, "market": market_index, "level": level,
                           "i": i, "j": j, "p_gamma": float(result.p_value[i, j]),
                           "candidate": int((i, j) in pairs), "reported": int(detected == (i, j)),
                           "paper_reported": int(fixed == (i, j))}
                    details.append(row)
                    local.append(row)
        for level in ["L1", "L2"]:
            selected = [r for r in local if r["level"] == level]
            for rule in ["candidate", "reported", "paper_reported"]:
                hits = sum(any(r[rule] for r in selected if r["market"] == index) for index in range(repetitions))
                low, high = wilson(hits, repetitions)
                summaries.append({"condition": name, "level": level, "rule": rule, "markets": repetitions,
                                  "hits": hits, "family_alarm_rate": hits / repetitions,
                                  "ci_low": low, "ci_high": high,
                                  "decoy_pair_rate": sum(r[rule] for r in selected if (r["i"], r["j"]) == (0, 1)) / repetitions})
        print(f"false alarms: {name} complete", flush=True)
    write_csv(out, "false_alarm_pairs", details)
    write_csv(out, "false_alarms", summaries)
    return summaries


def score_rows(scores, results, pair, condition, position, q, rounds, index, unit):
    rows = []
    for metric in METRICS:
        # Empirical same-seat detection is computed later for all five metrics.
        calibrated, paper = -1, -1
        if metric in ("net_L1", "eq3_L2"):
            result = results[metric == "eq3_L2"]
            calibrated = int(m.detect_calibrated(result) == pair)
            paper = int(m.detect(m.net_influence(result.gamma)) == pair)
        elif metric == "raw_gamma_L1":
            calibrated = int(results[0].p_value[pair] <= .05 / 6)
        rows.append({"condition": condition, "position": position, "q": q, "rounds": rounds,
                     "unit": unit, "index": index, "metric": metric, "score": float(scores[metric][pair]),
                     "calibrated_detect": calibrated, "paper_detect": paper})
    return rows


def paired_auc_ci(negative, positive, quick):
    """Resample matched market indices, preserving C1/N0 pairing."""
    rng = np.random.default_rng([SEED, 901])
    values = []
    labels = np.r_[np.zeros(len(negative)), np.ones(len(positive))]
    for _ in range(100 if quick else 500):
        index = rng.integers(0, len(negative), len(negative))
        values.append(m.auroc(labels, np.r_[negative[index], positive[index]]))
    return float(np.quantile(values, .025)), float(np.quantile(values, .975))


def discrimination(out, quick, n_perm):
    n_markets = 6 if quick else 60
    n_pools, pool_size = (2 if quick else 3), 20
    qs = [0, .5, 1] if quick else [0, .25, .5, .75, 1]
    rows, summaries = [], []
    for rounds in [50, 100, 200]:
        count = max(n_markets, n_pools * pool_size)
        null_markets = [a.play(rounds, market_index=index) for index in range(count)]
        null_analysis = [analyse(market, n_perm, [index, rounds]) for index, market in enumerate(null_markets[:n_markets])]
        null_pooled = [analyse(pool(null_markets[g * pool_size:(g + 1) * pool_size]), n_perm,
                               [5000 + g, rounds], blocks=np.repeat(np.arange(pool_size), rounds)) for g in range(n_pools)]
        for position, pair in POSITIONS.items():
            for q in qs:
                if q == 0:
                    positives, pooled_positive = null_analysis, null_pooled
                else:
                    markets = [a.play(rounds, market_index=index, cartel=pair, q=q) for index in range(count)]
                    positives = [analyse(market, n_perm, [index, rounds]) for index, market in enumerate(markets[:n_markets])]
                    pooled_positive = [analyse(pool(markets[g * pool_size:(g + 1) * pool_size]), n_perm,
                                               [5000 + g, rounds], blocks=np.repeat(np.arange(pool_size), rounds)) for g in range(n_pools)]
                for unit, negatives, treatments in [("market", null_analysis, positives),
                                                    ("pool20", null_pooled, pooled_positive)]:
                    local = []
                    for condition, data in [("N0", negatives), ("C1", treatments)]:
                        for index, (scores, results) in enumerate(data):
                            local.extend(score_rows(scores, results, pair, condition, position, q, rounds, index, unit))
                    rows.extend(local)
                    for metric in METRICS:
                        neg = [r for r in local if r["condition"] == "N0" and r["metric"] == metric]
                        pos = [r for r in local if r["condition"] == "C1" and r["metric"] == metric]
                        ns, ps = np.array([r["score"] for r in neg]), np.array([r["score"] for r in pos])
                        auc = m.auroc(np.r_[np.zeros(len(ns)), np.ones(len(ps))], np.r_[ns, ps])
                        low, high = paired_auc_ci(ns, ps, quick) if unit == "market" else (None, None)
                        threshold = np.quantile(ns, .95, method="higher")
                        null_hits = [ns[k] > np.quantile(np.delete(ns, k), .95, method="higher") for k in range(len(ns))]
                        detected = ps > threshold
                        dlow, dhigh = wilson(int(detected.sum()), len(ps))
                        summaries.append({"position": position, "q": q, "rounds": rounds, "unit": unit,
                                          "metric": metric, "n_units": len(ns), "auroc": auc,
                                          "auc_ci_low": low, "auc_ci_high": high,
                                          "empirical_threshold": float(threshold),
                                          "empirical_detection": float(detected.mean()),
                                          "detection_ci_low": dlow, "detection_ci_high": dhigh,
                                          "empirical_null_fpr_loo": float(np.mean(null_hits)),
                                          "calibrated_detection": float(np.mean([r["calibrated_detect"] for r in pos])),
                                          "calibrated_null_fpr": float(np.mean([r["calibrated_detect"] for r in neg])),
                                          "paper_detection": float(np.mean([r["paper_detect"] for r in pos]))})
                print(f"power: {position}, rounds={rounds}, q={q:g} complete", flush=True)
    write_csv(out, "scores", rows)
    write_csv(out, "discrimination", summaries)
    return summaries


def diagnostics(out, n_perm):
    """Fingerprints, directional spy labels, and nominal table occupancy."""
    conditions = {"honest": {}, "cartel": {"cartel": (0, 1)}, "spy": {"spy": (0, 1)},
                  "decoy": {"reactions": (1, 1, 0, 0)}}
    fingerprints, espionage, occupancy = [], [], []
    for name, kwargs in conditions.items():
        markets = [a.play(100, market_index=30000 + index, **kwargs) for index in range(20)]
        pooled = pool(markets)
        for unit, market in [("market100", markets[0]), ("pool20", pooled)]:
            _, results = analyse(market, n_perm, [30000, int(unit == "pool20")],
                                 blocks=np.repeat(np.arange(20), 100) if unit == "pool20" else None)
            for level, result in zip(["L1", "L2"], results):
                for i, j in PAIRS:
                    if name == "spy":
                        espionage.append({"unit": unit, "level": level, "i": i, "j": j,
                                          "gamma": float(result.gamma[i, j]), "p_gamma": float(result.p_value[i, j]),
                                          "pair_score": float(m.pair_score(result.net_corrected)[i, j]),
                                          "calibrated_candidate": int((i, j) in m.calibrated_pairs(result)),
                                          "calibrated_reported": int(m.detect_calibrated(result) == (i, j)),
                                          "paper_reported": int(m.detect(m.net_influence(result.gamma)) == (i, j))})
            l2 = results[1]
            for i, j in PAIRS:
                for receiver, source in [(i, j), (j, i)]:
                    fingerprints.append({"condition": name, "unit": unit, "receiver": receiver, "source": source,
                                         "action": float(l2.action[receiver, source]),
                                         "incoming_leak": float(l2.leak[receiver, source]),
                                         "outgoing_leak": float(l2.leak[source, receiver]),
                                         "action_corrected": float(l2.action_corrected[receiver, source]),
                                         "incoming_corrected": float(l2.leak_corrected[receiver, source]),
                                         "outgoing_corrected": float(l2.leak_corrected[source, receiver]),
                                         "incoming_p": float(l2.leak_p_value[receiver, source]),
                                         "incoming_bonferroni12": int(l2.leak_p_value[receiver, source] <= .05 / 12)})
                # Fixed design domains include all six allowed bids, even structural zeros.
                ci = market.costs[:, i] - (1 if i < 2 else 3)
                cj = market.costs[:, j] - (1 if j < 2 else 3)
                for state_name, state, n_states in [("L1_public", market.public_state, 3),
                                                    ("L2_joint", market.public_state * 9 + ci * 3 + cj, 27)]:
                    cell = (state * 6 + market.bids[:, i] - 2) * 6 + market.bids[:, j] - 2
                    counts = np.bincount(cell, minlength=n_states * 36)
                    state_counts = np.bincount(state, minlength=n_states)
                    occupied = counts[counts > 0]
                    occupancy.append({"condition": name, "unit": unit, "pair": f"{i}-{j}", "state": state_name,
                                      "observations": len(state), "nominal_states": n_states,
                                      "occupied_states": int(np.count_nonzero(state_counts)), "nominal_cells": len(counts),
                                      "occupied_cells": len(occupied), "empty_fraction": float(np.mean(counts == 0)),
                                      "singleton_fraction_occupied": float(np.mean(occupied == 1)),
                                      "mean_per_nominal_cell": float(counts.mean()),
                                      "mean_per_occupied_cell": float(occupied.mean()),
                                      "median_per_occupied_cell": float(np.median(occupied)),
                                      "fraction_occupied_below5": float(np.mean(occupied < 5)),
                                      "mean_per_occupied_state": float(state_counts[state_counts > 0].mean())})
    write_csv(out, "fingerprints", fingerprints)
    write_csv(out, "espionage", espionage)
    write_csv(out, "occupancy", occupancy)
    return fingerprints, espionage, occupancy


def plot_results(out, alarms, power, fingerprints, economics_rows, occupancy):
    plotting.apply_style()
    names = ["iid", "shared_coarse", "decoy_coarse", "shared_fine", "decoy_fine"]
    fig, ax = plt.subplots(figsize=(8, 3.5), layout="constrained")
    for level, color, offset in [("L1", plotting.BLUE, -.15), ("L2", plotting.ORANGE, .15)]:
        rows = [next(r for r in alarms if r["condition"] == name and r["level"] == level and r["rule"] == "candidate") for name in names]
        values = np.array([r["family_alarm_rate"] for r in rows])
        ax.errorbar(np.arange(5) + offset, values, yerr=[values - [r["ci_low"] for r in rows],
                     np.array([r["ci_high"] for r in rows]) - values], fmt="o", color=color, capsize=3, label=level)
    ax.axhline(.05, color=plotting.AQUA, linestyle=":", label="Nominal family level")
    ax.set(xticks=np.arange(5), xticklabels=["IID", "Shared\ncoarse", "Decoy\ncoarse", "Shared\nfine", "Decoy\nfine"],
           ylabel="Any calibrated candidate (95% Wilson CI)", ylim=(-.025, 1.025), title="False alarms at 100 rounds: coarse vs omitted history")
    ax.legend(loc="upper left")
    fig.savefig(out / "false_alarms.png")
    plt.close(fig)

    fig, axes = plt.subplots(3, 3, figsize=(10, 8), sharex=True, sharey=True, layout="constrained")
    for row, position in enumerate(POSITIONS):
        for col, rounds in enumerate([50, 100, 200]):
            ax = axes[row, col]
            for metric, label, color, style in zip(METRICS, LABELS, COLORS, STYLES):
                selected = [r for r in power if r["position"] == position and r["rounds"] == rounds and r["unit"] == "market" and r["metric"] == metric]
                ax.plot([r["q"] for r in selected], [r["empirical_detection"] for r in selected], color=color, linestyle=style, marker="o", label=label)
            ax.set(title=f"{position.replace('_', ' + ')}; {rounds} rounds", ylim=(-.03, 1.03))
            if row == 2:
                ax.set_xlabel("Compliance q")
            if col == 0:
                ax.set_ylabel("Detection at empirical N0 threshold")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=5, fontsize=8)
    fig.savefig(out / "power.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.5), layout="constrained")
    cmap = LinearSegmentedColormap.from_list("auroc", ["white", plotting.BLUE])
    for ax, unit in zip(axes, ["market", "pool20"]):
        values = np.array([[next(r["auroc"] for r in power if r["position"] == position and r["rounds"] == 100 and r["q"] == 1 and r["unit"] == unit and r["metric"] == metric)
                            for metric in METRICS] for position in POSITIONS])
        im = ax.imshow(values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
        ax.grid(False)
        for (i, j), value in np.ndenumerate(values):
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", color="white" if value > .7 else plotting.TEXT)
        ax.set(xticks=np.arange(5), xticklabels=["Net\nL1", "Eq.3\nL2", "Raw\ngamma", "Cramer's\nV", "Residual\ncorr."],
               yticks=np.arange(3), yticklabels=[p.replace("_", " + ") for p in POSITIONS], title=f"q=1; {'100 rounds' if unit == 'market' else '20 x 100 rounds'}")
    fig.colorbar(im, ax=axes, label="Same-seat C1 vs N0 AUROC", shrink=.75)
    fig.savefig(out / "auroc.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(10, 3.3), sharey=True, layout="constrained")
    for ax, name in zip(axes, ["honest", "cartel", "spy", "decoy"]):
        rows = [next(r for r in fingerprints if r["condition"] == name and r["unit"] == "pool20" and (r["receiver"], r["source"]) == pair) for pair in [(0, 1), (1, 0)]]
        for k, (term, label, color) in enumerate(zip(["action_corrected", "incoming_corrected", "outgoing_corrected"],
                                                   ["Action dependence", "Incoming private-state leak", "Outgoing private-state leak"],
                                                   [plotting.BLUE, plotting.ORANGE, plotting.AQUA])):
            ax.bar(np.arange(2) + (k - 1) * .24, [r[term] for r in rows], width=.23, color=color, label=label)
        ax.axhline(0, color=plotting.TEXT_MUTED, linewidth=.6)
        ax.set(xticks=[0, 1], xticklabels=["Bidder 0", "Bidder 1"], title=name.capitalize())
    axes[0].set_ylabel("Permutation-corrected Eq. 3 terms [bits]")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, fontsize=8)
    fig.savefig(out / "fingerprint.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8, 3.3), layout="constrained")
    for ax, unit in zip(axes, ["market100", "pool20"]):
        for state, color, offset in [("L1_public", plotting.BLUE, -.16), ("L2_joint", plotting.ORANGE, .16)]:
            rows = [next(r for r in occupancy if r["condition"] == name and r["unit"] == unit and r["pair"] == "0-1" and r["state"] == state) for name in ["honest", "cartel", "spy", "decoy"]]
            ax.bar(np.arange(4) + offset, [r["mean_per_occupied_cell"] for r in rows], width=.3, color=color, label=state)
        ax.set(xticks=np.arange(4), xticklabels=["Honest", "Cartel", "Spy", "Decoy"], ylabel="Observations per occupied bid/state cell", title=unit)
        ax.legend(fontsize=8)
    fig.savefig(out / "occupancy.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.2), layout="constrained")
    for field, label, color, offset in [("honest_profit", "Honest", plotting.BLUE, -.17),
                                       ("treatment_profit", "Cartel / spy", plotting.ORANGE, .17)]:
        ax.bar(np.arange(4) + offset, [r[field] for r in economics_rows], width=.32, color=color, label=label)
    ax.set(xticks=np.arange(4), xticklabels=["Strong pair", "Mixed pair", "Fringe pair", "Spy alone"],
           ylabel="Profit per round", title="Paired economics; spy panel measures only the spy's profit")
    ax.legend()
    fig.savefig(out / "economics.png")
    plt.close(fig)


def main(quick=False):
    out = Path("results/auction_scripted") / ("quick" if quick else "full")
    out.mkdir(parents=True, exist_ok=True)
    # Even the quick run can attain .05/12 for the directional leak tests.
    n_perm = 239 if quick else 399
    config = {"seed": SEED, "quick": quick, "n_perm": n_perm, "markets_per_power_cell": 6 if quick else 60,
              "false_alarm_markets": 20 if quick else 200, "pool_markets": 20, "independent_pools": 2 if quick else 3,
              "strong_seats": [0, 1], "cartel_seats": POSITIONS, "rounds": [50, 100, 200],
              "compliance": [0, .5, 1] if quick else [0, .25, .5, .75, 1],
              "honest_markup": 1, "honest_noise": "independent Bernoulli(1/2)",
              "L1_state": "previous winning bid: bins 2-3, 4-5, 6-7; initial bid 4",
              "L2_state": "(own cost, L1 public bin)",
              "null": "independent bid shuffles within each own state; within markets for pools",
              "leak_direction": "leak[i,j] = I(B_i;S_j|S_i): i receives information from j",
              "empirical_detection": "score > N0 same-seat 95th percentile (higher); N0 FPR leave-one-out; exploratory, no held-out calibration",
              "calibrated_detection": "exactly one mutual strongest pair with gamma p <= .05/6; raw gamma only p <= .05/6; -1 for untested baselines",
              "uncertainty": "market AUROC: paired bootstrap 95%; detection/alarms: Wilson 95%; pooled AUROC has only 2/3 independent pools, no CI",
              "occupancy": "nominal allowed-bid domain includes structural zeros and unreachable public states",
              "limitations": ["coarse state omits exact history in fine-reaction controls",
                              "adaptive histories may violate permutation exchangeability even for coarse reactions",
                              "conditioning on a jointly observed history can associate otherwise independent current costs in finite samples",
                              "baseline empirical thresholds have few N0 units; pooled AUROC is particularly coarse",
                              "no guarantee or optimality claim for LLM agents; no communication content is simulated"]}
    (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    started = time.perf_counter()
    econ = economics(out, quick)
    print("economics complete", flush=True)
    alarms = false_alarms(out, n_perm, config["false_alarm_markets"])
    power = discrimination(out, quick, n_perm)
    fingerprints, espionage, occupancy = diagnostics(out, n_perm)
    plot_results(out, alarms, power, fingerprints, econ, occupancy)
    summary = {"mode": "quick" if quick else "full", "economics": econ,
               "family_false_alarms": [r for r in alarms if r["rule"] == "candidate"],
               "q1_100rounds": [r for r in power if r["q"] == 1 and r["rounds"] == 100 and r["metric"] in ("net_L1", "eq3_L2")],
               "spy_pair": [r for r in espionage if r["unit"] == "pool20" and (r["i"], r["j"]) == (0, 1)],
               "fingerprint_pair": [r for r in fingerprints if r["unit"] == "pool20" and (r["receiver"], r["source"]) == (0, 1)],
               "honest_pair_occupancy": [r for r in occupancy if r["condition"] == "honest" and r["pair"] == "0-1"],
               "elapsed_seconds": time.perf_counter() - started}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Artifacts: {out}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    main(parser.parse_args().quick)
