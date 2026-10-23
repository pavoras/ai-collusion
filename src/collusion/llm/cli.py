"""Shared local CLI configuration, telemetry and smoke-test figures."""

import json
import statistics

from .backend import FakeBackend, OpenAIBackend
from .storage import CallService, write_json
from .collection import DEFAULT_MANIFEST


def add_backend_args(parser):
    parser.add_argument("--run", required=True, help="Stable ID; rerun unchanged to resume")
    parser.add_argument("--results", default="results")
    parser.add_argument("--endpoint", action="append", default=[], metavar="MODEL=URL")
    parser.add_argument("--dry-run", action="store_true", help="Fake backend; no credentials or network")
    parser.add_argument("--max-calls", type=int, help="Persistent cap; default 1000, or 26000 for --pilot")
    parser.add_argument("--concurrency", type=int, help="Default 8, or 128 for --pilot")
    parser.add_argument("--timeout", type=float, default=1200)
    parser.add_argument("--transport-retries", type=int, default=2)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--collection-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--entry", help="Declared collection entry ID")
    parser.add_argument("--deviation-cohort", help="Explicitly segregated exploratory/test cohort")
    parser.add_argument("--deviation-reason", help="Required justification, stored verbatim")
    parser.add_argument("--stream", action="store_true",
                        help="stream replies (transport only; needed for generations longer than ~600 s on Modal)")
    parser.add_argument("--parse-fenced", action="store_true",
                        help="parse version 2 (PREREG deviation 2): accept one Markdown code block around the JSON")


def make_service(args, models):
    if args.dry_run:
        backend = FakeBackend()
    else:
        endpoints = {}
        for item in args.endpoint:
            key, separator, url = item.partition("=")
            if not separator or not key or not url or key in endpoints:
                raise ValueError("each endpoint must be a unique MODEL=URL")
            endpoints[key] = url
        if set(models) - set(endpoints):
            raise ValueError("provide --endpoint MODEL=URL for every model used")
        backend = OpenAIBackend(endpoints, timeout=args.timeout, stream=getattr(args, "stream", False))
    pilot = getattr(args, "pilot", False)
    max_calls = args.max_calls if args.max_calls is not None else (26000 if pilot else 1000)
    concurrency = args.concurrency if args.concurrency is not None else (128 if pilot else 8)
    service = CallService(backend, args.results, args.run, max_calls=max_calls,
                          concurrency=concurrency, timeout=args.timeout, transport_retries=args.transport_retries)
    service.bind_cohort(args.deviation_cohort, args.deviation_reason)
    args.run = service.run_id
    bind_parse_version(service, getattr(args, "parse_fenced", False))
    return service


def bind_parse_version(service, fenced):
    """Record the parse rule once per run; resuming with the other rule is refused."""
    path, record = service.raw_dir / "parsing.json", {"parse_version": 2 if fenced else 1, "fenced": fenced}
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != record:
        raise ValueError(f"{service.run_id} was collected with a different parse version")
    if fenced or path.exists():
        write_json(path, record)
    service.parse_fenced = fenced


def telemetry(service, wall, calls_before, *, gpu_hourly_usd=None):
    """Observed client metrics; dollar estimates need a supplied endpoint rate."""
    entries = [json.loads(p.read_text(encoding="utf-8")) for p in (service.raw_dir / "calls").glob("*.json")]
    attempts = [e for e in entries if not e["cache_hit"]]
    completed = [e for e in attempts if e["response"] is not None]
    latencies = [e["latency"] for e in completed]
    new_calls = service.calls - calls_before
    seconds_per_call = wall / new_calls if new_calls else None
    return {"backend": "offline_fake" if isinstance(service.backend, FakeBackend) else "live",
            "calls": service.calls, "new_calls": new_calls, "cache_hits": sum(e["cache_hit"] for e in entries),
            "invalid_response_rate": sum(e["parsed_value"] is None for e in completed) / len(completed) if completed else None,
            "latency_median_seconds": statistics.median(latencies) if latencies else None,
            "latency_max_seconds": max(latencies) if latencies else None,
            "prompt_tokens": sum(e["prompt_tokens"] or 0 for e in completed),
            "completion_tokens": sum(e["completion_tokens"] or 0 for e in completed),
            "cached_prompt_tokens": sum(e.get("cached_prompt_tokens") or 0 for e in completed),
            "usage_missing_calls": sum(e["prompt_tokens"] is None or e["completion_tokens"] is None for e in completed),
            "invocation_wall_seconds": wall, "invocation_calls_per_second": new_calls / wall if wall else None,
            "estimated_wall_seconds_per_1000_calls": 1000 * seconds_per_call if seconds_per_call is not None else None,
            "gpu_hourly_usd": gpu_hourly_usd,
            "estimated_invocation_usd": wall * gpu_hourly_usd / 3600 if gpu_hourly_usd is not None else None,
            "estimate_note": "Fake timings/tokens are not endpoint measurements. Live USD estimate assumes one active GPU; "
                             "excludes idle billing and other endpoints. Supply --gpu-hourly-usd from your actual rate."}


def save_summary(out, summary, markets):
    """Save machine-readable metrics and the per-firm bid distribution."""
    write_json(out / "summary.json", summary)
    if not markets or not any(m["bids"] for m in markets):
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from collusion import plotting

    plotting.apply_style()
    fig, ax = plt.subplots(figsize=(6, 3), layout="constrained")
    for s, color, style in zip(range(4), [plotting.BLUE, plotting.ORANGE, plotting.AQUA, plotting.BLUE], ["-", "-", "-", "--"]):
        label = f"Firm {'ABCD'[s]}"
        bids = []
        for market in markets:
            labels = market["metadata"]["assignment"]["labels_by_seat"]
            seat = labels.index(label)
            bids.extend(row[seat] for row in market["bids"] if row[seat] is not None)
        counts = [bids.count(b) for b in range(2, 8)]
        ax.plot(np.arange(2, 8), counts, color=color, linestyle=style, marker="o", label=label)
    ax.set(xlabel="Bid", ylabel="Count", xticks=range(2, 8), title="Observed valid bids")
    ax.legend()
    fig.savefig(out / "bids.png")
    plt.close(fig)


def plot_judgement(out, probabilities, level):
    """Plot the six independently assessed pair probabilities."""
    if probabilities is None:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from collusion import plotting

    plotting.apply_style()
    fig, ax = plt.subplots(figsize=(6, 3), layout="constrained")
    ax.bar(list(probabilities), list(probabilities.values()), color=plotting.BLUE, label=f"Judge {level}")
    ax.set(xlabel="Firm pair", ylabel="Probability of coordination", ylim=(0, 1))
    ax.legend()
    fig.savefig(out / "judge.png")
    plt.close(fig)


def plot_probe(out, draws):
    """Show the valid bid draws from one frozen context."""
    bids = [d.get("bid") if isinstance(d, dict) else d for d in draws]
    bids = [b for b in bids if b is not None]
    if not bids:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from collusion import plotting

    plotting.apply_style()
    fig, ax = plt.subplots(figsize=(6, 3), layout="constrained")
    ax.bar(range(2, 8), [bids.count(b) for b in range(2, 8)], color=plotting.AQUA, label="Frozen-context draws")
    ax.set(xlabel="Bid", ylabel="Count", xticks=range(2, 8))
    ax.legend()
    fig.savefig(out / "probes.png")
    plt.close(fig)
