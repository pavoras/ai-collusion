"""Scientific estimands, frozen rules, matching and reproducibility."""

from dataclasses import replace

import numpy as np
import pytest
from scipy.stats import rankdata

from collusion.analysis.development import _size_cohort, scripted_record
from collusion.analysis.inference import (auc, block_weights, bootstrap_auc, exact_rate,
                                          localisation, primary_test)
from collusion.analysis.market import LABELS, PAIRS, analyze_market
from collusion.analysis.pipeline import analyze_collection, clean
from test_analysis_inputs import cell


def test_auc_swaps_and_rank_ties():
    assert auc([1, 1], [1, 1]) == .5
    assert auc([1, 2], [2, 3]) == .875
    loc = localisation([3, 3, 2, 1, 1, 0], 0, [1])
    assert loc == {"top1": .5, "mrr": 2 / 3, "correct_unique": 0, "wrong_pair": 1, "abstention": 0}
    assert localisation(np.ones(6), 0, [0, 1])["top1"] == 1 / 6
    assert localisation(np.ones(6), 0, [0, 1])["mrr"] == 1 / 3.5
    result = primary_test([1, 1], [1, 1])
    assert result["p_value"] == 1 and not result["reject"]
    assert primary_test([0] * 20, [1] * 20)["reject"]


def test_swap_implementation_matches_direct_auroc():
    negative, positive = np.array([0, 1, 1, 3]), np.array([1, 0, 2, 3])
    swaps = np.random.default_rng(20261027).integers(0, 2, (199, 4))
    observed = auc(negative, positive)
    exceed = sum(auc(np.where(s, positive, negative), np.where(s, negative, positive)) >= observed for s in swaps)
    result = primary_test(negative, positive, n_swaps=199)
    assert result["exceedances"] == exceed
    assert result["p_value"] == (1 + exceed) / 200


def test_shared_bootstrap_weights_and_auc():
    indices, weights = block_weights([2, 0, 1, 2], n_boot=30)
    assert indices == [0, 1, 2]
    assert (weights.sum(axis=1) == 3).all()
    negative, positive = np.array([0, 1, 2]), np.array([1, 2, 3])
    computed = bootstrap_auc(negative, positive, weights)
    for w, actual in zip(weights, computed):
        assert actual == pytest.approx(auc(np.repeat(negative, w), np.repeat(positive, w)))
    assert np.array_equal(weights, block_weights([0, 1, 2], n_boot=30)[1])
    assert exact_rate(0, 20)["low"] == 0 and exact_rate(20, 20)["high"] == 1


def test_scripted_cartel_primary_and_determinism():
    c0, c1 = cell("N0"), cell("C1-SS")
    markets = [scripted_record(i, c) for c in (c0, c1) for i in range(20)]
    # Registered 999 permutations and full 99,999 swaps; other costly secondaries are tested below.
    records = [analyze_market((m, 999, (200,), False)) for m in markets]
    negative, positive = [], []
    for r, scores in [(r, negative if r["cell"] == "N0" else positive) for r in records]:
        target = PAIRS.index(tuple(sorted(r["assignment"]["designated_pair"])))
        scores.append(r["views"][0]["levels"]["L2"]["scores"]["net"][target])
    primary = primary_test(negative, positive)
    assert primary["auroc"] >= .95 and primary["reject"]
    assert primary == primary_test(negative, positive)
    assert clean(records[0]) == clean(analyze_market((markets[0], 999, (200,), False)))


def test_matched_exclusion_labels_and_all_cells():
    c0, c1 = cell("N0", [0, 1]), cell("C1-SS", [0, 1])
    markets = [scripted_record(i, c) for c in (c0, c1) for i in (0, 1)]
    markets[0] = replace(markets[0], complete=np.zeros(200, bool))
    manifest = {"cells": [c0, c1], "sha256": "dev"}
    result = analyze_collection(markets, manifest, development=True, n_perm=9, n_boot=10,
                                fingerprint_boot=2, fingerprint_perm=3, prefixes=(200,), sensitivity=False)
    row = next(r for r in result["all_cells"] if r["cell"] == "C1-SS" and r["level"] == "L2" and r["detector"] == "net")
    assert row["auroc"]["n_blocks"] == 1 and row["matched_blocks_dropped"] == 1
    assert all("label:" + label in row for label in LABELS)
    assert sum(row["label:" + label] for label in LABELS) == row["coverage"]
    assert isinstance(result["primary"], dict)
    repeat = analyze_collection(markets, manifest, development=True, n_perm=9, n_boot=10,
                                fingerprint_boot=2, fingerprint_perm=3, prefixes=(200,), sensitivity=False, workers=2)
    del result["runtime"], repeat["runtime"]
    assert result == repeat
    with pytest.raises(ValueError, match="cannot be reduced"):
        analyze_collection(markets, manifest, n_perm=9)


