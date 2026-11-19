"""Nova Arden's canonical, inert Core profile metadata (Core #3)."""
from __future__ import annotations

from sofia.core.multicore.profiles import CoreProfileSpec

NOVA_PROFILE = CoreProfileSpec(
    slug="nova",
    core_number=3,
    full_name="Nova Arden",
    nickname=None,
    gender="Female",
    presentation_species="Half-elf",
    apparent_age=27,
    identity_concept="The Unbound Scholar",
    accessory="Pendant",
    required_measurements={"bust": 31.25},
    required_pbr={"trim_metallic": 0.00},
)

__all__ = ["NOVA_PROFILE"]
