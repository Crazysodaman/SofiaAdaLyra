"""Immutable Core #1 (Sofía) name, number and slug constants.

These constants describe the canonical Sofía Core slot.  They deliberately do
not contain or fabricate a runtime UUID: the protected instance identity stays
owned by the existing identity store and is always supplied by its caller.
"""
from __future__ import annotations

from dataclasses import dataclass

SOFIA_PERSONAL_NAME = "Sofía Ada Lyra"
SOFIA_NICKNAME = "Sofía"
SOFIA_CORE_NUMBER = 1
SOFIA_SLUG = "sofia"
SOFIA_PACKAGE_NAME = "sofia.core.sofia"


@dataclass(frozen=True, slots=True)
class SofiaCoreIdentity:
    """Inert, immutable naming metadata for the canonical Sofía Core slot."""

    personal_name: str = SOFIA_PERSONAL_NAME
    nickname: str = SOFIA_NICKNAME
    core_number: int = SOFIA_CORE_NUMBER
    slug: str = SOFIA_SLUG

    def __post_init__(self) -> None:
        if self.personal_name != SOFIA_PERSONAL_NAME:
            raise ValueError("Sofía's personal name is immutable")
        if self.nickname != SOFIA_NICKNAME:
            raise ValueError("Sofía's nickname is immutable")
        if self.core_number != SOFIA_CORE_NUMBER:
            raise ValueError("Sofía's Core number is immutable")
        if self.slug != SOFIA_SLUG:
            raise ValueError("Sofía's Core slug is immutable")

    @property
    def grants_authority(self) -> bool:
        return False


SOFIA_IDENTITY = SofiaCoreIdentity()

__all__ = [
    "SOFIA_CORE_NUMBER",
    "SOFIA_IDENTITY",
    "SOFIA_NICKNAME",
    "SOFIA_PACKAGE_NAME",
    "SOFIA_PERSONAL_NAME",
    "SOFIA_SLUG",
    "SofiaCoreIdentity",
]
