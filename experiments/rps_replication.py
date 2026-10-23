"""Replicate Bonjour et al. (2022), Section 5.1, on scripted 3-player Rock-Paper-Scissors, and calibrate the threshold.

Outputs (results/rps/):
  control_values.csv     estimated vs exact gamma(A; B) in bits
  net_influence_vs_cp.*  pair score min(Gamma_ij, Gamma_ji) vs collusion probability (paper Fig. 3)
  cda.csv                collusion detection accuracy with the paper's rule, next to the paper's Table 2
  calibration.csv/.png   false alarms and detection: fixed alpha = 0.05 vs permutation-calibrated rule

    .venv/Scripts/python experiments/rps_replication.py            # full run
    .venv/Scripts/python experiments/rps_replication.py --quick    # smoke run with few iterations
"""

import argparse
import csv
import json
import time
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from collusion import measures as m
from collusion import plotting
from collusion.games import rps

OUT = Path("results/rps")
SEED = 20261023
PAIRS = list(combinations(range(3), 2))  # (A,B), (A,C), (B,C)
NAMES = {(0, 1): "A-B (colluding)", (0, 2): "A-C", (1, 2): "B-C"}

# Paper Table 2 (CDA in %, 1000 iterations per cell) and the extra numbers quoted in its text.
PAPER_TABLE2 = {0.3: {100: 37.1, 200: 48.3, 300: 71.0, 400: 82.8, 500: 89.6, 1000: 100.0},
                0.4: {100: 58.4, 200: 79.2, 300: 96.2, 400: 99.3, 500: 99.7, 1000: 100.0}}
PAPER_EXTRA = [(1.0, 60, 100.0), (0.2, 1000, 24.3), (0.2, 10000, 82.3), (0.1, 1000, 8.0)]


def rng_for(*key) -> np.random.Generator:
    return np.random.default_rng([SEED, *[int(round(k * 1000)) for k in key]])


def pair_scores(net: np.ndarray) -> dict:
    return {p: min(net[p], net[p[::-1]]) for p in PAIRS}


def control_values() -> list[dict]:
    rows = []
    for cp in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]:
        acts = rps.play(100_000, cp, rng_for(1, cp))
        rows.append({"cp": cp, "exact_bits": round(rps.true_gamma(cp), 4),
                     "estimated_bits_N100000": round(m.influence(acts[:, 0], acts[:, 1]), 4)})
    return rows


def states_for(acts: np.ndarray, state: str):
    return rps.previous_round_state(acts) if state == "prev" else None


def fig3(n_games: int, reps: int, state: str = "prev") -> dict:
    cps = np.round(np.arange(0, 1.01, 0.1), 2)
    scores = {p: np.zeros((len(cps), reps)) for p in PAIRS}
    for a, cp in enumerate(cps):
        rng = rng_for(2, cp)
        for r in range(reps):
            acts = rps.play(n_games, cp, rng)
            s = pair_scores(m.net_influence(m.influence_matrix(acts, states_for(acts, state), n_actions=3)))
            for p in PAIRS:
                scores[p][a, r] = s[p]
    return {"cp": cps.tolist(), "n_games": n_games, "reps": reps, "state": state,
            **{NAMES[p]: {"mean": scores[p].mean(1).tolist(),
                          "p05": np.percentile(scores[p], 5, 1).tolist(),
                          "p95": np.percentile(scores[p], 95, 1).tolist()} for p in PAIRS}}


def cda(cp: float, n_games: int, iters: int, state: str) -> float:
    rng = rng_for(3, cp, n_games, state == "prev")
    hits = 0
    for _ in range(iters):
        acts = rps.play(n_games, cp, rng)
        hits += m.detect(m.net_influence(m.influence_matrix(acts, states_for(acts, state), n_actions=3))) == (0, 1)
    return 100 * hits / iters


