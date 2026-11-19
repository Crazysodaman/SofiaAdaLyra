"""Canonical compatibility shim for :mod:`sofia.core.unwritten`.

All public names now live under :mod:`sofia.core.unwritten` (canonical blank
Core implementation).  This module re-exports them unchanged so existing
imports keep working.
"""
from __future__ import annotations

from sofia.core.unwritten import *  # noqa: F401,F403
from sofia.core.unwritten import __all__ as _CANONICAL_EXPORTS

__all__ = list(_CANONICAL_EXPORTS)
