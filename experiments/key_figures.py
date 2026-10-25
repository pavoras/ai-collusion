"""Overview figures for the report, rendered from frozen analysis outputs.

Figure 1: study design (schematic) and what the auditor scores in matched markets.
Figure 2: where net influence beats correlation, and profit versus detectability.

No model calls and no statistical refitting: every plotted number is read from
the final analysis (final_v1) or the replication cohort (replication_v22), and
recorded with its JSON path in results/report_figures/key_figure_numbers.csv.
The per-market AUROCs recomputed for Figure 1 are asserted to equal the frozen ones.
"""

import csv
import json
from pathlib import Path
import shutil

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

from collusion.plotting import apply_style, BLUE, ORANGE, AQUA, TEXT, TEXT_MUTED, GRID

ROOT = Path(__file__).resolve().parents[1]
FINAL = "results/analysis/final_v1/results.json"
REPL = "results/analysis/replication_v22/results.json"
OUT = ROOT / "results/report_figures"
PAIRS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
GREY = "#8d8c87"
CELL_NAMES = {"C1-SS": "Cartel, strong pair", "C1-SF": "Cartel, strong + fringe",
              "C1-FF": "Cartel, fringe pair", "C1-NW": "Cartel, no warning",
              "C2": "Cartel, no channel", "E1": "Espionage (not a cartel)"}


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def find(rows, **keys):
    hits = [(i, r) for i, r in enumerate(rows) if all(r.get(k) == v for k, v in keys.items())]
    assert len(hits) == 1, (keys, len(hits))
    return hits[0]


def record(numbers, figure, panel, label, metric, value, source, path, n=None):
    numbers.append(dict(figure=figure, panel=panel, label=label, metric=metric, n=n,
                        estimate=value["estimate"] if isinstance(value, dict) else value,
                        low=value.get("low") if isinstance(value, dict) else None,
                        high=value.get("high") if isinstance(value, dict) else None,
                        source=f"{source} {path}"))


def save(fig, name):
    for suffix in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{suffix}", metadata={"CreationDate": None} if suffix == "pdf" else None)
    shutil.copyfile(OUT / f"{name}.pdf", ROOT / f"report/figures/{name}.pdf")
    plt.close(fig)


def auc(negative, positive):
    """Mann-Whitney AUROC with half credit for ties (the analysis convention)."""
    neg, pos = np.asarray(negative)[:, None], np.asarray(positive)[None, :]
    return float(((pos > neg) + .5 * (pos == neg)).mean())


def matched_scores(data, cell, level, detector):
    """Designated-pair scores of eligible matched markets, exactly as the frozen pipeline pairs them."""
    markets = {(m["cohort"], m["cell"], m["market_index"]): m for m in data["markets"]}
    _, row = find(data["all_cells"], cohort="registered", cell=cell, prefix=200, mask="complete",
                  level=level, detector=detector)
    out = []
    for (cohort, name, index), treatment in sorted(markets.items()):
        if (cohort, name) != ("registered", cell) or not treatment["eligible"]:
            continue
        control = markets.get(("registered", row["control"], index))
        if control is None or not control["eligible"]:
            continue
        view = lambda m: next(v for v in m["views"] if v["prefix"] == 200 and v["mask"] == "complete")
        target = PAIRS.index(tuple(sorted(treatment["assignment"]["designated_pair"])))
        out.append((index, view(control)["levels"][level]["scores"][detector][target],
                    view(treatment)["levels"][level]["scores"][detector][target]))
    return out, row


