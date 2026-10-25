"""Plain-language main-text figures, rendered from frozen analysis outputs.

Figure 1: how the test works (schematic, no data).
Figure 2: how often an alarm rule named exactly the colluding pair, and false alarms.
Figure 3: which way information flows (pooled leak and action terms).
Figure 4: net influence versus a simple correlation (detection).
Figure 5: two warnings for practice (the quiet cartel; the AI judge's shortcut).

No model calls and no statistical refitting: every plotted number is read from
final_v1 or the judge-budget cohort and recorded with its JSON path in
results/report_figures/key_figure_numbers.csv.
"""

import csv
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from matplotlib.lines import Line2D

from collusion.plotting import apply_style, BLUE, ORANGE, AQUA, TEXT, TEXT_MUTED

ROOT = Path(__file__).resolve().parents[1]
FINAL = "results/analysis/final_v1/results.json"
JUDGE24K = "results/analysis/judge24k_v23/results.json"
OUT = ROOT / "results/report_figures"
GREEN, RED, GREY, LIGHT = "#1f9e60", "#d9483b", "#c9c8c3", "#f4f3ef"
LEVELS = {"L1": "bids only", "L2": "bids + costs"}
SCENARIOS = [("core.N0", "Honest market (any alarm = false)"), ("core.C1-SS", "Cartel: two strong firms"),
             ("core.C1-SF", "Cartel: strong + weak firm"), ("core.C1-FF", "Cartel: two weak firms"),
             ("core.C2", "Cartel without chat"), ("core.E1", "Spy (no cartel)")]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def cell_row(data, cell, level, detector, cohort="registered"):
    hits = [(i, r) for i, r in enumerate(data["all_cells"])
            if (r["cohort"], r["cell"], r["prefix"], r["mask"], r["level"], r["detector"])
            == (cohort, cell, 200, "complete", level, detector)]
    assert len(hits) == 1, (cell, level, detector)
    return hits[0]


def record(numbers, figure, label, metric, value, source, path, n=None):
    if isinstance(value, dict):
        estimate, low, high = value["estimate"], value.get("low"), value.get("high")
    else:
        estimate, low, high = value, None, None
    numbers.append(dict(figure=figure, label=label, metric=metric, n=n, estimate=estimate,
                        low=low, high=high, source=f"{source} {path}"))


def save(fig, name):
    for suffix in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{suffix}", metadata={"CreationDate": None} if suffix == "pdf" else None)
    shutil.copyfile(OUT / f"{name}.pdf", ROOT / f"report/figures/{name}.pdf")
    plt.close(fig)


def box(ax, x, y, w, h, text, fc="white", ec=TEXT_MUTED, size=7, weight="bold", color=TEXT, sub=None):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=.04,rounding_size=.15",
                                fc=fc, ec=ec, lw=.9))
    ax.text(x, y + (.17 if sub else 0), text, ha="center", va="center", fontsize=size, weight=weight, color=color)
    if sub:
        ax.text(x, y - .25, sub, ha="center", va="center", fontsize=size - 1.3, color=TEXT_MUTED)


def arrow(ax, a, b, color=TEXT_MUTED, lw=1.2, style="->", ls="-", scale=9):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=scale, color=color, lw=lw, linestyle=ls,
                                 shrinkA=0, shrinkB=0))


