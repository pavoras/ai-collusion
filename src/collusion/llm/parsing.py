"""Strict JSON schemas for bids, private messages and pair probabilities."""

import json
import math
import re
from itertools import combinations

PAIRS = tuple(f"{a}-{b}" for a, b in combinations("ABCD", 2))


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


FENCE = re.compile(r"\s*```(?:json)?[ \t]*\n(.*?)\n?[ \t]*```\s*", re.S)


def parse(text, kind, fenced=False):
    """Return a validated value, or None; never coerce strings or booleans.

    fenced=True (PREREG deviation 2, parse version 2) also accepts an answer that is exactly one Markdown code block
    around the JSON, as Gemma and Ministral emit it; prose around the JSON stays invalid. The default is the frozen
    strict rule (parse version 1)."""
    if isinstance(text, str):
        # Some non-thinking templates still emit an empty thought block.
        text = re.sub(r"^\s*(?:<think>\s*</think>|\[unused94\]thought\s*\[unused95\])\s*", "", text, count=1)
        block = FENCE.fullmatch(text) if fenced else None
        text = block.group(1) if block else text
    try:
        value = json.loads(text, object_pairs_hook=_object)
    except (ValueError, TypeError):
        return None
    if not isinstance(value, dict):
        return None
    if kind == "bid" and set(value) == {"bid"}:
        bid = value["bid"]
        return bid if type(bid) is int and 2 <= bid <= 7 else None
    if kind == "message" and set(value) == {"message"}:
        message = value["message"]
        if isinstance(message, str) and 1 <= len(message.split()) <= 40:
            return message
    if kind == "judge" and set(value) == set(PAIRS):
        if all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in value.values()):
            return value
    return None
