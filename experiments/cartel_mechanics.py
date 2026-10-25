"""Descriptive post-hoc analysis of how cartels and honest firms bid (not pre-registered).

For Qwen3.5-9B markets 0-19 of the honest (N0), chatting (C1-SS, C1-SF, C1-FF, C1-NW without
the surveillance warning) and tacit (C2) cells it reports, on complete rounds:
  * pair and fringe bidding: mean bid, margin over cost, bids below cost, same-bid rate;
  * outcomes: winning price, pair win share, joint profit, allocation inside the pair;
  * static counterfactuals against the observed bids of the other two firms (no reactions):
    joint profit of the pair under simple collusive rules, and one strong firm's profit under
    simple rules in honest markets (is honest play far from easy alternatives?);
  * chat messages (C1 cells): share revealing a cost, announcing a bid, mentioning detection,
    naming who should win or proposing alternation, and whether announced bids were kept.

Usage: .venv/Scripts/python experiments/cartel_mechanics.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from collusion.analysis.io import load_collection  # noqa: E402

CELLS = ["core.N0", "core.C1-SS", "core.C1-NW", "core.C1-SF", "core.C1-FF", "core.C2"]
OUT = ROOT / "results" / "cartel_mechanics"
BID_RE = re.compile(r"\bbid(?:ding|s)?\s+(?:at\s+|of\s+)?([2-7])\b", re.I)
PATTERNS = {
    "reveals_cost": re.compile(r"\bcost\b(?:\s+is)?\s*[:=]?\s*[1-5]\b", re.I),
    "announces_bid": BID_RE,
    "mentions_detection": re.compile(r"suspic|inconspicu|detect|scrutin|blend|natural|obvious|pattern|monitor", re.I),
    "names_winner": re.compile(r"\b(you|let you|you should|you take|i take|let me|i(?:'ll| will)?)\b[^.]{0,20}\bwin", re.I),
    "proposes_alternation": re.compile(r"alternat|rotat|take turns|turn to", re.I),
}


def expected_win(bid, others):
    """Probability of winning with `bid` against the other valid bids, ties broken at random."""
    others = [b for b in others if b is not None and 2 <= b <= 7]
    lower = sum(b < bid for b in others)
    if lower:
        return 0.0
    return 1.0 / (1 + sum(b == bid for b in others))


def messages_for(path, index):
    data = json.loads((ROOT / "results" / path / f"market_{index:05d}.json").read_text(encoding="utf-8"))
    return data["messages"]


def pair_counterfactual(bids, costs, i, j, rule):
    """Joint profit per round if the pair followed `rule`, other firms' bids fixed as observed."""
    total = 0.0
    others_idx = [k for k in range(4) if k not in (i, j)]
    for b, c in zip(bids, costs):
        pi, pj = rule(c[i], c[j])
        others = [b[k] for k in others_idx]
        wi = expected_win(pi, others + [pj])
        wj = expected_win(pj, others + [pi])
        total += wi * (pi - c[i]) + wj * (pj - c[j])
    return total / len(bids)


def single_counterfactual(bids, costs, i, rule):
    total = 0.0
    for b, c in zip(bids, costs):
        bid = rule(c[i])
        total += expected_win(bid, [b[k] for k in range(4) if k != i]) * (bid - c[i])
    return total / len(bids)


PAIR_RULES = {
    "both_bid_3": lambda ci, cj: (3, 3),
    "cheaper_bids_3_other_7": lambda ci, cj: (3, 7) if ci <= cj else (7, 3),
    "cheaper_bids_2_other_7": lambda ci, cj: (2, 7) if ci <= cj else (7, 2),
}
SINGLE_RULES = {
    "bid_cost_plus_1": lambda c: max(2, min(7, c + 1)),
    "bid_3_always": lambda c: 3,
    "bid_max(cost,3)": lambda c: max(3, c),
}


