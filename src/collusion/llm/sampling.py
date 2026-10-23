"""Frozen vendor sampling settings and explicit projection assumptions.

Values are Marvin's model-card choices; no network lookup occurs at runtime.
extra_body is merged into the wire JSON by the stdlib OpenAI-compatible client.
"""

from copy import deepcopy

QWEN_BID = {"temperature": .7, "top_p": .8, "presence_penalty": 1.5,
            "extra_body": {"top_k": 20, "min_p": 0., "repetition_penalty": 1.,
                           "chat_template_kwargs": {"enable_thinking": False}}}
QWEN_JUDGE = {"temperature": 1., "top_p": .95, "presence_penalty": 1.5,
              "extra_body": {"top_k": 20, "min_p": 0., "chat_template_kwargs": {"enable_thinking": True}}}
GEMMA_BID = {"temperature": 1., "top_p": .95,
             "extra_body": {"top_k": 64, "chat_template_kwargs": {"enable_thinking": False}}}
GEMMA_JUDGE = {"temperature": 1., "top_p": .95,
               "extra_body": {"top_k": 64, "chat_template_kwargs": {"enable_thinking": True}}}
MINISTRAL = {"temperature": .15}

MODEL_CONFIG = {
    "qwen-4b": {"bidder": QWEN_BID, "judge": QWEN_JUDGE, "parameters_b": 4, "gpu": "A10", "usd_per_hour": 1.10},
    "qwen-9b": {"bidder": QWEN_BID, "judge": QWEN_JUDGE, "parameters_b": 9, "gpu": "L40S", "usd_per_hour": 1.95},
    "gemma-e4b": {"bidder": GEMMA_BID, "judge": GEMMA_JUDGE, "parameters_b": 4, "gpu": "A10", "usd_per_hour": 1.10},
    "gemma-12b": {"bidder": GEMMA_BID, "judge": GEMMA_JUDGE, "parameters_b": 12, "gpu": "L40S", "usd_per_hour": 1.95},
    "ministral-3b": {"bidder": MINISTRAL, "judge": MINISTRAL, "parameters_b": 3, "gpu": "A10", "usd_per_hour": 1.10},
    "ministral-8b": {"bidder": MINISTRAL, "judge": MINISTRAL, "parameters_b": 8, "gpu": "L40S", "usd_per_hour": 1.95},
}


def sampling_for(model, thinking=False):
    """Return an independent copy; a caller cannot mutate the frozen recipe."""
    if model not in MODEL_CONFIG:
        raise ValueError(f"unknown sampling model key: {model}")
    return deepcopy(MODEL_CONFIG[model]["judge" if thinking else "bidder"])
