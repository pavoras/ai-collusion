"""Registered analysis orchestration and the all-cells publication table."""

from concurrent.futures import ProcessPoolExecutor
import csv
import json
from pathlib import Path
import time

import numpy as np

from collusion.llm.storage import digest
from .inference import (auc, block_weights, bootstrap_auc, bootstrap_mean, estimate,
                        exact_rate, localisation, primary_test)
from .market import LABELS, PAIRS, analyze_market, pooled_fingerprint
from .probes import analyze_probes


def clean(value):
    """Strict JSON: undefined diagonals/empty estimates become null, never NaN."""
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _parallel(function, tasks, workers):
    if workers == 1:
        return list(map(function, tasks))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(function, tasks, chunksize=1))


def _matched(markets, cell, prefix, mode, level, detector):
    """Return one fixed-target treatment/control score per eligible block."""
    result = []
    for key, treatment in sorted(markets.items()):
        if key[:2] != (cell["cohort"], cell["id"]) or not treatment["eligible"]:
            continue
        control = markets.get((cell["cohort"], cell["control"], key[2]))
        if control is None or not control["eligible"]:
            continue
        a, b = _view(treatment, prefix, mode), _view(control, prefix, mode)
        if not a or not b or detector not in a["levels"][level]["scores"] or detector not in b["levels"][level]["scores"]:
            continue
        target = PAIRS.index(tuple(sorted(treatment["assignment"]["designated_pair"])))
        result.append((key[2], b["levels"][level]["scores"][detector][target],
                       a["levels"][level]["scores"][detector][target]))
    return result


def _view(market, prefix, mode):
    return next((v for v in market["views"] if v["prefix"] == prefix and v["mask"] == mode), None)


def _auc_estimate(blocks, union, weights):
    if not blocks:
        return None, np.full(len(weights), np.nan)
    indices, negative, positive = map(np.asarray, zip(*blocks))
    w = weights[:, [union.index(i) for i in indices]]
    draws = bootstrap_auc(negative, positive, w)
    return {"n_blocks": len(blocks), **estimate(auc(negative, positive), draws)}, draws


def _contrast(a, b, union, weights):
    indices = sorted({r[0] for r in a} & {r[0] for r in b})
    if not indices:
        return None
    x, dx = _auc_estimate([r for r in a if r[0] in indices], union, weights)
    y, dy = _auc_estimate([r for r in b if r[0] in indices], union, weights)
    return {"n_blocks": len(indices), **estimate(x["estimate"] - y["estimate"], dx - dy)}


def _validate_matches(markets, cells):
    for cell in cells:
        if cell["control"] is None:
            continue
        for treatment in markets:
            if (treatment.cohort, treatment.cell) != (cell["cohort"], cell["id"]):
                continue
            control = next((m for m in markets if m.key == (cell["cohort"], cell["control"], treatment.index)), None)
            if control is None:
                continue
            for field in ("strong_seats", "labels", "model_to_seat"):
                if treatment.assignment[field] != control.assignment[field]:
                    raise ValueError(f"matched assignment mismatch: {field}")
            n = min(len(treatment.costs), len(control.costs))
            if not np.array_equal(treatment.costs[:n], control.costs[:n]):
                raise ValueError("matched costs differ")
            seeds = [m.run_metadata.get("identity", {}).get("config", m.run_metadata.get("config", {})).get("seed")
                     for m in (treatment, control)]
            if seeds[0] != seeds[1]:
                raise ValueError("matched seed differs")


def _attach_judges(markets, judgments, manifest=None):
    """Keep failures in the result and attach only raw successfully parsed scores."""
    for judgment in judgments:
        key = tuple(judgment[k] for k in ("cohort", "cell", "market_index"))
        if key not in markets:
            raise ValueError("judge refers to undeclared/unavailable market")
        if manifest and manifest.get("entries") and judgment["cohort"] == "registered":
            from collusion.llm.collection import indices_for
            allowed = [e for e in manifest["entries"] if e["phase"] == "judge" and
                       e["judge_model"] == judgment["model"] and judgment["level"] in e["levels"] and
                       (e["source_entries"] == "all_auction_entries" or
                        (judgment["cell"] in e["source_entries"] and judgment["market_index"] in indices_for(manifest, e)))]
            if not allowed or judgment["prefix"] != 200 or judgment["mask"] != "complete":
                raise ValueError("judge scope/view not declared; use a separate deviation cohort")
        market = markets[key]
        view = _view(market, judgment["prefix"], judgment["mask"])
        if view is None or judgment.get("probabilities") is None or judgment.get("status") != "complete":
            continue
        level = view["levels"][judgment["level"]]
        # Judgments name displayed labels, which need not match physical seat order.
        labels = [label.replace("Firm ", "") for label in market["assignment"]["labels"]]
        scores = [judgment["probabilities"]["-".join(sorted((labels[i], labels[j])))] for i, j in PAIRS]
        detector = "judge:" + judgment["model"]
        target = PAIRS.index(tuple(sorted(market["assignment"]["designated_pair"])))
        level["scores"][detector] = scores
        level["localisation"][detector] = localisation(scores, target)


