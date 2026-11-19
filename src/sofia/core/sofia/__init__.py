"""Sofía, Core #1: immutable naming metadata and canonical asset references."""
from __future__ import annotations

from sofia.core.sofia.factory import (
    SOFIA_CONSTITUTION_PACKAGE,
    SOFIA_CONSTITUTION_PATH,
    SOFIA_PERSONALITY_PACKAGE,
    SOFIA_PERSONALITY_PATH,
    build_sofia_core_definition,
    sofia_constitution_reference,
    sofia_personality_reference,
)
from sofia.core.sofia.identity import (
    SOFIA_CORE_NUMBER,
    SOFIA_IDENTITY,
    SOFIA_NICKNAME,
    SOFIA_PACKAGE_NAME,
    SOFIA_PERSONAL_NAME,
    SOFIA_SLUG,
    SofiaCoreIdentity,
)

__all__ = [
    "SOFIA_CONSTITUTION_PACKAGE",
    "SOFIA_CONSTITUTION_PATH",
    "SOFIA_CORE_NUMBER",
    "SOFIA_IDENTITY",
    "SOFIA_NICKNAME",
    "SOFIA_PACKAGE_NAME",
    "SOFIA_PERSONALITY_PACKAGE",
    "SOFIA_PERSONALITY_PATH",
    "SOFIA_PERSONAL_NAME",
    "SOFIA_SLUG",
    "SofiaCoreIdentity",
    "build_sofia_core_definition",
    "sofia_constitution_reference",
    "sofia_personality_reference",
]
