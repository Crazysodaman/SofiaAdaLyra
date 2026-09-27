from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from sofia.config.model import SofiaConfiguration
from sofia.state.model import StateClass


class StateBackendKind(Enum):
    SQLITE = "sqlite"
    JSON = "json"
    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True, slots=True)
class StateInventoryEntry:
    name: str
    owner_package: str
    path: Path
    backend: StateBackendKind
    state_class: StateClass
    authoritative: bool
    notes: str = ""

    def __post_init__(self) -> None:
        for name in ("name", "owner_package"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.path, Path):
            raise TypeError("path must be a Path")
        if not isinstance(self.backend, StateBackendKind):
            raise TypeError("backend must be a StateBackendKind")
        if not isinstance(self.state_class, StateClass):
            raise TypeError("state_class must be a StateClass")
        if not isinstance(self.authoritative, bool):
            raise TypeError("authoritative must be boolean")


def configured_state_inventory(
    configuration: SofiaConfiguration,
) -> tuple[StateInventoryEntry, ...]:
    """
    Inventory the primary configured state roots known to composition.

    Package-specific SQLite tables are inventoried separately during migration;
    this function makes file/root ownership explicit without probing or
    mutating the filesystem.
    """
    if not isinstance(configuration, SofiaConfiguration):
        raise TypeError("configuration must be a SofiaConfiguration")

    state_path = Path(configuration.state_path)
    root = state_path.parent
    return (
        StateInventoryEntry(
            "application-state",
            "MEM",
            state_path,
            StateBackendKind.SQLITE,
            StateClass.SHARED_AUTHORITATIVE,
            True,
            "Current multi-package SQLite state; requires table-level inventory.",
        ),
        StateInventoryEntry(
            "canonical-identity",
            "CORE",
            Path(configuration.identity_path),
            StateBackendKind.JSON,
            StateClass.PROTECTED,
            True,
        ),
        StateInventoryEntry(
            "constitution",
            "CORE/SAFE",
            Path(configuration.constitution_path),
            StateBackendKind.FILE,
            StateClass.PROTECTED,
            True,
        ),
        StateInventoryEntry(
            "constitution-trusted-hash",
            "SAFE",
            Path(configuration.constitution_hash_path),
            StateBackendKind.FILE,
            StateClass.PROTECTED,
            True,
        ),
        StateInventoryEntry(
            "personality",
            "CORE",
            Path(configuration.personality_path),
            StateBackendKind.JSON,
            StateClass.SHARED_AUTHORITATIVE,
            True,
        ),
        StateInventoryEntry(
            "avatar",
            "AVATAR",
            Path(configuration.avatar_path),
            StateBackendKind.JSON,
            StateClass.SHARED_AUTHORITATIVE,
            True,
        ),
        StateInventoryEntry(
            "knowledge",
            "KNOW",
            root / "knowledge.json",
            StateBackendKind.JSON,
            StateClass.SHARED_AUTHORITATIVE,
            True,
        ),
        StateInventoryEntry(
            "knowledge-lifecycle",
            "KNOW",
            root / "knowledge-lifecycle.json",
            StateBackendKind.JSON,
            StateClass.SHARED_AUTHORITATIVE,
            True,
        ),
        StateInventoryEntry(
            "machine-locations",
            "ENVIRONMENT/OPS",
            root / "machine-locations.json",
            StateBackendKind.JSON,
            StateClass.SHARED_AUTHORITATIVE,
            True,
        ),
    )