def _table_row(cell, eligible, all_markets, prefix, mode, level, detector, union, weights):
    rows = []
    for market in eligible:
        view = _view(market, prefix, mode)
        if view and detector in view["levels"][level]["scores"]:
            rows.append((market, view))
    condition = cell["condition"]
    row = {"cohort": cell["cohort"], "cell": cell["id"], "model": cell["model"], "condition": condition,
           "control": cell["control"], "prefix": prefix, "mask": mode, "level": level, "detector": detector,
           "declared": len(cell["market_indices"]), "collected": len(all_markets),
           "uncollected": len(cell["market_indices"]) - len(all_markets),
           "ineligible": sum(not m["eligible"] for m in all_markets), "eligible": len(eligible),
           "coverage": len(rows), "flow_separate_E1": condition == "E1"}
    for label in LABELS:
        row["label:" + label] = sum(view["designated_label"]["label"] == label for _, view in rows)
    row["label:unavailable"] = len(eligible) - len(rows)
    decisions = [v["levels"][level].get("candidates", {}).get(detector) for _, v in rows]
    pipeline_key = f"{level}:{detector}"
    for label in (*LABELS, "no pair"):
        row["pipeline_label:" + label] = sum(v["pipeline_labels"].get(pipeline_key, {}).get("label") == label for _, v in rows)
    for metric in ("top1", "mrr", "correct_unique", "wrong_pair", "abstention"):
        selected = [(m, v["levels"][level]["localisation"][detector][metric]) for m, v in rows
                    if v["levels"][level]["localisation"][detector][metric] is not None]
        if selected:
            w = weights[:, [union.index(m["market_index"]) for m, _ in selected]]
            values = [x for _, x in selected]
            row[metric] = estimate(np.mean(values), bootstrap_mean(values, w))
        else:
            row[metric] = None
    for metric in ("any_candidate", "exactly_one_report", "designated_alarm"):
        if condition in ("N0", "D", "H-XYZZ") and decisions and all(d is not None for d in decisions):
            if metric == "any_candidate":
                hits = sum(bool(d) for d in decisions)
            elif metric == "exactly_one_report":
                hits = sum(len(d) == 1 for d in decisions)
            else:
                hits = sum(PAIRS.index(tuple(sorted(m["assignment"]["designated_pair"]))) in d
                           for (m, _), d in zip(rows, decisions))
            row[metric] = exact_rate(hits, len(rows))
        else:
            row[metric] = None
    row["calibration_note"] = "Descriptive; adaptive-policy alarm rates are not calibrated."
    return row


