from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MigrationPhase(Enum):
    EXPAND = "expand"
    MIGRATE = "migrate"
    CONTRACT = "contract"


@dataclass(frozen=True, slots=True)
class SchemaCompatibility:
    current_revision: int
    readable_min: int
    readable_max: int
    writable_min: int
    writable_max: int

    def __post_init__(self) -> None:
        values = (
            self.current_revision,
            self.readable_min,
            self.readable_max,
            self.writable_min,
            self.writable_max,
        )
        if any(type(value) is not int or value < 1 for value in values):
            raise ValueError("schema revisions must be positive integers")
        if self.readable_min > self.readable_max:
            raise ValueError("readable schema window is invalid")
        if self.writable_min > self.writable_max:
            raise ValueError("writable schema window is invalid")
        if not self.can_read(self.current_revision):
            raise ValueError("current revision must be readable")
        if not self.can_write(self.current_revision):
            raise ValueError("current revision must be writable")

    def can_read(self, revision: int) -> bool:
        return (
            type(revision) is int
            and self.readable_min <= revision <= self.readable_max
        )

    def can_write(self, revision: int) -> bool:
        return (
            type(revision) is int
            and self.writable_min <= revision <= self.writable_max
        )


@dataclass(frozen=True, slots=True)
class MigrationStep:
    migration_id: str
    from_revision: int
    to_revision: int
    phase: MigrationPhase
    reversible: bool

    def __post_init__(self) -> None:
        if not isinstance(self.migration_id, str) or not self.migration_id.strip():
            raise ValueError("migration_id must be nonempty")
        if (
            type(self.from_revision) is not int
            or type(self.to_revision) is not int
            or self.from_revision < 1
            or self.to_revision < 1
        ):
            raise ValueError("migration revisions must be positive integers")
        if self.to_revision < self.from_revision:
            raise ValueError("migration steps cannot move schema backward")
        if not isinstance(self.phase, MigrationPhase):
            raise TypeError("phase must be a MigrationPhase")
        if not isinstance(self.reversible, bool):
            raise TypeError("reversible must be boolean")


class SchemaRegistry:
    """Deterministic registry for reviewed State Plane migration steps."""

    def __init__(
        self,
        *,
        compatibility: SchemaCompatibility,
        steps: tuple[MigrationStep, ...] = (),
    ) -> None:
        if not isinstance(compatibility, SchemaCompatibility):
            raise TypeError("compatibility must be SchemaCompatibility")
        if not isinstance(steps, tuple):
            raise TypeError("steps must be a tuple")
        ids: set[str] = set()
        for step in steps:
            if not isinstance(step, MigrationStep):
                raise TypeError("steps must contain MigrationStep values")
            if step.migration_id in ids:
                raise ValueError("migration IDs must be unique")
            ids.add(step.migration_id)
        self.compatibility = compatibility
        self.steps = steps

    def path(
        self,
        *,
        from_revision: int,
        to_revision: int,
    ) -> tuple[MigrationStep, ...]:
        if type(from_revision) is not int or type(to_revision) is not int:
            raise TypeError("schema revisions must be integers")
        if to_revision < from_revision:
            raise ValueError("downgrade requires an explicit rollback plan")
        if to_revision == from_revision:
            return ()

        current = from_revision
        selected: list[MigrationStep] = []
        while current < to_revision:
            candidates = tuple(
                step
                for step in self.steps
                if step.from_revision == current
                and step.to_revision <= to_revision
            )
            if not candidates:
                raise LookupError(
                    f"no registered migration from schema revision {current}"
                )
            # Prefer the narrowest reviewed forward step. Phases for one
            # revision transition retain declaration order.
            next_revision = min(step.to_revision for step in candidates)
            phase_steps = tuple(
                step for step in candidates if step.to_revision == next_revision
            )
            selected.extend(phase_steps)
            current = next_revision
        return tuple(selected)
