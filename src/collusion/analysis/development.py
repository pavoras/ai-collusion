"""Offline known-truth fixtures and honest-vs-honest Monte Carlo validation."""

import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

import numpy as np

from collusion.games import auction
from collusion.llm.backend import FakeBackend
from collusion.llm.runner import RunConfig, run
from collusion.llm.storage import CallService, seed_for
from collusion.measures import pair_score, symmetric_permutation_test
from .inference import exact_rate, primary_test
from .io import adapt_legacy_assignment, compact_record, read_json
from .market import PAIRS, history

SEED = 20261030


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def scripted_record(index, cell, *, seed=SEED, independent_honest=False):
    """Convert the public auction simulator into exactly the harness JSON arrays."""
    strong = PAIRS[index % 6]
    fringe = tuple(s for s in range(4) if s not in strong)
    pair = ((strong[0], fringe[0]) if cell["id"] == "C1-SF" else fringe if cell["id"] == "C1-FF" else strong)
    condition = cell["condition"]
    config = {"condition": condition, "strong": list(strong), "pair": list(pair),
              "models": ["qwen-9b"] * 4, "seed": seed}
    kwargs = {"spy": pair} if condition == "E1" else ({"cartel": pair, "q": .5 if condition == "C2" else 1.0}
                                                       if condition in ("C1", "C2", "P0") else {})
    market = auction.play(200, seed=seed, market_index=index, strong=strong, **kwargs)
    if independent_honest:
        noise = np.random.default_rng([seed, index, 777]).integers(0, 2, (200, 4))
        market.bids = auction.honest_bid(market.costs, noise)
        ties = np.random.default_rng([seed, index, 1]).random(200)
        market.winners, market.payoffs = auction.settle(market.bids, market.costs, ties)
    assignment = adapt_legacy_assignment(config)
    data = {"schema": 1, "market_index": index, "planned_rounds": 200, "status": "complete",
            "bids": market.bids.tolist(), "costs": market.costs.tolist(), "winners": market.winners.tolist(),
            "payoffs": market.payoffs.tolist(), "invalid": [[False] * 4] * 200,
            "complete_round_mask": [True] * 200, "assignment": assignment}
    metadata = {"data_kind": "scripted", "config": config,
                "note": "Development only: C1/P0 q=1; C2 q=.5 is a scripted illustration, not a tacit LLM policy."}
    return compact_record(data, metadata, cell)


def make_development_collection(root, *, quick=False, include_fake=True):
    """Core 160 markets at full size, or 44 at quick size; never real outputs."""
    root = Path(root)
    n = 6 if quick else 20
    cells = []
    for name, condition in (("N0", "N0"), ("P0", "P0"), ("C1-SS", "C1"), ("C1-SF", "C1"),
                            ("C1-FF", "C1"), ("C2", "C2"), ("E1", "E1")):
        indices = list(range(8 if quick and name == "N0" else 40 if name == "N0" else n))
        cell = {"id": name, "condition": condition, "model": "qwen-9b", "cohort": "registered",
                "rounds": 200, "market_indices": indices, "control": None if name == "N0" else "N0"}
        cells.append(cell)
        directory = root / name
        for index in indices:
            record = scripted_record(index, cell)
            save(directory / f"market_{index:05d}.json", record.metadata)
        save(directory / "run_metadata.json", record.run_metadata)
    runs = [{"cell": c["id"], "cohort": c["cohort"], "path": c["id"]} for c in cells]
    if include_fake:
        fake_cell = {"id": "fake-N0", "condition": "N0", "model": "qwen-9b", "cohort": "fake",
                     "rounds": 200, "market_indices": [0], "control": None}
        with tempfile.TemporaryDirectory(prefix="fake_backend_", dir=root) as temporary:
            snapshot = Path(temporary) / "collection.json"
            save(snapshot, read_json(RunConfig().collection_manifest))
            config = RunConfig(rounds=200, collection_manifest=str(snapshot))
            service = CallService(FakeBackend(), temporary, "analysis_format_v2", max_calls=1000, concurrency=8)
            try:
                state = asyncio.run(run(config, service))[0]
                # Only older fake harness versions need the explicit legacy adapter.
                if not state.get("metadata", {}).get("assignment"):
                    state.setdefault("assignment", adapt_legacy_assignment(asdict(RunConfig())))
                state.setdefault("complete_round_mask", [all(b is not None for b in row) for row in state["bids"]])
                save(root / "fake-N0" / "market_00000.json", state)
                save(root / "fake-N0" / "run_metadata.json", {"data_kind": "fake", "config": asdict(RunConfig()),
                                                            "operations": {"calls": service.calls}})
            finally:
                service.close()
        cells.append(fake_cell)
        runs.append({"cell": "fake-N0", "cohort": "fake", "path": "fake-N0"})
    save(root / "collection.json", {"schema": "analysis-dev-v2", "data_kind": "scripted_and_fake", "cells": cells})
    save(root / "analysis_runs.json", {"runs": runs})
    return root / "collection.json"


def _size_cohort(task):
    repetition, n_blocks, n_perm = task
    negative, positive = [], []
    for index in range(n_blocks):
        cell = {"id": "N0", "condition": "N0", "model": "qwen-9b", "cohort": "size-check",
                "rounds": 200, "market_indices": list(range(n_blocks)), "control": None}
        for independent, scores in ((False, negative), (True, positive)):
            record = scripted_record(index, cell, seed=SEED + 100 + repetition, independent_honest=independent)
            result = symmetric_permutation_test(record.bids - 2, list(record.costs.T), public_state=history(record),
                                                n_perm=n_perm, rng=seed_for("size", repetition, index, independent))
            pair = tuple(sorted(record.assignment["designated_pair"]))
            scores.append(float(pair_score(result.net_corrected)[pair]))
    result = primary_test(negative, positive)
    return {"repetition": repetition, "negative_scores": negative, "positive_scores": positive, **result}


def size_check(repetitions=100, n_blocks=20, n_perm=999, workers=1):
    """Fresh independent simulated honest cohorts; full registered swap test."""
    from .pipeline import _parallel
    results = _parallel(_size_cohort, [(r, n_blocks, n_perm) for r in range(repetitions)], workers)
    return {"description": "Fresh honest-vs-honest paired-cost cohorts, independently seeded own-bid noise",
            "simulation_seed": SEED + 100, "per_market_permutations": n_perm, "blocks_per_cohort": n_blocks,
            "repetitions": repetitions, "rejection_rate": exact_rate(sum(r["reject"] for r in results), repetitions),
            "cohorts": results}
