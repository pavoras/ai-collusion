"""Operational cost projections for the provisional PLAN v4 scope, not outcomes."""

import csv
import math
from copy import deepcopy

from .sampling import MODEL_CONFIG
from .storage import write_json
from .collection import ROLES, V2_MANIFEST, collection_hash, indices_for, load_collection, rounds_for


def scope_projection(calls_per_hour, *, fake=False, probe_calls=None, judge_work_factor=10, manifest=None):
    """Scale GPU time linearly by nominal parameters and an explicit judge factor."""
    manifest = manifest or load_collection()
    probe_calls = manifest["parameters"]["probe_calls"]["value"] if probe_calls is None else probe_calls
    if probe_calls < 0 or not math.isfinite(judge_work_factor) or judge_work_factor <= 0:
        raise ValueError("nonnegative probe calls and positive judge work factor required")
    rows = []

    def add(block, condition, model, markets, calls_per_market, *, total=None, judge=False):
        config = MODEL_CONFIG[model]
        calls = markets * calls_per_market if total is None else total
        factor = config["parameters_b"] / 9 * (judge_work_factor if judge else 1)
        hours = calls / calls_per_hour * factor if calls_per_hour and calls_per_hour > 0 else None
        basis = ("offline fake illustration; not a spending estimate" if fake else
                 "measured qwen-9b bidder rate" if model == "qwen-9b" and not judge else "scaled assumption")
        rows.append({"block": block, "condition": condition, "model": model,
                     "calls_per_market": calls_per_market, "markets_per_block": markets,
                     "calls": calls, "gpu": config["gpu"], "usd_per_gpu_hour": config["usd_per_hour"],
                     "time_scale_vs_qwen9_bidder": factor, "basis": basis,
                     "projected_gpu_hours": hours, "projected_usd": hours * config["usd_per_hour"] if hours is not None else None})

    auctions = [e for e in manifest["entries"] if e["phase"] == "auction"]
    for entry in auctions:
        allocation = {}
        position = {"strong_strong": ROLES[:2], "strong_fringe": (ROLES[0], ROLES[2]), "fringe_fringe": ROLES[2:]}[entry["position"]]
        for role, model in entry["models_by_role"].items():
            per_round = 0 if entry["condition"] == "P0" and role in ROLES[:2] else 1
            if entry["condition"] in ("C1", "C1-NW", "C1-XX", "C1-XY", "M2") and role in position:
                per_round += 1
            allocation[model] = allocation.get(model, 0) + per_round * rounds_for(manifest, entry)
        for model, calls in allocation.items():
            if calls:
                add(entry["block"], entry["id"].split(".", 1)[1], model, len(indices_for(manifest, entry)), calls)
    add("probes", "declared partner-cost grid (or explicit projection override)", "qwen-9b", None, None, total=probe_calls)
    market_count = sum(len(indices_for(manifest, entry)) for entry in auctions)
    add("judge", "L1 + L2", "qwen-9b", market_count, 2, judge=True)
    add("judge spot check", "L1 + L2", "gemma-12b", 20 if manifest["manifest_version"] == "collection_v2" else 10, 2, judge=True)
    available = all(r["projected_gpu_hours"] is not None for r in rows)
    block_totals = []
    for block in dict.fromkeys(r["block"] for r in rows):
        selected = [r for r in rows if r["block"] == block]
        block_totals.append({"block": block, "calls": sum(r["calls"] for r in selected),
                             "projected_gpu_hours": sum(r["projected_gpu_hours"] for r in selected) if available else None,
                             "projected_usd": sum(r["projected_usd"] for r in selected) if available else None})
    return {"scope": f"{manifest['manifest_version']} provisional counts: {market_count} markets; pilot data are included in core",
            "measurement_source": "offline_fake_not_endpoint_performance" if fake else "qwen-9b N0/P0 under load",
            "measured_calls_per_hour": None if fake else calls_per_hour,
            "baseline_calls_per_hour_used": calls_per_hour,
            "assumptions": ["Same GPU efficiency for A10 and L40S; time per call scales as nominal parameters / 9.",
                            "Gemma E4B uses 4B as the nominal scaling proxy; architecture and token throughput are unmeasured.",
                            "All bidder/message/probe calls have equal work per call; thinking is not included in the measured bidder rate.",
                            f"Judge calls take {judge_work_factor:g} times bidder work, additionally scaled by parameters.",
                            f"Probe grid/explicit projection override: {probe_calls} total calls, not additional markets.",
                            "Mixed rows allocate calls per endpoint; GPU hours are summed across endpoints.",
                            "Excludes retries, warm-ups, idle billing and other-model cold starts; counts are not frozen sample sizes."],
            "rows": rows, "block_totals": block_totals, "total_calls": sum(r["calls"] for r in rows),
            "total_projected_gpu_hours": sum(r["projected_gpu_hours"] for r in rows) if available else None,
            "total_projected_usd": sum(r["projected_usd"] for r in rows) if available else None}


