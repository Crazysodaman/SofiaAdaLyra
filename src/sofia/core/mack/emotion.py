"""Mack Fuller's Core-owned simulated-emotion baseline (Core #2)."""
from __future__ import annotations

from sofia.core.multicore.emotion import EmotionBehaviorProfile

MACK_EMOTION_PROFILE = EmotionBehaviorProfile(
    continuity_key="mack-fuller",
    display_name="Mack Fuller",
    temperament={
        "steadiness": 0.82,
        "directness": 0.78,
        "protectiveness": 0.70,
        "curiosity": 0.45,
    },
    expressiveness=0.62,
    recovery_scale=1.25,
    serious_contexts=("safety", "engineering"),
)

__all__ = ["MACK_EMOTION_PROFILE"]
