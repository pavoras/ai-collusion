"""Seed-paired markets, simultaneous decisions and round-atomic checkpoints."""

import asyncio
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from collusion.games import auction
from .backend import BackendError
from .prompts import Context, VERSION, build_messages
from .sampling import sampling_for
from .collection import DEFAULT_MANIFEST, authorize, collection_hash, load_collection, resolve_market
from .reproducibility import write_reproducibility
from .scripted import cartel_bids
from .storage import BudgetStop, UncertainCall, digest, seed_for, write_json

CONDITIONS = ("N0", "P0", "C1", "C2", "D", "M2", "E1", "C1-XX", "C1-XY", "H-XYZZ")


@dataclass(frozen=True)
class RunConfig:
    condition: str = "N0"
    models: tuple = ("qwen-9b",) * 4
    rounds: int = 200
    markets: int = 1
    market_start: int = 0
    seed: int = 20261023
    strong: tuple = (0, 1)
    pair: tuple = (0, 1)
    compliance: float = 1.0
    cartel_position: str = "strong_strong"
    entry_id: str | None = None
    collection_manifest: str = str(DEFAULT_MANIFEST)
    deviation_cohort: str | None = None
    deviation_reason: str | None = None
    labels: tuple = ("Firm A", "Firm B", "Firm C", "Firm D")
    assignment: dict | None = None

    def __post_init__(self):
        if self.condition not in CONDITIONS or len(self.models) != 4 or any(not m for m in self.models):
            raise ValueError("condition and four nonempty model keys required")
        if self.rounds < 1 or self.markets < 1 or self.market_start < 0 or self.seed < 0:
            raise ValueError("positive rounds/markets and nonnegative seed/index required")
        for seats in (self.strong, self.pair):
            if len(seats) != 2 or len(set(seats)) != 2 or any(type(s) is not int or s not in range(4) for s in seats):
                raise ValueError("strong and pair must contain two distinct seats in 0..3")
        if not 0 <= self.compliance <= 1:
            raise ValueError("compliance must be in [0, 1]")
        if self.cartel_position not in ("strong_strong", "strong_fringe", "fringe_fringe"):
            raise ValueError("unknown strength-relative pair position")
        if self.assignment is None and (self.strong != (0, 1) or self.pair != (0, 1)):
            raise ValueError("physical seats come from the assignment manifest; select a strength-relative position")


