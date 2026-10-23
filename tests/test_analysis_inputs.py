"""Manifest enforcement, original chronology and common eligibility rules."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import asyncio
import json

import numpy as np
import pytest

from collusion.analysis.development import save, scripted_record
from collusion.analysis.io import (adapt_collection_manifest, compact_record, load_collection,
                                   load_judges, operational_report)
from collusion.analysis.market import analyze_market, history


@pytest.fixture
def tmp_path():
    parent = Path(__file__).resolve().parents[1] / "results/analysis_dev/test_temp"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as directory:
        yield Path(directory)


def cell(name="N0", indices=None):
    return {"id": name, "condition": "C1" if name == "C1-SS" else name,
            "model": "qwen-9b", "cohort": "registered", "rounds": 200,
            "market_indices": list(range(20)) if indices is None else indices,
            "control": "N0" if name != "N0" else None}


def test_collection_refuses_undeclared_and_keeps_cohorts_separate(tmp_path):
    c = cell(indices=[0])
    record = scripted_record(0, c)
    save(tmp_path / "N0/run_metadata.json", record.run_metadata)
    save(tmp_path / "N0/market_00000.json", record.metadata)
    save(tmp_path / "manifest.json", {"cells": [c]})
    save(tmp_path / "analysis_runs.json", {"runs": [{"cell": "N0", "path": "N0"}]})
    records, manifest = load_collection(tmp_path, tmp_path / "manifest.json")
    assert len(records) == 1
    report = operational_report(records, manifest)
    assert report["validated_markets"] == 1 and "primary" not in report
    repeated = operational_report([records[0], replace(records[0], cohort="deviation", run_metadata={})], manifest)
    assert len(repeated["operations_by_run"]) == 2
    assert all("calls" in run for run in repeated["operations_by_run"])
    bad = deepcopy(record.metadata)
    bad["market_index"] = 1
    save(tmp_path / "N0/market_00001.json", bad)
    with pytest.raises(ValueError, match="not declared"):
        load_collection(tmp_path, tmp_path / "manifest.json")
    deviation = {**c, "cohort": "deviation-temperature"}
    assert len(adapt_collection_manifest({"cells": [c, deviation]})) == 2
    with pytest.raises(ValueError, match="same cohort"):
        adapt_collection_manifest({"cells": [c, {**cell("C1-SS"), "cohort": "deviation"}]})


def test_round_extensions_and_missing_assignment_refused():
    c = cell()
    record = scripted_record(0, c)
    bad = deepcopy(record.metadata)
    bad["planned_rounds"] = 201
    with pytest.raises(ValueError, match="not declared"):
        compact_record(bad, record.run_metadata, c)
    bad = deepcopy(record.metadata)
    del bad["assignment"]
    with pytest.raises(ValueError, match="assignment missing"):
        compact_record(bad, record.run_metadata, c)
    bad = deepcopy(record.metadata)
    bad["complete_round_mask"][0] = False
    with pytest.raises(ValueError, match="mask"):
        compact_record(bad, record.run_metadata, c)


def test_common_mask_history_and_twenty_round_boundary():
    c = cell()
    record = scripted_record(0, c)
    data = deepcopy(record.metadata)
    # Incomplete round with a real winner must still update H; all-missing carries.
    for t in range(20):
        data["bids"][t] = [None] * 4
        data["invalid"][t] = [True] * 4
        data["winners"][t] = -1
        data["payoffs"][t] = [0] * 4
        data["complete_round_mask"][t] = False
    parsed = compact_record(data, record.run_metadata, c)
    assert parsed.eligible and parsed.missing_rounds == 20
    assert np.all(history(parsed)[:21] == 0)
    output = analyze_market((parsed, 9, (50, 200), True))
    assert [v["n_rounds"] for v in output["views"]] == [30, 50, 180, 200]
    assert all(len(v["leaks"]) == 12 for v in output["views"])
    assert all(v["levels"]["L1"]["scores"]["strength"] == [1, 0, 0, 0, 0, 0] for v in output["views"])
    assert not replace(parsed, complete=np.r_[np.zeros(21, bool), np.ones(179, bool)]).eligible
    assert not replace(record, bids=record.bids[:179], complete=record.complete[:179]).eligible
    bids = record.bids.copy()
    winners = record.winners.copy()
    bids[1] = 8
    winners[1] = -1
    changed = replace(record, bids=bids, winners=winners)
    assert history(changed)[2] == history(changed)[1] == record.bids[0, record.winners[0]]
    # A partially valid round keeps its original actual winning price.
    bids[1, 0] = 7
    winners[1] = 0
    assert history(changed)[2] == 7


def test_judge_failures_raw_probabilities_and_repeated_answers(tmp_path):
    j = {"cohort": "registered", "cell": "N0", "market_index": 0, "model": "qwen-9b", "level": "L1",
         "status": "invalid", "probabilities": None}
    save(tmp_path / "judges.json", {"judgments": [j]})
    assert load_judges(tmp_path / "judges.json")[0]["probabilities"] is None
    valid = {**j, "status": "complete", "probabilities": dict.fromkeys(("A-B", "A-C", "A-D", "B-C", "B-D", "C-D"), .9)}
    save(tmp_path / "judges.json", {"judgments": [valid]})
    assert sum(load_judges(tmp_path / "judges.json")[0]["probabilities"].values()) == pytest.approx(5.4)
    save(tmp_path / "judges.json", {"judgments": [j, valid]})
    with pytest.raises(ValueError, match="no answer selection"):
        load_judges(tmp_path / "judges.json")


def test_final_harness_format_with_native_manifest_and_partial_fake_run(tmp_path):
    from collusion.llm.backend import FakeBackend
    from collusion.llm.collection import DEFAULT_MANIFEST
    from collusion.llm.runner import RunConfig, run
    from collusion.llm.storage import CallService

    # The collection round may update its draft concurrently: pin this fixture.
    snapshot = tmp_path / "collection.json"
    save(snapshot, json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8")))
    service = CallService(FakeBackend(), tmp_path, "analysis_format_test", max_calls=8)
    try:
        state = asyncio.run(run(RunConfig(rounds=200, collection_manifest=str(snapshot)), service))[0]
    finally:
        service.close()
    assert len(state["bids"]) == 2
    save(tmp_path / "analysis_runs.json", {"runs": [{"cell": "core.N0", "path": "llm/analysis_format_test"}]})
    records, manifest = load_collection(tmp_path, snapshot)
    assert records[0].assignment["designated_pair"] == state["metadata"]["assignment"]["candidate_pairs"]["strong_strong"]
    assert records[0].assignment["roles"] == state["metadata"]["roles_by_seat"]
    assert not records[0].eligible
    assert records[0].run_metadata["reproducibility"]["static"]["manifest_hash"] == manifest["sha256"]
    assert operational_report(records, manifest)["validated_markets"] == 1
