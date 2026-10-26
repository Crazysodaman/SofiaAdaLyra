"""Application-owned supervision for independently managed components.

This is the component layer below the existing local runtime watchdog.  It
shares that watchdog's exact :class:`RunLease`; it is not another leader,
scheduler, or service manager.  A component backend remains responsible for
the actual process/container operation and can only be called while the
canonical local runtime lease is held.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
import re
import sqlite3
from typing import TYPE_CHECKING

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .lease import LocalRunLeaseStore, RunLease
from .supervisor import ManagedRuntimeBackend, ProcessState, RuntimeObservation

if TYPE_CHECKING:
    from .update_impact import ComponentUpdateCandidate, UpdateImpactPlan


_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class ComponentKind(str, Enum):
    CORE = "core"
    PLATFORM = "platform"
    OPTIONAL_MODULE = "optional_module"
    INFERENCE = "inference"


class DesiredComponentState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    QUARANTINED = "quarantined"


class ComponentHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    component_id: str
    kind: ComponentKind
    dependencies: tuple[str, ...] = ()
    enabled: bool = True
    failure_limit: int = 3
    heartbeat_timeout: timedelta = timedelta(minutes=2)

    def __post_init__(self) -> None:
        if not isinstance(self.component_id, str) or _ID.fullmatch(self.component_id) is None:
            raise ValueError("component_id must be a bounded lowercase identifier")
        if not isinstance(self.kind, ComponentKind):
            raise TypeError("kind must be ComponentKind")
        if type(self.dependencies) is not tuple or any(
            not isinstance(item, str) or _ID.fullmatch(item) is None
            for item in self.dependencies
        ):
            raise ValueError("dependencies must be bounded component identifiers")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must be unique")
        if self.component_id in self.dependencies:
            raise ValueError("component cannot depend on itself")
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be bool")
        if type(self.failure_limit) is not int or not 1 <= self.failure_limit <= 20:
            raise ValueError("failure_limit must be in 1..20")
        if not isinstance(self.heartbeat_timeout, timedelta) or not (
            timedelta(seconds=5) <= self.heartbeat_timeout <= timedelta(hours=1)
        ):
            raise ValueError("heartbeat_timeout must be in 5 seconds..1 hour")


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    component_id: str
    kind: ComponentKind
    desired: DesiredComponentState
    observed: ProcessState
    health: ComponentHealth
    failure_count: int
    last_heartbeat_at: datetime | None
    reason: str


@dataclass(frozen=True, slots=True)
class ComponentAction:
    component_id: str
    action: str
    status: ComponentStatus


class ComponentRuntimeSupervisor:
    """Durable component lifecycle subordinate to the canonical RUN lease."""

    def __init__(self, *, state_path: Path, lease_store: LocalRunLeaseStore) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be Path")
        if not isinstance(lease_store, LocalRunLeaseStore):
            raise TypeError("lease_store must be LocalRunLeaseStore")
        self._guard = CanonicalSQLiteGuard(state_path)
        if lease_store.path.resolve() != state_path.resolve():
            raise ValueError("component supervisor and RUN lease must share canonical state")
        self.lease_store = lease_store
        self._backends: dict[str, ManagedRuntimeBackend] = {}
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_component (
                    component_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    dependencies_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                    failure_limit INTEGER NOT NULL,
                    heartbeat_timeout_seconds INTEGER NOT NULL,
                    desired_state TEXT NOT NULL,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_heartbeat_at TEXT,
                    last_reason TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_component_event (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    lease_owner TEXT NOT NULL,
                    lease_epoch INTEGER NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _dependencies_json(spec: ComponentSpec) -> str:
        import json
        return json.dumps(spec.dependencies, separators=(",", ":"))

    def register(self, spec: ComponentSpec, backend: ManagedRuntimeBackend, *, now: datetime) -> None:
        if not isinstance(spec, ComponentSpec):
            raise TypeError("spec must be ComponentSpec")
        if not isinstance(backend, ManagedRuntimeBackend):
            raise TypeError("backend must be ManagedRuntimeBackend")
        moment = _utc(now)
        encoded = self._dependencies_json(spec)
        desired = DesiredComponentState.RUNNING if spec.enabled else DesiredComponentState.STOPPED
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            known = {
                item[0]
                for item in db.execute("SELECT component_id FROM run_component")
            }
            missing = [item for item in spec.dependencies if item not in known]
            if missing:
                raise RuntimeError(
                    f"component {spec.component_id} has unregistered dependencies: {missing}"
                )
            row = db.execute("SELECT * FROM run_component WHERE component_id=?", (spec.component_id,)).fetchone()
            if row is None:
                db.execute(
                    """INSERT INTO run_component VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (spec.component_id, spec.kind.value, encoded, int(spec.enabled),
                     spec.failure_limit, int(spec.heartbeat_timeout.total_seconds()),
                     desired.value, 0, None, "registered", moment.isoformat()),
                )
            elif (
                row["kind"] != spec.kind.value
                or row["dependencies_json"] != encoded
                or int(row["failure_limit"]) != spec.failure_limit
                or int(row["heartbeat_timeout_seconds"]) != int(spec.heartbeat_timeout.total_seconds())
            ):
                raise RuntimeError("component specification changed; reviewed migration required")
        self._backends[spec.component_id] = backend
        self._validate_graph()

    def _validate_graph(self) -> None:
        import json
        with closing(self._connect()) as db:
            rows = db.execute("SELECT component_id,dependencies_json FROM run_component").fetchall()
        graph = {row["component_id"]: tuple(json.loads(row["dependencies_json"])) for row in rows}
        for node, dependencies in graph.items():
            missing = [item for item in dependencies if item not in graph]
            if missing:
                raise RuntimeError(f"component {node} has unregistered dependencies: {missing}")
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(node: str) -> None:
            if node in visiting:
                raise RuntimeError("component dependency cycle detected")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)
        for node in sorted(graph):
            visit(node)

    def _require_lease(self, lease: RunLease, now: datetime) -> None:
        if not isinstance(lease, RunLease):
            raise TypeError("RunLease required")
        if not self.lease_store.holds(lease, now=_utc(now)):
            raise PermissionError("exact canonical RUN lease is not held")

    def _backend(self, component_id: str) -> ManagedRuntimeBackend:
        try:
            return self._backends[component_id]
        except KeyError as exc:
            raise LookupError("component backend is not registered in this runtime") from exc

    @staticmethod
    def _health(observation: RuntimeObservation, heartbeat: datetime | None, timeout: int, now: datetime) -> ComponentHealth:
        if observation.state is ProcessState.UNKNOWN:
            return ComponentHealth.UNKNOWN
        if observation.state is ProcessState.FAILED:
            return ComponentHealth.FAILED
        if observation.state is ProcessState.STOPPED:
            return ComponentHealth.UNREACHABLE
        if not observation.ready:
            return ComponentHealth.DEGRADED
        if heartbeat is not None and now - heartbeat > timedelta(seconds=timeout):
            return ComponentHealth.DEGRADED
        return ComponentHealth.HEALTHY

    def read_health(self, component_id: str, *, now: datetime) -> ComponentStatus:
        moment = _utc(now)
        backend = self._backend(component_id)
        observation = backend.observe()
        if not isinstance(observation, RuntimeObservation):
            raise TypeError("backend.observe must return RuntimeObservation")
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM run_component WHERE component_id=?", (component_id,)).fetchone()
        if row is None:
            raise LookupError("unknown component")
        heartbeat = None if row["last_heartbeat_at"] is None else datetime.fromisoformat(row["last_heartbeat_at"]).astimezone(timezone.utc)
        return ComponentStatus(
            component_id=component_id,
            kind=ComponentKind(row["kind"]),
            desired=DesiredComponentState(row["desired_state"]),
            observed=observation.state,
            health=self._health(observation, heartbeat, int(row["heartbeat_timeout_seconds"]), moment),
            failure_count=int(row["failure_count"]),
            last_heartbeat_at=heartbeat,
            reason=row["last_reason"],
        )

    def status(self, *, now: datetime) -> tuple[ComponentStatus, ...]:
        with closing(self._connect()) as db:
            ids = [row[0] for row in db.execute("SELECT component_id FROM run_component ORDER BY component_id")]
        return tuple(self.read_health(component_id, now=now) for component_id in ids)

    def plan_update(
        self, candidate: "ComponentUpdateCandidate",
    ) -> "UpdateImpactPlan":
        """Plan update impact from the durable registered component graph.

        Importing lazily avoids making the supervisor lifecycle depend on the
        release planner.  The returned plan is inert and carries no authority.
        """
        import json
        from .update_impact import ComponentUpdateCandidate, plan_component_update
        if not isinstance(candidate, ComponentUpdateCandidate):
            raise TypeError("candidate must be ComponentUpdateCandidate")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT component_id,kind,dependencies_json FROM run_component"
            ).fetchall()
            try:
                active_rows = db.execute(
                    """SELECT component_id,release_digest
                    FROM run_component_generation WHERE state='active'"""
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc):
                    raise
                active_rows = ()
        registered = {row["component_id"] for row in rows}
        return plan_component_update(
            candidate,
            component_kinds={
                row["component_id"]: ComponentKind(row["kind"]) for row in rows
            },
            dependencies={
                row["component_id"]: tuple(json.loads(row["dependencies_json"]))
                for row in rows
            },
            active_release_digests={
                row["component_id"]: row["release_digest"]
                for row in active_rows if row["component_id"] in registered
            },
        )

    def heartbeat(self, component_id: str, *, lease: RunLease, now: datetime) -> None:
        moment = _utc(now)
        self._require_lease(lease, moment)
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE run_component
                SET last_heartbeat_at=?,failure_count=0,last_reason='heartbeat',updated_at=?
                WHERE component_id=?""",
                (moment.isoformat(), moment.isoformat(), component_id),
            )
            if changed.rowcount != 1:
                raise LookupError("unknown component")

    def _event(self, db: sqlite3.Connection, component_id: str, event: str, reason: str, lease: RunLease, now: datetime) -> None:
        db.execute(
            "INSERT INTO run_component_event(component_id,event_type,reason,occurred_at,lease_owner,lease_epoch) VALUES(?,?,?,?,?,?)",
            (component_id, event, reason[:500], now.isoformat(), lease.owner_id, lease.epoch),
        )

    def _set_desired(self, component_id: str, desired: DesiredComponentState, *, lease: RunLease, now: datetime, reason: str) -> None:
        moment = _utc(now)
        self._require_lease(lease, moment)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE run_component SET desired_state=?,last_reason=?,updated_at=? WHERE component_id=?",
                (desired.value, reason[:500], moment.isoformat(), component_id),
            )
            if changed.rowcount != 1:
                raise LookupError("unknown component")
            self._event(db, component_id, desired.value, reason, lease, moment)

    def pause(self, component_id: str, *, lease: RunLease, now: datetime, reason: str) -> ComponentAction:
        backend = self._backend(component_id)
        self._require_lease(lease, now)
        # Persist the safe desired state before asking an external backend to
        # stop. A crash or backend exception must not make startup resurrect a
        # component the operator intended to pause.
        self._set_desired(component_id, DesiredComponentState.PAUSED, lease=lease, now=now, reason=reason)
        if backend.observe().state in (ProcessState.RUNNING, ProcessState.STARTING):
            backend.stop()
        return ComponentAction(component_id, "paused", self.read_health(component_id, now=now))

    def resume(self, component_id: str, *, lease: RunLease, now: datetime, reason: str) -> ComponentAction:
        self._set_desired(component_id, DesiredComponentState.RUNNING, lease=lease, now=now, reason=reason)
        return self.start_component(component_id, lease=lease, now=now)

    def stop_component(self, component_id: str, *, lease: RunLease, now: datetime, reason: str) -> ComponentAction:
        self._require_lease(lease, now)
        backend = self._backend(component_id)
        self._set_desired(component_id, DesiredComponentState.STOPPED, lease=lease, now=now, reason=reason)
        if backend.observe().state in (ProcessState.RUNNING, ProcessState.STARTING):
            backend.stop()
        return ComponentAction(component_id, "stopped", self.read_health(component_id, now=now))

    def start_component(self, component_id: str, *, lease: RunLease, now: datetime) -> ComponentAction:
        moment = _utc(now)
        self._require_lease(lease, moment)
        status = self.read_health(component_id, now=moment)
        if status.desired in (DesiredComponentState.PAUSED, DesiredComponentState.QUARANTINED):
            return ComponentAction(component_id, "blocked_" + status.desired.value, status)
        import json
        with closing(self._connect()) as db:
            row = db.execute("SELECT dependencies_json,enabled FROM run_component WHERE component_id=?", (component_id,)).fetchone()
        if not bool(row["enabled"]):
            return ComponentAction(component_id, "disabled", status)
        for dependency in json.loads(row["dependencies_json"]):
            dependency_status = self.read_health(dependency, now=moment)
            if dependency_status.health is not ComponentHealth.HEALTHY:
                return ComponentAction(component_id, "dependency_unhealthy", status)
        if status.observed is ProcessState.RUNNING and status.health is ComponentHealth.HEALTHY:
            if status.failure_count:
                with closing(self._connect()) as db, db:
                    db.execute(
                        """UPDATE run_component SET failure_count=0,
                        last_reason='healthy',updated_at=? WHERE component_id=?""",
                        (moment.isoformat(), component_id),
                    )
            return ComponentAction(component_id, "already_healthy", status)
        if status.observed is ProcessState.FAILED:
            quarantined = False
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT failure_count,failure_limit FROM run_component WHERE component_id=?",
                    (component_id,),
                ).fetchone()
                failures = int(row["failure_count"]) + 1
                if failures >= int(row["failure_limit"]):
                    db.execute(
                        """UPDATE run_component SET failure_count=?,
                        desired_state='quarantined',last_reason='crash_loop',updated_at=?
                        WHERE component_id=?""",
                        (failures, moment.isoformat(), component_id),
                    )
                    self._event(
                        db, component_id, "quarantined", "crash loop", lease, moment,
                    )
                    quarantined = True
                else:
                    db.execute(
                        """UPDATE run_component SET failure_count=?,
                        last_reason='observed_failed',updated_at=? WHERE component_id=?""",
                        (failures, moment.isoformat(), component_id),
                    )
                    self._event(
                        db, component_id, "crash_observed", "backend reported failed",
                        lease, moment,
                    )
            if quarantined:
                return ComponentAction(
                    component_id, "quarantined",
                    self.read_health(component_id, now=moment),
                )
        backend = self._backend(component_id)
        try:
            backend.start(epoch=lease.epoch)
        except Exception as exc:
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT failure_count,failure_limit FROM run_component WHERE component_id=?", (component_id,)).fetchone()
                failures = int(row["failure_count"]) + 1
                desired = DesiredComponentState.QUARANTINED if failures >= int(row["failure_limit"]) else DesiredComponentState.RUNNING
                db.execute(
                    "UPDATE run_component SET failure_count=?,desired_state=?,last_reason=?,updated_at=? WHERE component_id=?",
                    (failures, desired.value, f"start_failed:{type(exc).__name__}", moment.isoformat(), component_id),
                )
                self._event(db, component_id, "start_failed", type(exc).__name__, lease, moment)
            action = "quarantined" if desired is DesiredComponentState.QUARANTINED else "start_failed"
            return ComponentAction(component_id, action, self.read_health(component_id, now=moment))
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE run_component SET desired_state='running',last_reason='start_requested',updated_at=? WHERE component_id=?",
                (moment.isoformat(), component_id),
            )
            self._event(db, component_id, "start_requested", "dependency checks passed", lease, moment)
        return ComponentAction(component_id, "started", self.read_health(component_id, now=moment))

    def reconcile_startup(self, *, lease: RunLease, now: datetime) -> tuple[ComponentAction, ...]:
        moment = _utc(now)
        self._require_lease(lease, moment)
        self._validate_graph()
        import json
        with closing(self._connect()) as db:
            rows = db.execute("SELECT component_id,dependencies_json FROM run_component").fetchall()
        graph = {row["component_id"]: tuple(json.loads(row["dependencies_json"])) for row in rows}
        ordered: list[str] = []
        seen: set[str] = set()
        def add(node: str) -> None:
            if node in seen:
                return
            for dependency in graph[node]:
                add(dependency)
            seen.add(node)
            ordered.append(node)
        for node in sorted(graph):
            add(node)
        return tuple(self.start_component(node, lease=lease, now=moment) for node in ordered)
