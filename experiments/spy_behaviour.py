"""Descriptive post-hoc analysis of how the spy used the stolen cost (not pre-registered).

E1 markets 0-19 (Qwen3.5-9B): the spy is a strong firm told the other strong firm's current
cost. Each E1 market is compared with the honest N0 market of the same index (same costs, same
seats). Reports, on complete rounds:
  * profit per round of the spy seat and the victim seat in E1 and in the honest twin;
  * the spy's mean bid by the victim's cost, averaged over the spy's own cost (does the bid react
    to the stolen information?), and the same for the same seat in honest markets;
  * static counterfactuals against the observed bids of the other three firms (no reactions):
    the spy's profit under "bid cost + 1" and under a simple informed rule.

Usage: .venv/Scripts/python experiments/spy_behaviour.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from collusion.analysis.io import load_collection  # noqa: E402

OUT = ROOT / "results" / "spy_behaviour"


def expected_win(bid, others):
    others = [b for b in others if 2 <= b <= 7]
    if any(b < bid for b in others):
        return 0.0
    return 1.0 / (1 + sum(b == bid for b in others))


def informed_rule(own, victim):
    """Bid just at the victim's cost when that beats own cost, otherwise cost + 1."""
    return max(2, victim) if victim > own else max(2, min(7, own + 1))


def counterfactual(bids, costs, spy, victim, rule):
    total = 0.0
    for b, c in zip(bids, costs):
        bid = rule(c[spy], c[victim])
        total += expected_win(bid, [b[k] for k in range(4) if k != spy]) * (bid - c[spy])
    return total / len(bids)


def bid_by_victim_cost(bids, costs, spy, victim):
    """Mean spy bid for each victim cost, averaged over the spy's own cost (equal weights)."""
    out = {}
    for v in (1, 2, 3):
        cells = [bids[(costs[:, spy] == o) & (costs[:, victim] == v), spy] for o in (1, 2, 3)]
        out[v] = float(np.mean([x.mean() for x in cells if len(x)]))
    return out


def main():
    runs = json.loads((ROOT / "results" / "analysis_runs.json").read_text(encoding="utf-8"))["runs"]
    path = next(r["path"] for r in runs if r["cell"] == "core.E1")
    markets, _ = load_collection(ROOT / "results", ROOT / "experiments" / "manifests" / "collection_v2.json")
    honest = {m.index: m for m in markets if m.cohort == "registered" and m.cell == "core.N0" and m.eligible}
    rows = []
    for m in sorted((m for m in markets if m.cohort == "registered" and m.cell == "core.E1"
                     and m.index < 20 and m.eligible), key=lambda m: m.index):
        meta = json.loads((ROOT / "results" / path / f"market_{m.index:05d}.json").read_text(encoding="utf-8"))
        spy, victim = meta["metadata"]["assignment"]["spy_receiver"], meta["metadata"]["assignment"]["spy_victim"]
        h = honest[m.index]
        keep, hkeep = m.complete.astype(bool), h.complete.astype(bool)
        b, c, p = m.bids[keep], m.costs[keep], m.payoffs[keep]
        hb, hc, hp = h.bids[hkeep], h.costs[hkeep], h.payoffs[hkeep]
        e1_bid, n0_bid = bid_by_victim_cost(b, c, spy, victim), bid_by_victim_cost(hb, hc, spy, victim)
        rows.append({"index": m.index, "spy_profit": p[:, spy].mean(), "spy_profit_honest_twin": hp[:, spy].mean(),
                     "victim_profit": p[:, victim].mean(), "victim_profit_honest_twin": hp[:, victim].mean(),
                     "spy_win_share": float((m.winners[keep] == spy).mean()),
                     "spy_win_share_honest_twin": float((h.winners[hkeep] == spy).mean()),
                     **{f"spy_bid_victim_cost_{v}": e1_bid[v] for v in (1, 2, 3)},
                     **{f"twin_bid_victim_cost_{v}": n0_bid[v] for v in (1, 2, 3)},
                     "cf_spy_cost_plus_1": counterfactual(b, c, spy, victim, lambda o, v: max(2, min(7, o + 1))),
                     "cf_spy_informed": counterfactual(b, c, spy, victim, informed_rule)})
    keys = [k for k in rows[0] if k != "index"]
    summary = {"markets": len(rows), **{k: round(float(np.mean([r[k] for r in rows])), 4) for k in keys}}
    diff = np.array([r["spy_profit"] - r["spy_profit_honest_twin"] for r in rows])
    rng = np.random.default_rng(20261025)
    boot = [rng.choice(diff, len(diff)).mean() for _ in range(10000)]
    summary["spy_profit_minus_twin"] = round(float(diff.mean()), 4)
    summary["spy_profit_minus_twin_ci"] = [round(float(np.percentile(boot, q)), 4) for q in (2.5, 97.5)]
    summary["markets_spy_gained"] = int((diff > 0).sum())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps({"summary": summary, "markets": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
