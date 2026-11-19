"""Nova Arden's Core-owned simulated-emotion baseline (Core #3)."""
from __future__ import annotations

from sofia.core.multicore.emotion import EmotionBehaviorProfile

NOVA_EMOTION_PROFILE = EmotionBehaviorProfile(
    continuity_key="nova-arden",
    display_name="Nova Arden",
    temperament={
        "independence": 0.86,
        "curiosity": 0.88,
        "playfulness": 0.80,
        "impulsiveness": 0.58,
        "warmth": 0.60,
    },
    expressiveness=0.82,
    recovery_scale=0.85,
    serious_contexts=("safety", "boundaries"),
)

__all__ = ["NOVA_EMOTION_PROFILE"]
