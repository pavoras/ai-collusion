"""Exploratory frozen-context probe slopes and conditional leak estimates."""

from collections import defaultdict

import numpy as np

from collusion.llm.storage import seed_for
from collusion.measures import permutation_test
from .inference import block_weights, bootstrap_mean, estimate
from .io import read_json


def load_probes(path):
    """Explicit context index adapts harness probes.json without guessing linkage."""
    if path is None:
        return []
    from pathlib import Path
    index = Path(path)
    output = []
    seen = set()
    for entry in read_json(index)["contexts"]:
        for key in ("cohort", "cell", "market_index", "round", "seat", "own_cost", "partner_cost"):
            if key not in entry:
                raise ValueError(f"probe context index missing {key}")
        identity = tuple(entry[k] for k in ("cohort", "cell", "market_index", "round", "seat", "partner_cost"))
        if identity in seen:
            raise ValueError("duplicate probe context/cost; no repeated-answer selection")
        seen.add(identity)
        artifact = read_json(index.parent / entry["path"]) if "path" in entry else entry
        draws = artifact["draws"]
        bids = [d.get("bid") if isinstance(d, dict) else d for d in draws]
        if entry["partner_cost"] not in (1, 2, 3) or any(b is not None and (type(b) is not int or b not in range(2, 8)) for b in bids):
            raise ValueError("invalid probe bid/counterfactual cost")
        output.append({**entry, "bids": bids, "status": artifact.get("status"),
                       "message_failures": sum(isinstance(d, dict) and d.get("partner_message") is None for d in draws)})
    return output


def analyze_probes(records, *, n_boot=10000, n_perm=999):
    """Average slopes within frozen contexts, then markets; never over draws."""
    if not records:
        return {"status": "unavailable: no probe artifact supplied", "records": []}
    contexts = defaultdict(dict)
    for r in records:
        key = tuple(r[k] for k in ("cohort", "cell", "market_index", "round", "seat"))
        contexts[key][r["partner_cost"]] = r
    slopes, skipped = defaultdict(list), []
    for key, costs in contexts.items():
        if set(costs) != {1, 2, 3} or any(len(r["bids"]) != 5 or any(b is None for b in r["bids"]) for r in costs.values()):
            skipped.append(key)
            continue
        means = [np.mean(costs[c]["bids"]) for c in (1, 2, 3)]
        slopes[key[:3]].append(float((means[2] - means[0]) / 2))
    summaries = []
    for cohort, cell in sorted({key[:2] for key in contexts}):
        values = sorted((key[2], np.mean(v)) for key, v in slopes.items() if key[:2] == (cohort, cell))
        summary = {"cohort": cohort, "cell": cell, "slope": None, "leak": None,
                   "complete_contexts": sum(len(v) for key, v in slopes.items() if key[:2] == (cohort, cell))}
        if values:
            indices, weights = block_weights([i for i, _ in values], n_boot, seed_for(20261028, "probes", cohort, cell))
            means = [dict(values)[i] for i in indices]
            summary["slope"] = estimate(np.mean(means), bootstrap_mean(means, weights))
        actions, states = [], []
        for k, (key, costs) in enumerate(sorted(contexts.items())):
            if key[:2] != (cohort, cell):
                continue
            for c, record in sorted(costs.items()):
                for bid in record["bids"]:
                    if bid is not None:
                        actions.append([bid - 2, c - 1])
                        states.append(k)
        if actions:
            result = permutation_test(np.asarray(actions), states=np.asarray(states), n_perm=n_perm,
                                      rng=seed_for(20261029, "probe-leak", cohort, cell))
            summary["leak"] = {"raw": float(result.gamma[0, 1]), "corrected": float(result.gamma_corrected[0, 1]),
                               "p_value": float(result.p_value[0, 1]), "n_observed_bids": len(actions)}
        summaries.append(summary)
    return {"status": "supplied", "records": records, "summaries": summaries, "incomplete_contexts": skipped,
            "note": "Context-level slope requires all 3 costs x 5 valid bids; failures remain published. Leak uses observed bids."}
