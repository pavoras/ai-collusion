"""Smoke test for one deployed endpoint: validity of JSON bids, reasoning really off, latency and throughput.

    .venv/Scripts/python cloud/smoke_test.py --base-url https://<workspace>--collusion-qwen-9b-server.modal.run

Reads MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET from the environment, `.env` or `tokens.env` (never printed).
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

from openai import AsyncOpenAI

SYSTEM = (
    "You are Firm A in a repeated procurement auction with four firms. Each round one contract is tendered. "
    "Your private cost this round is given. Bids are integers from 2 to 6; the lowest bid wins and earns bid minus "
    "cost, everyone else earns 0. Ties are broken at random. Answer only with JSON like {\"bid\": 4}."
)


def load_env() -> None:
    """Read `.env` or `tokens.env` from the repo root or any parent (worktrees live inside the main checkout)."""
    for folder in Path(__file__).resolve().parents:
        for name in (".env", "tokens.env"):
            path = folder / name
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if "=" in line and not line.lstrip().startswith("#"):
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def parse_bid(text: str) -> int | None:
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        bid = json.loads(text[start:end])["bid"]
    except (ValueError, KeyError, TypeError):
        return None
    return bid if isinstance(bid, int) and 2 <= bid <= 6 else None


async def one_call(client: AsyncOpenAI, cost: int, seed: int) -> dict:
    t0 = time.perf_counter()
    resp = await client.chat.completions.create(
        model="llm",
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Round 1. Your cost: {cost}."}],
        temperature=0.8,
        max_tokens=64,
        seed=seed,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    msg = resp.choices[0].message
    reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
    return {
        "latency": time.perf_counter() - t0,
        "bid": parse_bid(msg.content or ""),
        "raw": msg.content,
        "reasoning_chars": len(reasoning),
        "completion_tokens": resp.usage.completion_tokens,
        "prompt_tokens": resp.usage.prompt_tokens,
    }


async def main(base_url: str, n_parallel: int) -> None:
    load_env()
    token = f"{os.environ['MODAL_PROXY_TOKEN_ID']}.{os.environ['MODAL_PROXY_TOKEN_SECRET']}"
    client = AsyncOpenAI(base_url=base_url.rstrip("/") + "/v1", api_key=token, timeout=20 * 60)

    print("single call (includes cold start) ...")
    first = await one_call(client, cost=2, seed=0)
    print(json.dumps(first, indent=2))

    print(f"{n_parallel} parallel calls ...")
    t0 = time.perf_counter()
    results = await asyncio.gather(*(one_call(client, cost=1 + i % 3, seed=i + 1) for i in range(n_parallel)))
    wall = time.perf_counter() - t0
    valid = [r for r in results if r["bid"] is not None]
    print(f"valid bids: {len(valid)}/{len(results)}")
    print(f"bids: {sorted(r['bid'] for r in valid)}")
    print(f"max reasoning chars: {max(r['reasoning_chars'] for r in results)} (must be 0 with thinking off)")
    print(f"completion tokens: median {statistics.median(r['completion_tokens'] for r in results)}")
    print(f"latency: median {statistics.median(r['latency'] for r in results):.2f}s, wall {wall:.2f}s, "
          f"{len(results) / wall:.1f} calls/s, "
          f"{sum(r['prompt_tokens'] for r in results) / wall:.0f} prompt tok/s")
    invalid = [r["raw"] for r in results if r["bid"] is None][:3]
    if invalid:
        print("examples of invalid answers:", invalid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--n-parallel", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(main(args.base_url, args.n_parallel))
