"""Opt-in, content-free performance observations for local diagnosis.

No prompts, model output, file paths, identities or evidence references are
recorded. Missing provider metrics remain unknown rather than invented zeroes.
"""
from __future__ import annotations

import os
import sys
from typing import Any


def performance_trace_enabled() -> bool:
    return os.environ.get("SOFIA_PERF_TRACE", "").strip() == "1"


def emit_performance(stage: str, **values: Any) -> None:
    """Write a concise diagnostic only when explicitly opted in.

    Callers must provide static stage names and numeric/unknown values only.
    The whitelist prevents accidental logging of user/model content.
    """
    if not performance_trace_enabled():
        return
    allowed = {
        "lock_wait_ms", "elapsed_ms", "load_ms", "prompt_eval_ms",
        "generation_ms", "provider_total_ms", "prompt_tokens",
        "generated_tokens", "context_tokens",
    }
    if stage not in {"conversation", "idle_reflection", "ollama"}:
        raise ValueError("Unsupported performance trace stage.")
    if set(values) - allowed:
        raise ValueError("Unsupported performance trace field.")
    parts = []
    for name, value in values.items():
        if value is None:
            parts.append(f"{name}=unknown")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError("Performance metrics must be nonnegative numbers or unknown.")
        else:
            parts.append(f"{name}={value:.1f}" if isinstance(value, float) else f"{name}={value}")
    print(f"[sofia-perf] {stage} " + " ".join(parts), file=sys.stderr, flush=True)


def ollama_metric(response: object, field: str, *, duration: bool = False) -> float | int | None:
    """Read Ollama's optional counters; duration fields are nanoseconds."""
    value = getattr(response, field, None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value / 1_000_000 if duration else value
