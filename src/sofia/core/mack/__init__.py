"""Mack Fuller, Core #2: package entrypoint and Core-owned definitions.

Loading a profile or composing a manifest here grants no identity allocation,
authority, installation or activation.  The caller always supplies the Core
UUID, and assets are resolved from this package's own directory.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sofia.core.mack.profile import MACK_PROFILE
from sofia.core.multicore.profiles import CoreProfile, load_core_profile

MACK_SLUG = "mack"
MACK_CORE_NUMBER = 2
MACK_PACKAGE_NAME = "sofia.core.mack"
MACK_CORE_ENTRYPOINT = "sofia.core.mack:mack_core_profile"

__all__ = [
    "MACK_CORE_ENTRYPOINT",
    "MACK_CORE_NUMBER",
    "MACK_PACKAGE_NAME",
    "MACK_PROFILE",
    "MACK_SLUG",
    "build_mack_package",
    "mack_core_profile",
]


def mack_core_profile(
    core_id: UUID,
    *,
    resource_root: Path | None = None,
    require_presentation_assets: bool = False,
) -> CoreProfile:
    """Load Mack's canonical profile with a caller-supplied Core UUID."""
    return load_core_profile(
        MACK_PROFILE,
        core_id,
        resource_root=resource_root,
        require_presentation_assets=require_presentation_assets,
    )


def build_mack_package(core_id: UUID, **options):
    """Compose Mack's inert installable package manifest (no installation)."""
    from sofia.core.multicore.packages import manifest_from_core_profile

    return manifest_from_core_profile(mack_core_profile(core_id, **options))
