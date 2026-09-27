"""Role-aware filesystem classification used before any cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PathClass(str, Enum):
    SOURCE = "source"
    SHARED_STATE = "shared_state"
    PROTECTED_STATE = "protected_state"
    SECRET = "secret"
    IMMUTABLE_ARTIFACT = "immutable_artifact"
    LOCAL_EPHEMERAL = "local_ephemeral"
    LOG = "log"
    BACKUP = "backup"


@dataclass(frozen=True, slots=True)
class ManagedPath:
    path: Path
    path_class: PathClass
    owner: str
    removable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path must be a Path")
        if not isinstance(self.path_class, PathClass):
            raise TypeError("path_class must be a PathClass")
        if not isinstance(self.owner, str) or not self.owner.strip():
            raise ValueError("owner must be non-empty")
        if not isinstance(self.removable, bool):
            raise TypeError("removable must be boolean")
        if self.path_class in {
            PathClass.PROTECTED_STATE,
            PathClass.SECRET,
            PathClass.BACKUP,
        } and self.removable:
            raise ValueError(
                "protected/secret/backup paths cannot be generically removable"
            )


@dataclass(frozen=True, slots=True)
class RuntimeLayout:
    """Explicit installation layout. Classification itself performs no I/O."""

    source_root: Path
    state_root: Path
    protected_root: Path
    secret_root: Path
    artifact_root: Path
    cache_root: Path
    log_root: Path
    backup_root: Path

    def __post_init__(self) -> None:
        values = (
            self.source_root,
            self.state_root,
            self.protected_root,
            self.secret_root,
            self.artifact_root,
            self.cache_root,
            self.log_root,
            self.backup_root,
        )
        if any(not isinstance(value, Path) for value in values):
            raise TypeError("all runtime layout roots must be Path values")
        normalized = tuple(value.resolve() for value in values)
        if len(set(normalized)) != len(normalized):
            raise ValueError("runtime layout roots must be distinct")

    def managed_roots(self) -> tuple[ManagedPath, ...]:
        return (
            ManagedPath(self.source_root, PathClass.SOURCE, "DEV"),
            ManagedPath(self.state_root, PathClass.SHARED_STATE, "MEM"),
            ManagedPath(
                self.protected_root,
                PathClass.PROTECTED_STATE,
                "SAFE",
            ),
            ManagedPath(self.secret_root, PathClass.SECRET, "SAFE"),
            ManagedPath(
                self.artifact_root,
                PathClass.IMMUTABLE_ARTIFACT,
                "OPS",
            ),
            ManagedPath(
                self.cache_root,
                PathClass.LOCAL_EPHEMERAL,
                "CLEAN",
                removable=True,
            ),
            ManagedPath(
                self.log_root,
                PathClass.LOG,
                "RUN",
                removable=True,
            ),
            ManagedPath(self.backup_root, PathClass.BACKUP, "SAFE"),
        )
