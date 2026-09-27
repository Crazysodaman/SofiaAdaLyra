"""Backend-neutral contracts for Sofía's logical State Plane.

This is a cross-package architecture boundary, not a new roadmap package.
"""

from sofia.state_plane.model import (
    StateClass,
    StateKey,
    StateRecord,
    StateScope,
)
from sofia.state_plane.inventory import (
    StateInventory,
    StateInventoryEntry,
    StorageKind,
)
from sofia.state_plane.schema import (
    MigrationPhase,
    SchemaCompatibility,
    SchemaMigration,
    SchemaMigrationError,
    SchemaRegistry,
)
from sofia.state_plane.sqlite import SQLiteStatePlane
from sofia.state_plane.store import (
    StateConflictError,
    StatePlane,
    StatePlaneError,
)

__all__ = [
    "MigrationPhase",
    "SchemaCompatibility",
    "SchemaMigration",
    "SchemaMigrationError",
    "SchemaRegistry",
    "SQLiteStatePlane",
    "StateClass",
    "StateConflictError",
    "StateInventory",
    "StateInventoryEntry",
    "StateKey",
    "StatePlane",
    "StatePlaneError",
    "StateRecord",
    "StateScope",
    "StorageKind",
]
