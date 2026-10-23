# Serving the models on Modal

Six open-weights models, each as its own private OpenAI-compatible vLLM endpoint (vLLM 0.31.0).

| Key | Hugging Face repo | GPU | $/h (modal.com/pricing, 23.10.2026) |
|---|---|---|---|
| `qwen-4b` | Qwen/Qwen3.5-4B | A10 | 1.10 |
| `qwen-9b` | Qwen/Qwen3.5-9B | L40S | 1.95 |
| `gemma-e4b` | google/gemma-4-E4B-it | A10 | 1.10 |
| `gemma-12b` | google/gemma-4-12B-it | L40S | 1.95 |
| `ministral-3b` | mistralai/Ministral-3-3B-Instruct-2512 | A10 | 1.10 |
| `ministral-8b` | mistralai/Ministral-3-8B-Instruct-2512 | L40S | 1.95 |

None of the repos is gated, so no Hugging Face token is needed. Vision and audio inputs are switched off.
Containers stop after 3 idle minutes; credits are only used while a game is running.

## One-time setup (Marvin)

```bash
.venv/Scripts/python -m pip install -e ".[dev,cloud]"
.venv/Scripts/modal setup
```

`modal setup` opens the browser to log in and stores a token in `~/.modal.toml`.

Then create a **proxy auth token** (Modal dashboard → Settings → Proxy Auth Tokens, or
`.venv/Scripts/modal workspace proxy-tokens --help`) and put it into `.env` in the repo root (never committed):

```
MODAL_PROXY_TOKEN_ID=wk-...
MODAL_PROXY_TOKEN_SECRET=ws-...
```

## Download weights (CPU container, cheap)

```bash
.venv/Scripts/modal run cloud/download_models.py --keys qwen-9b
```

## Deploy, test, stop

```bash
MODEL_KEY=qwen-9b .venv/Scripts/modal deploy cloud/modal_vllm.py
.venv/Scripts/python cloud/smoke_test.py --base-url <URL printed by deploy>
.venv/Scripts/modal app stop collusion-qwen-9b
```

In PowerShell set the variable first: `$env:MODEL_KEY = "qwen-9b"`.

The smoke test checks that bids parse as JSON, that no reasoning tokens are produced (Qwen runs with
`enable_thinking: false` per request), and reports latency and calls per second with 50 parallel requests.
