"""Platform-owned identity bootstrap mode.

The mode decides whether the protected identity must already exist when the
canonical home is opened. ``sofia.core.identity.model`` re-exports it for
compatibility during the integrated-wheel transition.
"""
from enum import Enum


class IdentityBootstrapMode(str, Enum):
    FIRST_BOOTSTRAP = "first_bootstrap"
    REQUIRE_EXISTING = "require_existing"
