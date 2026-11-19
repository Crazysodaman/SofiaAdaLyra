"""Mack Fuller's canonical, inert Core profile metadata (Core #2)."""
from __future__ import annotations

from sofia.core.multicore.profiles import CoreProfileSpec

MACK_PROFILE = CoreProfileSpec(
    slug="mack",
    core_number=2,
    full_name="Mack Fuller",
    nickname="Mack",
    gender="Male",
    presentation_species="Human",
    apparent_age=34,
    identity_concept="The Frontier Gentleman",
)

__all__ = ["MACK_PROFILE"]
