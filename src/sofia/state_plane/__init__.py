"""Backend-neutral contracts for Sofía's logical State Plane.

This is a cross-package architecture boundary, not a new roadmap package.
"""

from sofia.state_plane.model import (
    StateClass,
    StateKey,
    StateRecord,
    StateScope,
)
from sofia.state_plane.store import (
    StateConflictError,
    StatePlane,
    StatePlaneError,
)

__all__ = [
    "StateClass",
    "StateConflictError",
    "StateKey",
    "StatePlane",
    "StatePlaneError",
    "StateRecord",
    "StateScope",
]
