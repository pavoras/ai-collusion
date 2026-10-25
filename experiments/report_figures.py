"""Render the frozen final analysis; no model calls or statistical refitting.

--quick deliberately produces the same numbers and figures as the full run.
All uncertainty and random seeds belong to the frozen upstream analysis.
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from collusion.plotting import apply_style, BLUE, ORANGE, AQUA

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "results/analysis/final_v1/results.json"
JUDGE24K = "results/analysis/judge24k_v23/results.json"  # Addendum v2.3 cohort
OUT = ROOT / "results/report_figures"
SECTIONS = ROOT / "report/sections"
COLORS = {"net": BLUE, "correlation": ORANGE, "leak": AQUA,
          "strength": AQUA, "judge:qwen-9b": "#52514e", "paper": "#52514e"}
MARKERS = {"net": "o", "correlation": "s", "leak": "^",
           "strength": "^", "judge:qwen-9b": "D", "paper": "D"}
NAMES = {"net": "Net", "correlation": "Correlation", "leak": "Leak",
         "strength": "Strength", "judge:qwen-9b": "Qwen judge", "paper": "Paper rule"}
LABELS = ["both directions detected", "one direction detected, reverse weak",
          "neither detected, both weak", "unclear"]
CELLS = [("core.P0", "P0"), ("core.C1-SS", "C1-SS"),
         ("core.C1-SF", "C1-SF"), ("core.C1-FF", "C1-FF"),
         ("core.C1-NW", "C1-NW"), ("core.C2", "C2 (no channel)"),
         ("core.E1", "E1 (espionage)"),
         ("labs.gemma-12b.C1", "Gemma-12B"),
         ("labs.ministral-8b.C1", "Ministral-8B"),
         ("sizes.qwen-4b.C1", "Qwen-4B"),
         ("mixed.C1-XX", "Mixed XX"), ("mixed.C1-XY", "Mixed XY")]


def tex(value):
    """Escape plain labels, with optional breaks in long identifiers."""
    return str(value).replace("/", r"/\allowbreak ").replace(".", r".\allowbreak ").replace("_", r"\_\allowbreak ").replace("%", r"\%").replace("&", r"\&")


def interval(value, digits=3):
    if not value or value.get("estimate") is None:
        return "--"
    return (f"{value['estimate']:.{digits}f} "
            f"[{value['low']:.{digits}f}, {value['high']:.{digits}f}]")


def estimate(value):
    return "--" if not value else f"{value['estimate']:.3f}"


def source(path):
    return f"% source: {SOURCE} {path}"


def row(data, cell, level, detector, prefix=200, mask="complete"):
    matches = [(i, r) for i, r in enumerate(data["all_cells"])
               if (r["cohort"], r["cell"], r["prefix"], r["mask"], r["level"], r["detector"])
               == ("registered", cell, prefix, mask, level, detector)]
    assert len(matches) == 1, (cell, level, detector, prefix, mask)
    return matches[0]


def point(ax, value, y, detector, hollow=False):
    """Draw endpoints directly, allowing biased percentile intervals."""
    ax.plot([value["low"], value["high"]], [y, y], color=COLORS[detector], lw=1)
    ax.plot(value["estimate"], y, marker=MARKERS[detector], color=COLORS[detector],
            markerfacecolor="white" if hollow else COLORS[detector], ms=4, linestyle="none")


def record(numbers, figure, panel, cell, level, detector, metric, value, n, path, subset="all", source_file=SOURCE):
    numbers.append(dict(figure=figure, panel=panel, cell=cell, level=level,
                        detector=detector, metric=metric, subset=subset, n=n,
                        estimate=value["estimate"], low=value["low"], high=value["high"],
                        hits=value.get("hits"), source=f"{source_file} {path}"))


def save_figure(fig, name):
    for suffix in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{suffix}", metadata={"CreationDate": None} if suffix == "pdf" else None)
    shutil.copyfile(OUT / f"{name}.pdf", ROOT / f"report/figures/{name}.pdf")
    plt.close(fig)


def detector_figure(data, numbers):
    fig, axes = plt.subplots(1, 4, figsize=(6.5, 5.1), sharey=True,
                             gridspec_kw={"width_ratios": [1.3, .9, 1.3, .9]})
    positions = np.arange(len(CELLS), dtype=float)
    positions[6:] += .55
    positions[7:] += .55
    for j, level in enumerate(("L1", "L2")):
        ax, diff = axes[2*j:2*j+2]
        detectors = ("net", "correlation") if level == "L1" else ("net", "correlation", "leak")
        for y, (cell, label) in zip(positions, CELLS):
            counts = []
            for offset, detector in zip(np.linspace(-.23, .23, len(detectors)), detectors):
                i, r = row(data, cell, level, detector)
                v = r["auroc"]
                assert v is not None
                counts.append(v["n_blocks"])
                point(ax, v, y+offset, detector)
                record(numbers, "A", "AUROC", cell, level, detector, "auroc", v,
                       v["n_blocks"], f"all_cells[{i}].auroc")
            assert len(set(counts)) == 1
            if j == 0:
                ax.text(-.09, y, f"{label} ({counts[0]})", transform=ax.get_yaxis_transform(),
                        ha="right", va="center", fontsize=7)
            matches = [(i, r) for i, r in enumerate(data["contrasts"])
                       if r["cell"] == cell and r["prefix"] == 200 and r["mask"] == "complete"
                       and r["contrast"] == f"{level}:net minus {level}:correlation"]
            assert len(matches) == 1
            i, r = matches[0]
            point(diff, r["result"], y, "net")
            record(numbers, "A", "paired difference", cell, level, "net-correlation",
                   "auroc difference", r["result"], r["result"]["n_blocks"], f"contrasts[{i}].result")
        ax.set(title=f"{level}: AUROC", xlim=(-.03, 1.03), xticks=[0, .5, 1])
        diff.set(title="Net minus corr.", xlim=(-.6, .6), xticks=[-.5, 0, .5])
        ax.axvline(.5, color="#888888", ls=":", lw=.7)
        diff.axvline(0, color="#888888", ls=":", lw=.7)
    for ax in axes:
        ax.set_ylim(positions[-1]+.6, -.65)
        ax.set_yticks([])
        ax.tick_params(axis="x", labelsize=7)
        ax.axhline(positions[6]-.77, color="#aaaaaa", lw=.6)
        ax.axhline(positions[6]+.77, color="#aaaaaa", lw=.6)
        ax.grid(axis="y", visible=False)
    handles = [Line2D([], [], color=COLORS[d], marker=MARKERS[d], lw=1, label=NAMES[d])
               for d in ("net", "correlation", "leak")]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=8, bbox_to_anchor=(.60, -.01))
    fig.subplots_adjust(left=.25, right=.99, bottom=.10, top=.92, wspace=.25)
    save_figure(fig, "figure_a")


def localisation_figure(data, judge24k, numbers):
    """Top: all eligible markets. Middle: L2 judge-matched markets, registered 12k judge vs 24k judge."""
    fig = plt.figure(figsize=(6.5, 5.5))
    grid = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.1], hspace=.85, wspace=.85)
    detectors = ("net", "correlation", "strength", "judge:qwen-9b")
    for j, level in enumerate(("L1", "L2")):
        ax = fig.add_subplot(grid[0, j])
        labels = []
        for y, suffix in enumerate(("SS", "SF", "FF")):
            cell = f"core.C1-{suffix}"
            labels.append(f"{suffix} (n=20)")
            for offset, detector in zip(np.linspace(-.27, .27, 3), detectors[:3]):
                i, r = row(data, cell, level, detector)
                point(ax, r["top1"], y+offset, detector)
                record(numbers, "B", "localisation", cell, level, detector, "top1", r["top1"],
                       r["coverage"], f"all_cells[{i}].top1", "all")
        ax.set(yticks=range(3), yticklabels=labels, xlim=(-.05, 1.05),
               xticks=[0, .5, 1], ylim=(2.5, -.5), title=f"{level}: all eligible markets")
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", visible=False)
    for j, (source_data, source_file, cohort, title, subset) in enumerate((
            (data, SOURCE, "registered", "L2: 12k judge, matched", "judge matched"),
            (judge24k, JUDGE24K, "judge24k", "L2: 24k judge, matched", "judge24k matched"))):
        ax = fig.add_subplot(grid[1, j])
        labels = []
        for y, suffix in enumerate(("SS", "SF", "FF")):
            cell = f"core.C1-{suffix}"
            js = [(i, r) for i, r in enumerate(source_data["judge_comparisons"])
                  if (r["cohort"], r["cell"], r["level"]) == (cohort, cell, "L2")]
            if not js:
                labels.append(f"{suffix} (not run)")
                continue
            labels.append(f"{suffix} (n={js[0][1]['judge_localisation']['n_markets']})")
            for offset, detector in zip(np.linspace(-.27, .27, 4), detectors):
                i, r = next((i, r) for i, r in js if r["detector"] ==
                            ("net" if detector == "judge:qwen-9b" else detector))
                key = "judge_localisation" if detector == "judge:qwen-9b" else "detector_localisation"
                v = r[key]["top1"]
                point(ax, v, y+offset, detector, hollow=True)
                record(numbers, "B", "localisation", cell, "L2", detector, "top1", v,
                       r[key]["n_markets"], f"judge_comparisons[{i}].{key}.top1", subset, source_file)
        ax.set(yticks=range(3), yticklabels=labels, xlim=(-.05, 1.05),
               xticks=[0, .5, 1], ylim=(2.5, -.5), title=title)
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", visible=False)
    for j, metric in enumerate(("any_candidate", "exactly_one_report")):
        ax = fig.add_subplot(grid[2, j])
        labels = []
        for y, (level, detector) in enumerate((("L1", "net"), ("L2", "net"),
                                              ("L2", "leak"), ("L2", "paper"))):
            i, r = row(data, "core.N0", level, detector)
            v = r[metric]
            point(ax, v, y, detector)
            labels.append(f"{level} {detector}: {v['hits']}/{v['total']}")
            record(numbers, "B", "honest N0", "core.N0", level, detector, metric,
                   v, v["total"], f"all_cells[{i}].{metric}")
        ax.set(yticks=range(4), yticklabels=labels, xlim=(-.05, 1.05),
               xticks=[0, .5, 1], ylim=(3.5, -.5), xlabel="Fraction of honest markets",
               title="Any candidate" if j == 0 else "Exactly one report")
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", visible=False)
    handles = [Line2D([], [], color=COLORS[d], marker=MARKERS[d], lw=1, label=NAMES[d]) for d in detectors]
    fig.legend(handles=handles, loc="upper center", ncol=4, fontsize=7, bbox_to_anchor=(.57, 1.015))
    alarm_handles = [Line2D([], [], color=COLORS[d], marker=MARKERS[d], lw=1, label=NAMES[d])
                     for d in ("net", "leak", "paper")]
    fig.legend(handles=alarm_handles, loc="lower center", ncol=3, fontsize=7, bbox_to_anchor=(.57, -.005))
    fig.subplots_adjust(left=.19, right=.99, top=.90, bottom=.13)
    save_figure(fig, "figure_b")


def write_tex(name, lines):
    (SECTIONS / name).write_text("\n".join(lines)+"\n", encoding="utf-8")


def behaviour_table(data):
    lines = [r"\begin{table}[tb]\centering\small", r"\caption{Behaviour and designated-pair flow labels. Differences are treatment minus matched N0, in game units per round, with pointwise 95\% intervals. Flow counts are both / one (reverse weak) / neither (both weak) / unclear / unavailable. E1 is unilateral access.}",
             r"\label{tab:behaviour}", r"\begin{tabular}{@{}llll@{}}\toprule",
             r"Cell & Joint profit difference & Winning price difference & Flow counts \\\midrule"]
    for cell in ("core.C1-SS", "core.C2", "core.E1", "core.C1-NW"):
        values = []
        for metric in ("joint_profit", "winning_price"):
            i, r = next((i, r) for i, r in enumerate(data["behaviour"])
                        if r["cell"] == cell and r["prefix"] == 200 and r["mask"] == "complete" and r["metric"] == metric)
            values.append(interval(r["paired_difference"]))
            lines.append(source(f"behaviour[{i}].paired_difference; n_blocks"))
        i, r = row(data, cell, "L2", "net")
        counts = " / ".join(str(r[f"label:{label}"]) for label in LABELS+["unavailable"])
        lines.extend([source(f"all_cells[{i}].label:*"),
                      f"{cell.removeprefix('core.')} & {' & '.join(values)} & {counts}"+r"\\"])
    lines.extend([r"\bottomrule\end{tabular}", r"\end{table}"])
    write_tex("behaviour_table.tex", lines)


def longtable_start(caption, columns, header):
    return [r"\begingroup\footnotesize\setlength{\tabcolsep}{3pt}",
            r"\begin{longtable}{"+columns+"}", r"\caption{"+caption+r"}\\",
            r"\toprule "+header+r"\\\midrule\endfirsthead",
            r"\toprule "+header+r"\\\midrule\endhead",
            r"\bottomrule\endfoot"]


def all_cells_table(data):
    lines = longtable_start("All registered cells at the full prefix and complete mask. See the surrounding text for column definitions.",
                            "@{}lp{.6in}p{1.35in}p{1.25in}p{1.5in}@{}",
                            "Level / detector & Cov./n & AUROC [interval] & Top-1 [interval] & Unique / wrong / abstain")
    current = None
    for i, r in enumerate(data["all_cells"]):
        if r["prefix"] != 200 or r["mask"] != "complete":
            continue
        if r["cell"] != current:
            current = r["cell"]
            lines.extend([source(f"all_cells[{i}]"), r"\midrule",
                          r"\multicolumn{5}{@{}l}{\textbf{"+tex(current)+"}; "
                          + f"declared {r['declared']}, collected {r['collected']}, missing {r['uncollected']}, "
                          + f"ineligible {r['ineligible']}, eligible {r['eligible']}"+r"}\\*"])
        detector = r["detector"].replace("correlation", "corr.").replace("judge:qwen-9b", "Q judge").replace("judge:gemma-12b", "G judge")
        n = r["auroc"]["n_blocks"] if r["auroc"] else "--"
        rates = " / ".join(estimate(r[k]) for k in ("correct_unique", "wrong_pair", "abstention"))
        lines.extend([source(f"all_cells[{i}]"),
                      f"{r['level']} {tex(detector)} & {r['coverage']}/{n} & {interval(r['auroc'])} & {interval(r['top1'])} & {rates}"+r"\\*"])
        flow = "/".join(str(r[f"label:{k}"]) for k in LABELS+["unavailable"])
        pipe = "/".join(str(r[f"pipeline_label:{k}"]) for k in LABELS+["no pair"])
        alarms = "; ".join(f"{name} {r[key]['hits']}/{r[key]['total']} [{r[key]['low']:.3f}, {r[key]['high']:.3f}]"
                           for name, key in (("any", "any_candidate"), ("one", "exactly_one_report"), ("ref.", "designated_alarm")) if r[key])
        lines.append(r"\multicolumn{5}{@{}p{6.2in}@{}}{MRR "+interval(r["mrr"])
                     + f"; flow {flow}; pipeline {pipe}."+(" Alarms: "+alarms if alarms else "")+r"}\\")
    lines.extend([r"\end{longtable}\endgroup"])
    write_tex("all_cells_table.tex", lines)


def addendum_tables(data):
    a1 = data["addendum"]["A1"]
    lines = longtable_start("A1: warning removed minus warning present. Judge rows use only complete judged triplets; other full rows use all eligible triplets.",
                            "@{}p{3.2in}rp{2.1in}@{}", r"Endpoint / subset & n & Difference [95\% interval]")
    groups = [("All", a1, len(a1["indices"]), "addendum.A1")]
    groups += [(f"Judge {level} subset", v, v["covered_blocks"],
                f"addendum.A1.judge_coverage_and_matched_comparisons.{level}")
               for level, v in a1["judge_coverage_and_matched_comparisons"].items()]
    for name, values, n, path in groups:
        for group in ("auroc_differences", "behaviour_NW_minus_SS"):
            for key, value in values[group].items():
                count = n
                if name == "All" and "judge:" in key:
                    count = a1["judge_coverage_and_matched_comparisons"][key[:2]]["covered_blocks"]
                label = key.replace("relative_profit_uplift_difference", "relative uplift").replace("judge:qwen-9b", "Q judge")
                lines.extend([source(f"{path}.{group}.{key}"),
                              f"{tex(name+': '+label)} & {count} & {interval(value, 4)}"+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    write_tex("a1_table.tex", lines)

    a2 = data["addendum"]["A2"]
    lines = longtable_start("A2: registered placement-swap tests. None rejects after Holm correction across the registered endpoints.",
                            "@{}lrlrr@{}", r"Endpoint & n & Mean T [95\% interval] & Raw p & Holm p")
    for key, value in a2["endpoints"].items():
        lines.extend([source(f"addendum.A2.endpoints.{key}"),
                      f"{tex(key.replace('judge:qwen-9b', 'Q judge'))} & {value['test']['n_blocks']} & {interval(value['mean_T'], 5)} & {value['test']['p_value']:.5f} & {value['holm_p_value']:.5f}"+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    lines += longtable_start("A2 descriptive companions: original-cell interaction D and per-twin-pair contrasts. Counts are contributing matched cell/twin blocks.",
                             "@{}p{1.8in}rl l@{}", r"Endpoint / twin & n & Mean T [95\% interval] & D [95\% interval]")
    for key, v in a2["endpoints"].items():
        label = key.replace("judge:qwen-9b", "Q judge")
        lines.extend([source(f"addendum.A2.endpoints.{key}"),
                      f"{tex(label)} / pooled & {v['test']['n_blocks']} & {interval(v['mean_T'], 4)} & {interval(v['D_original_cells'], 4)}"+r"\\"])
        for twin, result in v["per_twin_pair"].items():
            lines.extend([source(f"addendum.A2.endpoints.{key}.per_twin_pair.{twin}; coverage.{twin}"),
                          f"{tex(label)} / {twin} & {v['coverage'][twin]['covered_blocks']} & {interval(result['mean_T'], 4)} & {interval(result['D_original_cell'], 4)}"+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    lines += longtable_start("A2 on each successful judge subset: descriptive detector companions, without an additional Holm family.",
                             "@{}p{1.8in}rl l@{}", r"Judge / detector / twin & n & Mean T [95\% interval] & D [95\% interval]")
    for level, group in a2["judge_coverage_and_matched_comparisons"].items():
        for detector, v in group.items():
            path = f"addendum.A2.judge_coverage_and_matched_comparisons.{level}.{detector}"
            for twin, result in [("pooled", v)]+list(v["per_twin_pair"].items()):
                n = v["test"]["n_blocks"] if twin == "pooled" else v["coverage"][twin]["covered_blocks"]
                d_key = "D_original_cells" if twin == "pooled" else "D_original_cell"
                lines.extend([source(path+("" if twin == "pooled" else f".per_twin_pair.{twin}")),
                              f"{tex(level+'/'+detector+'/'+twin)} & {n} & {interval(result['mean_T'], 4)} & {interval(result[d_key], 4)}"+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    lines += [r"\begin{center}\begin{tabular}{lll}\toprule Endpoint & Same-model candidates & Different-model candidates \\\midrule"]
    for key, v in a2["candidate_rates"].items():
        values = [rf"{s['hits']}/{s['pair_opportunities']} ({100*s['rate']:.3f}\%)" for s in v.values()]
        lines.extend([source(f"addendum.A2.candidate_rates.{key}"), tex(key)+" & "+" & ".join(values)+r"\\"])
    lines.append(r"\bottomrule\end{tabular}\end{center}")
    write_tex("a2_tables.tex", lines)


def judge_tables(data):
    counts = Counter((j["model"], j["cell"], j["level"], j["status"], j["failure"]) for j in data["judgments"])
    lines = longtable_start("Judge completion and content failures, including every attempted cell and access level. Invalid entries failed to return valid JSON under the registered budget and retry rule.",
                            "@{}llrrr@{}", "Judge / cell & Level & Total & Valid & Invalid JSON")
    groups = sorted(set(k[:3] for k in counts))
    for model, cell, level in groups:
        js = [j for j in data["judgments"] if (j["model"], j["cell"], j["level"]) == (model, cell, level)]
        valid = sum(j["status"] == "complete" for j in js)
        assert all(j["status"] == "complete" or j["failure"] == "invalid_judge_json" for j in js)
        lines.extend([source(f"judgments grouped by model={model}, cell={cell}, level={level}, status/failure"),
                      f"{tex(model+'/'+cell)} & {level} & {len(js)} & {valid} & {len(js)-valid}"+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    lines += longtable_start("Judge comparisons on identical successful matched blocks. Tiny or degenerate intervals do not imply precision.",
                             "@{}p{1.9in}rl l@{}", "Cell / level / detector & n & Detector AUROC [interval] & Judge AUROC [interval]")
    for i, r in enumerate(data["judge_comparisons"]):
        lines.extend([source(f"judge_comparisons[{i}]"),
                      f"{tex(r['cell']+'/'+r['level']+'/'+r['detector'])} & {r['judge_auroc']['n_blocks']} & {interval(r['detector_auroc'])} & {interval(r['judge_auroc'])}"+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    lines += longtable_start("Judge Brier scores on matched discrimination samples; prevalence is the artificial treatment/control balance, not real-world collusion prevalence.",
                             "@{}lrrr@{}", "Cell / level / judge & n & Brier & Prevalence")
    for i, r in enumerate(data["all_cells"]):
        if r["prefix"] == 200 and r["mask"] == "complete" and r.get("brier") is not None:
            lines.extend([source(f"all_cells[{i}].brier, artificial_prevalence, auroc.n_blocks"),
                          f"{tex(r['cell']+'/'+r['level']+'/'+r['detector'].replace('judge:', ''))} & {r['auroc']['n_blocks']} & {r['brier']:.4f} & {r['artificial_prevalence']:.3f}"+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    write_tex("judge_tables.tex", lines)


def sensitivity_and_fingerprints(data):
    lines = longtable_start(r"Prefix and missing-bid sensitivity for every available treatment comparison. Each entry is AUROC; exact intervals, exclusions and other metrics for every prefix/mask are in all\_cells.md.",
                            "@{}p{2.2in}lrrrr@{}", "Cell / level / detector & Mask & n (full) & Prefix 50 & 100 & 200")
    for cell, _ in CELLS:
        for level, detector in (("L1", "net"), ("L1", "correlation"), ("L2", "net"), ("L2", "correlation"), ("L2", "leak")):
            for mask in sorted(set(r["mask"] for r in data["all_cells"])):
                selected = [row(data, cell, level, detector, p, mask) for p in (50, 100, 200)]
                values = [estimate(r["auroc"]) for _, r in selected]
                n = selected[-1][1]["auroc"]["n_blocks"] if selected[-1][1]["auroc"] else 0
                lines.extend([source(", ".join(f"all_cells[{i}].auroc" for i, _ in selected)),
                              f"{tex(cell+'/'+level+'/'+detector)} & {tex(mask)} & {n} & "+" & ".join(values)+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    write_tex("sensitivity_table.tex", lines)
    lines = longtable_start("Pooled flow estimates in bits, per cell and term (descriptive). \\emph{action}: lockstep between the pair's bids; \\emph{leak\\_to\\_member\\_1}: member 2's cost in member 1's bids, and vice versa. An asterisk marks a point estimate outside its percentile interval (see text above); values are shown as frozen, not refitted.",
                            "@{}p{2.6in}rl@{}", r"Cell / term & Markets & Estimate [95\% interval]")
    flags = []
    for i, r in enumerate(data["fingerprints"]):
        for term, v in r["terms"].items():
            flag = not v["low"] <= v["estimate"] <= v["high"]
            if flag:
                flags.append(f"fingerprints[{i}].terms.{term}")
            lines.extend([source(f"fingerprints[{i}].terms.{term}; markets"),
                          f"{tex(r['cell']+'/'+term)} & {r['markets']} & {interval(v, 5)}"+(" *" if flag else "")+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    write_tex("fingerprint_table.tex", lines)
    return flags


def replication_and_checksums():
    lines = longtable_start("Scripted RPS detection percentages: published values versus our previous-state and no-state replications.",
                            "@{}rrrrr@{}", "Coordination probability & Games & Paper & Previous state & No state")
    with (ROOT / "results/rps/cda.csv").open(encoding="utf-8") as handle:
        for i, r in enumerate(csv.DictReader(handle)):
            lines.extend([f"% source: results/rps/cda.csv row[{i}]",
                          " & ".join(r[k] for k in ("cp", "n_games", "cda_paper", "cda_ours_prev_state", "cda_ours_no_state"))+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    lines += longtable_start("Scripted RPS honest-market any-pair alarm rates (coordination probability zero). This is a separate simulation, not LLM calibration.",
                             "@{}lrrr@{}", "State & Games & Fixed threshold & Permutation rule")
    with (ROOT / "results/rps/calibration.csv").open(encoding="utf-8") as handle:
        for i, r in enumerate(csv.DictReader(handle)):
            if float(r["cp"]) == 0:
                lines.extend([f"% source: results/rps/calibration.csv row[{i}]",
                              " & ".join(r[k] for k in ("state", "n_games", "fixed_any_alarm", "calibrated_any_alarm"))+r"\\"])
    lines.append(r"\end{longtable}\endgroup")
    write_tex("replication_table.tex", lines)
    paths = [SOURCE, "results/analysis/final_v1/all_cells.md",
             "experiments/manifests/collection_v2.json", "results/analysis_runs.json",
             "results/llm/judge_index_registered.json", "results/llm/probe_index.json",
             "src/collusion/llm/prompts.py", "src/collusion/analysis/io.py", JUDGE24K]
    digests = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    (OUT / "input_checksums.json").write_text(json.dumps(digests, indent=2)+"\n", encoding="utf-8")
    lines = [r"\paragraph{Input SHA-256 digests.} These are file-byte digests; the manifest's canonical content hash above is a different convention."]
    for path, digest in digests.items():
        lines += [f"% source: SHA-256 of {path}", r"\noindent\path{"+path+r"}\\",
                  r"\path{"+digest+r"}\par"]
    write_tex("checksums.tex", lines)


def source_ledger():
    """Export the manuscript's source annotations alongside printed numbers."""
    records = []
    generated = {"all_cells_table.tex", "behaviour_table.tex", "a1_table.tex", "a2_tables.tex",
                 "judge_tables.tex", "sensitivity_table.tex", "fingerprint_table.tex",
                 "replication_table.tex", "checksums.tex"}
    for path in sorted(SECTIONS.glob("*.tex")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if path.name in generated:
            references = []
            previous_comment = False
            for i, line in enumerate(lines, 1):
                if line.startswith("% source:"):
                    if not previous_comment:
                        references = []
                    references.append(line.removeprefix("% source: "))
                    previous_comment = True
                else:
                    previous_comment = False
                    if references and re.search(r"\d", line):
                        records.append(dict(file=str(path.relative_to(ROOT)), line=i,
                                            printed_tex=line, source="; ".join(references)))
        else:
            for block in "\n".join(lines).split("\n\n"):
                refs = [line.removeprefix("% source: ") for line in block.splitlines() if line.startswith("% source:")]
                if refs:
                    records.append(dict(file=str(path.relative_to(ROOT)), line="paragraph",
                                        printed_tex=" ".join(line for line in block.splitlines() if not line.startswith("%")),
                                        source="; ".join(refs)))
    with (OUT / "number_sources.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "line", "printed_tex", "source"])
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="Same frozen data; no resampling in either mode")
    parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (ROOT / "report/figures").mkdir(parents=True, exist_ok=True)
    data = json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    assert data["development"] is False
    assert data["primary"]["status"] == "available"
    assert data["analysis_freeze_commit"].startswith("4c4b6f1")
    apply_style()
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
                         "pdf.fonttype": 42, "ps.fonttype": 42, "axes.titleweight": "bold"})
    numbers = []
    detector_figure(data, numbers)
    judge24k = json.loads((ROOT / JUDGE24K).read_text(encoding="utf-8"))
    assert judge24k["development"] is False and judge24k["analysis_freeze_commit"] == data["analysis_freeze_commit"]
    localisation_figure(data, judge24k, numbers)
    with (OUT / "figure_numbers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(numbers[0]))
        writer.writeheader()
        writer.writerows(numbers)
    (OUT / "figure_numbers.json").write_text(json.dumps(numbers, indent=2)+"\n", encoding="utf-8")
    behaviour_table(data)
    all_cells_table(data)
    addendum_tables(data)
    judge_tables(data)
    flags = sensitivity_and_fingerprints(data)
    replication_and_checksums()
    source_ledger()
    provenance = {"source": SOURCE, "sha256": hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest(),
                  "analysis_freeze_commit": data["analysis_freeze_commit"],
                  "execution_revision": "7ca459c", "execution_revision_source": "Round 14 handover; deviation 5g",
                  "settings": data["settings"], "bootstrap": data["bootstrap"],
                  "figure_rows": len(numbers), "fingerprint_interval_flags": flags,
                  "randomness": "None: renders frozen estimates and intervals; --quick is identical."}
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"plotted_numbers": len(numbers), "source_sha256": provenance["sha256"],
                      "fingerprint_interval_flags": len(flags), "primary": data["primary"]}, indent=2))


if __name__ == "__main__":
    main()