def save_projection(out, projection):
    write_json(out / "projection.json", projection)
    with (out / "projection.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(projection["rows"][0]))
        writer.writeheader()
        writer.writerows(projection["rows"])
    with (out / "projection_blocks.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(projection["block_totals"][0]))
        writer.writeheader()
        writer.writerows(projection["block_totals"])


def projection_table(projection):
    """A printable table contains design counts and cost arithmetic only."""
    lines = ["Scope projection: " + projection["measurement_source"],
             "Block | Condition | Model | Calls/market | Markets | Calls | GPU ($/h) | GPU hours | USD | Basis"]
    for row in projection["rows"]:
        hours = f"{row['projected_gpu_hours']:.4f}" if row["projected_gpu_hours"] is not None else "unknown"
        usd = f"{row['projected_usd']:.4f}" if row["projected_usd"] is not None else "unknown"
        lines.append(f"{row['block']} | {row['condition']} | {row['model']} | {row['calls_per_market']} | "
                     f"{row['markets_per_block']} | {row['calls']} | {row['gpu']} ({row['usd_per_gpu_hour']:.2f}) | {hours} | {usd} | {row['basis']}")
    for block in projection["block_totals"]:
        lines.append(f"BLOCK TOTAL | {block['block']} | calls={block['calls']} | GPU hours={block['projected_gpu_hours']} | USD={block['projected_usd']}")
    lines.append(f"TOTAL | calls={projection['total_calls']} | GPU hours={projection['total_projected_gpu_hours']} | USD={projection['total_projected_usd']}")
    lines.extend("Assumption: " + assumption for assumption in projection["assumptions"])
    return "\n".join(lines)


def budget_projection(calls_per_hour, *, overhead_usd=None, judge_work_factor=10):
    """Project the frozen cumulative cut ladder; never authorize collection."""
    if not math.isfinite(calls_per_hour) or calls_per_hour <= 0:
        raise ValueError("positive measured rate required")
    if overhead_usd is not None and (not math.isfinite(overhead_usd) or overhead_usd < 0):
        raise ValueError("nonnegative startup/idle allowance required")
    manifest = load_collection(V2_MANIFEST)
    rows = []
    for step, branch in enumerate(("B0+", "B0+A1+A2", "B0+A1", "B0", "B1", "B2", "B3", "B4", "B5")):
        m = deepcopy(manifest)
        auctions = [e for e in m["entries"] if e["phase"] == "auction"]
        if step >= 1:
            auctions = [e for e in auctions if not e["id"].endswith(".A3")]
        if step >= 2:
            auctions = [e for e in auctions if e["block"] != "lookalike"]
        if step >= 3:
            auctions = [e for e in auctions if e["id"] != "core.C1-NW"]
        if step >= 4:
            auctions = [e for e in auctions if e["id"] != "core.C1-FF"]
        if step >= 5:
            m["parameters"]["core_n0_markets"]["value"] = 20
        if step >= 6:
            auctions = [e for e in auctions if not e["id"].startswith(("sizes.gemma-e4b.", "sizes.ministral-3b."))]
        if step >= 7:
            auctions = [e for e in auctions if e["id"] not in ("mixed.H-XYZZ", "mixed.C1-XY")]
        if step >= 8:
            for key in ("breadth_markets", "mixed_markets"):
                m["parameters"][key]["value"] = 6
        m["entries"] = auctions
        p = scope_projection(calls_per_hour, manifest=m, judge_work_factor=judge_work_factor)
        total = (p["total_projected_usd"] + overhead_usd) * 1.15 if overhead_usd is not None else None
        rows.append({"branch": branch, "calls": p["total_calls"], "work_usd": p["total_projected_usd"],
                     "startup_idle_usd": overhead_usd, "reserve_fraction": .15, "total_usd": total,
                     "fits_45_usd": total <= 45 if total is not None else None})
    return {"manifest_hash": collection_hash(manifest),
            "branches": rows, "selected": next((r["branch"] for r in rows if r["fits_45_usd"]), None),
            "cut_order": manifest["cancellation_policy"], "execution_order": manifest["execution_order"],
            "execution_schedule": manifest["execution_schedule"],
            "hard_cap_usd": 50, "selection_note": "Only unstarted work may be cancelled; spent costs remain charged. "
            "Missing overhead prevents branch selection. Retries/other unmeasured work must fit the reserve."}


def save_budget_projection(output, projection):
    """Persist branch arithmetic and a single-axis budget figure."""
    write_json(output / "projection.json", projection)
    with (output / "projection.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(projection["branches"][0]))
        writer.writeheader()
        writer.writerows(projection["branches"])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from collusion import plotting
    plotting.apply_style()
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    rows = projection["branches"]
    totals = [r["total_usd"] for r in rows]
    if all(t is not None for t in totals):
        ax.bar([r["branch"] for r in rows], totals, color=plotting.BLUE, label="Work + startup/idle + 15% reserve")
    else:
        ax.bar([r["branch"] for r in rows], [r["work_usd"] for r in rows], color=plotting.BLUE,
               label="Work only; overhead missing, branch selection unavailable")
    ax.axhline(45, color=plotting.ORANGE, linestyle="--", label="Branch threshold $45")
    ax.set(ylabel="Projected USD", xlabel="Cumulative cuts")
    ax.legend()
    fig.savefig(output / "projection.png")
    plt.close(fig)