def schematic(ax):
    """Four bidders, the cartel channel, the spy's view of a cost, and the two auditor access levels."""
    ax.set(xlim=(0, 11), ylim=(0, 7.0), aspect="equal", anchor="N")
    ax.axis("off")
    firms = {"A": (1.6, 4.5, "strong"), "B": (4.4, 4.5, "strong"), "C": (1.6, 1.5, "fringe"), "D": (4.4, 1.5, "fringe")}
    for name, (x, y, kind) in firms.items():
        ax.add_patch(FancyBboxPatch((x - .85, y - .6), 1.7, 1.2, boxstyle="round,pad=.05,rounding_size=.2",
                                    fc="white", ec=TEXT_MUTED, lw=.9))
        ax.text(x, y + .2, f"Firm {name}", ha="center", va="center", fontsize=7, weight="bold", color=TEXT)
        ax.text(x, y - .27, "cost 1-3" if kind == "strong" else "cost 3-5", ha="center",
                va="center", fontsize=5.8, color=TEXT_MUTED)
    for y, kind in ((4.5, "strong"), (1.5, "fringe")):
        ax.text(.2, y, kind, rotation=90, ha="center", va="center", fontsize=6, color=TEXT_MUTED)
    ax.add_patch(FancyArrowPatch((2.5, 4.85), (3.5, 4.85), arrowstyle="<->", mutation_scale=8, color=ORANGE, lw=1.4))
    ax.text(3.0, 5.75, "cartel: joint-profit goal, private\nmessages (C1) or none (C2)", ha="center", va="center",
            fontsize=5.8, color=ORANGE)
    ax.add_patch(FancyArrowPatch((3.5, 4.15), (2.5, 4.15), arrowstyle="->", mutation_scale=8, color=AQUA, lw=1.4,
                                 linestyle=(0, (3, 2))))
    ax.text(3.0, 3.3, "espionage (E1): A secretly\nsees B's cost, no cartel", ha="center", va="center",
            fontsize=5.8, color=AQUA)
    ax.text(3.0, .2, "200 rounds; lowest bid wins; bids become public", ha="center", va="center",
            fontsize=5.6, color=TEXT_MUTED)
    ax.add_patch(FancyArrowPatch((5.4, 3.0), (6.1, 3.0), arrowstyle="->", mutation_scale=9, color=TEXT_MUTED, lw=1.1))
    ax.add_patch(FancyBboxPatch((6.25, .9), 4.7, 4.3, boxstyle="round,pad=.05,rounding_size=.2",
                                fc="#f4f3ef", ec=TEXT_MUTED, lw=.9))
    ax.text(8.6, 4.75, "Auditor", ha="center", va="center", fontsize=7, weight="bold", color=TEXT)
    lines = (("L1: all bids and winners", TEXT), ("L2: L1 + every firm's cost", TEXT),
             ("never: messages, roles", TEXT_MUTED), ("scores each of 6 pairs:", TEXT),
             ("net influence or correlation", TEXT))
    for k, (line, color) in enumerate(lines):
        ax.text(6.5, 4.05 - .68 * k, line, ha="left", va="center", fontsize=5.9, color=color)
    ax.text(0, 7.0, "a  Design", fontsize=8, weight="semibold", color=TEXT, va="top")


def strip(ax, blocks, title, color, frozen):
    """Honest vs treatment designated-pair scores, one faint line per matched market pair."""
    _, neg, pos = map(np.asarray, zip(*blocks))
    for a, b in zip(neg, pos):
        ax.plot([0, 1], [a, b], color=GRID, lw=.7, zorder=1)
    jitter = np.linspace(-.06, .06, len(neg))
    ax.scatter(np.zeros(len(neg)) + jitter, neg, s=9, color=GREY, zorder=2, lw=0)
    ax.scatter(np.ones(len(pos)) + jitter, pos, s=9, color=color, zorder=2, lw=0)
    value = auc(neg, pos)
    assert abs(value - frozen["estimate"]) < 1e-12, (title, value, frozen["estimate"])
    ax.set_xticks([0, 1])
    ax.set_xlim(-.35, 1.35)
    ax.grid(axis="x", visible=False)
    ax.tick_params(labelsize=5.5)
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.set_title(f"{title}\nAUROC {value:.2f}", fontsize=7)
    return value


