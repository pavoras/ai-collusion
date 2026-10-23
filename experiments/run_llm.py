"""Run seed-paired LLM procurement markets or frozen-context probes.

Offline smoke: .venv/Scripts/python experiments/run_llm.py --run smoke_fake --smoke --dry-run
Live smoke: supply --endpoint qwen-9b=https://... and omit --dry-run.
Resuming uses the same run ID and science configuration; increase --max-calls
explicitly if the previous cap stopped the run. Never remove the raw cache to
resolve an uncertain submission: reconcile that request with the provider.
"""

import argparse
import asyncio
import json
from pathlib import Path
import time

from collusion.llm.backend import BackendError
from collusion.llm.cli import add_backend_args, make_service, plot_probe, save_summary, telemetry
from collusion.llm.probes import frozen_draw, partner_cost_draw
from collusion.llm.pilot import PilotLimits, run_pilot
from collusion.llm.projection import projection_table, budget_projection, save_budget_projection
from collusion.llm.runner import CONDITIONS, RunConfig, RunLock, run
from collusion.llm.storage import BudgetStop, UncertainCall, digest, seed_for, write_json
from collusion.llm.collection import ROLES, authorize, authorize_probe, collection_hash, entry_for, indices_for, load_collection, rounds_for
from collusion.llm.reproducibility import write_reproducibility
from collusion.llm.prompts import VERSION
from types import SimpleNamespace


async def probes(args, service, probe_config):
    if not args.source_call or args.probe_draws < 1:
        raise ValueError("probes require --source-call and positive --probe-draws")
    source = json.loads(Path(args.source_call).read_text(encoding="utf-8"))
    partner = None
    if args.probe == "partner-cost":
        if not args.partner_call or args.partner_cost is None:
            raise ValueError("partner-cost requires --partner-call and --partner-cost")
        partner = json.loads(Path(args.partner_call).read_text(encoding="utf-8"))
    entry = authorize_probe(probe_config, source, partner, args.probe, args.partner_cost, args.probe_draws)
    message_seed = seed_for(args.seed, "declared_partner_message", source["market"], source["round"],
                            source["seat"], args.partner_cost) if entry else None
    out = service.root / "llm" / service.run_id
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"mode": args.probe, "source": source["request_hash"], "partner": partner["request_hash"] if partner else None,
                "prompt_version": VERSION, "manifest_hash": collection_hash(load_collection(args.collection_manifest)),
                "deviation_cohort": args.deviation_cohort, "deviation_reason": args.deviation_reason,
                "cost": args.partner_cost, "seed": args.seed, "message_seed": message_seed, "draws": args.probe_draws,
                "endpoints": {m: service.backend.identity(m) for m in
                              {source["model"], partner["model"] if partner else source["model"]}}}
    with RunLock(service.raw_dir / "run.lock"):
        config = service.raw_dir / "config.json"
        if config.exists() and digest(json.loads(config.read_text(encoding="utf-8"))) != digest(manifest):
            raise ValueError("probe configuration changed; choose a new run_id")
        write_json(config, manifest)
        write_reproducibility(service, probe_config, [args.entry or "core.probes"])
        path = out / "probes.json"
        values = json.loads(path.read_text(encoding="utf-8"))["draws"] if path.exists() else []
        status = "complete"
        try:
            for i in range(len(values), args.probe_draws):
                seed = seed_for(args.seed, i)
                value = (await partner_cost_draw(service, source, partner, cost=args.partner_cost, seed=seed, message_seed=message_seed)
                         if partner else await frozen_draw(service, source, seed=seed, honest_reference=args.probe == "honest"))
                values.append(value)
                write_json(path, {"status": "running", "draws": values})
        except (BudgetStop, UncertainCall, BackendError) as error:
            status = type(error).__name__
        result = {"status": status, "draws": values}
        write_json(path, result)
        return result


