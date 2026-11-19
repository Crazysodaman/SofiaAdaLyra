"""Vera, Core #6: canonical package entrypoint.

The canonical implementation lives in :mod:`sofia.core.vera.identity` and the
inert profile constant in :mod:`sofia.core.vera.profile`.  Importing this
package allocates no identity, grants no authority and proves no voice or
avatar art exists.
"""
from __future__ import annotations

from sofia.core.vera.identity import *  # noqa: F401,F403
from sofia.core.vera.identity import __all__ as _IDENTITY_EXPORTS
from sofia.core.vera.profile import VERA_PROFILE

VERA_PACKAGE_NAME = "sofia.core.vera"
VERA_CORE_ENTRYPOINT = "sofia.core.vera:vera_core_profile"

__all__ = sorted({*_IDENTITY_EXPORTS, "VERA_CORE_ENTRYPOINT", "VERA_PACKAGE_NAME"})
