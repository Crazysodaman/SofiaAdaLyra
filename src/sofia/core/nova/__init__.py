"""Nova Arden, Core #3: package entrypoint and Core-owned definitions.

Loading a profile or composing a manifest here grants no identity allocation,
authority, installation or activation.  The caller always supplies the Core
UUID, and assets are resolved from this package's own directory.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sofia.core.multicore.profiles import CoreProfile, load_core_profile
from sofia.core.nova.profile import NOVA_PROFILE

NOVA_SLUG = "nova"
NOVA_CORE_NUMBER = 3
NOVA_PACKAGE_NAME = "sofia.core.nova"
NOVA_CORE_ENTRYPOINT = "sofia.core.nova:nova_core_profile"

__all__ = [
    "NOVA_CORE_ENTRYPOINT",
    "NOVA_CORE_NUMBER",
    "NOVA_PACKAGE_NAME",
    "NOVA_PROFILE",
    "NOVA_SLUG",
    "build_nova_package",
    "nova_core_profile",
]


def nova_core_profile(
    core_id: UUID,
    *,
    resource_root: Path | None = None,
    require_presentation_assets: bool = False,
) -> CoreProfile:
    """Load Nova's canonical profile with a caller-supplied Core UUID."""
    return load_core_profile(
        NOVA_PROFILE,
        core_id,
        resource_root=resource_root,
        require_presentation_assets=require_presentation_assets,
    )


def build_nova_package(core_id: UUID, **options):
    """Compose Nova's inert installable package manifest (no installation)."""
    from sofia.core.multicore.packages import manifest_from_core_profile

    return manifest_from_core_profile(nova_core_profile(core_id, **options))
