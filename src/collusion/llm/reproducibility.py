"""One local, auditable run record; cloud source is parsed, never imported."""

import ast
from functools import lru_cache
import hashlib
from importlib import metadata
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .collection import ROOT, collection_hash, load_collection
from .prompts import ROLE_TEXTS, RULES, VERSION, build_messages, frozen_build_messages
from .sampling import MODEL_CONFIG
from .storage import TOKEN_LIMITS, digest, write_json


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def packages():
    """Hash freeze output without retaining URLs or credentials it might contain."""
    env = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INDEX": "1", "PIP_CONFIG_FILE": os.devnull}
    result = subprocess.run([sys.executable, "-m", "pip", "--disable-pip-version-check", "--no-input", "freeze", "--all"],
                            capture_output=True, env=env, timeout=60, check=True)
    return {"python": sys.version, "pip_freeze_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "versions": dict(sorted((d.metadata["Name"], d.version) for d in metadata.distributions() if d.metadata["Name"]))}


def cloud_settings(path=None):
    """Extract only literal declarations; no eval, imports or Modal invocation."""
    source = Path(path or ROOT / "cloud/modal_vllm.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    nodes = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign)
             for target in node.targets if isinstance(target, ast.Name)}
    revisions = ast.literal_eval(nodes["REVISIONS"])
    models = {ast.literal_eval(k): {"repo": ast.literal_eval(v.elts[0]), "gpu": ast.literal_eval(v.elts[1]),
                                  "revision": revisions[ast.literal_eval(k)]}
              for k, v in zip(nodes["MODELS"].keys, nodes["MODELS"].values)}
    if any(not re.fullmatch(r"[0-9a-f]{40}", m["revision"]) for m in models.values()):
        raise ValueError("all served model revisions must be pinned commits")
    limits = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple):
            names = [n.id for n in node.targets[0].elts if isinstance(n, ast.Name)]
            if names == ["MAX_MODEL_LEN", "MAX_NUM_SEQS"] and isinstance(node.value, ast.IfExp):
                limits = {role: dict(zip(("max_model_len", "max_num_seqs"), ast.literal_eval(value)))
                          for role, value in [("bidder", node.value.orelse), ("judge", node.value.body)]}
    if not limits:
        raise ValueError("cloud serving limits could not be parsed")
    return {"source_sha256": text_hash(source), "vllm_version": ast.literal_eval(nodes["VLLM_VERSION"]),
            "models": models, "serving_limits": limits}


def write_reproducibility(service, config, entry_ids, *, phase="bidder", warmup_timeout=None, token_limits=None):
    manifest = load_collection(config.collection_manifest)
    from .judging import judge_messages
    bidder_template = frozen_build_messages if manifest["manifest_version"] == "collection_v1" else build_messages
    template = inspect.getsource(judge_messages if phase == "judge" else bidder_template)
    role_texts = {k: v for k, v in ROLE_TEXTS.items()
                  if manifest["manifest_version"] != "collection_v1" or k != "cartel_channel_nowarn"}
    cloud = cloud_settings()
    model_keys = set(config.models)
    static = {"schema_version": 1, "manifest_version": manifest["manifest_version"], "manifest_hash": collection_hash(manifest),
              "collection_manifest": manifest, "collection_entries": entry_ids,
              "deviation": {"cohort": config.deviation_cohort, "reason": config.deviation_reason},
              "prompt_template": {"version": VERSION, "text": template, "sha256": text_hash(template),
                                  "rules": RULES, "rules_sha256": text_hash(RULES)},
              "role_texts": {k: {"text": v, "sha256": text_hash(v)} for k, v in role_texts.items()},
              "sampling_table": MODEL_CONFIG, "token_limits": token_limits or TOKEN_LIMITS,
              "thinking_flags": {m: {r: MODEL_CONFIG[m][r].get("extra_body", {}).get("chat_template_kwargs", {}).get("enable_thinking")
                                     for r in ("bidder", "judge")} for m in model_keys},
              "retry_policy": {"validation_attempts": 2, "transport_retries": service.transport_retries,
                               "backoff_seconds": service.backoff, "timeout_seconds": service.timeout,
                               "warmup_timeout_seconds": warmup_timeout, "uncertain_requests": "never automatically resubmit"},
              "seed_derivation": {"run_seed": config.seed, "assignment": manifest["assignment"],
                                  "costs": "numpy.default_rng([seed, market_index, 0]); rows of 4 independent integer draws",
                                  "ties": "numpy.default_rng([seed, market_index, 1]); one uniform per round",
                                  "calls": "SHA256(canonical JSON [seed,index,round,physical_seat,step]) first 8 hex digits modulo 2**31",
                                  "scripted": "numpy.default_rng([seed,index,zero_based_round,120]); independent noncompliance streams 121+seat"},
              "packages": packages(), "cloud": cloud,
              "models": {m: {**cloud["models"][m], **cloud["serving_limits"][phase],
                             "revision_source": "pinned cloud config; not server-attested"} for m in model_keys}}
    if manifest["manifest_version"] == "collection_v2" and phase == "bidder":
        static["frozen_base_template"] = {"text": inspect.getsource(frozen_build_messages),
                                          "sha256": text_hash(inspect.getsource(frozen_build_messages))}
    path = service.raw_dir / "reproducibility.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if digest(existing["static"]) != digest(static):
            raise ValueError("reproducibility metadata changed; use a new run/deviation cohort")
        return existing
    record = {"static": static, "vllm_runtime": {m: {"version": cloud["vllm_version"], "source": "config",
              "probe_status": "not_yet_probed"} for m in model_keys}}
    write_json(path, record)
    return record


async def record_server_version(service, model):
    path = service.raw_dir / "reproducibility.json"
    if not path.exists():
        return
    record = json.loads(path.read_text(encoding="utf-8"))
    version = await service.backend.server_version(model)
    current = record["vllm_runtime"][model]
    if version:
        current.update(version=version, source="server GET /version", probe_status="reported")
    elif current["source"] == "config":
        current["probe_status"] = "offline_fake" if service.backend.identity(model).startswith("fake:") else "not_exposed_or_unavailable"
    write_json(path, record)