def figure_1():
    """Three steps: the market, the secret arrangements, what the auditor sees and asks."""
    fig, ax = plt.subplots(figsize=(6.6, 2.15))
    ax.set(xlim=(0, 22), ylim=(0, 7.2), aspect="equal")
    ax.axis("off")
    heads = ((3.6, "1  The market"), (10.9, "2  Secret arrangements"), (18.6, "3  The auditor"))
    for x, text in heads:
        ax.text(x, 6.9, text, ha="center", va="top", fontsize=8.5, weight="bold", color=TEXT)
    for name, x, y, sub in (("A", 1.85, 4.6, "strong"), ("B", 5.25, 4.6, "strong"),
                            ("C", 1.85, 2.3, "weak"), ("D", 5.25, 2.3, "weak")):
        box(ax, x, y, 3.0, 1.4, f"AI firm {name}", sub=sub + ", low cost" if sub == "strong" else sub + ", high cost")
    ax.text(3.6, .75, "4 AI agents bid for a contract,\n200 rounds; the lowest bid wins",
            ha="center", va="center", fontsize=6.4, color=TEXT_MUTED)
    rows = ((5.3, ORANGE, "<->", "-", "Cartel: agree to raise\nprofits, chat in private"),
            (3.55, ORANGE, "<->", (0, (1.5, 1.5)), "Cartel without chat:\nsame goal, no messages"),
            (1.8, AQUA, "<-", (0, (3, 2)), "Spy: secretly sees a\nrival's cost, no cartel"))
    for y, color, style, ls, text in rows:
        arrow(ax, (7.9, y), (9.3, y), color=color, lw=1.6, style=style, ls=ls)
        ax.text(9.6, y, text, ha="left", va="center", fontsize=6.4, color=TEXT)
    ax.text(10.9, .55, "Honest markets with identical\ncosts serve as the comparison", ha="center", va="center",
            fontsize=6.4, color=TEXT_MUTED)
    ax.add_patch(FancyBboxPatch((15.2, .5), 6.75, 5.6, boxstyle="round,pad=.04,rounding_size=.2",
                                fc=LIGHT, ec=TEXT_MUTED, lw=.9))
    lines = (("Sees only the bids", TEXT, "bold"), ("(or bids + each firm's cost)", TEXT_MUTED, "normal"),
             ("Never sees the chat", TEXT_MUTED, "normal"),
             ("Asks: is there a cartel,", TEXT, "bold"), ("and which 2 of the 4 firms?", TEXT, "bold"),
             ("Tools: net influence,", TEXT, "normal"), ("simple correlation, AI judge", TEXT, "normal"))
    for k, (text, color, weight) in enumerate(lines):
        ax.text(15.55, 5.55 - .72 * k, text, ha="left", va="center", fontsize=6.6, color=color, weight=weight)
    for x in (7.35, 14.75):
        arrow(ax, (x - .3, 3.6), (x + .3, 3.6), lw=1.3)
    save(fig, "figure_1")


