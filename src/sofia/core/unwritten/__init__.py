"""Unwritten, Core #7: neutral bootstrap entrypoint.

The canonical implementation lives in :mod:`sofia.core.unwritten.identity`.
Importing this package creates no identity, name, presentation, biography,
memory or authority.  A caller must supply the nonzero Core UUID explicitly;
the operator-facing label is neutral and never a personal identity.
"""
from __future__ import annotations

from uuid import UUID

from sofia.core.unwritten.identity import *  # noqa: F401,F403
from sofia.core.unwritten.identity import (
    MulticoreUnwrittenIdentity,
    __all__ as _IDENTITY_EXPORTS,
)

UNWRITTEN_PACKAGE_NAME = "sofia.core.unwritten"
UNWRITTEN_CORE_ENTRYPOINT = "sofia.core.unwritten:blank_core_profile"

__all__ = sorted(
    {*_IDENTITY_EXPORTS, "UNWRITTEN_CORE_ENTRYPOINT", "UNWRITTEN_PACKAGE_NAME",
     "bootstrap_unwritten_core"}
)


def bootstrap_unwritten_core(core_id: UUID, **options) -> MulticoreUnwrittenIdentity:
    """Build a blank Core #7 runtime owner without inventing personal identity."""
    return MulticoreUnwrittenIdentity(core_id=core_id, **options)
