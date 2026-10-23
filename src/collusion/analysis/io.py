"""Fail-closed compact market, assignment, collection and judge loading.

The collection root has analysis_runs.json, e.g.
{"runs": [{"cell": "core.N0", "path": "llm/n0", "cohort": "registered"}]}.
Native raw/n0/config.json and reproducibility.json are discovered automatically;
metadata_path/reproducibility_path can instead explicitly name root-relative
files. Standalone development directories contain run_metadata.json.
deviation_cells in this index explicitly enumerates separate named cohorts,
with their indices, rounds, controls and deviation_reason; the frozen manifest
is never rewritten to admit them.

Judgments need a {"judgments": [...]} index, binding path (a native judge.json),
cohort, cell, market_index, model, level, prefix (default 200) and mask (default
complete). The harness artifact does not itself identify its source market.
No filename inference, answer selection, probability renormalisation or imputation
is performed. Missing judgments are unavailable; supplied failures are retained.
"""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from collusion.llm.storage import digest


@dataclass
class MarketRecord:
    cell: str
    cohort: str
    index: int
    model: str
    condition: str
    control: str | None
    bids: np.ndarray
    costs: np.ndarray
    winners: np.ndarray
    payoffs: np.ndarray
    complete: np.ndarray
    assignment: dict
    metadata: dict
    run_metadata: dict
    planned_rounds: int = 200

    @property
    def missing_rounds(self):
        return self.planned_rounds - int(self.complete.sum())

    @property
    def eligible(self):
        return self.planned_rounds == 200 and self.missing_rounds <= 20

    @property
    def key(self):
        return self.cohort, self.cell, self.index


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def adapt_legacy_assignment(config):
    """Explicit adapter for pre-manifest fake runs; never infer roles from bids."""
    strong, pair = list(config["strong"]), list(config["pair"])
    condition = config["condition"]
    roles = ["honest"] * 4
    for seat in pair:
        roles[seat] = "cartel" if condition in ("C1", "C2", "P0", "M2") else "honest"
    if condition == "E1":
        roles[pair[0]], roles[pair[1]] = "spy", "victim"
    return {"strong_seats": strong, "designated_pair": pair, "roles": roles,
            "labels": list("ABCD"), "model_to_seat": list(config["models"])}


def normalize_assignment(value):
    """Validate explicit seats/roles; preserve pair order for receiver alignment."""
    value = dict(value)
    if "designated_pair" not in value and "pair" in value:
        value["designated_pair"] = value["pair"]
    if "strong_seats" not in value and "strong" in value:
        value["strong_seats"] = value["strong"]
    for field in ("strong_seats", "designated_pair"):
        seats = value.get(field, [])
        if len(seats) != 2 or len(set(seats)) != 2 or any(type(s) is not int or s not in range(4) for s in seats):
            raise ValueError(f"assignment requires explicit {field}")
    if len(value.get("roles", [])) != 4 or len(value.get("labels", [])) != 4:
        raise ValueError("assignment requires four explicit roles and labels")
    if len(set(value["labels"])) != 4 or "model_to_seat" not in value:
        raise ValueError("assignment requires distinct labels and model-to-seat metadata")
    return value


def adapt_collection_manifest(manifest):
    """Canonical cell records; no wildcard markets or inferred controls allowed."""
    cells = manifest.get("cells")
    if cells is None and manifest.get("schema_version") == 1 and "entries" in manifest:
        from collusion.llm.collection import ROLES, indices_for, rounds_for
        cells = []
        for entry in manifest["entries"]:
            if entry["phase"] != "auction":
                continue
            models = entry["models_by_role"]
            cells.append({**entry, "market_indices": indices_for(manifest, entry),
                          "rounds": rounds_for(manifest, entry), "cohort": "registered",
                          "analysis_condition": entry["id"].split(".")[-1],
                          "model": models[ROLES[0]] if len(set(models.values())) == 1 else entry["composition"],
                          "control": entry["matched_control"]})
    if not isinstance(cells, list) or not cells:
        raise ValueError("collection manifest must enumerate cells")
    result = []
    for entry in cells:
        cell = dict(entry)
        cell["id"] = cell.get("id", cell.get("cell_id"))
        cell["market_indices"] = cell.get("market_indices", cell.get("markets"))
        if not cell["id"] or not isinstance(cell["market_indices"], list):
            raise ValueError("manifest requires cell id and explicit market index list")
        if (any(type(i) is not int or i < 0 for i in cell["market_indices"])
                or len(set(cell["market_indices"])) != len(cell["market_indices"])):
            raise ValueError("invalid manifest indices")
        if cell.get("rounds") != 200:
            raise ValueError("registered analysis requires 200 declared rounds")
        for key in ("condition", "model"):
            if not cell.get(key):
                raise ValueError(f"manifest requires {key}")
        cell.setdefault("cohort", "registered")
        cell.setdefault("control", None)
        result.append(cell)
    keys = [(c["cohort"], c["id"]) for c in result]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate collection cells")
    for cell in result:
        if cell["control"] is not None and (cell["cohort"], cell["control"]) not in keys:
            raise ValueError("matched control must be declared in the same cohort")
    return result