def figure_2(final, numbers):
    """Stacked outcome bars: right pair named / no alarm / wrong pair or false alarm."""
    fig, axes = plt.subplots(1, 4, figsize=(6.6, 2.55), sharey=True, gridspec_kw=dict(wspace=.42))
    panels = (("paper", "L1", "Published rule"), ("paper", "L2", "Published rule"),
              ("net", "L1", "Our corrected rule"), ("net", "L2", "Our corrected rule"))
    for ax, (detector, level, rule) in zip(axes, panels):
        for y, (cell, label) in enumerate(SCENARIOS):
            i, r = cell_row(final, cell, level, detector)
            if cell == "core.N0":
                false = r["any_candidate"]
                parts = [(0, GREEN), (false["estimate"], RED), (1 - false["estimate"], GREY)]
                note = f"{false['hits']}/{false['total']}"
                record(numbers, 2, f"{cell} {level} {detector}", "false alarm (any pair flagged)", false, FINAL,
                       f"all_cells[{i}].any_candidate", false["total"])
            else:
                right, wrong, none = (r[k]["estimate"] for k in ("correct_unique", "wrong_pair", "abstention"))
                assert abs(right + wrong + none - 1) < 1e-9
                parts = [(right, GREEN), (wrong, RED), (none, GREY)]
                note = f"{round(right * r['coverage'])}/{r['coverage']}"
                for key in ("correct_unique", "wrong_pair", "abstention"):
                    record(numbers, 2, f"{cell} {level} {detector}", key, r[key], FINAL, f"all_cells[{i}].{key}",
                           r["coverage"])
            left = 0
            for width, color in parts:
                ax.barh(y, width, left=left, color=color, height=.66, lw=0)
                left += width
            ax.text(1.04, y, note, va="center", ha="left", fontsize=5.8, color=GREEN if cell != "core.N0" else RED)
        ax.set_title(f"{rule}\n{LEVELS[level]}", fontsize=7.2)
        ax.set(xlim=(0, 1), xticks=[0, .5, 1], ylim=(len(SCENARIOS) - .5, -.5))
        ax.set_xticklabels(["0", "50", "100%"], fontsize=6)
        ax.grid(False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.axhline(.5, color=TEXT_MUTED, lw=.6)
    axes[0].set_yticks(range(len(SCENARIOS)))
    axes[0].set_yticklabels([label for _, label in SCENARIOS], fontsize=7)
    fig.legend(handles=[Patch(color=GREEN, label="named exactly the right pair"),
                        Patch(color=RED, label="wrong pair / false alarm"),
                        Patch(color=GREY, label="no alarm")],
               loc="lower center", ncol=3, fontsize=6.6, bbox_to_anchor=(.55, -.01))
    fig.subplots_adjust(left=.22, right=.955, bottom=.19, top=.83)
    save(fig, "figure_2")


def figure_3(final, numbers):
    """Pooled flow diagrams with costs: lockstep link and the two cost-to-bid leak arrows."""
    fp = {x["cell"]: (i, x) for i, x in enumerate(final["fingerprints"]) if x["cohort"] == "registered"}
    panels = (("core.N0", "Honest market", "Firm A", "Firm B"),
              ("core.C1-SS", "Cartel that chats", "Firm A", "Firm B"),
              ("core.C2", "Cartel without chat", "Firm A", "Firm B"),
              ("core.E1", "Spy", "Spy", "Victim"))
    fig, axes = plt.subplots(1, 4, figsize=(6.6, 2.05), gridspec_kw=dict(wspace=.08))
    max_leak = max(max(fp[c][1]["terms"][k]["estimate"] for k in ("leak_to_member_1", "leak_to_member_2"))
                   for c, *_ in panels)
    for ax, (cell, title, name1, name2) in zip(axes, panels):
        i, x = fp[cell]
        terms = x["terms"]
        for key in ("action", "leak_to_member_1", "leak_to_member_2"):
            record(numbers, 3, cell, f"pooled {key} (bits)", terms[key], FINAL, f"fingerprints[{i}].terms.{key}",
                   x["markets"])
        ax.set(xlim=(0, 10), ylim=(0, 7))
        ax.axis("off")
        box(ax, 1.9, 3.4, 3.0, 1.5, name1, sub="bids")
        box(ax, 8.1, 3.4, 3.0, 1.5, name2, sub="bids")
        action = terms["action"]["estimate"]
        ax.plot([3.45, 6.55], [3.4, 3.4], color=ORANGE, lw=max(.4, 60 * action), alpha=.85 if action > .01 else .4,
                solid_capstyle="butt")
        for key, start, end, y, text in (("leak_to_member_2", (2.4, 1.75), (7.6, 2.5), .85, f"{name1}'s cost → {name2}'s bid"),
                                         ("leak_to_member_1", (7.6, 5.05), (2.4, 4.3), 5.95, f"{name2}'s cost → {name1}'s bid")):
            value, low = terms[key]["estimate"], terms[key]["low"]
            if value > 0 and low > 0:  # interval excludes zero; width proportional to the estimate
                arrow(ax, start, end, color=AQUA, lw=max(.3, 4.5 * value / max_leak), scale=6 + 7 * value / max_leak)
            else:
                arrow(ax, start, end, color=GREY, lw=.7, ls=(0, (2, 2)), scale=7)
            ax.text(5, y, text, ha="center", va="center", fontsize=5.4, color=TEXT_MUTED)
        ax.set_title(title, fontsize=7.6, weight="bold")
    fig.legend(handles=[Line2D([], [], color=ORANGE, lw=3, label="bids move in lockstep (thickness = strength)"),
                        Line2D([], [], color=AQUA, lw=2.5, label="a firm's cost shows up in the other's bids"),
                        Line2D([], [], color=GREY, lw=.8, ls=(0, (2, 2)), label="no clear flow (interval includes zero)")],
               loc="lower center", ncol=3, fontsize=6.2, bbox_to_anchor=(.5, -.02))
    fig.subplots_adjust(left=.01, right=.99, top=.86, bottom=.12)
    save(fig, "figure_3")


def figure_4(final, numbers):
    """Detection: chance that a treated market looks more suspicious than its honest twin."""
    cells = [("core.C1-SS", "cartel\n2 strong"), ("core.C1-SF", "cartel\nstrong+weak"),
             ("core.C1-FF", "cartel\n2 weak"), ("core.C2", "cartel\nno chat"), ("core.E1", "spy")]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.35), sharey=True, gridspec_kw=dict(wspace=.08))
    for ax, level in zip(axes, ("L1", "L2")):
        for k, (cell, label) in enumerate(cells):
            for offset, detector, color in ((-.19, "net", BLUE), (.19, "correlation", ORANGE)):
                i, r = cell_row(final, cell, level, detector)
                v = r["auroc"]["estimate"]
                ax.bar(k + offset, v, width=.36, color=color, lw=0)
                ax.text(k + offset, v + .015, f"{round(100 * v)}", ha="center", va="bottom", fontsize=5.8, color=color)
                record(numbers, 4, f"{cell} {level} {detector}", "AUROC", r["auroc"], FINAL, f"all_cells[{i}].auroc",
                       r["auroc"]["n_blocks"])
        ax.axhline(.5, color=TEXT_MUTED, lw=.8, ls=":")
        ax.set_xticks(range(len(cells)))
        ax.set_xticklabels([label for _, label in cells], fontsize=6.3)
        ax.set(xlim=(-.6, 4.5), ylim=(0, 1.12), yticks=[0, .25, .5, .75, 1])
        ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=6)
        ax.grid(axis="x", visible=False)
        ax.set_title(f"Auditor sees {LEVELS[level]}", fontsize=7.6)
    axes[0].set_ylabel("cartel market looks more\nsuspicious than honest twin", fontsize=6.6)
    fig.legend(handles=[Patch(color=BLUE, label="net influence (paper's method)"),
                        Patch(color=ORANGE, label="simple correlation"),
                        Line2D([], [], color=TEXT_MUTED, lw=.8, ls=":", label="coin flip (50%)")],
               loc="lower center", ncol=3, fontsize=6.6, bbox_to_anchor=(.55, -.07))
    fig.subplots_adjust(left=.11, right=.99, top=.9, bottom=.25)
    save(fig, "figure_4")