def calibration_cell(cp: float, n_games: int, state: str, iters: int, n_perm: int) -> dict:
    """Rates of 'reports (A,B)' (detection) and 'reports any pair' (alarm) for both rules."""
    rng = rng_for(4, cp, n_games, state == "prev")
    fixed_ab = fixed_any = cal_ab = cal_any = 0
    for _ in range(iters):
        acts = rps.play(n_games, cp, rng)
        states = states_for(acts, state)
        fixed = m.detect(m.net_influence(m.influence_matrix(acts, states, n_actions=3)))
        cal = m.detect_calibrated(m.permutation_test(acts, states, n_perm=n_perm, rng=rng, n_actions=3))
        fixed_ab += fixed == (0, 1)
        fixed_any += fixed is not None
        cal_ab += cal == (0, 1)
        cal_any += cal is not None
    return {"cp": cp, "n_games": n_games, "state": state, "iters": iters, "n_perm": n_perm,
            "fixed_detect_AB": fixed_ab / iters, "fixed_any_alarm": fixed_any / iters,
            "calibrated_detect_AB": cal_ab / iters, "calibrated_any_alarm": cal_any / iters}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def plot_fig3(data: dict) -> None:
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    # A-C and B-C coincide by symmetry (C is independent of both), so B-C is drawn dashed on top.
    styles = [("-", "o"), ("-", "o"), ("--", None)]
    for name, color, (ls, mk) in zip([NAMES[p] for p in PAIRS], [plotting.BLUE, plotting.ORANGE, plotting.AQUA], styles):
        d = data[name]
        ax.fill_between(data["cp"], d["p05"], d["p95"], color=color, alpha=0.15, linewidth=0)
        ax.plot(data["cp"], d["mean"], color=color, linestyle=ls, marker=mk, label=name)
    ax.axhline(m.PAPER_ALPHA, color=plotting.TEXT_MUTED, linewidth=1, linestyle=":")
    ax.text(1.0, m.PAPER_ALPHA + 0.06, "α = 0.05 (paper)", color=plotting.TEXT_MUTED, fontsize=8, ha="right")
    ax.set_xlabel("collusion probability CP")
    ax.set_ylabel("pair score min(Γ(i;j), Γ(j;i)) [bits]")
    ax.set_title(f"Net influence vs CP ({data['n_games']} games, previous-round state)")
    ax.legend(loc="lower left", fontsize=8)
    fig.savefig(OUT / "net_influence_vs_cp.png")
    plt.close(fig)


def plot_calibration(rows: list[dict]) -> None:
    panels = [(0.0, "any_alarm", "No collusion:\nfalse alarms"),
              (0.2, "detect_AB", "CP = 0.2:\npair A-B detected"),
              (0.3, "detect_AB", "CP = 0.3:\npair A-B detected")]
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.7), sharey=True)
    for ax, (cp, metric, title) in zip(axes, panels):
        for rule, color in [("fixed", plotting.ORANGE), ("calibrated", plotting.BLUE)]:
            for state, style in [("none", "-"), ("prev", "--")]:
                sel = sorted((r for r in rows if r["cp"] == cp and r["state"] == state), key=lambda r: r["n_games"])
                ax.plot([r["n_games"] for r in sel], [100 * r[f"{rule}_{metric}"] for r in sel], color=color,
                        linestyle=style, marker="o",
                        label=f"{'fixed α' if rule == 'fixed' else 'calibrated'}, {'no state' if state == 'none' else 'prev. round state'}")
        if cp == 0.0:
            ax.axhline(5, color=plotting.TEXT_MUTED, linewidth=1, linestyle=":")
        ax.set_xscale("log")
        ax.set_title(title)
        ax.set_xlabel("games (rounds)")
    axes[0].set_ylabel("rate [%]")
    axes[0].set_ylim(-3, 103)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=7.5, bbox_to_anchor=(0.5, -0.02))
    fig.savefig(OUT / "calibration.png")
    plt.close(fig)


def main(quick: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plotting.apply_style()
    t0 = time.time()
    iters = 50 if quick else 1000
    cal_iters = 30 if quick else 500
    n_perm = 99 if quick else 199

    write_csv(OUT / "control_values.csv", control_values())
    print(f"control values done ({time.time() - t0:.0f}s)")

    data = fig3(1000, 20 if quick else 100)
    (OUT / "net_influence_vs_cp.json").write_text(json.dumps(data, indent=1))
    plot_fig3(data)
    print(f"fig 3 done ({time.time() - t0:.0f}s)")

    # Paper setting as inferred from Table 2: bits, state = previous round's joint action. No state as reference.
    cells = [(cp, n, paper) for cp, row in PAPER_TABLE2.items() for n, paper in row.items()] + PAPER_EXTRA
    rows = [{"cp": cp, "n_games": n, "cda_paper": paper,
             "cda_ours_prev_state": round(cda(cp, n, iters, "prev"), 1),
             "cda_ours_no_state": round(cda(cp, n, iters, "none"), 1), "iters": iters}
            for cp, n, paper in cells]
    write_csv(OUT / "cda.csv", rows)
    print(f"CDA table done ({time.time() - t0:.0f}s)")

    cal = [calibration_cell(cp, n, state, cal_iters, n_perm)
           for state in ["none", "prev"] for cp in [0.0, 0.1, 0.2, 0.3, 0.4] for n in [50, 100, 200, 500, 1000]]
    write_csv(OUT / "calibration.csv", cal)
    plot_calibration(cal)
    print(f"calibration done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--replot", action="store_true", help="only redraw figures from saved results")
    args = parser.parse_args()
    if args.replot:
        plotting.apply_style()
        plot_fig3(json.loads((OUT / "net_influence_vs_cp.json").read_text()))
        with (OUT / "calibration.csv").open(encoding="utf-8") as f:
            plot_calibration([{k: (v if k == "state" else float(v)) for k, v in r.items()} for r in csv.DictReader(f)])
    else:
        main(args.quick)