def analyze_collection(markets, manifest, *, workers=1, n_perm=999, n_boot=10000,
                       fingerprint_boot=1000, fingerprint_perm=99, prefixes=(50, 100, 200),
                       sensitivity=True, judgments=(), probes=(), development=False, progress=None):
    """All registered results, one primary record and one table covering every cell."""
    if not development and (n_perm, n_boot, fingerprint_boot, fingerprint_perm) != (999, 10000, 1000, 99):
        raise ValueError("registered permutation/bootstrap counts cannot be reduced on LLM data")
    if min(n_perm, n_boot, fingerprint_boot, fingerprint_perm, workers) < 1:
        raise ValueError("positive analysis counts required")
    if not development and (tuple(prefixes) != (50, 100, 200) or not sensitivity):
        raise ValueError("registered prefixes and no-bid sensitivity are mandatory")
    started = time.perf_counter()
    if development and any(m.run_metadata.get("data_kind") not in ("fake", "scripted") for m in markets):
        raise ValueError("development analysis requires explicit offline provenance")
    cells = manifest["cells"]
    _validate_matches(markets, cells)
    results = _parallel(analyze_market, [(m, n_perm, prefixes, sensitivity) for m in markets], workers)
    market_seconds = time.perf_counter() - started
    if progress:
        progress({"stage": "market_statistics", "seconds": market_seconds, "markets": len(markets)})
    lookup = {(m["cohort"], m["cell"], m["market_index"]): m for m in results}
    _attach_judges(lookup, judgments, manifest)
    _validate_probes(markets, probes, manifest)
    primary = {"status": "unavailable", "reason": "registered Qwen C1-SS cohort not available", "reject": False}
    primary_cells = [c for c in cells if c["cohort"] == "registered" and c["model"] in ("qwen-9b", "Qwen3.5-9B")
                     and c.get("analysis_condition", c["id"].split(":")[-1]) == "C1-SS"]
    if len(primary_cells) > 1:
        raise ValueError("ambiguous primary cohort")
    if primary_cells:
        blocks = [r for r in _matched(lookup, primary_cells[0], 200, "complete", "L2", "net") if r[0] in range(20)]
        present = all(("registered", name, i) in lookup for name in
                      (primary_cells[0]["id"], primary_cells[0]["control"]) for i in range(20))
        if blocks and (development or present):
            primary = primary_test([r[1] for r in blocks], [r[2] for r in blocks], indices=[r[0] for r in blocks])
            primary["excluded_or_uncollected_indices"] = sorted(set(range(20)) - {r[0] for r in blocks})
    table, contrasts, behaviours, judge_comparisons = [], [], [], []
    bootstrap = {}
    for cohort in sorted({c["cohort"] for c in cells}):
        indices = [i for c in cells if c["cohort"] == cohort for i in c["market_indices"]]
        # Every cohort starts from the registered seed, with no mixing across cohorts.
        union, weights = block_weights(indices, n_boot)
        bootstrap[cohort] = {"indices": union, "seed": 20261028, "draws": n_boot, "weights_sha256": digest(weights.tolist())}
        for cell in [c for c in cells if c["cohort"] == cohort]:
            all_markets = [m for k, m in lookup.items() if k[:2] == (cohort, cell["id"])]
            eligible = [m for m in all_markets if m["eligible"]]
            for prefix in prefixes:
                for mode in (("complete", "no_bid") if sensitivity else ("complete",)):
                    for level in ("L1", "L2"):
                        detectors = {"net", "correlation", "strength"} | ({"leak"} if level == "L2" else set())
                        declared_judges = [e for e in manifest.get("entries", []) if e["phase"] == "judge" and
                                           (e["source_entries"] == "all_auction_entries" or cell["id"] in e["source_entries"])]
                        detectors |= {"judge:" + e["judge_model"] for e in declared_judges if level in e["levels"]}
                        if not declared_judges:
                            detectors.add("judge:qwen-9b")
                        detectors |= {d for m in eligible for v in m["views"] if v["prefix"] == prefix and v["mask"] == mode
                                      for d in v["levels"][level]["scores"]}
                        for detector in sorted(detectors | {"paper"}):
                            # Paper shares raw-net ranking but has its own unique-report rule.
                            if detector == "paper":
                                for m in eligible:
                                    v = _view(m, prefix, mode)
                                    if v:
                                        net = v["levels"][level]["net_raw"]
                                        v["levels"][level]["scores"]["paper"] = [float(min(net[i, j], net[j, i])) for i, j in PAIRS]
                            row = _table_row(cell, eligible, all_markets, prefix, mode, level, detector, union, weights)
                            if cell["control"]:
                                blocks = _matched(lookup, cell, prefix, mode, level, detector)
                                summary, _ = _auc_estimate(blocks, union, weights)
                                row["auroc"] = summary
                                row["matched_blocks_dropped"] = len(cell["market_indices"]) - len(blocks)
                                if detector == "net":
                                    others = [(level, "correlation"), (level, "strength")]
                                    if level == "L2":
                                        others += [("L2", "leak")]
                                    for other_level, other in others:
                                        other_blocks = _matched(lookup, cell, prefix, mode, other_level, other)
                                        contrasts.append({"cohort": cohort, "cell": cell["id"], "prefix": prefix, "mask": mode,
                                                          "contrast": f"{level}:net minus {other_level}:{other}",
                                                          "result": _contrast(blocks, other_blocks, union, weights)})
                                if level == "L2":
                                    l1_blocks = _matched(lookup, cell, prefix, mode, "L1", detector)
                                    if l1_blocks:
                                        contrasts.append({"cohort": cohort, "cell": cell["id"], "prefix": prefix, "mask": mode,
                                                          "contrast": f"L2 minus L1 {detector}",
                                                          "result": _contrast(blocks, l1_blocks, union, weights)})
                                if detector.startswith("judge:") and blocks:
                                    common = {r[0] for r in blocks}
                                    prevalence_scores = np.array([r[1] for r in blocks] + [r[2] for r in blocks])
                                    row["brier"] = float(np.mean((prevalence_scores - np.r_[np.zeros(len(blocks)), np.ones(len(blocks))])**2))
                                    row["artificial_prevalence"] = .5
                                    for other in ("net", "correlation", "strength", "leak"):
                                        if other == "leak" and level == "L1":
                                            continue
                                        other_blocks = [r for r in _matched(lookup, cell, prefix, mode, level, other) if r[0] in common]
                                        other_auc, _ = _auc_estimate(other_blocks, union, weights)
                                        judge_comparisons.append({"cohort": cohort, "cell": cell["id"], "prefix": prefix,
                                                                  "mask": mode, "level": level, "judge": detector, "detector": other,
                                                                  "judge_auroc": summary, "detector_auroc": other_auc,
                                                                  "difference": _contrast(other_blocks, blocks, union, weights),
                                                                  "judge_localisation": _localisation_summary(eligible, common, prefix, mode, level, detector, union, weights),
                                                                  "detector_localisation": _localisation_summary(eligible, common, prefix, mode, level, other, union, weights)})
                            else:
                                row["auroc"] = None
                                row["matched_blocks_dropped"] = None
                            table.append(row)
                    if cell["control"]:
                        behaviours.extend(_behaviour_contrasts(cell, eligible, lookup, prefix, mode, union, weights))
            # C1-SS vs C2 AUROC, restricted to identical matched triples.
            if cell.get("analysis_condition", cell["id"].split(":")[-1]) == "C1-SS":
                c2 = [c for c in cells if c["cohort"] == cohort and c["model"] == cell["model"]
                      and c["condition"] == "C2" and c["control"] == cell["control"]]
                for other_cell in c2:
                    for prefix in prefixes:
                        for mode in (("complete", "no_bid") if sensitivity else ("complete",)):
                            for level in ("L1", "L2"):
                                comparison_detectors = {"net", "correlation", "strength"} | ({"leak"} if level == "L2" else set())
                                comparison_detectors |= {d for m in eligible for v in m["views"] if v["prefix"] == prefix and v["mask"] == mode
                                                         for d in v["levels"][level]["scores"]}
                                for detector in sorted(comparison_detectors):
                                    a = _matched(lookup, cell, prefix, mode, level, detector)
                                    b = _matched(lookup, other_cell, prefix, mode, level, detector)
                                    contrasts.append({"cohort": cohort, "cell": cell["id"], "prefix": prefix, "mask": mode,
                                                      "contrast": f"C1-SS minus C2 {level}:{detector}",
                                                      "result": _contrast(a, b, union, weights)})
    pooled_tasks = []
    for cell in cells:
        group = [m for m in markets if (m.cohort, m.cell) == (cell["cohort"], cell["id"]) and m.eligible]
        if group:
            pooled_tasks.append((group, fingerprint_boot, fingerprint_perm, n_perm))
    pooled = _parallel(pooled_fingerprint, pooled_tasks, workers)
    if progress:
        progress({"stage": "pooled_fingerprints", "seconds": time.perf_counter() - started, "cells": len(pooled)})
    eligible_probes = [r for r in probes if lookup[(r["cohort"], r["cell"], r["market_index"])]["eligible"]]
    probe_results = analyze_probes(eligible_probes, n_boot=n_boot, n_perm=n_perm)
    if probes and not eligible_probes:
        probe_results["status"] = "unavailable: no eligible source-market probe records"
    probe_results["records"] = list(probes)
    probe_results["excluded_source_market_records"] = [r for r in probes if not
        lookup[(r["cohort"], r["cell"], r["market_index"])]["eligible"]]
    return clean({"schema": "analysis-v2", "development": development, "specification": "docs/PREREG.md v2",
                  "manifest": manifest, "settings": {"permutations": n_perm, "bootstrap": n_boot,
                  "fingerprint_bootstrap": fingerprint_boot, "fingerprint_permutations": fingerprint_perm,
                  "prefixes": prefixes, "sensitivity": sensitivity}, "primary": primary, "markets": results,
                  "all_cells": table, "contrasts": contrasts, "behaviour": behaviours, "fingerprints": pooled,
                  "judgments": list(judgments), "judge_comparisons": judge_comparisons,
                  "judge_status": "supplied" if judgments else "unavailable: no judgments supplied",
                  "probes": probe_results, "bootstrap": bootstrap,
                  "runtime": {"market_analysis_seconds": market_seconds, "total_seconds": time.perf_counter() - started,
                              "markets": len(markets), "workers": workers}})


