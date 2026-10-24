"""Run the registered partner-cost probes (core.probes) and write the probe context index for the analysis.

Each context (C1-SS market, round, cartel seat from the manifest grid) and counterfactual partner cost is one
ordinary `run_llm.py --probe partner-cost` call on the logged source bid and partner message; rerunning resumes
from each probe run's cache.

    .venv/Scripts/python experiments/probe_batch.py --calls results/raw/core_C1-SS_v1c/calls \
        --index results/llm/probe_index.json --endpoint qwen-9b=https://...-qwen-9b-server.us-east.modal.direct
"""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
V1 = "experiments/manifests/collection_v1.json"
sys.path.insert(0, str(ROOT / "src"))
from collusion.llm.collection import indices_for, load_collection  # noqa: E402


def contexts(calls, manifest_path):
    """Source bid (first validation attempt) and partner message per declared market, round and cartel seat."""
    manifest = load_collection(manifest_path)
    entry = next(e for e in manifest["entries"] if e["id"] == "core.probes")
    markets, rounds = set(indices_for(manifest, entry)), set(entry["context_rounds"])
    logs = {}
    for path in sorted(Path(calls).glob("*.json")):
        call = json.loads(path.read_text(encoding="utf-8"))
        if (call.get("collection_entry") in entry["source_entries"] and call.get("market") in markets
                and call.get("round") in rounds and call.get("role") == "cartel_channel"
                and call.get("validation_attempt") == 0 and call.get("kind") in ("bid", "message")):
            logs.setdefault((call["market"], call["round"], call["seat"], call["kind"]), (path, call))
    for (market, rnd, seat, kind), (path, call) in sorted(logs.items()):
        if kind != "bid":
            continue
        partner = next((v for k, v in logs.items() if k[:2] == (market, rnd) and k[2] != seat and k[3] == "message"), None)
        if partner is None:
            raise SystemExit(f"no partner message for market {market} round {rnd} seat {seat}")
        for cost in entry["counterfactual_costs"]:
            yield {"market_index": market, "round": rnd, "seat": seat, "own_cost": own_cost(call), "partner_cost": cost,
                   "source": str(path), "partner": str(partner[0]), "draws": entry["bid_draws_per_cost"],
                   "run": f"probe_C1-SS_m{market:02d}_r{rnd}_s{seat}_c{cost}"}


def own_cost(call):
    context = call["context"]  # logged as a dict or as its Python repr
    return context["cost"] if isinstance(context, dict) else ast.literal_eval(context)["cost"]


def probe(job, endpoint, results, max_calls, timeout):
    backend = ["--dry-run"] if endpoint == "dry-run" else ["--endpoint", endpoint]
    cmd = [sys.executable, "experiments/run_llm.py", "--probe", "partner-cost", "--source-call", job["source"],
           "--partner-call", job["partner"], "--partner-cost", str(job["partner_cost"]),
           "--probe-draws", str(job["draws"]), "--run", job["run"], "--collection-manifest", V1, "--entry", "core.probes",
           *backend, "--results", results, "--transport-retries", "10", "--max-calls", str(max_calls),
           "--timeout", str(timeout)]
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return job, done.returncode, done.stderr[-300:]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--calls", required=True, help="call-log folder of the source C1-SS run")
    p.add_argument("--index", required=True, help="probe context index JSON to write (paths relative to it)")
    p.add_argument("--endpoint", required=True, help="MODEL=URL of the bidder app, or dry-run")
    p.add_argument("--parallel", type=int, default=16)
    p.add_argument("--results", default="results")
    p.add_argument("--max-calls", type=int, default=40, help="per-probe cap on backend attempts")
    p.add_argument("--timeout", type=float, default=600)
    args = p.parse_args()
    todo = list(contexts(args.calls, V1))
    index_path = Path(args.index)
    records, failures = [], []
    with ThreadPoolExecutor(args.parallel) as pool:
        for job, code, err in pool.map(lambda j: probe(j, args.endpoint, args.results, args.max_calls, args.timeout), todo):
            out = Path(args.results) / "llm" / job["run"] / "probes.json"
            if not out.exists():
                failures.append((job["run"], code, err))
                continue
            records.append({"cohort": "registered", "cell": "core.C1-SS",
                            **{k: job[k] for k in ("market_index", "round", "seat", "own_cost", "partner_cost")},
                            "path": out.resolve().relative_to(index_path.parent.resolve()).as_posix()})
            print(f"{job['run']}: exit {code}", flush=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps({"contexts": records}, indent=2) + "\n", encoding="utf-8")
    print(f"{len(todo)} probe contexts x costs, {len(records)} indexed, {len(failures)} without output")
    for run, code, err in failures:
        print(f"NO OUTPUT {run} (exit {code}): {err}")


if __name__ == "__main__":
    main()
