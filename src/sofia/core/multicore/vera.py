"""Canonical compatibility shim for :mod:`sofia.core.vera`.

All public names now live under :mod:`sofia.core.vera` (canonical
implementation) and :mod:`sofia.core.vera.profile` (inert profile constant).
This module re-exports them unchanged so existing imports keep working.
"""
from __future__ import annotations

from sofia.core.vera import *  # noqa: F401,F403
from sofia.core.vera import __all__ as _CANONICAL_EXPORTS

__all__ = list(_CANONICAL_EXPORTS)
