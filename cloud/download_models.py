"""Download model weights into the `hf-cache` volume on a cheap CPU container (no GPU time spent on downloads).

    modal run cloud/download_models.py                    # all six models
    modal run cloud/download_models.py --keys qwen-9b     # comma-separated subset
"""

import modal

image = modal.Image.debian_slim(python_version="3.12").uv_pip_install("huggingface_hub[hf_xet]").env(
    {"HF_XET_HIGH_PERFORMANCE": "1"}
)
hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)

app = modal.App("collusion-download")


@app.function(image=image, volumes={"/root/.cache/huggingface": hf_cache}, timeout=60 * 60, cpu=4)
def download(repo: str) -> str:
    from huggingface_hub import snapshot_download

    # Only what vLLM loads: weights, configs, tokenizer and chat template.
    path = snapshot_download(repo, allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "*.jinja", "*.tekken*"])
    hf_cache.commit()
    return path


@app.local_entrypoint()
def main(keys: str = ""):
    from modal_vllm import MODELS  # local only; the container never imports it

    selected = [k.strip() for k in keys.split(",") if k.strip()] or list(MODELS)
    repos = [MODELS[k][0] for k in selected]
    for repo, path in zip(repos, download.map(repos)):
        print(f"{repo}: {path}")