async def main(args):
    if args.project_calls_per_hour is not None:
        projection = budget_projection(args.project_calls_per_hour, overhead_usd=args.projection_overhead_usd,
                                       judge_work_factor=args.judge_work_factor)
        output = Path(args.results) / args.run
        save_budget_projection(output, projection)
        print(json.dumps(projection, indent=2))
        return 0
    manifest = load_collection(args.collection_manifest)
    args.seed = manifest["run_seed"] if args.seed is None else args.seed
    selected = next((e for e in manifest["entries"] if e["id"] == args.entry), None) if args.entry else None
    args.market_start = args.market_start if args.market_start is not None else (indices_for(manifest, selected)[0]
        if selected and "market_indices" in selected else 0)
    args.condition = args.condition or (selected["condition"] if selected and selected["phase"] == "auction" else "N0")
    args.cartel_position = args.cartel_position or (selected.get("position", "strong_strong") if selected else "strong_strong")
    if args.models is None:
        args.models = [selected["models_by_role"][r] for r in ROLES] if selected and "models_by_role" in selected else ["qwen-9b"]
    models = tuple(args.models * 4) if len(args.models) == 1 else tuple(args.models)
    if len(models) != 4:
        raise ValueError("--models takes one model or four models in strong_0,strong_1,fringe_0,fringe_1 order")
    if selected is None and not args.probe:
        try:
            selected = entry_for(SimpleNamespace(entry_id=args.entry, condition=args.condition, models=models,
                                                cartel_position=args.cartel_position), manifest)
        except ValueError:
            if not args.deviation_cohort:
                raise
    args.rounds = args.rounds if args.rounds is not None else (rounds_for(manifest, selected) if selected and "round_count_parameter" in selected else manifest["parameters"]["rounds"]["value"])
    args.markets = args.markets if args.markets is not None else (1 if args.smoke else len(indices_for(manifest, selected)) if selected and "market_indices" in selected else 1)
    if args.smoke and (args.condition != "N0" or args.markets != 1 or len(set(models)) != 1 or args.probe):
        raise ValueError("--smoke requires exactly one N0 market, one model and no probes")
    if args.gpu_hourly_usd is not None and args.gpu_hourly_usd < 0:
        raise ValueError("GPU rate cannot be negative")
    if args.pilot and (args.smoke or args.probe or args.condition != "N0" or models != ("qwen-9b",) * 4):
        raise ValueError("--pilot requires qwen-9b only and cannot be combined with smoke/probes/other conditions")
    if args.quick:
        args.rounds = min(args.rounds, 12 if args.pilot else 3)
        args.markets = 1
    config = RunConfig(condition=args.condition, models=models, rounds=args.rounds, markets=args.markets,
                       market_start=args.market_start, seed=args.seed, compliance=args.compliance,
                       cartel_position=args.cartel_position, entry_id=args.entry, collection_manifest=args.collection_manifest,
                       deviation_cohort=args.deviation_cohort, deviation_reason=args.deviation_reason)
    if args.probe:
        if not args.source_call:
            raise ValueError("--source-call is required")
        source = json.loads(Path(args.source_call).read_text(encoding="utf-8"))
        partner = json.loads(Path(args.partner_call).read_text(encoding="utf-8")) if args.partner_call else None
        authorize_probe(config, source, partner, args.probe, args.partner_cost, args.probe_draws)
    else:
        authorize(config)
    needed_models = models
    if args.probe:
        logs = [Path(p) for p in (args.source_call, args.partner_call) if p]
        needed_models = tuple(json.loads(p.read_text(encoding="utf-8"))["model"] for p in logs)
        from dataclasses import replace
        config = replace(config, models=tuple((needed_models * 4)[:4]))
    service = make_service(args, needed_models)
    started = time.perf_counter()
    before = service.calls
    try:
        if args.pilot:
            report, projection = await run_pilot(config, service,
                limits=PilotLimits(max_minutes=args.max_minutes, max_p95_seconds=args.max_p95_seconds,
                                   warmup_timeout=args.warmup_timeout),
                market_concurrency=args.market_concurrency, probe_calls=args.projection_probe_calls,
                judge_work_factor=args.judge_work_factor)
            print(json.dumps(report, indent=2))
            print(projection_table(projection))
            print(f"Raw logs: {service.raw_dir}\nOutputs: {service.root / 'llm' / args.run}")
            return 0 if report["status"] == "complete" else 2
        if args.probe:
            result = await probes(args, service, config)
            summary = {**telemetry(service, time.perf_counter() - started, before), **result}
            write_json(service.root / "llm" / args.run / "summary.json", summary)
            plot_probe(service.root / "llm" / args.run, result["draws"])
            complete = result["status"] == "complete"
        else:
            markets = await run(config, service, market_concurrency=args.market_concurrency or 4)
            wall = time.perf_counter() - started
            valid = [b for m in markets for row in m["bids"] for b in row if b is not None]
            total = 4 * sum(len(m["bids"]) for m in markets)
            invalid = sum(sum(row) for m in markets for row in m["invalid"])
            complete = all(m["status"] == "complete" for m in markets)
            summary = {**telemetry(service, wall, before, gpu_hourly_usd=args.gpu_hourly_usd),
                       "status": "complete" if complete else "stopped", "market_statuses": [m["status"] for m in markets],
                       "completed_rounds": sum(len(m["bids"]) for m in markets),
                       "invalid_bid_rate": invalid / total if total else None,
                       "bid_min": min(valid) if valid else None, "bid_max": max(valid) if valid else None,
                       "bid_spread": max(valid) - min(valid) if valid else None,
                       "planned_calls_without_retries": args.markets * args.rounds * (6 if args.condition in ("C1", "C1-NW", "M2", "C1-XX", "C1-XY") else 2 if args.condition == "P0" else 4)}
            save_summary(service.root / "llm" / args.run, summary, markets)
        print(json.dumps(summary, indent=2))
        print(f"Raw logs: {service.raw_dir}\nAnalysis: {service.root / 'llm' / args.run}")
        return 0 if complete else 2
    finally:
        service.close()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    add_backend_args(p)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--pilot", action="store_true", help="Warm up then collect N0 + P0 concurrently; blinded operations only")
    p.add_argument("--condition", choices=CONDITIONS)
    p.add_argument("--models", nargs="+", help="One model, or four models in strength-role order")
    p.add_argument("--rounds", type=int)
    p.add_argument("--markets", type=int, help="Per condition: default 1, or 20 for --pilot")
    p.add_argument("--market-start", type=int)
    p.add_argument("--project-calls-per-hour", type=float, help="Offline v2 branch projection from measured operational rate")
    p.add_argument("--projection-overhead-usd", type=float, help="Measured/allowed startup and idle USD; required for branch choice")
    p.add_argument("--market-concurrency", type=int, help="Default 4, or all requested markets for --pilot")
    p.add_argument("--max-minutes", type=float, default=75, help="Cumulative active pilot wall time; in-flight calls are drained")
    p.add_argument("--max-p95-seconds", type=float, default=60)
    p.add_argument("--warmup-timeout", type=float, default=1200)
    p.add_argument("--projection-probe-calls", type=int, help="Projection-only override; default from collection manifest")
    p.add_argument("--judge-work-factor", type=float, default=10, help="Unmeasured judge/bidder time ratio for projection only")
    p.add_argument("--cartel-position", choices=["strong_strong", "strong_fringe", "fringe_fringe"])
    p.add_argument("--compliance", type=float, default=1)
    p.add_argument("--gpu-hourly-usd", type=float, help="Your actual single-endpoint GPU rate; no invented default price")
    p.add_argument("--probe", choices=["frozen", "honest", "partner-cost"])
    p.add_argument("--source-call")
    p.add_argument("--partner-call")
    p.add_argument("--partner-cost", type=int)
    p.add_argument("--probe-draws", type=int, default=10)
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        raise SystemExit(asyncio.run(main(args)))
    except ValueError as error:
        raise SystemExit(str(error)) from None