def _run_metadata(directory):
    for name in ("run_metadata.json", "metadata.json", "config.json"):
        path = directory / name
        if path.exists():
            return read_json(path)
    raise ValueError(f"missing run metadata in {directory}")


def adapt_harness_assignment(assignment, data, cell):
    """Collection v1 role/seat schema; derive the target from declared position."""
    value = dict(assignment)
    if "role_seats" not in value:
        return value
    position = cell.get("position", "strong_strong")
    if cell["condition"] in ("P0", "E1"):
        pair = [value["role_seats"][r] for r in ("strong_0", "strong_1")]
    else:
        pair = value["candidate_pairs"][position]
    value.setdefault("designated_pair", data.get("designated_pair", pair))
    value.setdefault("labels", value["labels_by_seat"])
    value.setdefault("model_to_seat", value["models_by_seat"])
    value.setdefault("roles", data.get("metadata", {}).get("roles_by_seat", [
        next(r for r, s in value["role_seats"].items() if s == seat) for seat in range(4)]))
    return value


def compact_record(data, metadata, cell, *, legacy_fake=False):
    """Validate the compact JSON arrays before any detector is evaluated."""
    index = data["market_index"]
    if index not in cell["market_indices"] or data.get("planned_rounds") != cell["rounds"]:
        raise ValueError("market or rounds not declared in collection manifest")
    assignment = data.get("assignment", data.get("metadata", {}).get("assignment"))
    if assignment is None and legacy_fake:
        assignment = adapt_legacy_assignment(metadata["identity"]["config"])
    if assignment is None:
        raise ValueError("per-market assignment missing; no silent fixed-seat fallback")
    assignment = normalize_assignment(adapt_harness_assignment(assignment, data, cell))
    raw_bids = data["bids"]
    n = len(raw_bids)
    bids = np.asarray([[8 if b is None else b for b in row] for row in raw_bids], dtype=int).reshape(n, 4)
    if n > cell["rounds"] or any(b is not None and (type(b) is not int or b not in range(2, 8))
                                    for row in raw_bids for b in row):
        raise ValueError("invalid compact bids or undeclared round extension")
    costs = np.asarray(data["costs"])
    winners = np.asarray(data["winners"])
    payoffs = np.asarray(data["payoffs"])
    if n == 0:
        costs, payoffs, winners = np.empty((0, 4), int), np.empty((0, 4), int), np.empty(0, int)
    if costs.shape != (n, 4) or payoffs.shape != (n, 4) or winners.shape != (n,):
        raise ValueError("inconsistent compact array lengths")
    if (not np.issubdtype(costs.dtype, np.integer) or not np.isin(costs, range(1, 6)).all()
            or not np.issubdtype(winners.dtype, np.integer) or not np.isfinite(payoffs).all()):
        raise ValueError("invalid costs, winners or payoffs")
    strong = assignment["strong_seats"]
    for seat in range(4):
        if not np.isin(costs[:, seat], range(1, 4) if seat in strong else range(3, 6)).all():
            raise ValueError("cost support disagrees with assignment")
    complete = (bids != 8).all(axis=1)
    stored_mask = data.get("complete_round_mask")
    if stored_mask is not None and not np.array_equal(stored_mask, complete):
        raise ValueError("stored complete-round mask disagrees with bids")
    if "invalid" in data and not np.array_equal(data["invalid"], bids == 8):
        raise ValueError("invalid flags disagree with bids")
    for t, winner in enumerate(winners):
        valid = bids[t] != 8
        if (winner not in range(-1, 4) or (valid.any() and
                (winner < 0 or bids[t, winner] != bids[t, valid].min())) or (not valid.any() and winner != -1)):
            raise ValueError("winner disagrees with original bids")
        expected = np.zeros(4)
        if winner >= 0:
            expected[winner] = bids[t, winner] - costs[t, winner]
        if not np.array_equal(payoffs[t], expected):
            raise ValueError("payoffs disagree with original settlement")
    return MarketRecord(cell["id"], cell["cohort"], index, cell["model"], cell["condition"], cell["control"],
                        bids, costs, winners, payoffs, complete, assignment, data, metadata, cell["rounds"])


