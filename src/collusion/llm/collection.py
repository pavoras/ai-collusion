"""Versioned collection declarations and balanced, condition-independent seats."""

from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from .storage import digest
from .prompts import VERSION

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = ROOT / "experiments/manifests/collection_v1.json"
ROLES = ("strong_0", "strong_1", "fringe_0", "fringe_1")
POSITIONS = {"strong_strong": ROLES[:2], "strong_fringe": (ROLES[0], ROLES[2]), "fringe_fringe": ROLES[2:]}


def load_collection(path=DEFAULT_MANIFEST):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not data.get("entries"):
        raise ValueError("unsupported or empty collection manifest")
    ids = [e["id"] for e in data["entries"]]
    if len(ids) != len(set(ids)) or set(data["execution_order"]) != set(ids):
        raise ValueError("collection entry IDs/order must be unique and complete")
    return data


def indices_for(manifest, entry):
    selection = entry["market_indices"]
    count = manifest["parameters"][selection["count_parameter"]]["value"]
    if type(count) is not int or count < 1:
        raise ValueError("collection market-count placeholder needs a positive value")
    return list(range(selection["start"], selection["start"] + count))


def rounds_for(manifest, entry):
    return manifest["parameters"][entry["round_count_parameter"]]["value"]


def entry_for(config, manifest):
    candidates = [e for e in manifest["entries"] if e["phase"] == "auction" and
                  (e["id"] == config.entry_id if config.entry_id else
                   e["condition"] == config.condition and e["position"] == config.cartel_position and
                   tuple(e["models_by_role"][r] for r in ROLES) == config.models)]
    if len(candidates) != 1:
        raise ValueError("run is not a unique declared collection cell; specify --entry or an explicit deviation cohort")
    return candidates[0]


def authorize(config):
    """Check declarations before any backend submission, even for a fake backend."""
    manifest = load_collection(config.collection_manifest)
    if config.assignment is not None:
        raise ValueError("runner requires role models; market assignments are resolved internally")
    if config.deviation_cohort:
        if not config.deviation_reason or not config.deviation_reason.strip():
            raise ValueError("a deviation cohort requires a nonempty reason")
        return manifest, None
    entry = entry_for(config, manifest)
    allowed_rounds = [rounds_for(manifest, entry), *entry.get("allowed_round_extensions", [])]
    selected = set(range(config.market_start, config.market_start + config.markets))
    if (config.condition != entry["condition"] or config.cartel_position != entry["position"] or
            config.models != tuple(entry["models_by_role"][r] for r in ROLES) or
            config.rounds not in allowed_rounds or not selected <= set(indices_for(manifest, entry)) or
            config.seed != manifest["run_seed"] or config.compliance != entry.get("compliance", 1.)):
        raise ValueError("undeclared run, indices, rounds or policy; use --deviation-cohort and --deviation-reason")
    return manifest, entry


def pair_order(seed, stream):
    """Seeded six-pair cycle; adjacent complementary pairs balance 20 markets."""
    groups = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
    rng = np.random.default_rng([seed, stream])
    result = []
    for index in rng.permutation(3):
        pair = groups[int(index)]
        result.extend(pair if rng.integers(2) == 0 else pair[::-1])
    return result


def assignment_for(index, models, seed=20261023):
    """Physical seats and displayed labels each cycle through all six pairs."""
    if index < 0 or len(models) != 4:
        raise ValueError("nonnegative market index and four role models required")
    strong = pair_order(seed, 100)[index % 6]
    fringe = tuple(s for s in range(4) if s not in strong)
    rng = np.random.default_rng([seed, index, 102])
    ordered = [*rng.permutation(strong).tolist(), *rng.permutation(fringe).tolist()]
    role_seats = dict(zip(ROLES, ordered))
    strong_labels = pair_order(seed, 101)[index % 6]
    fringe_labels = tuple(s for s in range(4) if s not in strong_labels)
    displayed = [*rng.permutation(strong_labels).tolist(), *rng.permutation(fringe_labels).tolist()]
    labels, model_seats = [None] * 4, [None] * 4
    for seat, label, model in zip(ordered, displayed, models):
        labels[seat], model_seats[seat] = f"Firm {'ABCD'[label]}", model
    return {"schema_version": 1, "assignment_seed": seed, "market_index": index,
            "role_seats": role_seats, "strong_seats": sorted(strong), "fringe_seats": sorted(fringe),
            "labels_by_seat": labels, "models_by_seat": model_seats,
            "models_by_role": dict(zip(ROLES, models)),
            "cost_ranges_by_seat": [[1, 2, 3] if s in strong else [3, 4, 5] for s in range(4)],
            "candidate_pairs": {name: [role_seats[r] for r in roles] for name, roles in POSITIONS.items()},
            "spy_receiver": role_seats["strong_0"], "spy_victim": role_seats["strong_1"]}