def test_honest_cohort_size_smoke():
    # Eight fresh null cohorts cannot estimate a 5% rate precisely: a loose smoke guard only.
    results = [_size_cohort((r, 6, 19)) for r in range(8)]
    assert sum(r["reject"] for r in results) <= 3
    assert all(0 <= r["p_value"] <= 1 for r in results)


def test_displayed_judge_labels_follow_seats():
    from collusion.analysis.pipeline import _attach_judges
    record = analyze_market((scripted_record(0, cell()), 9, (200,), False))
    record["assignment"]["labels"] = ["Firm C", "Firm A", "Firm D", "Firm B"]
    judgment = {"cohort": "registered", "cell": "N0", "market_index": 0, "level": "L2", "prefix": 200,
                "mask": "complete", "model": "qwen-9b", "status": "complete",
                "probabilities": dict(zip(("A-B", "A-C", "A-D", "B-C", "B-D", "C-D"), np.arange(6) / 10))}
    _attach_judges({("registered", "N0", 0): record}, [judgment])
    scores = record["views"][0]["levels"]["L2"]["scores"]["judge:qwen-9b"]
    assert scores == [.1, .5, .3, .2, .0, .4]
    # Registered judge views cannot silently become prefix or no-bid judgments.
    manifest = {"entries": [{"phase": "judge", "judge_model": "qwen-9b", "levels": ["L1", "L2"],
                              "source_entries": "all_auction_entries"}]}
    with pytest.raises(ValueError, match="scope/view not declared"):
        _attach_judges({("registered", "N0", 0): record}, [{**judgment, "prefix": 50}], manifest)


def test_probe_slopes_weight_contexts_then_markets():
    from collusion.analysis.probes import analyze_probes
    records = []
    for index in (0, 1):
        for seat in (0, 1):
            for cost in (1, 2, 3):
                records.append({"cohort": "dev", "cell": "C1-SS", "market_index": index, "round": 110,
                                "seat": seat, "own_cost": 1, "partner_cost": cost, "bids": [cost + 2] * 5})
    result = analyze_probes(records, n_boot=20, n_perm=9)
    assert result["summaries"][0]["slope"]["estimate"] == 1
    assert result["summaries"][0]["complete_contexts"] == 4
    assert result["summaries"][0]["leak"]["raw"] == pytest.approx(np.log2(3))


def test_judge_comparisons_use_matched_coverage_and_unscaled_probabilities():
    c0, c1 = cell("N0", [0, 1]), cell("C1-SS", [0, 1])
    markets = [scripted_record(i, c) for c in (c0, c1) for i in (0, 1)]
    judgments = []
    for market in markets:
        labels = [f"{'ABCD'[i]}-{'ABCD'[j]}" for i, j in PAIRS]
        probabilities = dict.fromkeys(labels, .7)
        target = tuple(sorted(market.assignment["designated_pair"]))
        probabilities[f"{'ABCD'[target[0]]}-{'ABCD'[target[1]]}"] = .1 if market.cell == "N0" else .9
        failed = market.cell == "N0" and market.index == 1
        judgments.append({"cohort": "registered", "cell": market.cell, "market_index": market.index,
                          "level": "L2", "model": "qwen-9b", "prefix": 200, "mask": "complete",
                          "status": "failed" if failed else "complete", "probabilities": None if failed else probabilities})
    result = analyze_collection(markets, {"cells": [c0, c1]}, development=True, judgments=judgments,
                                n_perm=9, n_boot=20, fingerprint_boot=2, fingerprint_perm=3,
                                prefixes=(200,), sensitivity=False)
    row = next(r for r in result["all_cells"] if r["cell"] == "C1-SS" and r["level"] == "L2" and r["detector"] == "judge:qwen-9b")
    assert row["coverage"] == 2 and row["auroc"]["n_blocks"] == 1
    assert row["auroc"]["estimate"] == 1 and row["brier"] == pytest.approx(.01)
    assert row["correct_unique"] is None and row["artificial_prevalence"] == .5
    assert len(result["judgments"]) == 4
    assert all(c["detector_auroc"]["n_blocks"] == 1 for c in result["judge_comparisons"])


def test_ineligible_probe_sources_are_retained_without_outcome_estimates():
    c = cell("N0", [0])
    market = scripted_record(0, c)
    probes = [{"cohort": "registered", "cell": "N0", "market_index": 0, "round": 110, "seat": 0,
               "own_cost": int(market.costs[109, 0]), "partner_cost": cost, "bids": [cost + 2] * 5}
              for cost in (1, 2, 3)]
    market = replace(market, complete=np.zeros(200, bool))
    result = analyze_collection([market], {"cells": [c]}, development=True, probes=probes,
                                n_perm=3, n_boot=3, fingerprint_boot=1, fingerprint_perm=1,
                                prefixes=(200,), sensitivity=False)
    assert len(result["probes"]["records"]) == len(result["probes"]["excluded_source_market_records"]) == 3
    assert "summaries" not in result["probes"]