def load_collection(root, manifest_path, *, legacy_fake=False):
    """Load only enumerated run directories; reject undeclared/duplicate markets."""
    root, manifest_path = Path(root), Path(manifest_path)
    manifest = read_json(manifest_path)
    cells = adapt_collection_manifest(manifest)
    records, seen = [], set()
    # A run index is explicit: directories outside it are never searched.
    run_index = read_json(root / "analysis_runs.json")
    if run_index.get("deviation_cells"):
        deviations = run_index["deviation_cells"]
        if any(c.get("cohort", "registered") == "registered" or not c.get("deviation_reason") for c in deviations):
            raise ValueError("deviation declarations require a separate named cohort and reason")
        cells = adapt_collection_manifest({"cells": cells + deviations})
    runs = run_index["runs"]
    for run in runs:
        candidates = [c for c in cells if c["id"] == run["cell"] and c["cohort"] == run.get("cohort", "registered")]
        if len(candidates) != 1:
            raise ValueError("undeclared run/cell/cohort")
        cell = candidates[0]
        directory = (root / run["path"]).resolve()
        if not directory.is_relative_to(root.resolve()):
            raise ValueError("run path escapes collection root")
        if run.get("metadata_path"):
            path = (root / run["metadata_path"]).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("metadata path escapes collection root")
            metadata = read_json(path)
        elif directory.parent.name == "llm" and (root / "raw" / directory.name / "config.json").exists():
            metadata = read_json(root / "raw" / directory.name / "config.json")
        else:
            metadata = _run_metadata(directory)
        metadata["analysis_run_reference"] = {"cell": cell["id"], "cohort": cell["cohort"], "path": run["path"]}
        repro_path = (root / run["reproducibility_path"]) if run.get("reproducibility_path") else root / "raw" / directory.name / "reproducibility.json"
        if repro_path.exists():
            if not repro_path.resolve().is_relative_to(root.resolve()):
                raise ValueError("reproducibility path escapes collection root")
            metadata["reproducibility"] = read_json(repro_path)
        summary = directory / "summary.json"
        if summary.exists():
            # Whitelist operational fields only; never echo arbitrary run outputs in blind mode.
            allowed = ("backend", "calls", "new_calls", "cache_hits", "invalid_response_rate", "latency_median_seconds",
                       "latency_max_seconds", "prompt_tokens", "completion_tokens", "cached_prompt_tokens", "usage_missing_calls",
                       "invocation_wall_seconds", "gpu_hourly_usd", "estimated_invocation_usd")
            metadata["operations"] = {k: v for k, v in read_json(summary).items() if k in allowed}
        config = metadata.get("identity", {}).get("config", metadata.get("config", {}))
        if config and config.get("condition") != cell["condition"]:
            raise ValueError("run condition disagrees with collection cell")
        if metadata.get("max_rounds", config.get("rounds", cell["rounds"])) != cell["rounds"]:
            raise ValueError("run round count is not declared")
        endpoints = metadata.get("identity", {}).get("endpoints", metadata.get("endpoints", {}))
        offline = metadata.get("data_kind") in ("scripted", "fake") or (endpoints and all(
            e.startswith("fake://") for e in endpoints.values()))
        if legacy_fake and not offline:
            raise ValueError("legacy assignment adapter is restricted to verified offline data")
        for path in sorted(directory.glob("market_*.json")):
            record = compact_record(read_json(path), metadata, cell, legacy_fake=legacy_fake)
            compact_meta = record.metadata.get("metadata", {})
            identity = metadata.get("identity", {})
            if cell["cohort"] == "registered":
                if any(m.get("manifest_hash") not in (None, digest(manifest)) for m in (compact_meta, identity)):
                    raise ValueError("collection manifest hash mismatch")
                if any(m.get("collection_entry") not in (None, cell["id"]) for m in (compact_meta, identity)):
                    raise ValueError("market/run collection entry mismatch")
            if "assignment" in manifest and "models_by_role" in cell and cell["cohort"] == "registered":
                from collusion.llm.collection import ROLES, assignment_for
                expected = assignment_for(record.index, [cell["models_by_role"][r] for r in ROLES], manifest["assignment"]["seed"])
                for field, value in expected.items():
                    if record.assignment.get(field) != value:
                        raise ValueError(f"assignment disagrees with manifest: {field}")
            if "models_by_role" in cell:
                if record.assignment.get("models_by_role") != cell["models_by_role"]:
                    raise ValueError("model roles disagree with declared collection cell")
            elif len(set(record.assignment["model_to_seat"])) != 1 or record.assignment["model_to_seat"][0] != cell["model"]:
                raise ValueError("model-to-seat mapping disagrees with declared homogeneous model")
            recorded_cohort = compact_meta.get("deviation_cohort") or metadata.get("deviation_cohort") or config.get("deviation_cohort")
            if recorded_cohort and recorded_cohort != cell["cohort"]:
                raise ValueError("deviation cohort cannot be analysed as the registered cohort")
            if "run_seed" in manifest and not recorded_cohort and config.get("seed") != manifest["run_seed"]:
                raise ValueError("run seed disagrees with collection manifest")
            if record.key in seen:
                raise ValueError("duplicate market in collection")
            seen.add(record.key)
            records.append(record)
    return sorted(records, key=lambda m: m.key), {**manifest, "cells": cells, "sha256": digest(manifest)}