def resolve_market(config, index, manifest=None):
    manifest = manifest or load_collection(config.collection_manifest)
    assignment = assignment_for(index, config.models, manifest["assignment"]["seed"])
    pair = assignment["candidate_pairs"][config.cartel_position]
    if config.condition in ("P0", "E1"):
        pair = [assignment["role_seats"][r] for r in ROLES[:2]]
    return replace(config, strong=tuple(assignment["strong_seats"]), pair=tuple(pair),
                   models=tuple(assignment["models_by_seat"]), labels=tuple(assignment["labels_by_seat"]),
                   assignment=assignment)


def collection_hash(manifest):
    return digest(manifest)


def authorize_judge(manifest, market, model, level, entry_id=None, deviation_cohort=None, deviation_reason=None):
    if deviation_cohort:
        if not deviation_reason or not deviation_reason.strip():
            raise ValueError("a deviation reason is required")
        return None
    entry_id = entry_id or ("judge.qwen9b" if model == "qwen-9b" else "judge.gemma12b")
    entry = next((e for e in manifest["entries"] if e["id"] == entry_id and e["phase"] == "judge"), None)
    source_id = market.get("metadata", {}).get("collection_entry")
    source = next((e for e in manifest["entries"] if e["id"] == source_id and e["phase"] == "auction"), None)
    if (entry is None or source is None or entry["judge_model"] != model or level not in entry["levels"] or
            market["metadata"].get("manifest_hash") != collection_hash(manifest) or
            market.get("planned_rounds") not in [rounds_for(manifest, source), *source.get("allowed_round_extensions", [])] or
            market["metadata"].get("deviation_cohort") is not None or
            market["market_index"] not in indices_for(manifest, source) or
            (entry["source_entries"] != "all_auction_entries" and
             (source_id not in entry["source_entries"] or market["market_index"] not in indices_for(manifest, entry)))):
        raise ValueError("undeclared judge scope; explicit deviation cohort and reason required")
    return entry


def authorize_probe(config, source, partner, kind, cost, draws):
    """A probe context must belong to the declared source, round and role grid."""
    manifest = load_collection(config.collection_manifest)
    if config.deviation_cohort:
        if not config.deviation_reason or not config.deviation_reason.strip():
            raise ValueError("a deviation reason is required")
        return None
    entry = next((e for e in manifest["entries"] if e["id"] == (config.entry_id or "core.probes") and e["phase"] == "probe"), None)
    if entry is None or not entry.get("enabled") or kind not in entry["kinds"] or partner is None:
        raise ValueError("undeclared probe mode; explicit deviation cohort and reason required")
    origin = next((e for e in manifest["entries"] if e["id"] == source.get("collection_entry")), None)
    assignment = assignment_for(source["market"], tuple(entry["models_by_role"][r] for r in ROLES), manifest["assignment"]["seed"])
    seats = [assignment["role_seats"][r] for r in entry["context_roles"]]
    if (origin is None or origin["id"] not in entry["source_entries"] or config.seed != manifest["run_seed"] or
            source["market"] not in indices_for(manifest, entry) or source["round"] not in entry["context_rounds"] or
            source["seat"] not in seats or source["kind"] != "bid" or source["role"] != "cartel_channel" or
            source.get("prompt_version") != partner.get("prompt_version") or source.get("prompt_version") != VERSION or
            source.get("assignment_hash") != digest(assignment) or partner.get("assignment_hash") != digest(assignment) or
            partner.get("collection_entry") != origin["id"] or partner["kind"] != "message" or
            partner["market"] != source["market"] or partner["round"] != source["round"] or
            partner["seat"] != next(s for s in seats if s != source["seat"]) or
            source["model"] != assignment["models_by_seat"][source["seat"]] or partner["model"] != source["model"] or
            cost not in entry["counterfactual_costs"] or draws != entry["bid_draws_per_cost"]):
        raise ValueError("undeclared probe context, cost or draw count; explicit deviation cohort and reason required")
    return entry
