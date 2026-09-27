"""Inventory every durable/current-state surface before migration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re

from sofia.state_plane.model import StateClass

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")


class StorageKind(str, Enum):
    SQLITE = "sqlite"
    JSON = "json"
    TEXT = "text"
    DIRECTORY = "directory"
    MEMORY = "memory"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class StateInventoryEntry:
    entry_id: str
    owner_package: str
    state_class: StateClass
    storage_kind: StorageKind
    location: str
    authoritative: bool
    migration_required: bool
    notes: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("entry_id", self.entry_id),
            ("owner_package", self.owner_package),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded identifier")
        if not isinstance(self.state_class, StateClass):
            raise TypeError("state_class must be StateClass")
        if not isinstance(self.storage_kind, StorageKind):
            raise TypeError("storage_kind must be StorageKind")
        if not isinstance(self.location, str) or not self.location.strip():
            raise ValueError("location required")
        if not isinstance(self.authoritative, bool):
            raise TypeError("authoritative must be boolean")
        if not isinstance(self.migration_required, bool):
            raise TypeError("migration_required must be boolean")
        if not isinstance(self.notes, str):
            raise TypeError("notes must be text")


@dataclass(frozen=True, slots=True)
class StateInventory:
    entries: tuple[StateInventoryEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise TypeError("entries must be a tuple")
        ids: set[str] = set()
        for entry in self.entries:
            if not isinstance(entry, StateInventoryEntry):
                raise TypeError(
                    "entries must contain StateInventoryEntry values"
                )
            if entry.entry_id in ids:
                raise ValueError("state inventory entry IDs must be unique")
            ids.add(entry.entry_id)

    def authoritative(self) -> tuple[StateInventoryEntry, ...]:
        return tuple(item for item in self.entries if item.authoritative)

    def pending_migration(self) -> tuple[StateInventoryEntry, ...]:
        return tuple(item for item in self.entries if item.migration_required)
