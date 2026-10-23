"""Run the registered LLM judge over every complete market of the given runs and write the judge index.

Each judgement is one `experiments/judge.py` call (same prompt, seed derivation, retry rule and logging), run in
parallel subprocesses. A finished judgement is never repeated: rerunning resumes from each judge run's cache.

    .venv/Scripts/python experiments/judge_batch.py --index results/llm/judge_index_core.json \
        --group core.N0=results/llm/pilot_qwen9b_v5/N0 --group core.C1-SS=results/llm/core_C1-SS_v1 \
        --endpoint qwen-9b=https://...-qwen-9b-judge-server.us-east.modal.direct
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
V1 = "experiments/manifests/collection_v1.json"


def jobs(groups, levels, model, suffix=""):
    for spec in groups:
        cell, rest = spec.split("=", 1)
        run_dir, manifest, entry = (rest.split("@") + [V1, "judge.qwen9b"])[:3]
        for path in sorted(Path(run_dir).glob("market_*.json")):
            market = json.loads(path.read_text(encoding="utf-8"))
            if market.get("status") != "complete":
                raise SystemExit(f"{path} is not complete; judge only finished cells")
            for level in levels:
                run = f"judge_{model}_{cell.replace('.', '_')}_{market['market_index']:05d}_{level}{suffix}"
                yield {"cell": cell, "market_index": market["market_index"], "level": level, "model": model,
                       "run": run, "market": str(path), "manifest": manifest, "entry": entry}


def judge(job, endpoint, results, max_calls, timeout):
    backend = ["--dry-run"] if endpoint == "dry-run" else ["--endpoint", endpoint]
    cmd = [sys.executable, "experiments/judge.py", job["market"], "--run", job["run"], "--model", job["model"],
           "--level", job["level"], *backend, "--collection-manifest", job["manifest"],
           "--entry", job["entry"], "--results", results, "--transport-retries", "10", "--max-calls", str(max_calls),
           "--timeout", str(timeout)]
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return job, done.returncode, done.stderr[-300:]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--group", action="append", required=True, help="CELL=RUN_DIR[@MANIFEST[@JUDGE_ENTRY]]")
    p.add_argument("--index", required=True, help="judge index JSON to write (paths relative to it)")
    p.add_argument("--endpoint", required=True, help="MODEL=URL of the judge app, or dry-run for the fake backend")
    p.add_argument("--model", default="qwen-9b")
    p.add_argument("--levels", nargs="+", default=["L1", "L2"])
    p.add_argument("--parallel", type=int, default=24)
    p.add_argument("--results", default="results")
    p.add_argument("--max-calls", type=int, default=20,
                   help="per-judgement cap on backend attempts (safe cold-start failures count too)")
    p.add_argument("--timeout", type=float, default=3600, help="per-request seconds; long thinking queues under load")
    p.add_argument("--run-suffix", default="", help="new judge run IDs after an uncertain submission (same requests)")
    args = p.parse_args()
    todo = list(jobs(args.group, args.levels, args.model, args.run_suffix))
    index_path = Path(args.index)
    records, failures = [], []
    with ThreadPoolExecutor(args.parallel) as pool:
        for job, code, err in pool.map(lambda j: judge(j, args.endpoint, args.results, args.max_calls, args.timeout), todo):
            out = Path(args.results) / "llm" / job["run"] / "judge.json"
            if not out.exists():
                failures.append((job["run"], code, err))
                continue
            records.append({"cohort": "registered", "cell": job["cell"], "market_index": job["market_index"],
                            "level": job["level"], "model": job["model"],
                            "path": Path(out).resolve().relative_to(index_path.parent.resolve()).as_posix()})
            print(f"{job['run']}: exit {code}", flush=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps({"judgments": records}, indent=2) + "\n", encoding="utf-8")
    print(f"{len(records)} judgements indexed, {len(failures)} without output")
    for run, code, err in failures:
        print(f"NO OUTPUT {run} (exit {code}): {err}")


if __name__ == "__main__":
    main()
