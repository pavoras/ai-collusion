"""Market-level scripted power; run with .venv/Scripts/python experiments/auction_power.py.

All outputs, including resumable cell CSVs, stay in results/auction_power/.
The quick run uses a small pool, not fewer permutations or a different rule.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import replace
from functools import lru_cache
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy.stats import beta, binom

from collusion.games.auction import play
from collusion.measures import auroc, pair_score, symmetric_permutation_test
from collusion import plotting

SEED = 20261026
PAIRS = list(combinations(range(4), 2))
POSITIONS = {"strong_strong": (0, 1), "strong_fringe": (0, 2), "fringe_fringe": (2, 3)}
POPULATIONS = {"iid": (0, 0, 0, 0), "shared_fine": (1, 1, 1, 1)}
NS = (10, 15, 20, 30, 40)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/auction_power"


@lru_cache(maxsize=2)
def spy_policy(reactions):
    """Exact best response for receiver 0 to victim 1, integrating honest rivals."""
    bids = np.arange(2, 8)
    others = np.array(list(product(bids, repeat=3)))
    ties = (bids[:, None, None] == others).sum(axis=-1)
    wins = (bids[:, None] <= others.min(axis=1)) / (1 + ties)
    table = np.empty((6, 3, 3), dtype=int)
    for last in bids:
        for victim_cost in range(1, 4):
            pmfs = []
            for seat, costs in [(1, [victim_cost]), (2, [3, 4, 5]), (3, [3, 4, 5])]:
                possible = np.clip(np.repeat(costs, 2) + 1 + np.tile([0, 1], len(costs))
                                   + reactions[seat] * (last - 4), 2, 7)
                pmfs.append(np.bincount(possible - 2, minlength=6) / len(possible))
            weights = np.prod([pmfs[i][others[:, i] - 2] for i in range(3)], axis=0)
            win_probability = wins @ weights
            for cost in range(1, 4):
                table[last - 2, cost - 1, victim_cost - 1] = bids[np.argmax((bids - cost) * win_probability)]
    return table


def partial_spy(rounds, index, q, reactions):
    """Local compliance extension until play supports spy q; same seeded auction laws."""
    # Public play supplies paired costs and untruncated independent honest noise.
    base = play(rounds, seed=SEED, market_index=index)
    noise = base.bids - base.costs - 1
    compliant = np.random.default_rng([SEED, index, 20]).random(rounds) < q
    ties = np.random.default_rng([SEED, index, 1]).random(rounds)
    policy = spy_policy(tuple(reactions))
    bids, payoffs = np.empty_like(base.bids), np.zeros_like(base.payoffs)
    winners, history = np.empty(rounds, dtype=int), np.empty(rounds, dtype=int)
    last = 4
    for t in range(rounds):
        history[t] = last
        bids[t] = np.clip(base.costs[t] + 1 + noise[t] + np.asarray(reactions) * (last - 4), 2, 7)
        if compliant[t]:
            bids[t, 0] = policy[last - 2, base.costs[t, 0] - 1, base.costs[t, 1] - 1]
        tied = np.flatnonzero(bids[t] == bids[t].min())
        winner = tied[int(ties[t] * len(tied))]
        winners[t] = winner
        payoffs[t, winner] = bids[t, winner] - base.costs[t, winner]
        last = bids[t, winner]
    return replace(base, bids=bids, payoffs=payoffs, winners=winners, compliant=compliant,
                   last_winning_bid=history, public_state=np.minimum((history - 2) // 2, 2))


@lru_cache(maxsize=1)
def native_spy_compliance():
    """Check behavior, since older play signatures accept q but ignore it for spies."""
    honest = play(100, seed=SEED, market_index=999)
    zero = play(100, seed=SEED, market_index=999, spy=(0, 1), q=0)
    return np.array_equal(honest.bids, zero.bids)


def exact_interval(hits, total):
    """Two-sided 95% Clopper-Pearson interval."""
    low = 0.0 if hits == 0 else beta.ppf(.025, hits, total - hits + 1)
    high = 1.0 if hits == total else beta.ppf(.975, hits + 1, total - hits)
    return float(low), float(high)


def resample_auc(negative, positive, n, repetitions, seed):
    """AUROC sampling distribution from paired whole-market draws with replacement."""
    negative, positive = np.asarray(negative), np.asarray(positive)
    if negative.ndim != 1 or negative.shape != positive.shape or not len(negative):
        raise ValueError("equal nonempty score vectors required")
    if not np.isfinite(np.r_[negative, positive]).all() or min(n, repetitions) < 1:
        raise ValueError("finite scores and positive sampling counts required")
    rng = np.random.default_rng(seed)
    draws = rng.integers(len(negative), size=(repetitions, n))
    comparisons = (positive[:, None] > negative).astype(float)
    comparisons += .5 * (positive[:, None] == negative)
    # Batches bound memory at the largest planned sample size.
    values = np.concatenate([comparisons[d[:, :, None], d[:, None, :]].mean(axis=(1, 2))
                             for d in np.array_split(draws, max(1, repetitions // 200))])
    return values, draws


def quantiles(values):
    return dict(zip(("median", "low", "high"), map(float, np.quantile(values, [.5, .025, .975]))))


def leak_class(result, pair):
    """Fixed round-4 rule: significance /12, absence p>=.2 and effect<=.05 bits."""
    i, j = pair
    p = np.array([result.leak_p_value[i, j], result.leak_p_value[j, i]])
    effect = np.array([result.leak_corrected[i, j], result.leak_corrected[j, i]])
    significant = p <= .05 / 12
    absent = (p >= .2) & (effect <= .05)
    if significant.all():
        return "two-way"
    if significant[0] and absent[1]:
        return "one-way j->i"
    if significant[1] and absent[0]:
        return "one-way i->j"
    return "none" if absent.all() else "unclear"


def analyse(market, n_perm, key):
    """Public API only; exact pre-round history at both access levels."""
    rows = []
    for k, level in enumerate(("L1", "L2")):
        result = symmetric_permutation_test(
            market.bids - 2, None if level == "L1" else list(market.costs.T),
            public_state=market.last_winning_bid, n_perm=n_perm, rng=[SEED, *key, k])
        scores = pair_score(result.net_corrected)
        candidates = [p for p in PAIRS if result.p_value[p] <= .05 / 6 and scores[p] > 0]
        reported = candidates[0] if len(candidates) == 1 else None
        for pair in PAIRS:
            i, j = pair
            rows.append({"level": level, "i": i, "j": j, "score": float(scores[pair]),
                         "detected": int(reported == pair), "candidate": int(pair in candidates),
                         "family_alarm": int(bool(candidates)), "reported_any": int(reported is not None),
                         "p_gamma": float(result.p_value[pair]),
                         "leak_class": leak_class(result, pair) if level == "L2" else "unobservable",
                         "leak_family_alarm": int(np.any(result.leak_p_value <= .05 / 12)) if k else 0,
                         "p_incoming": float(result.leak_p_value[i, j]) if k else 1.0,
                         "p_outgoing": float(result.leak_p_value[j, i]) if k else 1.0})
    return rows


def grid(quick=False):
    """N0 is simulated once per population/round count and reused by seat."""
    cells = []
    rounds_grid = (100, 200, 300) if not quick else (100, 200)
    for population in POPULATIONS:
        for rounds in rounds_grid:
            cells.append((population, rounds, "N0", "all", 0.0))
            for position in POSITIONS:
                if position == "fringe_fringe" and rounds != 200:
                    continue
                for q in ((1.0, .75, .5, .25) if not quick else (1.0, .5)):
                    cells.append((population, rounds, "cartel", position, q))
            for q in (1.0, .5):
                cells.append((population, rounds, "spy", "strong_strong", q))
    return cells


def cell_name(cell):
    return "_".join(map(str, cell)).replace(".", "p")


def simulate_cell(task):
    """Independent cell worker, with costs/noise paired across conditions."""
    cell, pool_size, n_perm = task
    population, rounds, condition, position, q = cell
    rows = []
    pair = POSITIONS.get(position)
    population_index = list(POPULATIONS).index(population)
    condition_index = (0 if condition == "N0" else 1 if condition == "cartel" else 2)
    position_index = list(POSITIONS).index(position) if pair else 0
    for index in range(pool_size):
        kwargs = {} if condition == "N0" else {condition: pair, "q": q}
        if condition == "spy" and not native_spy_compliance():
            market = partial_spy(rounds, index, q, POPULATIONS[population])
        else:
            market = play(rounds, seed=SEED, market_index=index,
                          reactions=POPULATIONS[population], coarse=False, **kwargs)
        key = [population_index, rounds, condition_index, position_index, int(q * 100), index]
        for row in analyse(market, n_perm, key):
            if pair and (row["i"], row["j"]) != pair:
                continue
            row.update({"population": population, "rounds": rounds, "condition": condition,
                        "position": position, "q": q, "market": index,
                        "realized_q": float(market.compliant.mean())})
            rows.append(row)
    return rows


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    integers = ("i", "j", "detected", "candidate", "family_alarm", "reported_any",
                "leak_family_alarm", "rounds", "market")
    for row in rows:
        for name in integers:
            row[name] = int(row[name])
        for name in ("score", "p_gamma", "p_incoming", "p_outgoing", "q", "realized_q"):
            row[name] = float(row[name])
    return rows


def summarise(data, cells, pool_size, repetitions):
    """Distribution across hypothetical n-market experiments, not a CI on a pool AUROC."""
    power, leaks, alarms = [], [], []
    grouped = {}
    for row in data:
        key = (row["population"], row["rounds"], row["condition"], row["position"], row["q"],
               row["level"], row["i"], row["j"])
        grouped.setdefault(key, []).append(row)
    for cell_index, cell in enumerate(cells):
        population, rounds, condition, position, q = cell
        if condition == "N0":
            continue
        pair = POSITIONS[position]
        meta = dict(zip(("population", "rounds", "condition", "position", "q"), cell))
        for level in ("L1", "L2"):
            positive = grouped[(*cell, level, *pair)]
            negative = grouped[(population, rounds, "N0", "all", 0.0, level, *pair)]
            ps, ns = [r["score"] for r in positive], [r["score"] for r in negative]
            pool_auc = auroc(np.r_[np.zeros(pool_size), np.ones(pool_size)], np.r_[ns, ps])
            hits = sum(r["detected"] for r in positive)
            dlow, dhigh = exact_interval(hits, pool_size)
            truth = "two-way" if condition == "cartel" else "one-way j->i"
            correct = np.array([r["leak_class"] == truth for r in positive])
            gated = correct & np.array([r["detected"] for r in positive], dtype=bool)
            for n in NS:
                values, draws = resample_auc(ns, ps, n, repetitions, [SEED, 800, cell_index, n])
                power.append({**meta, "level": level, "n": n, "pool_size": pool_size,
                              "pool_auc": pool_auc, **{f"auc_{k}": v for k, v in quantiles(values).items()},
                              "detection_rate": hits / pool_size, "detection_low": dlow,
                              "detection_high": dhigh,
                              **{f"detection_experiment_{k}": v for k, v in quantiles(
                                  np.array([r["detected"] for r in positive])[draws].mean(1)).items()}})
                if level == "L2":
                    llow, lhigh = exact_interval(int(correct.sum()), pool_size)
                    leaks.append({**meta, "n": n, "pool_size": pool_size, "truth": truth,
                                  "correct_rate": float(correct.mean()), "correct_low": llow, "correct_high": lhigh,
                                  "gated_correct_rate": float(gated.mean()),
                                  "unclear_rate": sum(r["leak_class"] == "unclear" for r in positive) / pool_size,
                                  **{f"experiment_{k}": v for k, v in quantiles(correct[draws].mean(1)).items()}})
    for population in POPULATIONS:
        for rounds in sorted({c[1] for c in cells}):
            for level in ("L1", "L2"):
                negative = grouped[(population, rounds, "N0", "all", 0.0, level, 0, 1)]
                endpoints = [("pair_family", "family_alarm", negative), ("pair_reported", "reported_any", negative)]
                if level == "L2":
                    endpoints.append(("leak_family", "leak_family_alarm", negative))
                for position, pair in POSITIONS.items():
                    target = grouped[(population, rounds, "N0", "all", 0.0, level, *pair)]
                    endpoints.append((f"target_{position}", "detected", target))
                for endpoint, field, negative in endpoints:
                    flags = np.array([r[field] for r in negative])
                    for n in (10, 20, 40):
                        # Prefix is a concrete independent N0 experiment; pool is its planning distribution.
                        count = min(n, pool_size)
                        hits = int(flags[:count].sum())
                        low, high = exact_interval(hits, count)
                        acceptable = [k for k in range(n + 1) if exact_interval(k, n)[1] < .2]
                        probability = float(binom.cdf(max(acceptable), n, flags.mean())) if acceptable else 0.0
                        plow, phigh = exact_interval(int(flags.sum()), pool_size)
                        alarms.append({"population": population, "rounds": rounds, "level": level,
                                       "endpoint": endpoint, "n_requested": n, "n_observed": count,
                                       "hits": hits, "rate": hits / count, "low": low, "high": high,
                                       "pool_size": pool_size, "pool_rate": float(flags.mean()),
                                       "pool_low": plow, "pool_high": phigh,
                                       "probability_upper_below_20pct": probability})
    return power, leaks, alarms


def recommendations(power, alarms):
    rows = []
    for population in POPULATIONS:
        for position in POSITIONS:
            eligible = [r for r in power if r["condition"] == "cartel" and r["population"] == population
                        and r["position"] == position and r["level"] == "L2" and r["q"] == .5]
            passing = [r for r in eligible if r["auc_low"] > .7]
            frontier = [r for r in passing if not any(
                s["n"] <= r["n"] and s["rounds"] <= r["rounds"] and
                (s["n"], s["rounds"]) != (r["n"], r["rounds"]) for s in passing)]
            joint = [r for r in passing if any(a["population"] == population and a["rounds"] == r["rounds"]
                     and a["level"] == "L2" and a["endpoint"] == "pair_family"
                     and a["n_requested"] == r["n"] and a["n_observed"] == r["n"]
                     and a["high"] < .2 for a in alarms)]
            best = min(joint, key=lambda r: (r["n"] * r["rounds"], r["rounds"], r["n"])) if joint else None
            rows.append({"population": population, "position": position,
                         "auc_frontier": [{k: r[k] for k in ("n", "rounds", "auc_low")} for r in frontier],
                         "smallest_joint_by_total_rounds": None if best is None else {
                             k: best[k] for k in ("n", "rounds", "auc_low")}})
    return rows


def sensitivity_comparison(data):
    """Same market IDs at 239 versus 999 permutations; no new calibration threshold."""
    baseline = read_csv(OUT / "full/markets.csv")
    key = lambda r: tuple(r[k] for k in ("population", "rounds", "condition", "position", "q", "level", "i", "j", "market"))
    low = {key(r): r for r in baseline}
    groups = {}
    for row in data:
        groups.setdefault(key(row)[:-1], []).append(row)
    rows = []
    for group, high in groups.items():
        old = [low[key(r)] for r in high]
        names = ("population", "rounds", "condition", "position", "q", "level", "i", "j")
        meta = dict(zip(names, group))
        truth = "two-way" if meta["condition"] == "cartel" else "one-way j->i"
        rows.append({**meta, "markets": len(high), "low_permutations": 239, "high_permutations": 999,
                     "detection_low_perm": float(np.mean([r["detected"] for r in old])),
                     "detection_high_perm": float(np.mean([r["detected"] for r in high])),
                     "changed_detections": sum(a["detected"] != b["detected"] for a, b in zip(old, high)),
                     "correct_leak_low_perm": float(np.mean([r["leak_class"] == truth for r in old])),
                     "correct_leak_high_perm": float(np.mean([r["leak_class"] == truth for r in high])),
                     "changed_leak_classes": sum(a["leak_class"] != b["leak_class"] for a, b in zip(old, high))})
    return rows


def figure(out, power):
    """Half-page appendix panel; exact same cells as the numeric output."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plotting.apply_style()
    fig, ax = plt.subplots(figsize=(3.5, 2.8), layout="constrained")
    for q, color, style in [(1.0, plotting.BLUE, "-"), (.75, plotting.ORANGE, "--"),
                             (.5, plotting.AQUA, "-"), (.25, plotting.BLUE, ":")]:
        rows = [r for r in power if r["population"] == "iid" and r["condition"] == "cartel"
                and r["position"] == "strong_strong" and r["rounds"] == 200
                and r["level"] == "L2" and r["q"] == q]
        if rows:
            ax.plot([r["n"] for r in rows], [r["auc_high"] - r["auc_low"] for r in rows], marker="o",
                    color=color, linestyle=style, label=f"q = {q:g}")
    ax.set(xlabel="Markets per condition", ylabel="AUROC 95% range width", ylim=(-.01, .3),
           xticks=NS, title="L2, strong pair, 200 rounds")
    ax.legend(fontsize=7, loc="upper right", ncol=2)
    fig.savefig(out / "appendix_power.png")
    fig.savefig(out / "appendix_power.pdf")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--sensitivity", action="store_true", help="999-permutation check on 80 matched markets in selected cells")
    parser.add_argument("--pool-size", type=int)
    parser.add_argument("--resamples", type=int)
    parser.add_argument("--permutations", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cartel-only", action="store_true", help="Run the cartel subset")
    args = parser.parse_args()
    args.permutations = args.permutations or (999 if args.sensitivity else 239)
    pool_size = args.pool_size or (2 if args.quick else 80 if args.sensitivity else 400)
    repetitions = args.resamples or (100 if args.quick else 4000)
    if args.permutations < 239 or min(pool_size, repetitions, args.workers) < 1:
        parser.error("need >=239 permutations and positive pool/resample/worker counts")
    started = time.perf_counter()
    out = OUT / ("quick" if args.quick else "sensitivity" if args.sensitivity else "full")
    out.mkdir(parents=True, exist_ok=True)
    cells = [c for c in grid(args.quick) if not args.cartel_only or c[2] != "spy"]
    if args.sensitivity:
        cells = [c for c in cells if c[1] in (100, 200) and (c[2] == "N0" or (
            c[3] == "strong_strong" and (c[4] == .5 or c[1] == 200 and c[4] in (1.0, .25))))]
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__).resolve(), ROOT / "src/collusion/measures.py", ROOT / "src/collusion/games/auction.py")}
    signature = hashlib.sha256(json.dumps([source_hashes, pool_size, args.permutations], sort_keys=True).encode()).hexdigest()[:12]
    cache = out / "cells" / signature
    cache.mkdir(parents=True, exist_ok=True)
    data, pending = [], []
    for cell in cells:
        path = cache / f"{cell_name(cell)}.csv"
        if path.exists():
            data.extend(read_csv(path))
        else:
            pending.append(cell)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for cell, rows in zip(pending, executor.map(simulate_cell, [
                (c, pool_size, args.permutations) for c in pending])):
            write_csv(cache / f"{cell_name(cell)}.csv", rows)
            data.extend(rows)
            print(f"{cell_name(cell)}: {pool_size} markets; elapsed {time.perf_counter()-started:.1f}s", flush=True)
    data.sort(key=lambda r: (r["population"], r["rounds"], r["condition"], r["position"],
                             r["q"], r["market"], r["level"], r["i"], r["j"]))
    power, leaks, alarms = summarise(data, cells, pool_size, repetitions)
    for name, rows in [("markets", data), ("power", power), ("leaks", leaks), ("false_alarms", alarms)]:
        write_csv(out / f"{name}.csv", rows)
    if args.sensitivity:
        write_csv(out / "permutation_comparison.csv", sensitivity_comparison(data))
    figure(out, power)
    summary = {"command": ".venv/Scripts/python " + " ".join(sys.argv), "seed": SEED,
               "quick": args.quick, "pool_size_per_cell": pool_size, "resampled_experiments": repetitions,
               "n_perm": args.permutations, "workers": args.workers, "source_sha256": source_hashes,
               "cells": len(cells), "simulated_markets": len(cells) * pool_size,
               "cached_cells": len(cells) - len(pending), "runtime_is_current_invocation": True,
               "spy_compliance": "native play" if native_spy_compliance() else "local validated extension; exact same q=0/1 bids, costs, winners and history as public play",
               "n_per_side": NS, "populations": POPULATIONS, "spy_positions": "strong_strong only",
               "state": "exact pre-round last winning bid; L2 adds each bidder's own cost",
               "detection": "exactly one mutual strongest corrected pair, gamma p<=.05/6",
               "false_alarm": "any candidate among six pairs; reported-any also exported",
               "leak": "L2 only; correct designated pattern, not conditional on detection; gated rate also exported",
               "leak_rule": "significant p<=.05/12; absent p>=.2 AND corrected leak<=.05 bits; else unclear",
               "sampling": "paired market-index draws with replacement; AUROC uses all cross-class comparisons with half ties",
               "ranges": "2.5-97.5% sampling range across n-market experiments, conditional on finite scripted pool; not a CI on truth",
               "false_alarm_intervals": "two-sided exact Clopper-Pearson on first n N0 markets; pool interval and plug-in planning probability also exported",
               "recommendations": recommendations(power, alarms),
               "limitations": ["239 permutations resolve direction threshold only at zero exceedances; separate 999-permutation sensitivity exported",
                               "finite pool uncertainty is not included in resampled ranges",
                               "paired adaptive history may violate within-state exchangeability",
                               "shared Bernoulli compliance is a particular scripted alternative, not an LLM forecast",
                               "operational absence guard is not an equivalence test",
                               "quick uses only two markets per cell and cannot justify sample sizes"],
               "elapsed_seconds": time.perf_counter() - started}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
