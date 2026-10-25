"""Plain-language main-text figures, rendered from frozen analysis outputs.

Figure 1: how the test works (schematic, no data).
Figure 2: how often an alarm rule named exactly the colluding pair, and false alarms.
Figure 3: which way information flows (pooled leak and action terms).
Figure 4: net influence versus a simple correlation (detection).
Figure 5: two warnings for practice (the quiet cartel; the AI judge's shortcut).
Figure 6: scripted-simulation expectations versus LLM observations.
Figure 7: rounds needed, and other bidder models.

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
GREEN, RED, GREY, LIGHT, GRID_LINE = "#1f9e60", "#d9483b", "#c9c8c3", "#f4f3ef", "#b9b8b3"
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
    """Pooled flow diagrams with costs: lockstep band and cost-to-bid arrows, with a one-line verdict."""
    from matplotlib.patches import Circle
    fp = {x["cell"]: (i, x) for i, x in enumerate(final["fingerprints"]) if x["cohort"] == "registered"}
    # (cell, title, names, verdict, expected pattern: lockstep?, flow B->A?, flow A->B?) -- asserted against the data
    panels = (("core.N0", "Honest market", ("A", "B"), "no link", (False, False, False)),
              ("core.C1-SS", "Cartel that chats", ("A", "B"), "lockstep, costs\nshared both ways", (True, True, True)),
              ("core.C2", "Cartel without chat", ("A", "B"), "only a weak trace", (False, False, True)),
              ("core.E1", "Spy", ("Spy", "Victim"), "one way: the spy\nuses the victim's cost", (False, True, False)))
    fig, axes = plt.subplots(1, 4, figsize=(6.6, 1.95), gridspec_kw=dict(wspace=.06))
    max_leak = max(max(fp[c][1]["terms"][k]["estimate"] for k in ("leak_to_member_1", "leak_to_member_2"))
                   for c, *_ in panels)
    for ax, (cell, title, (name1, name2), verdict, expected) in zip(axes, panels):
        i, x = fp[cell]
        terms = x["terms"]
        for key in ("action", "leak_to_member_1", "leak_to_member_2"):
            record(numbers, 3, cell, f"pooled {key} (bits)", terms[key], FINAL, f"fingerprints[{i}].terms.{key}",
                   x["markets"])
        clear = {k: terms[k]["estimate"] > 0 and terms[k]["low"] > 0 for k in ("leak_to_member_1", "leak_to_member_2")}
        lockstep = terms["action"]["estimate"] > .01
        assert (lockstep, clear["leak_to_member_1"], clear["leak_to_member_2"]) == expected, cell
        ax.set(xlim=(0, 10), ylim=(0, 10), aspect="equal")
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((.2, .2), 9.6, 9.6, boxstyle="round,pad=0,rounding_size=.6", fc=LIGHT, ec="none"))
        ax.text(5, 9.15, title, ha="center", va="center", fontsize=7.6, weight="bold", color=TEXT)
        positions = {1: (2.5, 4.2), 2: (7.5, 4.2)}
        for k, name in ((1, name1), (2, name2)):
            x0, y0 = positions[k]
            ax.add_patch(FancyBboxPatch((x0 - .95, 6.75), 1.9, .9, boxstyle="round,pad=.05,rounding_size=.3",
                                        fc="white", ec=TEXT_MUTED, lw=.7))
            ax.text(x0, 7.2, "cost", ha="center", va="center", fontsize=5.8, color=TEXT_MUTED)
            ax.plot([x0, x0], [6.7, 5.45], color=GREY, lw=.8)
            ax.add_patch(Circle((x0, y0), 1.25, fc="white", ec=TEXT, lw=1.0, zorder=3))
            ax.text(x0, y0 + .25, name, ha="center", va="center", fontsize=7 if len(name) < 5 else 6, weight="bold", color=TEXT, zorder=4)
            ax.text(x0, y0 - .38, "bids", ha="center", va="center", fontsize=5.6, color=TEXT_MUTED, zorder=4)
        action = terms["action"]["estimate"]
        ax.plot([3.75, 6.25], [4.2, 4.2], color=ORANGE if lockstep else GREY, lw=max(.6, 55 * action),
                solid_capstyle="butt", zorder=2)
        # leak_to_member_1: member 2's cost -> member 1's bids; leak_to_member_2: member 1's cost -> member 2's bids
        for key, start, end, rad in (("leak_to_member_1", (7.0, 6.75), (3.45, 5.05), .25),
                                     ("leak_to_member_2", (3.0, 6.75), (6.55, 5.05), -.25)):
            value = terms[key]["estimate"]
            if clear[key]:
                ax.add_patch(FancyArrowPatch(start, end, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                                             mutation_scale=7 + 6 * value / max_leak, lw=.8 + 3.2 * value / max_leak,
                                             color=AQUA, zorder=5, shrinkA=0, shrinkB=0))
            else:
                ax.add_patch(FancyArrowPatch(start, end, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                                             mutation_scale=6, lw=.6, color=GREY, ls=(0, (2, 2)), zorder=1,
                                             shrinkA=0, shrinkB=0))
        good = cell != "core.N0" and (lockstep or any(clear.values()))
        ax.text(5, 1.45, verdict, ha="center", va="center", fontsize=6.6, weight="bold",
                color=(AQUA if cell == "core.E1" else ORANGE) if good and cell != "core.C2" else TEXT_MUTED)
    fig.legend(handles=[Line2D([], [], color=ORANGE, lw=4, label="bids move in lockstep"),
                        Line2D([], [], color=AQUA, lw=2.2, marker=">", ms=4, label="a firm's cost shows up in the other's bids"),
                        Line2D([], [], color=GREY, lw=.8, ls=(0, (2, 2)), label="no clear flow")],
               loc="lower center", ncol=3, fontsize=6.4, bbox_to_anchor=(.5, -.03), handlelength=2)
    fig.subplots_adjust(left=.005, right=.995, top=1.0, bottom=.12)
    save(fig, "figure_3")


def figure_4(final, numbers):
    """Detection: chance that a treated market looks more suspicious than its honest twin."""
    cells = [("core.C1-SS", "cartel\n2 strong"), ("core.C1-SF", "cartel\nstrong+weak"),
             ("core.C1-FF", "cartel\n2 weak"), ("core.C2", "cartel\nno chat"), ("core.E1", "spy")]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.15), sharey=True, gridspec_kw=dict(wspace=.08))
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
    fig, (left, right) = plt.subplots(1, 2, figsize=(6.6, 2.1), gridspec_kw=dict(width_ratios=[1.35, 1], wspace=.55))
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


def figure_6(final, numbers):
    """Dumbbell chart: what the scripted simulation predicted versus what the LLM markets showed."""
    root = "results/auction_power/full"
    power = list(csv.DictReader((ROOT / root / "power.csv").open(encoding="utf-8")))
    leaks = list(csv.DictReader((ROOT / root / "leaks.csv").open(encoding="utf-8")))
    alarms = list(csv.DictReader((ROOT / root / "false_alarms.csv").open(encoding="utf-8")))

    def sim(rows, name, column, **keys):
        hits = [(i, r) for i, r in enumerate(rows) if all(r[a] == b for a, b in keys.items())]
        assert len(hits) == 1, keys
        i, r = hits[0]
        return float(r[column]), f"{root}/{name} row[{i}].{column}"

    base = dict(population="iid", rounds="200")
    items = []
    for level, name in (("L1", "bids only"), ("L2", "bids + costs")):
        v, path = sim(alarms, "false_alarms.csv", "pool_rate", level=level, endpoint="pair_family", n_requested="40", **base)
        i, r = cell_row(final, "core.N0", level, "net")
        items.append((f"Honest: false alarm ({name})", v, path, r["any_candidate"]["estimate"],
                      f"all_cells[{i}].any_candidate", True))
    for cell, position, label in (("core.C1-SS", "strong_strong", "Cartel, two strong"),
                                  ("core.C1-SF", "strong_fringe", "Cartel, strong + weak"),
                                  ("core.C1-FF", "fringe_fringe", "Cartel, two weak")):
        for level, name in (("L1", "bids only"), ("L2", "bids + costs")):
            v, path = sim(power, "power.csv", "detection_rate", condition="cartel", position=position, q="1.0",
                          level=level, n="20", **base)
            i, r = cell_row(final, cell, level, "net")
            items.append((f"{label}: right pair ({name})", v, path, r["correct_unique"]["estimate"],
                          f"all_cells[{i}].correct_unique", False))
    v, path = sim(power, "power.csv", "detection_rate", condition="spy", position="strong_strong", q="1.0",
                  level="L2", n="20", **base)
    i, r = cell_row(final, "core.E1", "L2", "net")
    items.append(("Spy: right pair (bids + costs)", v, path, r["correct_unique"]["estimate"],
                  f"all_cells[{i}].correct_unique", False))
    v, path = sim(leaks, "leaks.csv", "correct_rate", condition="cartel", position="strong_strong", q="1.0",
                  n="20", **base)
    i, r = cell_row(final, "core.C1-SS", "L2", "net")
    items.append(("Cartel, two strong: two-way flow seen", v, path,
                  r["label:both directions detected"] / r["eligible"], f"all_cells[{i}].label:both directions detected", False))
    v, path = sim(leaks, "leaks.csv", "correct_rate", condition="spy", position="strong_strong", q="1.0",
                  n="20", **base)
    i, r = cell_row(final, "core.E1", "L2", "net")
    items.append(("Spy: one-way flow seen", v, path,
                  r["label:one direction detected, reverse weak"] / r["eligible"],
                  f"all_cells[{i}].label:one direction detected, reverse weak", False))

    fig, ax = plt.subplots(figsize=(6.6, 2.2))
    for y, (label, expected, spath, observed, opath, honest) in enumerate(items):
        ax.plot([expected, observed], [y, y], color=GREY, lw=2.2, zorder=1, solid_capstyle="round")
        ax.plot(expected, y, "o", ms=6, mfc="white", mec=TEXT_MUTED, mew=1.2, zorder=2)
        ax.plot(observed, y, "o", ms=6, color=RED if honest and observed > .1 else BLUE, zorder=3)
        ax.text(1.04, y, f"{int(100 * expected + .5)}% → {int(100 * observed + .5)}%", va="center", ha="left",
                fontsize=6.2, color=TEXT_MUTED)
        record(numbers, 6, label, "simulation expectation", expected, *spath.split(" ", 1))
        record(numbers, 6, label, "LLM observation", observed, FINAL, opath)
    ax.set(xlim=(-.02, 1.02), ylim=(len(items) - .5, -.6), xticks=[0, .25, .5, .75, 1])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=6.2)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([item[0] for item in items], fontsize=6.6)
    ax.axhline(1.5, color=GRID_LINE, lw=.7)
    ax.axhline(7.5, color=GRID_LINE, lw=.7)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", mfc="white", mec=TEXT_MUTED, ms=6,
                              label="expected: scripted simulation (planned before data)"),
                       Line2D([], [], marker="o", ls="", color=BLUE, ms=6, label="observed: AI agents")],
              loc="lower center", bbox_to_anchor=(.45, 1.0), ncol=2, fontsize=6.4, borderaxespad=.3)
    ax.set_xlabel("share of markets (20 per type, 40 honest)", fontsize=6.6)
    fig.subplots_adjust(left=.31, right=.88, top=.9, bottom=.13)
    save(fig, "figure_6")


def figure_7(final, numbers):
    """(a) alarm hits versus observed rounds; (b) other bidder models: hits and honest-market false alarms."""
    def row_at(cell, level, detector, prefix):
        hits = [(i, r) for i, r in enumerate(final["all_cells"])
                if (r["cohort"], r["cell"], r["prefix"], r["mask"], r["level"], r["detector"])
                == ("registered", cell, prefix, "complete", level, detector)]
        assert len(hits) == 1
        return hits[0]

    fig, (left, right) = plt.subplots(1, 2, figsize=(6.6, 2.25), gridspec_kw=dict(width_ratios=[1.1, 1.3], wspace=.5))
    prefixes = (50, 100, 200)
    for cell, label, color, marker in (("core.C1-FF", "cartel: two weak", GREEN, "o"),
                                       ("core.C1-SS", "cartel: two strong", BLUE, "s"),
                                       ("core.C1-SF", "cartel: strong + weak", ORANGE, "^")):
        values = []
        for p in prefixes:
            i, r = row_at(cell, "L1", "net", p)
            values.append(r["correct_unique"]["estimate"])
            record(numbers, 7, f"{cell} L1 net prefix {p}", "correct_unique", r["correct_unique"], FINAL,
                   f"all_cells[{i}].correct_unique", r["coverage"])
        left.plot(prefixes, values, marker=marker, color=color, ms=4, lw=1.4, label=label)
        left.text(212, values[-1], label, va="center", fontsize=5.8, color=color)
    values = []
    for p in prefixes:
        i, r = row_at("core.N0", "L1", "net", p)
        values.append(r["any_candidate"]["estimate"])
        record(numbers, 7, f"core.N0 L1 net prefix {p}", "false alarm", r["any_candidate"], FINAL,
               f"all_cells[{i}].any_candidate", r["any_candidate"]["total"])
    left.plot(prefixes, values, marker="x", color=RED, ms=4, lw=1.2, ls="--", label="honest: false alarm")
    left.text(212, values[-1] + .03, "honest:\nfalse alarm", va="center", linespacing=.95, fontsize=5.8, color=RED)
    left.set(xticks=prefixes, xlim=(35, 330), ylim=(-.03, 1.05), yticks=[0, .5, 1])
    left.spines["bottom"].set_bounds(35, 215)
    left.set_yticklabels(["0%", "50%", "100%"], fontsize=6)
    left.tick_params(axis="x", labelsize=6)
    left.set_xlabel("rounds the auditor observes", fontsize=6.6)
    left.set_ylabel("markets with the right pair named", fontsize=6.4)
    left.set_title("a  Longer observation, more cartels found", loc="left", fontsize=7.4)

    models = (("core.C1-SS", "core.N0", "Qwen3.5-9B (main)"), ("sizes.qwen-4b.C1", "sizes.qwen-4b.N0", "Qwen3.5-4B"),
              ("labs.gemma-12b.C1", "labs.gemma-12b.N0", "Gemma-4-12B"),
              ("labs.ministral-8b.C1", "labs.ministral-8b.N0", "Ministral-3-8B"),
              ("mixed.C1-XX", "mixed.D", "Mixed: Qwen+Qwen cartel"),
              ("mixed.C1-XY", "mixed.H-XYZZ", "Mixed: Qwen+Gemma cartel"))
    for y, (cell, control, label) in enumerate(models):
        i, r = cell_row(final, cell, "L1", "net")
        hit = r["correct_unique"]["estimate"]
        record(numbers, 7, f"{cell} L1 net", "correct_unique", r["correct_unique"], FINAL,
               f"all_cells[{i}].correct_unique", r["coverage"])
        j, c = cell_row(final, control, "L1", "net")
        alarm = c["any_candidate"]
        record(numbers, 7, f"{control} L1 net", "false alarm", alarm, FINAL, f"all_cells[{j}].any_candidate",
               alarm["total"])
        right.barh(y - .19, hit, height=.36, color=GREEN, lw=0)
        right.barh(y + .19, alarm["estimate"], height=.36, color=RED, lw=0)
        right.text(hit + .02, y - .19, f"{round(hit * r['coverage'])}/{r['coverage']}", va="center", fontsize=5.6,
                   color=GREEN)
        right.text(alarm["estimate"] + .02, y + .19, f"{alarm['hits']}/{alarm['total']}", va="center", fontsize=5.6,
                   color=RED)
    right.set_yticks(range(len(models)))
    right.set_yticklabels([m[2] for m in models], fontsize=6.3)
    right.set(xlim=(0, 1.12), ylim=(len(models) - .5, -.6), xticks=[0, .5, 1])
    right.set_xticklabels(["0%", "50%", "100%"], fontsize=6)
    right.grid(axis="y", visible=False)
    right.tick_params(axis="y", length=0)
    right.legend(handles=[Patch(color=GREEN, label="cartel: right pair named"),
                          Patch(color=RED, label="honest: false alarm")],
                 fontsize=5.8, loc="upper center", bbox_to_anchor=(.45, -.1), ncol=2, handlelength=1, borderaxespad=.2)
    right.set_title("b  Other bidder models (bids only)", loc="left", fontsize=7.4)
    fig.subplots_adjust(left=.08, right=.99, top=.88, bottom=.19)
    save(fig, "figure_7")


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
    figure_6(final, numbers)
    figure_7(final, numbers)
    with (OUT / "key_figure_numbers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(numbers[0]))
        writer.writeheader()
        writer.writerows(numbers)
    print(json.dumps({"recorded_numbers": len(numbers)}))


if __name__ == "__main__":
    main()