def operational_report(markets, manifest):
    """Blind report: input validation and operations only, no detector outcomes."""
    histogram = {kind: {str(b): 0 for b in range(2, 9)} for kind in ("strong", "fringe")}
    for market in markets:
        for seat in range(4):
            kind = "strong" if seat in market.assignment["strong_seats"] else "fringe"
            for bid in range(2, 9):
                histogram[kind][str(bid)] += int((market.bids[:, seat] == bid).sum())
    unique = {}
    for market in markets:
        reference = market.run_metadata.get("analysis_run_reference", {"cell": market.cell, "cohort": market.cohort})
        fields = ("calls", "invalid_response_rate", "transport_error_rate", "latency_median_seconds",
                  "latency_max_seconds", "prompt_tokens", "completion_tokens", "estimated_invocation_usd")
        unique[digest(reference)] = {"run": reference, **dict.fromkeys(fields), **market.run_metadata.get("operations", {})}
    return {"mode": "blind", "validated_markets": len(markets), "manifest_sha256": manifest["sha256"],
            "declared_markets": sum(len(c["market_indices"]) for c in manifest["cells"]),
            "observed_rounds": sum(len(m.bids) for m in markets), "bid_histograms_by_firm_type": histogram,
            "no_bid_category": 8, "operations_by_run": list(unique.values()),
            "operations_note": "Calls/errors/latency/tokens/cost are retained as supplied; unavailable fields are not estimated."}


def load_judges(path):
    """Explicit artifact index binds each raw judgment to its market/view."""
    if path is None:
        return []
    index_path = Path(path)
    results, seen = [], set()
    for record in read_json(index_path)["judgments"]:
        result = {**record, **read_json(index_path.parent / record["path"])} if "path" in record else dict(record)
        for field in ("cohort", "cell", "market_index", "level", "model"):
            if field not in result:
                raise ValueError(f"judge index missing {field}")
        result.setdefault("prefix", 200)
        result.setdefault("mask", "complete")
        key = tuple(result[k] for k in ("cohort", "cell", "market_index", "level", "model", "prefix", "mask"))
        if key in seen:
            raise ValueError("multiple judgments for one market/view; no answer selection")
        seen.add(key)
        probabilities = result.get("probabilities")
        if probabilities is not None and (set(probabilities) != {"A-B", "A-C", "A-D", "B-C", "B-D", "C-D"}
                or any(not isinstance(p, (float, int)) or not 0 <= p <= 1 for p in probabilities.values())):
            raise ValueError("judge probabilities must be six raw probabilities")
        results.append(result)
    return results
