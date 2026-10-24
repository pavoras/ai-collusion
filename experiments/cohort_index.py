"""Write a run index that re-declares registered collection cells as a separate named cohort.

Each deviation cell is a full copy of the registered manifest entry (position, models and condition decide the
designated pair), with only the cohort, market indices, control and reason replaced, so the frozen analysis treats
the cohort exactly like the registered cells. Paths are relative to the analysis input root (`results`).

    .venv/Scripts/python experiments/cohort_index.py --out results/analysis_runs_v22.json --cohort replication \
        --reason "..." --cell rep.N0=core.N0:20-39:llm/core_N0_v1 --cell rep.E1=core.E1:20-39:llm/rep_E1_v22__deviation_replication:rep.N0
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from collusion.analysis.io import adapt_collection_manifest  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--manifest", default="experiments/manifests/collection_v2.json")
    p.add_argument("--registered-index", default="results/analysis_runs.json",
                   help="source of run metadata/reproducibility paths for reused registered runs")
    p.add_argument("--cohort", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--cell", action="append", required=True,
                   help="NEW_ID=REGISTERED_ID:START-END:RUN_PATH[:CONTROL_ID]")
    args = p.parse_args()
    registered = {c["id"]: c for c in adapt_collection_manifest(json.loads((ROOT / args.manifest).read_text(encoding="utf-8")))}
    reg_runs = json.loads((ROOT / args.registered_index).read_text(encoding="utf-8"))["runs"]
    cells, runs = [], []
    for spec in args.cell:
        new_id, rest = spec.split("=", 1)
        source, span, path, *control = rest.split(":")
        start, end = map(int, span.split("-"))
        cell = {**registered[source], "id": new_id, "cohort": args.cohort, "market_indices": list(range(start, end + 1)),
                "control": control[0] if control else None, "matched_control": control[0] if control else None,
                "deviation_reason": args.reason, "registered_source": source}
        cells.append(cell)
        run = {"cell": new_id, "cohort": args.cohort, "path": path}
        for r in reg_runs:  # reuse explicit metadata paths of registered runs (e.g. the pilot N0)
            if r["path"] == path:
                run.update({k: r[k] for k in ("metadata_path", "reproducibility_path") if k in r})
        runs.append(run)
    out = {"note": args.note, "deviation_cells": cells, "runs": runs}
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(cells)} cells")


if __name__ == "__main__":
    main()
