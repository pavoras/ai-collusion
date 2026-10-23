"""Serve one open-weights model as a private OpenAI-compatible endpoint on Modal (vLLM).

Pick the model at deploy time; every model becomes its own app, so several can run at once (mixed populations):

    MODEL_KEY=qwen-9b modal deploy cloud/modal_vllm.py     # deploy, prints the URL
    modal app stop collusion-qwen-9b                       # stop it again
    MODEL_KEY=qwen-9b SERVE_ROLE=judge modal deploy cloud/modal_vllm.py   # judge app, 32k context

The endpoint is private (Modal proxy auth). Clients send `Authorization: Bearer <token_id>.<token_secret>`, which
works as the `api_key` of the OpenAI client. Weights are cached in the `hf-cache` volume (see download_models.py).
"""

import json
import os
import subprocess

import modal

VLLM_VERSION = "0.31.0"  # first release that registers all three families; 0.32.0 is newer but only days old
MINUTES = 60
PORT = 8000

# Text-only use: all vision/audio inputs are switched off so no memory goes to them.
NO_IMAGE = {"image": 0}
NO_VISION = {"image": 0, "video": 0}
NO_MEDIA = {"image": 0, "video": 0, "audio": 0}
MISTRAL_FORMAT = ["--tokenizer-mode", "mistral", "--config-format", "mistral", "--load-format", "mistral"]

MODELS = {
    # key: (Hugging Face repo, GPU, media limits, extra vLLM args)
    "qwen-4b": ("Qwen/Qwen3.5-4B", "A10", NO_VISION, ["--reasoning-parser", "qwen3"]),
    "qwen-9b": ("Qwen/Qwen3.5-9B", "L40S", NO_VISION, ["--reasoning-parser", "qwen3"]),
    "gemma-e4b": ("google/gemma-4-E4B-it", "A10", NO_MEDIA, ["--reasoning-parser", "gemma4"]),
    "gemma-12b": ("google/gemma-4-12B-it", "L40S", NO_MEDIA, ["--reasoning-parser", "gemma4"]),
    "ministral-3b": ("mistralai/Ministral-3-3B-Instruct-2512", "A10", NO_IMAGE, MISTRAL_FORMAT),
    "ministral-8b": ("mistralai/Ministral-3-8B-Instruct-2512", "L40S", NO_IMAGE, MISTRAL_FORMAT),
}

# Hugging Face commits cached in the hf-cache volume (read 23.10.2026); pinned so every run serves the same weights.
REVISIONS = {
    "qwen-4b": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
    "qwen-9b": "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
    "gemma-e4b": "ee0ef6023621cff504d758262d4e04895a5af4a2",
    "gemma-12b": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
    "ministral-3b": "b35d4dfe56c142746f54dbd64f579faab2744308",
    "ministral-8b": "5b26027e7b19eeb4b7352e1fed3926375dd2cb4d",
}

MODEL_KEY = os.environ.get("MODEL_KEY", "qwen-9b")
if MODEL_KEY not in MODELS:
    raise SystemExit(f"MODEL_KEY must be one of {sorted(MODELS)}, got {MODEL_KEY!r}")
REPO, GPU, MEDIA_LIMITS, EXTRA_ARGS = MODELS[MODEL_KEY]
# SERVE_ROLE=judge deploys a second app with a long context (a 200-round log plus thinking does not fit in 8k).
JUDGE = os.environ.get("SERVE_ROLE", "bidder") == "judge"
MAX_MODEL_LEN, MAX_NUM_SEQS = (32768, 32) if JUDGE else (8192, 128)

image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install(f"vllm=={VLLM_VERSION}", "huggingface_hub[hf_xet]")
    .env({"HF_XET_HIGH_PERFORMANCE": "1", "HF_HUB_OFFLINE": "1", "VLLM_LOG_STATS_INTERVAL": "10",
          "MODEL_KEY": MODEL_KEY, "SERVE_ROLE": "judge" if JUDGE else "bidder"})
)

hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App(f"collusion-{MODEL_KEY}" + ("-judge" if JUDGE else ""))


@app.server(
    image=image,
    gpu=GPU,
    port=PORT,
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    scaledown_window=3 * MINUTES,  # idle containers stop quickly: credits only burn while we play
    startup_timeout=20 * MINUTES,  # first start compiles kernels
    target_concurrency=MAX_NUM_SEQS,  # bidders: ~30 games x 4 agents in parallel
)
class Server:
    @modal.enter()
    def start(self):
        cmd = [
            "vllm", "serve", REPO, "--revision", REVISIONS[MODEL_KEY],
            "--served-model-name", REPO, "llm",
            "--host", "0.0.0.0", "--port", str(PORT),
            "--max-model-len", str(MAX_MODEL_LEN),
            "--max-num-seqs", str(MAX_NUM_SEQS),
            "--gpu-memory-utilization", "0.90",
            "--limit-mm-per-prompt", json.dumps(MEDIA_LIMITS),
            "--uvicorn-log-level", "warning",
            *EXTRA_ARGS,
        ]
        print(*cmd, flush=True)
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()