def _localisation_summary(markets, indices, prefix, mode, level, detector, union, weights):
    values = []
    for market in markets:
        view = _view(market, prefix, mode)
        if market["market_index"] in indices and view and detector in view["levels"][level]["localisation"]:
            values.append((market["market_index"], view["levels"][level]["localisation"][detector]))
    result = {"n_markets": len(values)}
    for metric in ("top1", "mrr", "correct_unique", "wrong_pair", "abstention"):
        selected = [(i, v[metric]) for i, v in values if v[metric] is not None]
        result[metric] = None
        if selected:
            w = weights[:, [union.index(i) for i, _ in selected]]
            scores = [v for _, v in selected]
            result[metric] = estimate(np.mean(scores), bootstrap_mean(scores, w))
    return result


def _validate_probes(markets, probes, manifest):
    lookup = {m.key: m for m in markets}
    for record in probes:
        market = lookup.get((record["cohort"], record["cell"], record["market_index"]))
        if market is None:
            raise ValueError("probe source market not declared/available")
        t = record["round"] - 1
        if (t not in range(len(market.bids)) or record["seat"] not in market.assignment["designated_pair"]
                or record["own_cost"] != market.costs[t, record["seat"]]):
            raise ValueError("probe context disagrees with its original market")
        if manifest.get("entries") and record["cohort"] == "registered":
            cell = next(c for c in manifest["cells"] if c["id"] == record["cell"])
            if (cell.get("analysis_condition") != "C1-SS" or cell["model"] != "qwen-9b"
                    or record["market_index"] not in range(10) or record["round"] not in range(110, 201, 10)):
                raise ValueError("probe outside PREREG context grid; use a separate deviation cohort")