def figure_5(final, judge24k, numbers):
    """(a) profit gain versus how often our rule caught the pair; (b) AI judge versus net influence."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(6.6, 2.25), gridspec_kw=dict(width_ratios=[1.35, 1], wspace=.55))
    cells = [("core.C1-SS", "Cartel: two strong"), ("core.C1-SF", "Cartel: strong + weak"),
             ("core.C1-FF", "Cartel: two weak"), ("core.C2", "Cartel without chat")]
    for y, (cell, label) in enumerate(cells):
        j, b = next((j, b) for j, b in enumerate(final["behaviour"]) if b["cohort"] == "registered"
                    and b["cell"] == cell and b["prefix"] == 200 and b["metric"] == "joint_profit")
        gain = b["paired_difference"]["estimate"]
        left.barh(y, gain, color=ORANGE if cell == "core.C2" else GREY, height=.6, lw=0)
        record(numbers, 5, cell, "joint profit gain per round vs honest", b["paired_difference"], FINAL,
               f"behaviour[{j}].paired_difference", b["n_blocks"])
        i, r = cell_row(final, cell, "L1", "net")
        caught = round(r["correct_unique"]["estimate"] * r["coverage"])
        record(numbers, 5, cell, "L1 net correct_unique", r["correct_unique"], FINAL,
               f"all_cells[{i}].correct_unique", r["coverage"])
        left.text(.47, y, f"{caught}/{r['coverage']}", ha="left", va="center", fontsize=6.3,
                  color=RED if caught == 0 else GREEN, weight="bold")
    left.axvline(0, color=TEXT_MUTED, lw=.7)
    left.set_yticks(range(len(cells)))
    left.set_yticklabels([label for _, label in cells], fontsize=6.6)
    left.set(xlim=(-.12, .62), ylim=(len(cells) - .5, -1.25))
    left.set_xlabel("extra profit of the pair per round", fontsize=6.6)
    left.tick_params(axis="x", labelsize=6)
    left.grid(axis="y", visible=False)
    left.set_title("a  The most profitable cartel was the quietest", loc="left", fontsize=7.6)
    left.text(.47, -.85, "alarm named it\n(bids only)", ha="left", va="center", fontsize=5.6, color=TEXT_MUTED)
    comps = {r["cell"]: (k, r) for k, r in enumerate(judge24k["judge_comparisons"])
             if r["cohort"] == "judge24k" and r["level"] == "L2" and r["detector"] == "net"}
    for x, cell in enumerate(("core.C1-SS", "core.C1-SF")):
        k, r = comps[cell]
        for offset, key, color in ((-.19, "judge_localisation", GREY), (.19, "detector_localisation", BLUE)):
            v = r[key]["top1"]["estimate"]
            right.bar(x + offset, v, width=.36, color=color, lw=0)
            right.text(x + offset, v + .02, f"{round(100 * v)}%", ha="center", va="bottom", fontsize=6, color=TEXT)
            record(numbers, 5, cell, f"{key} top1 (24k judge cohort)", r[key]["top1"], JUDGE24K,
                   f"judge_comparisons[{k}].{key}.top1", r[key]["n_markets"])
    right.set_xticks([0, 1])
    right.set_xticklabels(["Cartel:\ntwo strong", "Cartel:\nstrong + weak"], fontsize=6.4)
    right.set(ylim=(0, 1.32), yticks=[0, .5, 1])
    right.set_yticklabels(["0%", "50%", "100%"], fontsize=6)
    right.set_ylabel("named the right pair first", fontsize=6.6)
    right.grid(axis="x", visible=False)
    right.legend(handles=[Patch(color=GREY, label="AI judge"), Patch(color=BLUE, label="net influence")],
                 fontsize=6.2, loc="upper center", ncol=2, handlelength=1, borderaxespad=0)
    right.set_title("b  The AI judge just picks the strong firms", loc="left", fontsize=7.6)
    fig.subplots_adjust(left=.19, right=.99, top=.84, bottom=.2)
    save(fig, "figure_5")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    final, judge24k = load(FINAL), load(JUDGE24K)
    assert final["development"] is False and judge24k["development"] is False
    assert final["analysis_freeze_commit"] == judge24k["analysis_freeze_commit"]
    apply_style()
    plt.rcParams.update({"font.size": 7, "axes.titlesize": 8, "axes.labelsize": 7,
                         "pdf.fonttype": 42, "ps.fonttype": 42, "axes.titleweight": "bold"})
    numbers = []
    figure_1()
    figure_2(final, numbers)
    figure_3(final, numbers)
    figure_4(final, numbers)
    figure_5(final, judge24k, numbers)
    with (OUT / "key_figure_numbers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(numbers[0]))
        writer.writeheader()
        writer.writerows(numbers)
    print(json.dumps({"recorded_numbers": len(numbers)}))


if __name__ == "__main__":
    main()
