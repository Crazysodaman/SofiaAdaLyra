"""Typed persistent-world entities shared by storage, editor, and renderers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
from typing import Mapping


WORLD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def world_id(value: str, label: str) -> str:
    if not isinstance(value, str) or WORLD_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a canonical world identifier")
    return value


def bounded_text(value: str, label: str, maximum: int = 240) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{label} must be bounded text")
    return value.strip()


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("world timestamps must be timezone-aware")
    return value


class SpaceKind(str, Enum):
    ROOM = "room"
    BUILDING = "building"
    WORKSPACE = "workspace"
    SHARED = "shared"
    PRIVATE = "private"
    OUTDOOR = "outdoor"


class ObjectKind(str, Enum):
    FURNITURE = "furniture"
    ELECTRONICS = "electronics"
    ART = "art"
    BOOK = "book"
    INSTRUMENT = "instrument"
    TOOL = "tool"
    DECORATION = "decoration"
    PLANT = "plant"
    TERMINAL = "terminal"
    EQUIPMENT = "equipment"
    WARDROBE = "wardrobe"
    CONTAINER = "container"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class Transform:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    scale: float = 1.0

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.z, self.pitch, self.yaw, self.roll, self.scale)
        if any(type(value) not in (int, float) for value in values):
            raise TypeError("transform values must be numbers")
        if not 0.01 <= float(self.scale) <= 100.0:
            raise ValueError("scale must be in 0.01..100")
        if any(abs(float(value)) > 1_000_000 for value in (self.x, self.y, self.z)):
            raise ValueError("world position exceeds supported bounds")


@dataclass(frozen=True, slots=True)
class WorldSpace:
    space_id: str
    name: str
    kind: SpaceKind
    owner_principal_id: str
    audience_id: str
    parent_space_id: str | None
    archived: bool
    revision: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        world_id(self.space_id, "space_id")
        bounded_text(self.name, "space name")
        world_id(self.owner_principal_id, "owner_principal_id")
        bounded_text(self.audience_id, "audience_id", 160)
        if self.parent_space_id is not None:
            world_id(self.parent_space_id, "parent_space_id")
        if type(self.archived) is not bool or type(self.revision) is not int or self.revision < 1:
            raise ValueError("space archive/revision is invalid")
        aware(self.created_at); aware(self.updated_at)


@dataclass(frozen=True, slots=True)
class WorldObject:
    object_id: str
    name: str
    kind: ObjectKind
    owner_principal_id: str
    audience_id: str
    space_id: str
    transform: Transform
    container_id: str | None = None
    group_id: str | None = None
    asset_id: str | None = None
    state: Mapping[str, object] = field(default_factory=dict)
    archived: bool = False
    revision: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.object_id, "object_id"), (self.owner_principal_id, "owner_principal_id"),
            (self.space_id, "space_id"),
        ):
            world_id(value, label)
        bounded_text(self.name, "object name")
        bounded_text(self.audience_id, "audience_id", 160)
        for value, label in (
            (self.container_id, "container_id"), (self.group_id, "group_id"),
            (self.asset_id, "asset_id"),
        ):
            if value is not None:
                world_id(value, label)
        if self.container_id == self.object_id:
            raise ValueError("an object cannot contain itself")
        if not isinstance(self.transform, Transform):
            raise TypeError("transform must be Transform")
        if not isinstance(self.state, Mapping):
            raise TypeError("state must be a mapping")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be positive")
        if self.created_at is not None:
            aware(self.created_at)
        if self.updated_at is not None:
            aware(self.updated_at)


@dataclass(frozen=True, slots=True)
class ScenePage:
    space: WorldSpace
    objects: tuple[WorldObject, ...]
    next_cursor: str | None
    total_stored: int
    render_budget: int


@dataclass(frozen=True, slots=True)
class WorldMutationReceipt:
    receipt_id: str
    entity_type: str
    entity_id: str
    action: str
    revision: int
    actor_principal_id: str
    evidence_ref: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class WorldInteractionDecision:
    interaction_id: str
    actor_id: str
    object_id: str
    space_id: str
    verb: str
    gesture: str | None
    object_revision: int
    evidence_ref: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorldInteractionReceipt:
    receipt_id: str
    interaction_id: str
    status: str
    renderer_backend: str
    acknowledged: bool
    detail: str
    occurred_at: datetime
