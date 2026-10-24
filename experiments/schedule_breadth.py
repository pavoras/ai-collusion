"""Launch the declared A2 twin cells and breadth entries (labs, mixed, sizes, each with its A3 extension).

All runs use parse version 2 (PREREG deviation 2). Seed-paired cells share requests; the ledger lets a process wait
for an identical request in flight elsewhere, and short staggers spread the opening load. Each entry is one ordinary
`run_llm.py` call; resuming = rerunning this script (finished runs replay from cache).

    .venv/Scripts/python experiments/schedule_breadth.py --logs <dir> [--only labs mixed sizes]
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from collusion.llm.backend import modal_token  # noqa: E402

V2 = "experiments/manifests/collection_v2.json"
URL = "https://kempermarvin95--collusion-{}-server.us-east.modal.direct"
STAGGER = 2 * 60  # seconds


def endpoint_models(entry):
    return sorted(set(entry["models_by_role"].values()))


def warm(models, timeout=25 * 60):
    """Wake each endpoint (a cold container answers 503 until vLLM is up)."""
    token, start, waiting = modal_token(ROOT), time.time(), set(models)
    while waiting and time.time() - start < timeout:
        for model in sorted(waiting):
            request = urllib.request.Request(URL.format(model) + "/v1/models", headers={"Authorization": f"Bearer {token}"})
            try:
                if urllib.request.urlopen(request, timeout=60).status == 200:
                    print(f"{time.strftime('%H:%M')} {model} ready after {time.time() - start:.0f} s", flush=True)
                    waiting.discard(model)
            except Exception:
                pass
        if waiting:
            time.sleep(10)
    if waiting:
        raise SystemExit(f"endpoints not ready: {sorted(waiting)}")


def launch(entry, logs, suffix=""):
    twin = entry["id"].startswith("lookalike.")
    run = "v2_" + entry["id"].replace(".", "_") + ("_p2" if twin else "") + suffix
    markets = 20 if twin else 10
    # Ceilings, not targets: 4 bids per round plus validation retries and cold-start transport retries.
    caps = markets * 200 * (5.5 if entry["condition"] in ("N0", "D", "H-XYZZ") or twin else 6.7)
    cmd = [sys.executable, "experiments/run_llm.py", "--collection-manifest", V2, "--entry", entry["id"], "--run", run,
           "--markets", str(markets), "--rounds", "200", "--market-concurrency", str(markets), "--concurrency", "128",
           "--transport-retries", "10", "--max-calls", str(int(caps)), "--parse-fenced"]
    for model in endpoint_models(entry):
        cmd += ["--endpoint", f"{model}={URL.format(model)}"]
    out, err = open(logs / f"{run}.out", "a", encoding="utf-8"), open(logs / f"{run}.err", "a", encoding="utf-8")
    print(f"{time.strftime('%H:%M')} launch {run}", flush=True)
    return run, subprocess.Popen(cmd, cwd=ROOT, stdout=out, stderr=err)


WAVES = {  # block: waves of entry IDs
    "lookalike": [["lookalike.LX", "lookalike.LY", "lookalike.LZ"],
                  ["lookalike.LX-swap", "lookalike.LY-swap", "lookalike.LZ-swap"]],
    "labs": [["labs.gemma-12b.N0", "labs.gemma-12b.N0.A3", "labs.ministral-8b.N0", "labs.ministral-8b.N0.A3"],
             ["labs.gemma-12b.C1", "labs.gemma-12b.C1.A3", "labs.ministral-8b.C1", "labs.ministral-8b.C1.A3",
              "mixed.D", "mixed.D.A3", "mixed.H-XYZZ", "mixed.H-XYZZ.A3"],
             ["mixed.C1-XX", "mixed.C1-XX.A3", "mixed.C1-XY", "mixed.C1-XY.A3"]],
    "sizes": [["sizes.qwen-4b.N0", "sizes.qwen-4b.N0.A3", "sizes.gemma-e4b.N0", "sizes.gemma-e4b.N0.A3",
               "sizes.ministral-3b.N0", "sizes.ministral-3b.N0.A3"],
              ["sizes.qwen-4b.C1", "sizes.qwen-4b.C1.A3", "sizes.gemma-e4b.C1", "sizes.gemma-e4b.C1.A3",
               "sizes.ministral-3b.C1", "sizes.ministral-3b.C1.A3"]],
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--logs", required=True)
    p.add_argument("--only", nargs="+", choices=sorted(WAVES), default=sorted(WAVES))
    p.add_argument("--run-suffix", default="", help="new run IDs when a stopped run cannot resume (cache replays)")
    p.add_argument("--no-stagger", action="store_true", help="launch all waves at once (resuming from cache)")
    args = p.parse_args()
    logs = Path(args.logs)
    logs.mkdir(parents=True, exist_ok=True)
    entries = {e["id"]: e for e in json.loads((ROOT / V2).read_text(encoding="utf-8"))["entries"]}
    blocks = {b: [[entries[i] for i in wave] for wave in WAVES[b]] for b in args.only}
    warm(sorted({m for waves in blocks.values() for wave in waves for e in wave for m in endpoint_models(e)}))
    running, depth = [], max(len(w) for w in blocks.values())
    for k in range(depth):
        for waves in blocks.values():
            if k < len(waves):
                running += [launch(e, logs, args.run_suffix) for e in waves[k]]
        if k + 1 < depth and not args.no_stagger:
            time.sleep(STAGGER)
    for run, process in running:
        print(f"{time.strftime('%H:%M')} {run}: exit {process.wait()}", flush=True)


if __name__ == "__main__":
    main()
