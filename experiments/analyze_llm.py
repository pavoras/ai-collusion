"""Frozen offline analysis; never contacts a model or network.

Development: .venv/Scripts/python experiments/analyze_llm.py --dev --quick
Full core:   .venv/Scripts/python experiments/analyze_llm.py --dev --workers 4
Blind:       ... --blind --input COLLECTION --manifest COLLECTION.json

analysis_runs.json explicitly maps run paths to manifest cells and cohorts.
Judge inputs are an explicit JSON judgments index; failed judgments stay in it.
Quick reduces development bootstrap/fingerprint counts only, never 999 market
permutations or the 99,999-swap primary test. Full defaults are PREREG counts.
"""

import argparse
import json
from pathlib import Path
import re

from collusion.analysis import analyze_collection, load_collection, operational_report, write_results
from collusion.analysis.development import make_development_collection, save, size_check
from collusion.analysis.io import load_judges
from collusion.analysis.addendum import placement_size_check
from collusion.analysis.probes import load_probes

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "results/analysis_dev"


def figure(output, result):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from collusion import plotting

    plotting.apply_style()
    fig, ax = plt.subplots(figsize=(7, 3.5), layout="constrained")
    for detector, color in (("net", plotting.BLUE), ("leak", plotting.ORANGE), ("correlation", plotting.AQUA)):
        rows = [r for r in result["all_cells"] if r["cohort"] == "registered" and r["prefix"] == 200
                and r["mask"] == "complete" and r["level"] == "L2" and r["detector"] == detector and r["auroc"]]
        if rows:
            ax.plot([r["cell"] for r in rows], [r["auroc"]["estimate"] for r in rows], marker="o", color=color, label=detector)
    ax.axhline(.5, color=plotting.TEXT_MUTED, linestyle="--", label="AUROC .5")
    ax.set(xlabel="Scripted development cell", ylabel="AUROC vs matched N0", ylim=(0, 1.05))
    ax.legend(ncol=2)
    fig.savefig(output / "development_auroc.png")
    plt.close(fig)


def main(args):
    if args.quick and not args.dev:
        raise ValueError("--quick is restricted to offline development")
    if args.addendum_size_repetitions:
        if not args.dev:
            raise ValueError("addendum size simulation is development only")
        output = DEV / "addendum_v2"
        output.mkdir(parents=True, exist_ok=True)
        check = placement_size_check(args.addendum_size_repetitions, n_swaps=1999 if args.quick else 99999)
        save(output / "placement_size.json", check)
        save(output / f"placement_size_{check['n_swaps']}_swaps.json", check)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from collusion import plotting
        plotting.apply_style()
        fig, ax = plt.subplots(figsize=(7, 3.5), layout="constrained")
        rates = check["endpoint_size"]
        ax.errorbar(range(7), [r["estimate"] for r in rates],
                    yerr=[[r["estimate"] - r["low"] for r in rates], [r["high"] - r["estimate"] for r in rates]],
                    fmt="o", color=plotting.BLUE, label="Exchangeable fake cell/twin scores, 95% intervals")
        ax.axhline(.05, color=plotting.ORANGE, linestyle="--", label="Nominal 5%")
        ax.set(xlabel="Pre-specified endpoint", ylabel="Rejection rate", xticks=range(7))
        ax.legend()
        fig.savefig(output / "placement_size.png")
        plt.close(fig)
        print(json.dumps(check, indent=2))
        return
    if args.dev:
        output = DEV / ("quick" if args.quick else "full_core")
        manifest_path = make_development_collection(output / "inputs", quick=args.quick, include_fake=args.quick)
        collection = output / "inputs"
    else:
        if not args.input or not args.manifest:
            raise ValueError("--input and --manifest are required outside development")
        collection, manifest_path = args.input, args.manifest
        output = ROOT / "results/analysis" / args.name
    markets, manifest = load_collection(collection, manifest_path, legacy_fake=args.legacy_fake)
    if args.blind:
        print(json.dumps(operational_report(markets, manifest), indent=2))
        return
    if not args.dev and not re.fullmatch("[0-9a-f]{40}", args.analysis_freeze_commit or ""):
        raise ValueError("unblinded LLM analysis requires --analysis-freeze-commit (the previously recorded analysis commit)")
    if args.dev and any(m.run_metadata.get("data_kind") not in ("fake", "scripted") for m in markets):
        raise ValueError("--dev refuses data without explicit offline provenance")
    result = analyze_collection(markets, manifest, workers=args.workers, development=args.dev,
                                n_boot=200 if args.quick else 10000,
                                fingerprint_boot=3 if args.quick else 1000,
                                judgments=load_judges(args.judges), probes=load_probes(args.probes),
                                progress=lambda event: print(json.dumps(event), flush=True))
    result["analysis_freeze_commit"] = args.analysis_freeze_commit
    if args.size_repetitions:
        result["size_check"] = size_check(args.size_repetitions, workers=args.workers)
    write_results(output, result)
    if args.dev:
        figure(output, result)
    print(json.dumps({"output": str(output), "primary": result["primary"], "runtime": result["runtime"],
                      "size_check": result.get("size_check", {}).get("rejection_rate")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dev", action="store_true")
    mode.add_argument("--blind", action="store_true")
    mode.add_argument("--unblind", action="store_true")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--judges", type=Path)
    parser.add_argument("--probes", type=Path)
    parser.add_argument("--legacy-fake", action="store_true")
    parser.add_argument("--analysis-freeze-commit")
    parser.add_argument("--name", default="registered_v2")
    parser.add_argument("--size-repetitions", type=int, default=0)
    parser.add_argument("--addendum-size-repetitions", type=int, default=0,
                        help="Only run the seeded exchangeable-cell/twin offline size simulation")
    options = parser.parse_args()
    if options.size_repetitions and not options.dev:
        parser.error("size simulation is development only")
    main(options)