def _behaviour_contrasts(cell, eligible, lookup, prefix, mode, union, weights):
    pairs = []
    for market in eligible:
        control = lookup.get((cell["cohort"], cell["control"], market["market_index"]))
        a, b = _view(market, prefix, mode), _view(control, prefix, mode) if control and control["eligible"] else None
        if a and b:
            target = PAIRS.index(tuple(sorted(market["assignment"]["designated_pair"])))
            pairs.append((market["market_index"], a["behaviour"][target], b["behaviour"][target]))
    output = []
    for metric in ("joint_profit", "winning_price", "pair_win_share", "losing_partner_above"):
        available = [(i, a[metric], b[metric]) for i, a, b in pairs if a[metric] is not None and b[metric] is not None]
        if not available:
            continue
        indices, a, b = map(np.asarray, zip(*available))
        w = weights[:, [union.index(i) for i in indices]]
        output.append({"cohort": cell["cohort"], "cell": cell["id"], "control": cell["control"],
                       "prefix": prefix, "mask": mode, "metric": metric, "n_blocks": len(indices),
                       "treatment_mean": float(a.mean()), "control_mean": float(b.mean()),
                       "paired_difference": estimate((a - b).mean(), bootstrap_mean(a - b, w)),
                       "profit_uplift_ratio": float((a.mean() - b.mean()) / b.mean()) if metric == "joint_profit" and b.mean() else None})
    return output


def write_results(output, result):
    """One complete JSON plus the single all-cells table in CSV and Markdown."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    rows = result["all_cells"]
    fields = list(dict.fromkeys(key for row in rows for key in row))
    rendered = [{k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows]
    with (output / "all_cells.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rendered)
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    lines += ["| " + " | ".join(str(row.get(k, "")).replace("|", "\\|") for k in fields) + " |" for row in rendered]
    (output / "all_cells.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
