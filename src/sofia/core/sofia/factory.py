"""Canonical Sofía asset references and an inert Core definition factory.

Sofía's protected constitution, personality and runtime identity stay in their
existing canonical locations.  This module only builds references to those
unchanged assets and requires the caller to supply the protected runtime UUID.
No UUID is generated, migrated or embedded here.
"""
from __future__ import annotations

from hashlib import sha256
from importlib.resources import files
from uuid import UUID

from sofia.core.sofia.identity import SOFIA_PERSONAL_NAME
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreAssetReference, CoreDefinition
from sofia.sdk.identity import AegisIdentity, IdentityKind

SOFIA_CONSTITUTION_PATH = "constitution/constitution.md"
SOFIA_PERSONALITY_PATH = "personality/personality.json"
SOFIA_CONSTITUTION_PACKAGE = "sofia.core.constitution"
SOFIA_PERSONALITY_PACKAGE = "sofia.core.personality"

__all__ = [
    "SOFIA_CONSTITUTION_PACKAGE",
    "SOFIA_CONSTITUTION_PATH",
    "SOFIA_PERSONALITY_PACKAGE",
    "SOFIA_PERSONALITY_PATH",
    "build_sofia_core_definition",
    "sofia_constitution_reference",
    "sofia_personality_reference",
]


def _reference(package: str, name: str, path: str) -> CoreAssetReference:
    raw = files(package).joinpath(name).read_bytes()
    return CoreAssetReference(path, sha256(raw).hexdigest(), len(raw))


def sofia_constitution_reference() -> CoreAssetReference:
    """Reference Sofía's existing protected constitution asset."""
    return _reference(
        SOFIA_CONSTITUTION_PACKAGE,
        "constitution.md",
        SOFIA_CONSTITUTION_PATH,
    )


def sofia_personality_reference() -> CoreAssetReference:
    """Reference Sofía's existing canonical personality asset."""
    return _reference(
        SOFIA_PERSONALITY_PACKAGE,
        "personality.json",
        SOFIA_PERSONALITY_PATH,
    )


def build_sofia_core_definition(
    core_id: UUID,
    *,
    revision: int,
    runtime_release_sha256: str,
    name: str = SOFIA_PERSONAL_NAME,
) -> CoreDefinition:
    """Build an inert definition for the caller-supplied protected Sofía UUID."""
    if not isinstance(core_id, UUID) or core_id.int == 0:
        raise ValueError("an existing nonzero Sofía Core UUID is required")
    return CoreDefinition(
        identity=AegisIdentity(IdentityKind.CORE, core_id),
        name=name,
        revision=revision,
        runtime_release_sha256=runtime_release_sha256,
        sdk_protocol=SDK_PROTOCOL_VERSION,
        constitution=sofia_constitution_reference(),
        personality=sofia_personality_reference(),
    )