def figure_1(final, numbers):
    fig = plt.figure(figsize=(6.6, 2.5))
    schematic(fig.add_axes([0.0, 0.02, 0.42, 0.94]))
    panels = (("C1-SS", "net", "Cartel: net"), ("C1-SS", "correlation", "Cartel: corr."),
              ("E1", "net", "Spy: net"), ("E1", "correlation", "Spy: corr."))
    for k, (cell, detector, title) in enumerate(panels):
        ax = fig.add_axes([0.535 + k * 0.1175, 0.12, 0.08, 0.62])
        blocks, row = matched_scores(final, f"core.{cell}", "L2", detector)
        i, _ = find(final["all_cells"], cohort="registered", cell=f"core.{cell}", prefix=200, mask="complete",
                    level="L2", detector=detector)
        strip(ax, blocks, title, BLUE if detector == "net" else ORANGE, row["auroc"])
        ax.set_xticklabels(["honest", "cartel" if cell != "E1" else "spy"])
        record(numbers, 1, "b", f"core.{cell} L2 {detector}", "auroc", row["auroc"], FINAL,
               f"all_cells[{i}].auroc", row["auroc"]["n_blocks"])
        for index, neg, pos in blocks:
            record(numbers, 1, "b", f"core.{cell} L2 {detector} market {index}", "designated score (control, treatment)",
                   {"estimate": pos, "low": neg, "high": None}, FINAL,
                   f"markets[cell=core.{cell}|{row['control']}, market_index={index}].views[prefix=200,mask=complete].levels.L2.scores.{detector}")
        if k == 0:
            ax.set_ylabel("score of the designated pair (L2)", fontsize=6.3)
    fig.text(.45, .985, "b  Each matched pair of markets (same costs), markets 0-19",
             fontsize=8, weight="semibold", color=TEXT, va="top")
    save(fig, "figure_1")


