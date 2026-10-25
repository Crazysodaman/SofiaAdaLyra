"""Canonical state exports, lazy so Core-free clients remain Core-free."""
from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "SchemaCompatibility": ("component_schema", "SchemaCompatibility"),
    "JsonStateRepository": ("json_repository", "JsonStateRepository"),
    "create_state_plane": ("factory", "create_state_plane"),
    **{name: ("model", name) for name in (
        "StateClass", "StateKey", "StateRecord",
    )},
    **{name: ("namespaces", name) for name in (
        "HABIT_COVERAGE", "HABIT_EVIDENCE_INVALIDATION", "HABIT_EXPECTATION",
        "HABIT_OBSERVATION", "HABIT_PATTERN", "HABIT_SUPPRESSION",
        "REL_CONTACT_OBSERVATION", "StateNamespaceSpec",
    )},
    **{name: ("plane", name) for name in (
        "StatePlane", "StatePlaneConflictError", "StateWrite",
    )},
    **{name: ("replication", name) for name in (
        "ReplicatedStatePlane", "ReplicationHealth",
        "ReplicationPartialCommitError", "SQLiteReplicationWitness",
        "StaleWriterError", "WriterLease",
    )},
    "SQLiteStatePlane": ("sqlite_plane", "SQLiteStatePlane"),
    **{name: ("platform", name) for name in (
        "MigrationPlan", "NamespaceHandle", "RestorePlan",
        "StatePlatformService",
    )},
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
