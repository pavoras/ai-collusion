"""Judge one complete market at L1 or L2; never exposes experimental labels.

Example: .venv/Scripts/python experiments/judge.py results/llm/smoke_fake/market_00000.json
         --run judge_fake --dry-run --level L1
Both access levels use the same fixed model and vendor sampling, thinking enabled.
"""

import argparse
import asyncio
import json
from pathlib import Path
import time

from collusion.llm.cli import add_backend_args, make_service, plot_judgement, telemetry
from collusion.llm.judging import NoCompleteRounds, judge_market, judge_messages
from collusion.llm.runner import RunConfig, RunLock
from collusion.llm.collection import authorize_judge, collection_hash, load_collection
from collusion.llm.reproducibility import write_reproducibility
from collusion.llm.prompts import VERSION
from collusion.llm.sampling import sampling_for
from collusion.llm.storage import digest, seed_for, write_json


async def main(args):
    market = json.loads(Path(args.market).read_text(encoding="utf-8"))
    if market.get("status") != "complete":
        raise ValueError("judge requires a complete market")
    collection = load_collection(args.collection_manifest)
    args.seed = collection["run_seed"] if args.seed is None else args.seed
    entry = authorize_judge(collection, market, args.model, args.level, args.entry,
                            args.deviation_cohort, args.deviation_reason)
    try:
        messages = judge_messages(market, args.level)
    except NoCompleteRounds:
        messages = []
    # --quick still judges the entire supplied market; supply a quick market for a short context.
    service = make_service(args, [args.model])
    before = service.calls
    started = time.perf_counter()
    out = service.root / "llm" / args.run
    out.mkdir(parents=True, exist_ok=True)
    try:
        with RunLock(service.raw_dir / "run.lock"):
            manifest = {"kind": "judge", "level": args.level, "model": args.model, "seed": args.seed,
                        "prompt_version": VERSION, "sampling": sampling_for(args.model, True),
                        "manifest_hash": collection_hash(collection), "entry": entry["id"] if entry else None,
                        "deviation_cohort": args.deviation_cohort, "deviation_reason": args.deviation_reason,
                        "public_prompt_hash": digest(messages), "endpoint": service.backend.identity(args.model)}
            path = service.raw_dir / "config.json"
            if path.exists() and digest(json.loads(path.read_text(encoding="utf-8"))) != digest(manifest):
                raise ValueError("judge configuration changed; choose a new run_id")
            write_json(path, manifest)
            config = RunConfig(models=(args.model,) * 4, seed=args.seed, collection_manifest=args.collection_manifest,
                               deviation_cohort=args.deviation_cohort, deviation_reason=args.deviation_reason)
            write_reproducibility(service, config, [entry["id"] if entry else args.entry or "judge.deviation"], phase="judge")
            result = await judge_market(service, market, args.model,
                                        seed_for(args.seed, "judge", market["market_index"], args.level), args.level)
            probabilities, status = result["probabilities"], result["status"]
            write_json(out / "judge.json", result)
            plot_judgement(out, probabilities, args.level)
            summary = {**telemetry(service, time.perf_counter() - started, before), **result}
            write_json(out / "summary.json", summary)
            print(json.dumps(summary, indent=2))
            return 0 if status == "complete" else 2
    finally:
        service.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    add_backend_args(p)
    p.add_argument("market")
    p.add_argument("--level", choices=["L1", "L2"], default="L1")
    p.add_argument("--model", default="qwen-9b")
    args = p.parse_args()
    try:
        raise SystemExit(asyncio.run(main(args)))
    except ValueError as error:
        raise SystemExit(str(error)) from None