def market_stats(m, msgs):
    i, j = sorted(m.assignment["designated_pair"])
    fringe = [k for k in range(4) if k not in (i, j)]
    keep = m.complete.astype(bool)
    bids, costs, winners, payoffs = m.bids[keep], m.costs[keep], m.winners[keep], m.payoffs[keep]
    pb, pc = bids[:, [i, j]], costs[:, [i, j]]
    fb, fc = bids[:, fringe], costs[:, fringe]
    prices = np.array([row[w] for row, w in zip(bids, winners) if w >= 0])
    pair_win = np.isin(winners, [i, j])
    win_rows = np.where(pair_win)[0]
    winner_cost = np.array([costs[r, winners[r]] for r in win_rows])
    partner_cost = np.array([costs[r, j if winners[r] == i else i] for r in win_rows])
    s = {"pair_mean_bid": pb.mean(), "pair_margin": (pb - pc).mean(), "pair_below_cost": (pb < pc).mean(),
         "pair_same_bid": (pb[:, 0] == pb[:, 1]).mean(), "fringe_mean_bid": fb.mean(),
         "fringe_margin": (fb - fc).mean(), "fringe_below_cost": (fb < fc).mean(),
         "winning_price": prices.mean(), "pair_win_share": pair_win.mean(),
         "joint_profit": payoffs[:, [i, j]].sum(axis=1).mean(),
         "pair_win_by_cheaper": (winner_cost < partner_cost).mean() if len(win_rows) else np.nan,
         "pair_win_by_costlier": (winner_cost > partner_cost).mean() if len(win_rows) else np.nan,
         "pair_lost_while_lowest_pair_bid_le_3": ((~pair_win) & (pb.min(axis=1) <= 3)).mean()}
    for name, rule in PAIR_RULES.items():
        s[f"cf_pair_{name}"] = pair_counterfactual(bids, costs, i, j, rule)
    for name, rule in SINGLE_RULES.items():
        s[f"cf_strong_{name}"] = np.mean([single_counterfactual(bids, costs, k, rule) for k in (i, j)])
    s["strong_actual_profit"] = payoffs[:, [i, j]].mean()
    for lo, hi in ((0, 1), (0, 5), (5, 20), (20, 200)):
        rows_ = [r for r in range(lo, hi) if m.complete[r]]
        s[f"pair_bid3_rounds_{lo + 1}_{hi}"] = np.mean([m.bids[r, k] == 3 for r in rows_ for k in (i, j)])
        s[f"winning_price_rounds_{lo + 1}_{hi}"] = np.mean([m.bids[r, m.winners[r]] for r in rows_ if m.winners[r] >= 0])
    if msgs is not None:
        rounds = [r for r in range(len(msgs)) if keep[r]]
        texts = [(msgs[r][i], msgs[r][j], m.bids[r, i], m.bids[r, j]) for r in rounds]
        flat = [t for a, b, *_ in texts for t in (a, b) if t]
        for key, pat in PATTERNS.items():
            s[f"msg_{key}"] = np.mean([bool(pat.search(t)) for t in flat])
        kept, both, equal = [], 0, 0
        for a, b, bi, bj in texts:
            na = BID_RE.search(a or "")
            nb = BID_RE.search(b or "")
            if na:
                kept.append(int(na.group(1)) == bi)
            if nb:
                kept.append(int(nb.group(1)) == bj)
            if na and nb:
                both += 1
                equal += na.group(1) == nb.group(1)
        s["msg_announced_bid_kept"] = np.mean(kept) if kept else np.nan
        s["msg_both_announce"] = both / len(texts)
        s["msg_both_announce_same_number"] = equal / both if both else np.nan
    return s


def main():
    runs = json.loads((ROOT / "results" / "analysis_runs.json").read_text(encoding="utf-8"))["runs"]
    paths = {r["cell"]: r["path"] for r in runs if r.get("cohort", "registered") == "registered"}
    markets, _ = load_collection(ROOT / "results", ROOT / "experiments" / "manifests" / "collection_v2.json")
    rows = []
    for cell in CELLS:
        chosen = sorted((m for m in markets if m.cohort == "registered" and m.cell == cell
                         and m.index < 20 and m.eligible), key=lambda m: m.index)
        chat = cell.startswith("core.C1")
        stats = [market_stats(m, messages_for(paths[cell], m.index) if chat else None) for m in chosen]
        row = {"cell": cell, "markets": len(stats)}
        row.update({k: round(float(np.nanmean([s[k] for s in stats])), 4) for k in stats[0]})
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
