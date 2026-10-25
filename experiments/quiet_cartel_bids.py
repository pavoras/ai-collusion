"""Descriptive post-hoc look at how the designated pair bids (not pre-registered).

Explains why the cartel without chat (C2) leaves little trace: for the designated pair in
Qwen markets 0-19 it reports how often both members submit the same bid, how concentrated
each member's bids are, and how much a member's bid still varies once its own cost is known
(conditional entropy H(B_i | C_i) in bits). Reads the registered collection only.

Usage: .venv/Scripts/python experiments/quiet_cartel_bids.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from collusion.analysis.io import load_collection  # noqa: E402

CELLS = {"core.N0": "honest (reference pair)", "core.C1-SS": "cartel with chat (two strong)",
         "core.C2": "cartel without chat (two strong)"}
OUT = ROOT / "results" / "quiet_cartel"


def entropy(values):
    counts = np.array(list(Counter(values).values()), dtype=float)
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum())


def conditional_entropy(bids, costs):
    total = len(bids)
    return sum((costs == c).sum() / total * entropy(bids[costs == c]) for c in np.unique(costs))


def market_stats(market):
    i, j = sorted(market.assignment["designated_pair"])
    keep = market.complete.astype(bool)
    bids, costs = market.bids[keep], market.costs[keep]
    members = [(bids[:, k], costs[:, k]) for k in (i, j)]
    return {"same_bid": float((bids[:, i] == bids[:, j]).mean()),
            "modal_share": float(np.mean([Counter(b).most_common(1)[0][1] / len(b) for b, _ in members])),
            "h_bid_given_cost": float(np.mean([conditional_entropy(b, c) for b, c in members])),
            "mean_bid": float(bids[:, [i, j]].mean()),
            "share_bid_3": float((bids[:, [i, j]] == 3).mean())}


def main():
    markets, _ = load_collection(ROOT / "results", ROOT / "experiments" / "manifests" / "collection_v2.json")
    rows = []
    for cell, label in CELLS.items():
        chosen = [m for m in markets if m.cohort == "registered" and m.cell == cell and m.index < 20 and m.eligible]
        stats = [market_stats(m) for m in chosen]
        row = {"cell": cell, "label": label, "markets": len(stats)}
        row.update({k: round(float(np.mean([s[k] for s in stats])), 4) for k in stats[0]})
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
