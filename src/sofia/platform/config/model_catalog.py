"""Central local-model presets.

These names are recommendations and first-boot defaults only. Runtime cognition
uses ProviderConfiguration values supplied by saved settings or environment
overrides; no cognitive engine is coupled to a concrete model identifier.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocalModelPreset:
    key: str
    model: str
    context_size: int
    purpose: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("model preset key is required")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model preset model is required")
        if type(self.context_size) is not int or self.context_size <= 0:
            raise ValueError("model preset context_size must be positive")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("model preset purpose is required")


LEGACY_SINGLE_PRESET = LocalModelPreset(
    key="legacy-single",
    model="qwen3:14b",
    context_size=20000,
    purpose="Existing single-model compatibility default.",
)
RECOMMENDED_PRIMARY_PRESET = LocalModelPreset(
    key="local-primary",
    model="qwen3.5:9b",
    context_size=16000,
    purpose="Primary reasoning, technical work, tools, and planning.",
)
RECOMMENDED_SECONDARY_PRESET = LocalModelPreset(
    key="local-secondary-open",
    model="huihui_ai/qwen3.5-abliterated:4B",
    context_size=8192,
    purpose="Fast/open conversation and verification review.",
)

LOCAL_MODEL_PRESETS = (
    LEGACY_SINGLE_PRESET,
    RECOMMENDED_PRIMARY_PRESET,
    RECOMMENDED_SECONDARY_PRESET,
)

DEFAULT_PROVIDER_MODEL = RECOMMENDED_PRIMARY_PRESET.model
DEFAULT_PROVIDER_CONTEXT_SIZE = RECOMMENDED_PRIMARY_PRESET.context_size
DEFAULT_PROVIDER_MAX_OUTPUT_TOKENS = 768
RECOMMENDED_PRIMARY_MODEL = RECOMMENDED_PRIMARY_PRESET.model
RECOMMENDED_PRIMARY_CONTEXT_SIZE = RECOMMENDED_PRIMARY_PRESET.context_size
RECOMMENDED_SECONDARY_MODEL = RECOMMENDED_SECONDARY_PRESET.model
RECOMMENDED_SECONDARY_CONTEXT_SIZE = RECOMMENDED_SECONDARY_PRESET.context_size


def known_local_model_names() -> tuple[str, ...]:
    """Return editable UI suggestions, never an allow-list."""
    return tuple(dict.fromkeys(preset.model for preset in LOCAL_MODEL_PRESETS))
