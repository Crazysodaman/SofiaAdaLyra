"""Engineering 22E: remote capability claims and evidence freshness.

A peer's advertised capabilities are untrusted declarations, not permission.
Only a separate authenticated transport can establish who supplied them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID


def _aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{label} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware.")


def _identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    if len(value) > 128 or any(ch.isspace() for ch in value):
        raise ValueError(f"{label} must be at most 128 characters, without spaces.")


@dataclass(frozen=True)
class RemoteCapability:
    """A named, explicitly bounded interface, not executable code."""

    name: str
    operations: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.name, "Capability name")
        if not isinstance(self.operations, tuple) or not self.operations:
            raise ValueError("Capability operations must be a nonempty tuple.")
        for operation in self.operations:
            _identifier(operation, "Capability operation")
        if len(set(self.operations)) != len(self.operations):
            raise ValueError("Duplicate operations are forbidden.")


@dataclass(frozen=True)
class CapabilityInventory:
    """Caller-supplied remote report; peer claims alone are not verification."""

    node_id: UUID
    observed_at: datetime
    capabilities: tuple[RemoteCapability, ...]
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, UUID):
            raise TypeError("Inventory node_id must be a UUID.")
        _aware(self.observed_at, "Inventory observed_at")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("Inventory source must be a nonempty string.")
        if not isinstance(self.capabilities, tuple):
            raise TypeError("Inventory capabilities must be a tuple.")
        if any(not isinstance(item, RemoteCapability) for item in self.capabilities):
            raise TypeError("Inventory entries must be RemoteCapability instances.")
        if len({item.name for item in self.capabilities}) != len(self.capabilities):
            raise ValueError("Duplicate capability names are forbidden.")

    def advertises(self, capability: str, operation: str) -> bool:
        return any(item.name == capability and operation in item.operations
                   for item in self.capabilities)


def inventory_is_current(inventory: CapabilityInventory, *, now: datetime,
                         max_age: timedelta) -> bool:
    if not isinstance(inventory, CapabilityInventory):
        raise TypeError("inventory must be a CapabilityInventory.")
    _aware(now, "now")
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValueError("max_age must be a positive timedelta.")
    return timedelta(0) <= now - inventory.observed_at <= max_age