class RunLock:
    """An OS lock prevents simultaneous writers; a crashed process releases it."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.handle = self.path.open("a+b")
        self.handle.seek(0, 2)
        if self.handle.tell() == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            import msvcrt
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            import fcntl
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.handle.close()
                raise RuntimeError("this run already has an active writer") from None
        except OSError:
            self.handle.close()
            raise RuntimeError("this run already has an active writer") from None
        return self

    def __exit__(self, *args):
        self.handle.close()


def market_randomness(config, index):
    """Match games.auction costs and ties exactly, independent of condition/model."""
    if config.assignment is None:
        config = resolve_market(config, index)
    minima = np.array([1 if s in config.strong else 3 for s in range(4)])
    costs = np.random.default_rng([config.seed, index, 0]).integers(0, 3, (config.rounds, 4)) + minima
    ties = np.random.default_rng([config.seed, index, 1]).random(config.rounds)
    return costs, ties


def role_for(config, seat):
    if seat in config.pair:
        if config.condition == "P0":
            return "scripted"
        if config.condition in ("C1", "M2", "C1-XX", "C1-XY"):
            return "cartel_channel"
        if config.condition == "C2":
            return "cartel_tacit"
        if config.condition == "E1" and seat == config.pair[0]:
            return "spy"
    return "honest"


def context_for(config, state, costs, round_index, seat):
    role = role_for(config, seat)
    partner = next((s for s in config.pair if s != seat), None) if role.startswith("cartel") else None
    history = [{"round": t + 1, "bids": state["bids"][t], "winner": state["winners"][t],
                "profit": state["payoffs"][t][seat]} for t in range(max(0, round_index - 10), round_index)]
    victim = config.pair[1] if role == "spy" else None
    return Context(seat, role, 1 if seat in config.strong else 3, int(costs[round_index, seat]),
                   round_index + 1, history, sum(row[seat] for row in state["payoffs"]),
                   partner=partner, victim=victim,
                   leaked_cost=int(costs[round_index, victim]) if victim is not None else None, labels=list(config.labels))


async def _all(awaitables):
    """Drain all dispatched calls before surfacing a stop/error."""
    values = await asyncio.gather(*awaitables, return_exceptions=True)
    errors = [v for v in values if isinstance(v, BaseException)]
    if errors:
        raise next((e for e in errors if not isinstance(e, BudgetStop)), errors[0])
    return values


def _settle(bids, costs, tie):
    if all(b is None for b in bids):
        return -1, [0] * 4
    valid_bids = np.array([[b if b is not None else 8 for b in bids]])
    winners, payoffs = auction.settle(valid_bids, np.asarray(costs)[None, :], [tie])
    return int(winners[0]), payoffs[0].tolist()


async def _market(config, service, index, out, control=None):
    if config.assignment is None:
        config = resolve_market(config, index)
    path = out / f"market_{index:05d}.json"
    fields = ("bids", "costs", "winners", "payoffs", "messages", "invalid", "message_invalid", "complete_round_mask")
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "schema": 2, "market_index": index, "planned_rounds": config.rounds, "status": "running",
        **{field: [] for field in fields}}
    metadata = {"assignment": config.assignment, "condition": config.condition, "collection_entry": config.entry_id,
                "manifest_hash": collection_hash(load_collection(config.collection_manifest)),
                "roles_by_seat": [role_for(config, s) for s in range(4)],
                "deviation_cohort": config.deviation_cohort, "deviation_reason": config.deviation_reason}
    if "metadata" in state and state["metadata"] != metadata:
        raise ValueError("market assignment or collection metadata changed")
    state["metadata"] = metadata
    lengths = {len(state[field]) for field in fields}
    if len(lengths) != 1 or len(state["bids"]) > config.rounds:
        raise ValueError("inconsistent market checkpoint")
    costs, ties = market_randomness(config, index)
    completed = len(state["bids"])
    if completed and not np.array_equal(np.asarray(state["costs"]), costs[:completed]):
        raise ValueError("checkpoint costs do not match the seeded stream")
    state["planned_rounds"] = config.rounds
    state["status"] = "complete" if completed == config.rounds else "running"
    state.pop("stop_reason", None)
    write_json(path, state)
    try:
        for t in range(len(state["bids"]), config.rounds):
            if control is not None:
                control.check()
            contexts = [context_for(config, state, costs, t, seat) for seat in range(4)]
            channel = [s for s in range(4) if contexts[s].role == "cartel_channel"]
            private = [None] * 4

            async def decide(seat, step):
                c = contexts[seat]
                metadata = {"condition": config.condition, "market": index, "round": t + 1, "seat": seat,
                            "role": c.role, "context": c.data(), "prompt_version": VERSION,
                            "label": config.labels[seat], "firm_type": "strong" if seat in config.strong else "fringe",
                            "collection_entry": config.entry_id, "assignment_hash": digest(config.assignment)}
                return await service.ask(config.models[seat], build_messages(c, step),
                                         seed_for(config.seed, index, t + 1, seat, step), step, metadata)

            if channel:
                messages = await _all([decide(s, "message") for s in channel])
                for seat, message in zip(channel, messages):
                    private[seat] = message
                for seat in channel:
                    contexts[seat].own_message = private[seat]
                    contexts[seat].partner_message = private[contexts[seat].partner]
            llm_seats = [s for s in range(4) if contexts[s].role != "scripted"]
            values = await _all([decide(s, "bid") for s in llm_seats])
            bids = [None] * 4
            for seat, value in zip(llm_seats, values):
                bids[seat] = value
            if config.condition == "P0":
                for seat, bid in cartel_bids(costs[t], state, config, index, t).items():
                    bids[seat] = bid
            winner, payoffs = _settle(bids, costs[t], ties[t])
            for key, value in {"bids": bids, "costs": costs[t].tolist(), "winners": winner,
                               "payoffs": payoffs, "messages": private,
                               "invalid": [b is None for b in bids],
                               "complete_round_mask": all(b is not None for b in bids),
                               "message_invalid": [s in channel and private[s] is None for s in range(4)]}.items():
                state[key].append(value)
            state["status"] = "complete" if t + 1 == config.rounds else "running"
            write_json(path, state)
    except (BudgetStop, UncertainCall, BackendError) as error:
        state["status"] = ("budget_stop" if isinstance(error, BudgetStop) else
                           "uncertain_call" if isinstance(error, UncertainCall) else "backend_error")
        if control is not None:
            control.fail(str(error) if isinstance(error, BudgetStop) else state["status"])
            state["stop_reason"] = control.reason
        write_json(path, state)
    except OSError:
        if control is not None:
            control.fail("checkpoint_io_error")
        raise
    return state


def run_identity(config, service):
    """Science is immutable; requested round counts and index ranges can grow."""
    settings = asdict(config)
    for field in ("rounds", "markets", "market_start", "strong", "pair", "labels", "assignment", "collection_manifest"):
        settings.pop(field)
    manifest, entry = authorize(config)
    return {"schema": 3, "prompt_version": VERSION, "config": settings,
            "manifest_hash": collection_hash(manifest), "collection_entry": entry["id"] if entry else None,
            "sampling": {m: sampling_for(m) for m in set(config.models)},
            "endpoints": {m: service.backend.identity(m) for m in set(config.models)}}


def save_manifest(path, identity, rounds, indices):
    """Allow extensions, reject scientific changes and accidental truncation."""
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if previous is not None:
        if digest(previous.get("identity")) != digest(identity):
            raise ValueError("run configuration changed; choose a new run_id")
        if rounds < previous["max_rounds"]:
            raise ValueError("round count cannot decrease within a run")
    manifest = {"identity": identity, "max_rounds": rounds,
                "market_indices": sorted(set(indices) | set(previous["market_indices"] if previous else []))}
    write_json(path, manifest)


async def run(config, service, *, market_concurrency=4):
    """Resume completed rounds; partial rounds replay exclusively through the cache."""
    if market_concurrency < 1:
        raise ValueError("market_concurrency must be positive")
    manifest, entry = authorize(config)
    from dataclasses import replace
    if entry is not None:
        config = replace(config, entry_id=entry["id"])
    service.bind_cohort(config.deviation_cohort, config.deviation_reason)
    out = service.root / "llm" / service.run_id
    out.mkdir(parents=True, exist_ok=True)
    with RunLock(service.raw_dir / "run.lock"):
        save_manifest(service.raw_dir / "config.json", run_identity(config, service), config.rounds,
                      range(config.market_start, config.market_start + config.markets))
        write_reproducibility(service, config, [entry["id"]] if entry else [])
        semaphore = asyncio.Semaphore(market_concurrency)

        async def play(index):
            async with semaphore:
                return await _market(resolve_market(config, index, manifest), service, index, out)

        return await _all([play(i) for i in range(config.market_start, config.market_start + config.markets)])