def figure_2(final, repl, numbers):
    fig, (left, right) = plt.subplots(1, 2, figsize=(6.6, 2.9), gridspec_kw=dict(width_ratios=[1, 1.1], wspace=.5))
    order = ["E1", "C2", "C1-SS", "C1-SF", "C1-FF", "C1-NW"]
    left.axvspan(0, .75, color=BLUE, alpha=.06, lw=0)
    left.axvspan(-.75, 0, color=ORANGE, alpha=.06, lw=0)
    left.axvline(0, color=TEXT_MUTED, lw=.8)
    yticks, ylabels = [], []
    for y, cell in enumerate(order):
        i, c = find(final["contrasts"], cohort="registered", cell=f"core.{cell}", prefix=200, mask="complete",
                    contrast="L2:net minus L2:correlation")
        v = c["result"]
        left.errorbar(v["estimate"], y - .13, xerr=[[v["estimate"] - v["low"]], [v["high"] - v["estimate"]]],
                      fmt="o", color=TEXT, ms=4, lw=1.1, capsize=0)
        record(numbers, 2, "a", f"core.{cell} original", "L2 net minus correlation AUROC", v, FINAL,
               f"contrasts[{i}].result", v["n_blocks"])
        hit = [(j, r) for j, r in enumerate(repl["contrasts"]) if r["cell"] == f"rep.{cell}" and r["prefix"] == 200
               and r["mask"] == "complete" and r["contrast"] == "L2:net minus L2:correlation"]
        if hit:
            j, r = hit[0]
            w = r["result"]
            left.errorbar(w["estimate"], y + .17, xerr=[[w["estimate"] - w["low"]], [w["high"] - w["estimate"]]],
                          fmt="o", mfc="white", color=TEXT, ms=4, lw=1.1, capsize=0)
            record(numbers, 2, "a", f"rep.{cell} replication", "L2 net minus correlation AUROC", w, REPL,
                   f"contrasts[{j}].result", w["n_blocks"])
        yticks.append(y)
        ylabels.append(CELL_NAMES[cell])
    left.set(yticks=yticks, xlim=(-.75, .75), ylim=(len(order) - .5, -.6),
             xlabel="AUROC difference, net influence minus correlation (L2)")
    left.set_yticklabels(ylabels, fontsize=7)
    left.tick_params(axis="x", labelsize=6.5)
    left.grid(axis="y", visible=False)
    left.text(.72, -.45, "net better", ha="right", va="center", fontsize=6.5, color=BLUE)
    left.text(-.72, -.45, "correlation better", ha="left", va="center", fontsize=6.5, color=ORANGE)
    left.legend(handles=[Line2D([], [], marker="o", color=TEXT, ls="", ms=4, label="markets 0-19"),
                         Line2D([], [], marker="o", mfc="white", color=TEXT, ls="", ms=4, label="fresh markets 20-39")],
                loc="upper left", bbox_to_anchor=(0, .93), fontsize=6.3, handletextpad=.2, borderaxespad=.2)
    left.set_title("a  Net influence minus correlation", loc="left")

    points = []
    for cell in order:
        for data, source, cohort, name, hollow in ((final, FINAL, "registered", f"core.{cell}", False),
                                                   (repl, REPL, "replication", f"rep.{cell}", True)):
            hit = [(j, b) for j, b in enumerate(data["behaviour"]) if b["cohort"] == cohort and b["cell"] == name
                   and b["prefix"] == 200 and b["metric"] == "joint_profit" and b.get("mask", "complete") == "complete"]
            if not hit:
                continue
            j, b = hit[0]
            x = b["paired_difference"]["estimate"]
            record(numbers, 2, "b", name, "joint profit uplift per round vs N0", b["paired_difference"], source,
                   f"behaviour[{j}].paired_difference", b["n_blocks"])
            ys = {}
            for detector in ("net", "correlation"):
                i, r = find(data["all_cells"], cohort=cohort, cell=name, prefix=200, mask="complete",
                            level="L2", detector=detector)
                ys[detector] = r["auroc"]["estimate"]
                record(numbers, 2, "b", name, f"L2 {detector} AUROC", r["auroc"], source,
                       f"all_cells[{i}].auroc", r["auroc"]["n_blocks"])
            right.plot([x, x], [ys["correlation"], ys["net"]], color=GRID, lw=1.6, zorder=1)
            for detector, color, marker in (("net", BLUE, "o"), ("correlation", ORANGE, "s")):
                right.plot(x, ys[detector], marker=marker, ms=4.5, ls="", zorder=2,
                           color=color, mfc="white" if hollow else color, mew=1.1)
            points.append((cell, hollow, x, max(ys.values()), min(ys.values())))
    places = {("E1", False): (-.13, .70, "right"), ("E1", True): (-.07, .68, "left"),
              ("C2", False): (.399, .465, "center"), ("C2", True): (.27, .7525, "right"),
              ("C1-SS", False): (.155, .845, "left"), ("C1-SS", True): (.185, .905, "left"),
              ("C1-SF", False): (-.075, .85, "right"), ("C1-FF", False): (-.01, 1.025, "right"),
              ("C1-NW", False): (-.19, .94, "left")}
    short = {"E1": "spy", "C2": "no channel", "C1-SS": "strong pair", "C1-SF": "strong+fringe",
             "C1-FF": "fringe pair", "C1-NW": "no warning"}
    for cell, hollow, *_ in points:
        x, y, ha = places[(cell, hollow)]
        right.text(x, y, short[cell] + (" (fresh)" if hollow else ""), fontsize=6.2, color=TEXT_MUTED,
                   ha=ha, va="center")
    right.axhline(.5, color=TEXT_MUTED, lw=.7, ls=":")
    right.axvline(0, color=TEXT_MUTED, lw=.7)
    right.text(-.33, .52, "chance", fontsize=6.2, color=TEXT_MUTED, va="bottom")
    right.set(xlim=(-.35, .5), ylim=(.3, 1.05), xlabel="Joint profit gain of the pair vs. honest markets (per round)",
              ylabel="Detection AUROC (L2)")
    right.tick_params(labelsize=6.5)
    right.legend(handles=[Line2D([], [], marker="o", color=BLUE, ls="", ms=4.5, label="net influence"),
                          Line2D([], [], marker="s", color=ORANGE, ls="", ms=4.5, label="correlation"),
                          Line2D([], [], marker="o", color=GREY, mfc="white", ls="", ms=4.5, label="fresh markets")],
                 loc="lower right", fontsize=6.3, handletextpad=.2, borderaxespad=.2)
    right.set_title("b  Profit vs. detectability", loc="left")
    save(fig, "figure_2")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    final, repl = load(FINAL), load(REPL)
    assert final["development"] is False and repl["development"] is False
    assert final["analysis_freeze_commit"] == repl["analysis_freeze_commit"]
    apply_style()
    plt.rcParams.update({"font.size": 7, "axes.titlesize": 8, "axes.labelsize": 7,
                         "pdf.fonttype": 42, "ps.fonttype": 42, "axes.titleweight": "semibold"})
    numbers = []
    figure_1(final, numbers)
    figure_2(final, repl, numbers)
    with (OUT / "key_figure_numbers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(numbers[0]))
        writer.writeheader()
        writer.writerows(numbers)
    print(json.dumps({"recorded_numbers": len(numbers)}))


if __name__ == "__main__":
    main()
