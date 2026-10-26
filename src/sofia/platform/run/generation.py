"""Durable generation fencing for independently hosted components."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.sdk import ComponentEndpoint, ComponentKind

from .lease import LocalRunLeaseStore, RunLease


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class GenerationState(str, Enum):
    STAGED = "staged"
    ACTIVE = "active"
    DRAINING = "draining"
    RETIRED = "retired"
    QUARANTINED = "quarantined"


class ComponentGenerationStore:
    """One active generation per component under the canonical RUN lease.

    This store fences state/IPC authority only.  It does not start, stop, kill,
    or prove the health of an OS process.
    """

    def __init__(self, *, state_path: Path, lease_store: LocalRunLeaseStore) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be Path")
        if not isinstance(lease_store, LocalRunLeaseStore):
            raise TypeError("lease_store must be LocalRunLeaseStore")
        if lease_store.path.resolve() != state_path.resolve():
            raise ValueError("generation store and RUN lease must share canonical state")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.lease_store = lease_store
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_component_generation(
                    component_id TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK(generation > 0),
                    kind TEXT NOT NULL,
                    release_digest TEXT NOT NULL,
                    platform_instance_id TEXT NOT NULL,
                    core_identity_id TEXT,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    lease_owner TEXT NOT NULL,
                    lease_epoch INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    PRIMARY KEY(component_id,generation)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS run_one_active_component_generation
                ON run_component_generation(component_id)
                WHERE state='active';
                CREATE UNIQUE INDEX IF NOT EXISTS run_one_active_core_identity
                ON run_component_generation(core_identity_id)
                WHERE state='active' AND core_identity_id IS NOT NULL;
                CREATE TABLE IF NOT EXISTS run_component_generation_event(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    previous_state TEXT,
                    next_state TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    lease_owner TEXT NOT NULL,
                    lease_epoch INTEGER NOT NULL,
                    reason TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _require_lease(self, lease: RunLease, now: datetime) -> datetime:
        moment = _utc(now)
        if not isinstance(lease, RunLease) or not self.lease_store.holds(
            lease, now=moment
        ):
            raise PermissionError("exact canonical RUN lease is not held")
        return moment

    @staticmethod
    def _event(
        db: sqlite3.Connection, endpoint: ComponentEndpoint,
        previous: GenerationState | None, next_state: GenerationState,
        lease: RunLease, now: datetime, reason: str,
    ) -> None:
        db.execute(
            """INSERT INTO run_component_generation_event(
            component_id,generation,previous_state,next_state,occurred_at,
            lease_owner,lease_epoch,reason) VALUES(?,?,?,?,?,?,?,?)""",
            (endpoint.component_id, endpoint.generation,
             None if previous is None else previous.value, next_state.value,
             now.isoformat(), lease.owner_id, lease.epoch, reason[:500]),
        )

    def stage(
        self, *, component_id: str, kind: ComponentKind, release_digest: str,
        platform_instance_id: str, core_identity_id: str | None,
        lease: RunLease, now: datetime, reason: str,
    ) -> ComponentEndpoint:
        moment = self._require_lease(lease, now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT COALESCE(MAX(generation),0) FROM run_component_generation "
                "WHERE component_id=?", (component_id,),
            ).fetchone()
            generation = int(row[0]) + 1
            endpoint = ComponentEndpoint(
                component_id, kind, release_digest, generation,
                platform_instance_id, core_identity_id,
            )
            db.execute(
                """INSERT INTO run_component_generation VALUES(
                ?,?,?,?,?,?,'staged',?,?,?,?,?)""",
                (endpoint.component_id, endpoint.generation, endpoint.kind.value,
                 endpoint.release_digest, endpoint.platform_instance_id,
                 endpoint.core_identity_id, moment.isoformat(), moment.isoformat(),
                 lease.owner_id, lease.epoch, reason[:500]),
            )
            self._event(
                db, endpoint, None, GenerationState.STAGED, lease, moment, reason,
            )
        return endpoint

    def _transition(
        self, endpoint: ComponentEndpoint, *, expected: GenerationState,
        target: GenerationState, lease: RunLease, now: datetime, reason: str,
    ) -> ComponentEndpoint:
        if not isinstance(endpoint, ComponentEndpoint):
            raise TypeError("endpoint must be ComponentEndpoint")
        moment = self._require_lease(lease, now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if target is GenerationState.ACTIVE:
                active = db.execute(
                    "SELECT generation FROM run_component_generation "
                    "WHERE component_id=? AND state='active'",
                    (endpoint.component_id,),
                ).fetchone()
                if active is not None:
                    raise RuntimeError("another component generation is already active")
                if endpoint.core_identity_id is not None:
                    identity_active = db.execute(
                        "SELECT component_id,generation FROM run_component_generation "
                        "WHERE core_identity_id=? AND state='active'",
                        (endpoint.core_identity_id,),
                    ).fetchone()
                    if identity_active is not None:
                        raise RuntimeError("Core identity already has an active generation")
            changed = db.execute(
                """UPDATE run_component_generation SET state=?,updated_at=?,
                lease_owner=?,lease_epoch=?,reason=?
                WHERE component_id=? AND generation=? AND kind=?
                AND release_digest=? AND platform_instance_id=?
                AND core_identity_id IS ? AND state=?""",
                (target.value, moment.isoformat(), lease.owner_id, lease.epoch,
                 reason[:500], endpoint.component_id, endpoint.generation,
                 endpoint.kind.value, endpoint.release_digest,
                 endpoint.platform_instance_id, endpoint.core_identity_id,
                 expected.value),
            )
            if changed.rowcount != 1:
                raise RuntimeError("component generation changed or identity mismatched")
            self._event(db, endpoint, expected, target, lease, moment, reason)
        return endpoint

    def activate(
        self, endpoint: ComponentEndpoint, *, lease: RunLease,
        now: datetime, reason: str,
    ) -> ComponentEndpoint:
        return self._transition(
            endpoint, expected=GenerationState.STAGED, target=GenerationState.ACTIVE,
            lease=lease, now=now, reason=reason,
        )

    def quarantine_staged(
        self, endpoint: ComponentEndpoint, *, lease: RunLease,
        now: datetime, reason: str,
    ) -> ComponentEndpoint:
        return self._transition(
            endpoint, expected=GenerationState.STAGED,
            target=GenerationState.QUARANTINED,
            lease=lease, now=now, reason=reason,
        )

    def begin_drain(
        self, endpoint: ComponentEndpoint, *, lease: RunLease,
        now: datetime, reason: str,
    ) -> ComponentEndpoint:
        return self._transition(
            endpoint, expected=GenerationState.ACTIVE, target=GenerationState.DRAINING,
            lease=lease, now=now, reason=reason,
        )

    def fence(
        self, endpoint: ComponentEndpoint, *, lease: RunLease,
        now: datetime, reason: str, quarantine: bool = False,
    ) -> ComponentEndpoint:
        return self._transition(
            endpoint, expected=GenerationState.DRAINING,
            target=(GenerationState.QUARANTINED if quarantine else GenerationState.RETIRED),
            lease=lease, now=now, reason=reason,
        )

    def is_active(self, endpoint: ComponentEndpoint) -> bool:
        if not isinstance(endpoint, ComponentEndpoint):
            return False
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT 1 FROM run_component_generation
                WHERE component_id=? AND generation=? AND kind=?
                AND release_digest=? AND platform_instance_id=?
                AND core_identity_id IS ? AND state='active'""",
                (endpoint.component_id, endpoint.generation, endpoint.kind.value,
                 endpoint.release_digest, endpoint.platform_instance_id,
                 endpoint.core_identity_id),
            ).fetchone()
        return row is not None

    def state(self, endpoint: ComponentEndpoint) -> GenerationState | None:
        if not isinstance(endpoint, ComponentEndpoint):
            raise TypeError("endpoint must be ComponentEndpoint")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT state FROM run_component_generation "
                "WHERE component_id=? AND generation=?",
                (endpoint.component_id, endpoint.generation),
            ).fetchone()
        return None if row is None else GenerationState(row[0])

    def active_for_core_identity(
        self, core_identity_id: str,
    ) -> ComponentEndpoint | None:
        if not isinstance(core_identity_id, str) or not core_identity_id.strip():
            raise ValueError("core_identity_id required")
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT component_id,kind,release_digest,generation,
                platform_instance_id,core_identity_id
                FROM run_component_generation
                WHERE core_identity_id=? AND state='active'""",
                (core_identity_id,),
            ).fetchone()
        if row is None:
            return None
        return ComponentEndpoint(
            row["component_id"], ComponentKind(row["kind"]),
            row["release_digest"], int(row["generation"]),
            row["platform_instance_id"], row["core_identity_id"],
        )

    def active_for_component(
        self, component_id: str,
    ) -> ComponentEndpoint | None:
        """Return the exact active endpoint, never a historical generation."""
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("component_id required")
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT component_id,kind,release_digest,generation,
                platform_instance_id,core_identity_id
                FROM run_component_generation
                WHERE component_id=? AND state='active'""",
                (component_id,),
            ).fetchone()
        if row is None:
            return None
        return ComponentEndpoint(
            row["component_id"], ComponentKind(row["kind"]),
            row["release_digest"], int(row["generation"]),
            row["platform_instance_id"], row["core_identity_id"],
        )
