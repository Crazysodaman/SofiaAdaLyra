from sofia.platform.state.component_schema import SchemaCompatibility
from sofia.platform.state.json_repository import JsonStateRepository
from sofia.platform.state.factory import create_state_plane
from sofia.platform.state.model import StateClass, StateKey, StateRecord
from sofia.platform.state.namespaces import (
    HABIT_COVERAGE,
    HABIT_EVIDENCE_INVALIDATION,
    HABIT_EXPECTATION,
    HABIT_OBSERVATION,
    HABIT_PATTERN,
    HABIT_SUPPRESSION,
    REL_CONTACT_OBSERVATION,
    StateNamespaceSpec,
)
from sofia.platform.state.plane import StatePlane, StatePlaneConflictError, StateWrite
from sofia.platform.state.replication import (
    ReplicatedStatePlane,
    ReplicationHealth,
    ReplicationPartialCommitError,
    SQLiteReplicationWitness,
    StaleWriterError,
    WriterLease,
)
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.sdk_facade import PlatformSDKStateFacade

__all__ = [
    "HABIT_COVERAGE",
    "HABIT_EVIDENCE_INVALIDATION",
    "HABIT_EXPECTATION",
    "HABIT_OBSERVATION",
    "HABIT_PATTERN",
    "HABIT_SUPPRESSION",
    "JsonStateRepository",
    "REL_CONTACT_OBSERVATION",
    "SchemaCompatibility",
    "ReplicatedStatePlane",
    "ReplicationHealth",
    "ReplicationPartialCommitError",
    "SQLiteReplicationWitness",
    "StaleWriterError",
    "WriterLease",
    "create_state_plane",
    "StateClass",
    "StateKey",
    "StateNamespaceSpec",
    "StatePlane",
    "StatePlaneConflictError",
    "StateWrite",
    "StateRecord",
    "SQLiteStatePlane",
    "PlatformSDKStateFacade",
    "MigrationPlan",
    "NamespaceHandle",
    "RestorePlan",
    "StatePlatformService",
]


def __getattr__(name: str):
    """Lazily load the backup facade without a config/state import cycle."""
    if name in {
        "MigrationPlan", "NamespaceHandle", "RestorePlan",
        "StatePlatformService",
    }:
        from sofia.platform.state import platform
        return getattr(platform, name)
    raise AttributeError(name)
