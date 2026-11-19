"""Vera's canonical, inert Core profile metadata (Core #6)."""
from __future__ import annotations

from sofia.core.multicore.profiles import CoreProfileSpec

VERA_PROFILE = CoreProfileSpec(
    slug="vera",
    core_number=6,
    full_name="Vera",
    nickname="Vera",
    gender="Female",
    presentation_species="Human",
    apparent_age=26,
    identity_concept="Original Spartan-inspired character",
    accessory="Watch",
    required_measurements={
        "head_proportions": 8.0,
        "shoulders": 19.0,
        "bust": 38.0,
        "underbust": 34.0,
        "waist": 33.5,
        "hips": 41.0,
        "inseam": 37.5,
        "arm_span": 80.5,
        "neck": 15.5,
        "hand": 8.4,
        "foot": 12.0,
        "upper_arm": 14.5,
        "thigh": 25.5,
        "calf": 17.0,
        "hair_top": 4.0,
        "hair_sides": 4.0,
        "hair_back": 4.0,
    },
    required_pbr={"skin_roughness": 0.55, "hair_roughness": 0.45},
)

__all__ = ["VERA_PROFILE"]
