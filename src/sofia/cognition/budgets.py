"""Provider context/output budgets derived from validated routing complexity."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelTokenBudget:
    context_tokens: int | None
    output_tokens: int | None


_CONTEXT_TARGETS = {
    "fast": 2048,
    "standard": 4096,
    "deep": 8192,
    "open": 8192,
    "verify": 16384,
}
_OUTPUT_TARGETS = {
    "fast": 384,
    "standard": 1024,
    "deep": 2048,
    "open": 2048,
    "verify": 3072,
}


def model_token_budget(
    route_hint: str | None,
    *,
    configured_context: int | None,
    configured_output: int | None,
) -> ModelTokenBudget:
    """Choose a small bounded window while never exceeding configuration."""
    # Direct provider consumers without a validated route retain the explicit
    # operator configuration. Production conversation requests carry a Matrix/
    # NEURO route hint and therefore receive dynamic allocation.
    if route_hint is None:
        return ModelTokenBudget(configured_context, configured_output)
    route = route_hint if route_hint in _CONTEXT_TARGETS else "standard"
    context = _CONTEXT_TARGETS[route]
    output = _OUTPUT_TARGETS[route]
    if configured_context is not None:
        context = min(context, configured_context)
    if configured_output is not None:
        output = min(output, configured_output)
    # Leave enough room for at least a small response on constrained models.
    output = min(output, max(128, context // 3))
    return ModelTokenBudget(context, output)
