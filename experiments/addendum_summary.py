"""Summarise the Addendum v2.2 replication and v2.3 judge-budget check next to the original final_v1 values.

Reads only frozen analysis outputs (no model calls) and writes a JSON summary plus a LaTeX table for the report:

    .venv/Scripts/python experiments/addendum_summary.py --replication results/analysis/replication_v22/results.json \
        --judge results/analysis/judge24k_v23/results.json --out results/analysis/addendum_summary
"""

import argparse
import json
from pathlib import Path

FINAL = "results/analysis/final_v1/results.json"
PAIRS = [("E1", "core.E1", "rep.E1"), ("C2", "core.C2", "rep.C2"), ("C1-SS", "core.C1-SS", "rep.C1-SS")]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path and Path(path).exists() else None


def cell_row(d, cohort, cell, level, detector):
    return next((r for r in d["all_cells"] if r["cohort"] == cohort and r["cell"] == cell and r["level"] == level
                 and r["detector"] == detector and r["prefix"] == 200 and r["mask"] == "complete"), None)


def contrast(d, cohort, cell, name):
    return next((r["result"] for r in d["contrasts"] if r["cohort"] == cohort and r["cell"] == cell and r["contrast"] == name
                 and r["prefix"] == 200 and r["mask"] == "complete"), None)


def behaviour(d, cohort, cell, metric):
    row = next((r for r in d["behaviour"] if r["cohort"] == cohort and r["cell"] == cell and r["metric"] == metric
                and r["prefix"] == 200 and r["mask"] == "complete"), None)
    if row is None:
        return None
    diff = row["paired_difference"]
    return diff if isinstance(diff, dict) else json.loads(diff.replace("'", '"').replace("None", "null"))


def est(x):
    return None if not x else {k: x.get(k) for k in ("estimate", "low", "high", "n_blocks") if k in x}


def replication(final, rep):
    out = {}
    for name, original, replicated in PAIRS:
        entry = {}
        for label, d, cohort, cell in (("original", final, "registered", original), ("replication", rep, "replication", replicated)):
            if d is None or cell_row(d, cohort, cell, "L2", "net") is None:
                continue
            values = {f"{lvl}:{det}": est(cell_row(d, cohort, cell, lvl, det)["auroc"])
                      for lvl in ("L1", "L2") for det in ("net", "correlation", "paper") + (("leak",) if lvl == "L2" else ())}
            values["L1:net-correlation"] = est(contrast(d, cohort, cell, "L1:net minus L1:correlation"))
            values["L2:net-correlation"] = est(contrast(d, cohort, cell, "L2:net minus L2:correlation"))
            values["joint_profit"] = est(behaviour(d, cohort, cell, "joint_profit"))
            values["eligible"] = cell_row(d, cohort, cell, "L2", "net")["eligible"]
            entry[label] = values
        out[name] = entry
    verdicts = {}
    rep_e1 = out.get("E1", {}).get("replication")
    if rep_e1:
        verdicts["R1 E1 L2 net-correlation > 0"] = rep_e1["L2:net-correlation"]["low"] > 0
        verdicts["R1b E1 L1 net-correlation > 0"] = rep_e1["L1:net-correlation"]["low"] > 0
    rep_c2 = out.get("C2", {}).get("replication")
    if rep_c2:
        verdicts["R2 C2 joint profit uplift > 0"] = rep_c2["joint_profit"]["low"] > 0
    rep_ss = out.get("C1-SS", {}).get("replication")
    if rep_ss:
        verdicts["R4 C1-SS L2 net AUROC > 0.5"] = rep_ss["L2:net"]["low"] > 0.5
    return out, verdicts


def judge_summary(final, judge):
    if judge is None:
        return None
    def status(d, cohort):
        rows = [j for j in d["judgments"] if j.get("cohort") == cohort and j.get("level") == "L2" and j.get("model") == "qwen-9b"
                and j.get("cell") in ("core.N0", "core.C1-SS", "core.C1-SF") and j.get("market_index") in range(20)]
        return {"judgements": len(rows), "valid": sum(j.get("status") == "complete" for j in rows)}
    result = {"registered_12k": status(final, "registered"), "judge24k": status(judge, "judge24k")}
    for cell in ("core.C1-SS", "core.C1-SF", "core.N0"):
        for label, d, cohort in (("registered_12k", final, "registered"), ("judge24k", judge, "judge24k")):
            row = cell_row(d, cohort, cell, "L2", "judge:qwen-9b")
            result.setdefault(cell, {})[label] = {"coverage": row["coverage"] if row else None,
                                                   "auroc": est(row["auroc"]) if row else None,
                                                   "top1": est(row["top1"]) if row else None}
    comps = [c for d, cohort in ((final, "registered"), (judge, "judge24k")) for c in d["judge_comparisons"]
             if c["cohort"] == cohort and c["level"] == "L2" and c["cell"] in ("core.C1-SS", "core.C1-SF")
             and c["prefix"] == 200 and c["mask"] == "complete" and c["detector"] in ("net", "correlation")]
    result["matched_comparisons"] = [{"cohort": c["cohort"], "cell": c["cell"], "detector": c["detector"], "judge_auroc": est(c["judge_auroc"]),
                                      "detector_auroc": est(c["detector_auroc"]), "judge_minus_detector": est(c["difference"]),
                                      "n_markets": (c["judge_localisation"] or {}).get("n_markets"),
                                      "judge_top1": est((c["judge_localisation"] or {}).get("top1")),
                                      "detector_top1": est((c["detector_localisation"] or {}).get("top1"))} for c in comps]
    return result


def fmt(x, nd=3):
    if not x:
        return "--"
    return f"{x['estimate']:.{nd}f} [{x['low']:.{nd}f}, {x['high']:.{nd}f}]"


def latex(rep):
    lines = [r"\begin{table}[tb]", r"\centering\small", r"\setlength{\tabcolsep}{3pt}",
             r"\caption{Out-of-sample replication (Addendum v2.2). Original: registered markets 0--19; replication: fresh "
             r"treatment markets 20--39 against the registered N0 markets 20--39. Estimates with 95\% block-bootstrap "
             r"intervals (20 matched blocks). Profit is the paired joint-profit difference versus N0.}",
             r"\label{tab:replication}", r"\begin{tabular}{llccc}", r"\toprule",
             r"Cell & Sample & L2 net AUROC & L2 net $-$ corr. & Joint profit vs N0\\", r"\midrule"]
    for name in ("E1", "C2", "C1-SS"):
        for label in ("original", "replication"):
            v = rep.get(name, {}).get(label)
            if v:
                lines.append(f"{name} & {label} & {fmt(v['L2:net'])} & {fmt(v['L2:net-correlation'])} & {fmt(v['joint_profit'])}\\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--replication", required=True)
    p.add_argument("--judge")
    p.add_argument("--out", required=True)
    p.add_argument("--table", default="report/sections/addendum_table.tex")
    args = p.parse_args()
    final, rep, judge = load(FINAL), load(args.replication), load(args.judge)
    rep_values, verdicts = replication(final, rep)
    summary = {"sources": {"final": FINAL, "replication": args.replication, "judge": args.judge},
               "replication": rep_values, "preregistered_verdicts": verdicts, "judge_budget": judge_summary(final, judge)}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    Path(args.table).write_text(latex(rep_values), encoding="utf-8")
    print(json.dumps({"verdicts": verdicts, "judge": summary["judge_budget"] and {
        k: v for k, v in summary["judge_budget"].items() if k != "matched_comparisons"}}, indent=2))


if __name__ == "__main__":
    main()
