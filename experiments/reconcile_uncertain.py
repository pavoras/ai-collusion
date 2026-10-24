"""Release uncertain judge requests whose reply was provably never delivered, with an audit log.

An uncertain request blocks automatic resubmission (storage.CallService). This script is the manual reconciliation
step: it only touches requests that (1) are in state 'uncertain', (2) belong to the given run-ID prefix, and (3) whose
every attempt ended at the client timeout, so the client closed the connection, vLLM aborted the generation and no
answer was ever read. The identical request (same seed) may then be submitted again; nothing was observed that could
be selected on. Every released key is appended to the audit log.

    .venv/Scripts/python experiments/reconcile_uncertain.py --run-prefix judge_qwen-9b_ --min-latency 1199 \
        --reason "client timeout 1200 s under load; vLLM aborts on disconnect" --log results/llm/reconciliation_log.json
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache", default="results/raw/response_cache.sqlite3")
    p.add_argument("--run-prefix", required=True)
    p.add_argument("--min-latency", type=float, required=True, help="seconds; attempts below this are not timeouts")
    p.add_argument("--reason", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--exclude", default=None, help="skip keys with an attempt from a run ID containing this")
    p.add_argument("--dead-pending", action="store_true",
                   help="also release 'pending' keys of these runs; only when no process of the prefix is alive")
    p.add_argument("--apply", action="store_true", help="without it, only list what would be released")
    args = p.parse_args()
    db = sqlite3.connect(args.cache, timeout=60)
    # Scan without holding the write lock (running collectors time out after 30 s); lock only for the update.
    db.execute("CREATE INDEX IF NOT EXISTS attempts_key ON attempts(key)")
    states = ("uncertain", "pending") if args.dead_pending else ("uncertain",)
    rows = db.execute(f"SELECT key FROM requests WHERE state IN ({','.join('?' * len(states))})", states).fetchall()
    released = []
    for (key,) in rows:
        attempts = db.execute("SELECT run_id,state,latency,error FROM attempts WHERE key=?", (key,)).fetchall()
        if not attempts or not all(r[0].startswith(args.run_prefix) for r in attempts):
            continue
        if args.exclude and any(args.exclude in r[0] for r in attempts):
            continue
        if any(r[1] == "pending" for r in attempts):
            if args.dead_pending:
                released.append({"key": key, "attempts": [{"run_id": r[0], "state": r[1], "latency": r[2],
                                                           "error": r[3]} for r in attempts]})
            continue
        if not all(r[1] in ("uncertain", "safe_failure", "failed") or r[1] is None for r in attempts):
            continue
        timeouts = [r for r in attempts if r[1] == "uncertain"]
        if not timeouts or any((r[2] or 0) < args.min_latency for r in timeouts):
            continue
        released.append({"key": key, "attempts": [{"run_id": r[0], "state": r[1], "latency": r[2], "error": r[3]}
                                                  for r in attempts]})
    if args.apply:
        db.execute("BEGIN IMMEDIATE")
        db.executemany("UPDATE requests SET state='reconciled_lost' WHERE key=? AND state IN ('uncertain','pending')",
                       [(r["key"],) for r in released])
        db.execute("COMMIT")
        log = Path(args.log)
        entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
        entries.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reason": args.reason,
                        "run_prefix": args.run_prefix, "min_latency": args.min_latency, "released": released})
        log.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"{len(released)} of {len(rows)} uncertain requests {'released' if args.apply else 'would be released'}")
    for r in released:
        print(r["key"][:16], [(a["run_id"], a["state"], round(a["latency"] or 0)) for a in r["attempts"]])


if __name__ == "__main__":
    main()
