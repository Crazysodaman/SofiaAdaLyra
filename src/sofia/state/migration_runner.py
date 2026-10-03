"""Transactional reviewed schema migration runner.

The runner binds the existing SchemaRegistry, global migration lease, executable
reviewed operations and central component schema registry into one fail-closed
path. One revision transition, including all declared phases for that
transition, commits atomically with its migration audit rows and registry update.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Callable

from sofia.state.component_schema import StateSchemaCoordinator
from sofia.state.migration_lease import (
    MigrationLease,
    MigrationLeaseLost,
    MigrationLeaseStore,
)
from sofia.state.plane import StatePlane
from sofia.state.schema import (
    MigrationStep,
    SchemaCompatibility,
    SchemaRegistry,
)


MigrationCallable = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True, slots=True)
class MigrationOperation:
    step: MigrationStep
    compatibility: SchemaCompatibility
    apply: MigrationCallable
    validate: MigrationCallable

    def __post_init__(self) -> None:
        if not isinstance(self.step, MigrationStep):
            raise TypeError("step must be MigrationStep")
        if not isinstance(self.compatibility, SchemaCompatibility):
            raise TypeError("compatibility must be SchemaCompatibility")
        if self.compatibility.current_revision != self.step.to_revision:
            raise ValueError(
                "operation compatibility must describe step.to_revision"
            )
        if not callable(self.apply) or not callable(self.validate):
            raise TypeError("apply and validate must be callable")


@dataclass(frozen=True, slots=True)
class MigrationRunResult:
    component: str
    from_revision: int
    to_revision: int
    migration_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]


class StateMigrationRunner:
    """Execute registered SQLite migrations under one fenced global lease."""

    @staticmethod
    def _clock_now(explicit_now: datetime | None) -> datetime:
        return (
            explicit_now.astimezone(timezone.utc)
            if explicit_now is not None
            else datetime.now(timezone.utc)
        )

    def __init__(
        self,
        *,
        state_path: Path,
        state_plane: StatePlane,
        owner_id: str,
        lease_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if not isinstance(state_path, Path) or not state_path.is_file():
            raise FileNotFoundError("existing state database required")
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id must be nonempty")
        if (
            not isinstance(lease_ttl, timedelta)
            or lease_ttl <= timedelta(0)
            or lease_ttl > timedelta(hours=1)
        ):
            raise ValueError("lease_ttl must be in (0, 1 hour]")
        self.state_path = state_path
        self.state_plane = state_plane
        self.owner_id = owner_id.strip()
        self.lease_ttl = lease_ttl
        self.schemas = StateSchemaCoordinator(state_path)
        self.leases = MigrationLeaseStore(state_plane)

    @staticmethod
    def _group_transitions(
        steps: tuple[MigrationStep, ...],
    ) -> tuple[tuple[MigrationStep, ...], ...]:
        groups: list[list[MigrationStep]] = []
        for step in steps:
            key = (step.from_revision, step.to_revision)
            if not groups or (
                groups[-1][0].from_revision,
                groups[-1][0].to_revision,
            ) != key:
                groups.append([step])
            else:
                groups[-1].append(step)
        return tuple(tuple(group) for group in groups)

    @staticmethod
    def _lease_matches(
        expected: MigrationLease,
        current: MigrationLease | None,
        *,
        now: datetime,
    ) -> bool:
        return (
            current is not None
            and current.owner_id == expected.owner_id
            and current.fencing_token == expected.fencing_token
            and current.expires_at > now
        )

    def _require_lease(
        self,
        lease: MigrationLease,
        *,
        now: datetime,
    ) -> None:
        current = self.leases.current()
        if not self._lease_matches(lease, current, now=now):
            raise MigrationLeaseLost(
                "migration lease changed or expired before transition"
            )

    def run(
        self,
        *,
        component: str,
        registry: SchemaRegistry,
        operations: tuple[MigrationOperation, ...],
        target_revision: int,
        evidence_prefix: str,
        now: datetime | None = None,
    ) -> MigrationRunResult:
        if not isinstance(component, str) or not component.strip():
            raise ValueError("component must be nonempty")
        if not isinstance(registry, SchemaRegistry):
            raise TypeError("registry must be SchemaRegistry")
        if not isinstance(operations, tuple):
            raise TypeError("operations must be a tuple")
        if type(target_revision) is not int or target_revision < 1:
            raise ValueError("target_revision must be positive")
        if not isinstance(evidence_prefix, str) or not evidence_prefix.strip():
            raise ValueError("evidence_prefix must be nonempty")

        current = self.schemas.current(component)
        if current is None:
            raise RuntimeError(
                "component must be registered before migration"
            )
        start_revision = current.current_revision
        path = registry.path(
            from_revision=start_revision,
            to_revision=target_revision,
        )
        if not path:
            return MigrationRunResult(
                component=component,
                from_revision=start_revision,
                to_revision=target_revision,
                migration_ids=(),
                evidence_refs=(),
            )

        by_id: dict[str, MigrationOperation] = {}
        for operation in operations:
            if not isinstance(operation, MigrationOperation):
                raise TypeError(
                    "operations must contain MigrationOperation"
                )
            migration_id = operation.step.migration_id
            if migration_id in by_id:
                raise ValueError("migration operations must have unique IDs")
            by_id[migration_id] = operation

        missing = tuple(
            step.migration_id
            for step in path
            if step.migration_id not in by_id
        )
        if missing:
            raise LookupError(
                "missing executable migration operations: "
                + ", ".join(missing)
            )

        moment = self._clock_now(now)
        lease = self.leases.acquire(
            owner_id=self.owner_id,
            now=moment,
            ttl=self.lease_ttl,
        )
        migration_ids: list[str] = []
        evidence_refs: list[str] = []
        primary_error: BaseException | None = None
        try:
            for group in self._group_transitions(path):
                transition_from = group[0].from_revision
                transition_to = group[0].to_revision
                step_time = self._clock_now(now)
                self._require_lease(lease, now=step_time)

                selected = tuple(
                    by_id[step.migration_id] for step in group
                )
                compatibility = selected[0].compatibility
                if any(
                    item.compatibility != compatibility
                    for item in selected
                ):
                    raise ValueError(
                        "all phases in one transition must agree on compatibility"
                    )

                db = sqlite3.connect(
                    self.state_path,
                    timeout=30,
                )
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA busy_timeout=30000")
                db.execute("PRAGMA foreign_keys=ON")
                try:
                    db.execute("BEGIN IMMEDIATE")
                    row = db.execute(
                        """
                        SELECT current_revision
                        FROM state_schema_component
                        WHERE component=?
                        """,
                        (component,),
                    ).fetchone()
                    if (
                        row is None
                        or int(row["current_revision"])
                        != transition_from
                    ):
                        raise RuntimeError(
                            "component schema changed before migration step"
                        )

                    for operation in selected:
                        operation.apply(db)
                        operation.validate(db)

                    applied_at = self._clock_now(now)
                    for operation in selected:
                        evidence_ref = (
                            f"{evidence_prefix}:"
                            f"{operation.step.migration_id}:"
                            f"fence-{lease.fencing_token}"
                        )
                        db.execute(
                            """
                            INSERT INTO state_schema_migration (
                                migration_id,component,from_revision,
                                to_revision,applied_at,evidence_ref
                            )
                            VALUES (?,?,?,?,?,?)
                            """,
                            (
                                operation.step.migration_id,
                                component,
                                transition_from,
                                transition_to,
                                applied_at.isoformat(),
                                evidence_ref,
                            ),
                        )
                        migration_ids.append(
                            operation.step.migration_id
                        )
                        evidence_refs.append(evidence_ref)

                    changed = db.execute(
                        """
                        UPDATE state_schema_component
                        SET current_revision=?,readable_min=?,
                            readable_max=?,writable_min=?,
                            writable_max=?,registered_at=?
                        WHERE component=? AND current_revision=?
                        """,
                        (
                            compatibility.current_revision,
                            compatibility.readable_min,
                            compatibility.readable_max,
                            compatibility.writable_min,
                            compatibility.writable_max,
                            applied_at.isoformat(),
                            component,
                            transition_from,
                        ),
                    )
                    if changed.rowcount != 1:
                        raise RuntimeError(
                            "component schema registry changed during migration"
                        )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                self.leases.release(
                    lease,
                    now=self._clock_now(now),
                )
            except MigrationLeaseLost:
                if primary_error is None:
                    raise

        final = self.schemas.current(component)
        if final is None or final.current_revision != target_revision:
            raise RuntimeError(
                "migration completed without expected schema revision"
            )
        return MigrationRunResult(
            component=component,
            from_revision=start_revision,
            to_revision=target_revision,
            migration_ids=tuple(migration_ids),
            evidence_refs=tuple(evidence_refs),
        )
