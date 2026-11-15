"""Governed lifecycle for signed, synthetic Core components.

This module owns *synthetic* Core lifecycle evidence only. Signature,
content and physical installation remain the responsibility of the existing
:class:`~sofia.platform.ops.component_install.CoreComponentInstaller` and
:class:`~sofia.platform.ops.component_install.CoreComponentRegistry`; there is
deliberately no second verifier here.

Process start/stop is delegated to an injected backend. Tests use a fake
backend and no real Sofía Core, personal state, memory migration or production
credential is ever launched by this module.

Every consequential operation requires a caller-supplied authorization
callback for the exact operation, artifact fingerprint and expected generation,
plus a current freshness check. These callbacks are interfaces only: this
module does not establish authority.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
import sqlite3
from pathlib import Path
from typing import Callable, Iterator, Protocol
from uuid import UUID, uuid4

from sofia.platform.ops.component_install import (
    CORE_DISTRIBUTION,
    CoreComponentArtifact,
    CoreComponentInstallError,
    CoreComponentInstaller,
    CoreComponentReceipt,
)
from sofia.platform.ops.platform_install import InstallAuthority, InstallOutcome

_UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}")


class SyntheticCoreLifecycleError(RuntimeError):
    """A synthetic Core lifecycle contract was violated."""


class SyntheticCoreLifecycleConflict(SyntheticCoreLifecycleError):
    """A stale, duplicate or invalid lifecycle transition was refused."""


class SyntheticCorePendingReconciliation(SyntheticCoreLifecycleError):
    """An earlier process operation still requires truthful reconciliation."""


class SyntheticCoreBackendUncertain(SyntheticCoreLifecycleError):
    """The process backend could not establish whether an operation happened."""


class SyntheticCoreState(str, Enum):
    INSTALLED = "installed"
    ACTIVE = "active"
    STOPPED = "stopped"
    DETACHED = "detached"
    REMOVED = "removed"


class SyntheticCoreOperation(str, Enum):
    INSTALL = "install"
    START = "start"
    STOP = "stop"
    DETACH = "detach"
    REMOVE = "remove"


class SyntheticCoreOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    ALREADY_STOPPED = "ALREADY_STOPPED"
    ALREADY_DETACHED = "ALREADY_DETACHED"
    ALREADY_REMOVED = "ALREADY_REMOVED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class CoreProcessObservation(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class SyntheticCoreProcessBackend(Protocol):
    """Narrow process boundary; no shell, argv or credential is exposed."""

    def start(self, *, core_id: str, lineage_id: str, generation: int) -> CoreProcessObservation:
        ...

    def stop(self, *, core_id: str, lineage_id: str, generation: int) -> CoreProcessObservation:
        ...

    def observe(self, *, core_id: str, lineage_id: str, generation: int) -> CoreProcessObservation:
        ...


SyntheticCoreAuthorizer = Callable[[str, str, int], bool]
SyntheticCoreFreshness = Callable[[], bool]
SyntheticCorePlatformHealth = Callable[[], bool]


def _canonical_uuid(value: object, label: str) -> str:
    if not isinstance(value, str) or _UUID_TEXT.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase canonical UUID")
    parsed = UUID(value)
    if parsed.int == 0 or str(parsed) != value:
        raise ValueError(f"{label} must be a lowercase canonical UUID")
    return value


def _owner(value: object) -> str:
    if not isinstance(value, str) or _OWNER.fullmatch(value) is None:
        raise ValueError("owner_id must be a bounded canonical identifier")
    return value


def _generation(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _aware(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("lifecycle time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _observation(value: object) -> CoreProcessObservation:
    if isinstance(value, CoreProcessObservation):
        return value
    try:
        return CoreProcessObservation(str(value).lower())
    except (TypeError, ValueError):
        return CoreProcessObservation.UNKNOWN


@dataclass(frozen=True, slots=True)
class SyntheticCoreBinding:
    """Durable, owner-scoped identity evidence for one synthetic Core."""

    owner_id: str
    core_id: str
    lineage_id: str
    generation: int
    state: SyntheticCoreState
    artifact_sha256: str
    version: str
    installed_at: datetime
    updated_at: datetime
    last_operation: SyntheticCoreOperation | None = None
    last_outcome: SyntheticCoreOutcome | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        _owner(self.owner_id)
        _canonical_uuid(self.core_id, "core_id")
        _canonical_uuid(self.lineage_id, "lineage_id")
        _generation(self.generation, "generation")
        if not isinstance(self.state, SyntheticCoreState):
            raise TypeError("binding state must be a SyntheticCoreState")
        if not isinstance(self.artifact_sha256, str) or _SHA256.fullmatch(self.artifact_sha256) is None:
            raise ValueError("binding requires a lowercase artifact SHA-256")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("binding version is required")
        _aware(self.installed_at)
        _aware(self.updated_at)


@dataclass(frozen=True, slots=True)
class SyntheticCorePendingOperation:
    operation_id: str
    owner_id: str
    core_id: str
    lineage_id: str
    operation: SyntheticCoreOperation
    generation: int
    expected_generation: int
    artifact_sha256: str
    started_at: datetime
    observed: str
    detail: str


@dataclass(frozen=True, slots=True)
class SyntheticCoreLifecycleReceipt:
    operation: SyntheticCoreOperation
    outcome: SyntheticCoreOutcome
    owner_id: str
    core_id: str
    lineage_id: str
    generation: int
    state: SyntheticCoreState
    artifact_sha256: str
    happened_at: datetime
    detail: str = ""
    platform_healthy: bool | None = None
    install_receipt: CoreComponentReceipt | None = None


class SyntheticCoreLifecycleStore:
    """Platform-owned SQLite evidence; never canonical Core state."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if self.path.name == "sofia.db":
            raise ValueError("synthetic Core lifecycle must not use canonical state")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS ops_synthetic_core_binding (
                    owner_id TEXT NOT NULL,
                    core_id TEXT NOT NULL UNIQUE,
                    lineage_id TEXT NOT NULL UNIQUE,
                    generation INTEGER NOT NULL CHECK(generation>=0),
                    state TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    version TEXT NOT NULL,
                    installed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_operation TEXT,
                    last_outcome TEXT,
                    detail TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(owner_id, core_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS ops_synthetic_core_active_lineage
                ON ops_synthetic_core_binding(lineage_id)
                WHERE state='active';
                CREATE UNIQUE INDEX IF NOT EXISTS ops_synthetic_core_live_artifact
                ON ops_synthetic_core_binding(owner_id, artifact_sha256)
                WHERE state!='removed';
                CREATE TABLE IF NOT EXISTS ops_synthetic_core_operation (
                    operation_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    core_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    expected_generation INTEGER NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    observed TEXT NOT NULL DEFAULT '',
                    outcome TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    detail TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS ops_synthetic_core_one_unresolved
                ON ops_synthetic_core_operation(core_id)
                WHERE outcome IS NULL;
                CREATE TABLE IF NOT EXISTS ops_synthetic_core_event (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    owner_id TEXT NOT NULL,
                    core_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    state_before TEXT,
                    state_after TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS ops_synthetic_core_event_identity
                ON ops_synthetic_core_event(owner_id, core_id, sequence);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _binding(row: sqlite3.Row) -> SyntheticCoreBinding:
        return SyntheticCoreBinding(
            owner_id=row["owner_id"],
            core_id=row["core_id"],
            lineage_id=row["lineage_id"],
            generation=int(row["generation"]),
            state=SyntheticCoreState(row["state"]),
            artifact_sha256=row["artifact_sha256"],
            version=row["version"],
            installed_at=datetime.fromisoformat(row["installed_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_operation=(
                None if row["last_operation"] is None
                else SyntheticCoreOperation(row["last_operation"])
            ),
            last_outcome=(
                None if row["last_outcome"] is None
                else SyntheticCoreOutcome(row["last_outcome"])
            ),
            detail=row["detail"],
        )

    @staticmethod
    def _operation(row: sqlite3.Row) -> SyntheticCorePendingOperation:
        return SyntheticCorePendingOperation(
            operation_id=row["operation_id"],
            owner_id=row["owner_id"],
            core_id=row["core_id"],
            lineage_id=row["lineage_id"],
            operation=SyntheticCoreOperation(row["operation"]),
            generation=int(row["generation"]),
            expected_generation=int(row["expected_generation"]),
            artifact_sha256=row["artifact_sha256"],
            started_at=datetime.fromisoformat(row["started_at"]),
            observed=row["observed"],
            detail=row["detail"],
        )

    def binding(self, owner_id: str, core_id: str) -> SyntheticCoreBinding | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM ops_synthetic_core_binding "
                "WHERE owner_id=? AND core_id=?",
                (_owner(owner_id), _canonical_uuid(core_id, "core_id")),
            ).fetchone()
        return None if row is None else self._binding(row)

    def bindings(self, owner_id: str) -> tuple[SyntheticCoreBinding, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM ops_synthetic_core_binding "
                "WHERE owner_id=? ORDER BY core_id",
                (_owner(owner_id),),
            ).fetchall()
        return tuple(self._binding(row) for row in rows)

    def live_artifact(self, owner_id: str, artifact_sha256: str) -> SyntheticCoreBinding | None:
        if _SHA256.fullmatch(artifact_sha256) is None:
            raise ValueError("artifact_sha256 must be lowercase SHA-256")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM ops_synthetic_core_binding "
                "WHERE owner_id=? AND artifact_sha256=? AND state!='removed'",
                (_owner(owner_id), artifact_sha256),
            ).fetchone()
        return None if row is None else self._binding(row)

    def active_lineage(self, lineage_id: str) -> SyntheticCoreBinding | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM ops_synthetic_core_binding "
                "WHERE lineage_id=? AND state='active'",
                (_canonical_uuid(lineage_id, "lineage_id"),),
            ).fetchone()
        return None if row is None else self._binding(row)

    def unresolved_operations(
        self, core_id: str | None = None,
    ) -> tuple[SyntheticCorePendingOperation, ...]:
        with closing(self._connect()) as db:
            if core_id is None:
                rows = db.execute(
                    "SELECT * FROM ops_synthetic_core_operation "
                    "WHERE outcome IS NULL ORDER BY started_at, operation_id"
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM ops_synthetic_core_operation "
                    "WHERE core_id=? AND outcome IS NULL "
                    "ORDER BY started_at, operation_id",
                    (_canonical_uuid(core_id, "core_id"),),
                ).fetchall()
        return tuple(self._operation(row) for row in rows)

    def operations(
        self, owner_id: str, core_id: str,
    ) -> tuple[dict[str, object], ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM ops_synthetic_core_operation "
                "WHERE owner_id=? AND core_id=? ORDER BY started_at, operation_id",
                (_owner(owner_id), _canonical_uuid(core_id, "core_id")),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def events(
        self, owner_id: str, core_id: str,
    ) -> tuple[dict[str, object], ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM ops_synthetic_core_event "
                "WHERE owner_id=? AND core_id=? ORDER BY sequence",
                (_owner(owner_id), _canonical_uuid(core_id, "core_id")),
            ).fetchall()
        return tuple(dict(row) for row in rows)


class SyntheticCoreLifecycle:
    """One-writer, owner-scoped lifecycle for signed synthetic Cores."""

    def __init__(
        self,
        *,
        store_path: Path | str,
        platform_id: str,
        installer: CoreComponentInstaller,
        backend: SyntheticCoreProcessBackend,
        authorization: SyntheticCoreAuthorizer,
        freshness: SyntheticCoreFreshness,
        platform_health_check: SyntheticCorePlatformHealth,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(installer, CoreComponentInstaller):
            raise TypeError("installer must be a CoreComponentInstaller")
        for method in ("start", "stop", "observe"):
            if not callable(getattr(backend, method, None)):
                raise TypeError("backend must implement synthetic Core process control")
        if not callable(authorization):
            raise TypeError("authorization callback must be callable")
        if not callable(freshness):
            raise TypeError("freshness callback must be callable")
        if not callable(platform_health_check):
            raise TypeError("platform health callback must be callable")
        self.platform_id = _canonical_uuid(platform_id, "platform_id")
        self.installer = installer
        self.backend = backend
        self.store = SyntheticCoreLifecycleStore(store_path)
        self._authorization = authorization
        self._freshness = freshness
        self._platform_health = platform_health_check
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.reconcile()

    def _now(self) -> datetime:
        return _aware(self._clock())

    def _authorize(
        self,
        operation: SyntheticCoreOperation,
        fingerprint: str,
        expected_generation: int,
    ) -> None:
        if self._freshness() is not True:
            raise PermissionError("synthetic Core lifecycle authorization is stale")
        if self._authorization(
            operation.value, fingerprint, expected_generation
        ) is not True:
            raise PermissionError(
                f"synthetic Core {operation.value} authorization denied"
            )

    def _platform_is_healthy(self) -> bool:
        try:
            return self._platform_health() is True
        except Exception:
            return False

    @staticmethod
    def _require_binding(
        binding: SyntheticCoreBinding | None,
        owner_id: str,
        core_id: str,
    ) -> SyntheticCoreBinding:
        if binding is None:
            raise PermissionError("synthetic Core is not bound to this owner")
        return binding

    def _require_no_pending(self, core_id: str) -> None:
        if self.store.unresolved_operations(core_id):
            raise SyntheticCorePendingReconciliation(
                "previous synthetic Core process operation requires reconciliation"
            )

    @staticmethod
    def _append_event(
        db: sqlite3.Connection,
        *,
        owner_id: str,
        core_id: str,
        lineage_id: str,
        operation: SyntheticCoreOperation,
        generation: int,
        state_before: SyntheticCoreState | None,
        state_after: SyntheticCoreState,
        outcome: SyntheticCoreOutcome,
        artifact_sha256: str,
        occurred_at: datetime,
        detail: str,
    ) -> None:
        db.execute(
            "INSERT INTO ops_synthetic_core_event("
            "event_id,owner_id,core_id,lineage_id,operation,generation,"
            "state_before,state_after,outcome,artifact_sha256,occurred_at,detail"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"synthetic-core-event-{uuid4().hex}",
                owner_id,
                core_id,
                lineage_id,
                operation.value,
                generation,
                None if state_before is None else state_before.value,
                state_after.value,
                outcome.value,
                artifact_sha256,
                occurred_at.isoformat(),
                detail[:2000],
            ),
        )

    @staticmethod
    def _write_binding(db: sqlite3.Connection, binding: SyntheticCoreBinding) -> None:
        db.execute(
            "UPDATE ops_synthetic_core_binding SET "
            "generation=?,state=?,version=?,updated_at=?,last_operation=?,"
            "last_outcome=?,detail=? WHERE owner_id=? AND core_id=?",
            (
                binding.generation,
                binding.state.value,
                binding.version,
                binding.updated_at.isoformat(),
                None if binding.last_operation is None else binding.last_operation.value,
                None if binding.last_outcome is None else binding.last_outcome.value,
                binding.detail[:2000],
                binding.owner_id,
                binding.core_id,
            ),
        )

    def _begin_pending(
        self,
        *,
        binding: SyntheticCoreBinding,
        operation: SyntheticCoreOperation,
        generation: int,
        expected_generation: int,
        at: datetime,
    ) -> SyntheticCorePendingOperation:
        operation_id = f"synthetic-core-op-{uuid4().hex}"
        try:
            with self.store.transaction() as db:
                db.execute(
                    "INSERT INTO ops_synthetic_core_operation("
                    "operation_id,owner_id,core_id,lineage_id,operation,"
                    "generation,expected_generation,artifact_sha256,started_at"
                    ") VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        operation_id,
                        binding.owner_id,
                        binding.core_id,
                        binding.lineage_id,
                        operation.value,
                        generation,
                        expected_generation,
                        binding.artifact_sha256,
                        at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise SyntheticCorePendingReconciliation(
                "previous synthetic Core process operation requires reconciliation"
            ) from exc
        return SyntheticCorePendingOperation(
            operation_id=operation_id,
            owner_id=binding.owner_id,
            core_id=binding.core_id,
            lineage_id=binding.lineage_id,
            operation=operation,
            generation=generation,
            expected_generation=expected_generation,
            artifact_sha256=binding.artifact_sha256,
            started_at=at,
            observed="",
            detail="",
        )

    @staticmethod
    def _resolve_pending(
        db: sqlite3.Connection,
        pending: SyntheticCorePendingOperation,
        *,
        outcome: SyntheticCoreOutcome,
        observed: CoreProcessObservation,
        at: datetime,
        detail: str,
    ) -> None:
        changed = db.execute(
            "UPDATE ops_synthetic_core_operation SET outcome=?,observed=?,"
            "completed_at=?,detail=? WHERE operation_id=? AND outcome IS NULL",
            (
                outcome.value,
                observed.value,
                at.isoformat(),
                detail[:2000],
                pending.operation_id,
            ),
        )
        if changed.rowcount != 1:
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core process operation was already resolved"
            )

    def reconcile(self) -> tuple[SyntheticCoreLifecycleReceipt, ...]:
        """Finish crashed PENDING operations using observation, never retry."""
        receipts: list[SyntheticCoreLifecycleReceipt] = []
        for pending in self.store.unresolved_operations():
            try:
                observed = _observation(
                    self.backend.observe(
                        core_id=pending.core_id,
                        lineage_id=pending.lineage_id,
                        generation=pending.generation,
                    )
                )
            except Exception as exc:  # backend unavailability is an observation
                self._record_unknown(pending, f"observation failed: {type(exc).__name__}")
                continue
            if observed is CoreProcessObservation.UNKNOWN:
                self._record_unknown(pending, "process state remains unknown")
                continue
            with self.store.transaction() as db:
                row = db.execute(
                    "SELECT * FROM ops_synthetic_core_binding WHERE core_id=?",
                    (pending.core_id,),
                ).fetchone()
                if row is None:
                    raise SyntheticCoreLifecycleConflict(
                        "pending operation has no bound synthetic Core identity"
                    )
                binding = self.store._binding(row)
                before, after = binding.state, binding.state
                generation = binding.generation
                outcome = SyntheticCoreOutcome.FAILED
                if pending.operation is SyntheticCoreOperation.START:
                    if observed is CoreProcessObservation.RUNNING:
                        after = SyntheticCoreState.ACTIVE
                        generation = pending.generation
                        outcome = SyntheticCoreOutcome.SUCCEEDED
                    elif before is SyntheticCoreState.ACTIVE:
                        after = SyntheticCoreState.STOPPED
                elif pending.operation is SyntheticCoreOperation.STOP:
                    if observed is CoreProcessObservation.STOPPED:
                        after = SyntheticCoreState.STOPPED
                        outcome = SyntheticCoreOutcome.SUCCEEDED
                    else:
                        after = SyntheticCoreState.ACTIVE
                else:
                    raise SyntheticCoreLifecycleConflict(
                        "only process start/stop may remain pending"
                    )
                at = self._now()
                reconciled = SyntheticCoreBinding(
                    owner_id=binding.owner_id,
                    core_id=binding.core_id,
                    lineage_id=binding.lineage_id,
                    generation=generation,
                    state=after,
                    artifact_sha256=binding.artifact_sha256,
                    version=binding.version,
                    installed_at=binding.installed_at,
                    updated_at=at,
                    last_operation=pending.operation,
                    last_outcome=outcome,
                    detail=f"reconciled {pending.operation.value}: observed {observed.value}",
                )
                self._write_binding(db, reconciled)
                self._resolve_pending(
                    db, pending, outcome=outcome, observed=observed, at=at,
                    detail=reconciled.detail,
                )
                self._append_event(
                    db,
                    owner_id=reconciled.owner_id,
                    core_id=reconciled.core_id,
                    lineage_id=reconciled.lineage_id,
                    operation=pending.operation,
                    generation=reconciled.generation,
                    state_before=before,
                    state_after=after,
                    outcome=outcome,
                    artifact_sha256=reconciled.artifact_sha256,
                    occurred_at=at,
                    detail=reconciled.detail,
                )
            receipts.append(
                SyntheticCoreLifecycleReceipt(
                    operation=pending.operation,
                    outcome=outcome,
                    owner_id=reconciled.owner_id,
                    core_id=reconciled.core_id,
                    lineage_id=reconciled.lineage_id,
                    generation=reconciled.generation,
                    state=reconciled.state,
                    artifact_sha256=reconciled.artifact_sha256,
                    happened_at=at,
                    detail=reconciled.detail,
                )
            )
        return tuple(receipts)

    def _record_unknown(
        self, pending: SyntheticCorePendingOperation, detail: str
    ) -> None:
        with self.store.transaction() as db:
            changed = db.execute(
                "UPDATE ops_synthetic_core_operation SET observed='unknown',detail=? "
                "WHERE operation_id=? AND outcome IS NULL",
                (detail[:2000], pending.operation_id),
            )
            if changed.rowcount != 1:
                raise SyntheticCoreLifecycleConflict(
                    "synthetic Core process operation was already resolved"
                )

    def install(
        self,
        *,
        owner_id: str,
        core_id: str,
        lineage_id: str,
        artifact: CoreComponentArtifact,
        wheel_path: Path,
        authority: InstallAuthority,
        approval_id: str | None = None,
        expected_generation: int = 0,
        synthetic: bool = True,
    ) -> SyntheticCoreLifecycleReceipt:
        """Install signed synthetic Core bytes through the existing installer."""
        if synthetic is not True:
            raise PermissionError("this lifecycle accepts synthetic Cores only")
        if not isinstance(artifact, CoreComponentArtifact):
            raise TypeError("CoreComponentArtifact required")
        if artifact.artifact_id != CORE_DISTRIBUTION:
            raise SyntheticCoreLifecycleConflict("synthetic Core artifact ID is invalid")
        owner = _owner(owner_id)
        core = _canonical_uuid(core_id, "core_id")
        lineage = _canonical_uuid(lineage_id, "lineage_id")
        if core == lineage:
            raise ValueError("core_id and lineage_id must be distinct")
        if self.platform_id in {core, lineage}:
            raise ValueError("synthetic Core identity must differ from the Platform")
        if _generation(expected_generation, "expected_generation") != 0:
            raise SyntheticCoreLifecycleConflict(
                "new synthetic Core must start from expected generation zero"
            )
        self._authorize(
            SyntheticCoreOperation.INSTALL, artifact.sha256, expected_generation
        )
        self._require_no_pending(core)
        if self.store.binding(owner, core) is not None:
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core identity is already bound to this owner"
            )
        if self.store.live_artifact(owner, artifact.sha256) is not None:
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core artifact is already bound to this owner"
            )
        try:
            installed = self.installer.execute(
                artifact,
                Path(wheel_path),
                authority=authority,
                approval_id=approval_id,
            )
        except CoreComponentInstallError:
            raise
        if installed.outcome is not InstallOutcome.SUCCEEDED:
            raise SyntheticCoreLifecycleConflict(
                "Core component installation did not succeed"
            )
        at = self._now()
        binding = SyntheticCoreBinding(
            owner_id=owner,
            core_id=core,
            lineage_id=lineage,
            generation=0,
            state=SyntheticCoreState.INSTALLED,
            artifact_sha256=artifact.sha256,
            version=artifact.version,
            installed_at=installed.installed_at,
            updated_at=at,
            last_operation=SyntheticCoreOperation.INSTALL,
            last_outcome=SyntheticCoreOutcome.SUCCEEDED,
            detail="signed synthetic Core installed by the existing component installer",
        )
        try:
            with self.store.transaction() as db:
                db.execute(
                    "INSERT INTO ops_synthetic_core_binding("
                    "owner_id,core_id,lineage_id,generation,state,"
                    "artifact_sha256,version,installed_at,updated_at,"
                    "last_operation,last_outcome,detail"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        binding.owner_id,
                        binding.core_id,
                        binding.lineage_id,
                        binding.generation,
                        binding.state.value,
                        binding.artifact_sha256,
                        binding.version,
                        binding.installed_at.isoformat(),
                        binding.updated_at.isoformat(),
                        binding.last_operation.value,
                        binding.last_outcome.value,
                        binding.detail,
                    ),
                )
                self._append_event(
                    db,
                    owner_id=owner,
                    core_id=core,
                    lineage_id=lineage,
                    operation=SyntheticCoreOperation.INSTALL,
                    generation=0,
                    state_before=None,
                    state_after=SyntheticCoreState.INSTALLED,
                    outcome=SyntheticCoreOutcome.SUCCEEDED,
                    artifact_sha256=artifact.sha256,
                    occurred_at=at,
                    detail=binding.detail,
                )
        except sqlite3.IntegrityError as exc:
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core identity or artifact is already bound"
            ) from exc
        return SyntheticCoreLifecycleReceipt(
            operation=SyntheticCoreOperation.INSTALL,
            outcome=SyntheticCoreOutcome.SUCCEEDED,
            owner_id=owner,
            core_id=core,
            lineage_id=lineage,
            generation=0,
            state=SyntheticCoreState.INSTALLED,
            artifact_sha256=artifact.sha256,
            happened_at=at,
            detail=binding.detail,
            install_receipt=installed,
        )

    def start(
        self,
        *,
        owner_id: str,
        core_id: str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        """Start one process generation under a fresh caller authorization."""
        self.reconcile()
        owner = _owner(owner_id)
        core = _canonical_uuid(core_id, "core_id")
        expected = _generation(expected_generation, "expected_generation")
        self._require_no_pending(core)
        binding = self._require_binding(self.store.binding(owner, core), owner, core)
        if binding.state is SyntheticCoreState.ACTIVE:
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core already has an active process"
            )
        if binding.state in (SyntheticCoreState.DETACHED, SyntheticCoreState.REMOVED):
            raise SyntheticCoreLifecycleConflict(
                "detached or removed synthetic Core cannot start"
            )
        if binding.generation != expected:
            raise SyntheticCoreLifecycleConflict(
                "stale expected generation for synthetic Core start"
            )
        if self.store.active_lineage(binding.lineage_id) is not None:
            raise SyntheticCoreLifecycleConflict(
                "another process is active for this identity lineage"
            )
        self._authorize(
            SyntheticCoreOperation.START, binding.artifact_sha256, expected
        )
        next_generation = binding.generation + 1
        at = self._now()
        pending = self._begin_pending(
            binding=binding,
            operation=SyntheticCoreOperation.START,
            generation=next_generation,
            expected_generation=expected,
            at=at,
        )
        try:
            raw = self.backend.start(
                core_id=core,
                lineage_id=binding.lineage_id,
                generation=next_generation,
            )
            observed = _observation(raw)
            if raw is None:
                observed = _observation(
                    self.backend.observe(
                        core_id=core,
                        lineage_id=binding.lineage_id,
                        generation=next_generation,
                    )
                )
        except Exception as exc:
            self._record_unknown(
                pending, f"start outcome unknown: {type(exc).__name__}"
            )
            raise SyntheticCoreBackendUncertain(
                "synthetic Core start outcome is unknown; do not retry blindly"
            ) from exc
        if observed is CoreProcessObservation.UNKNOWN:
            self._record_unknown(pending, "start observed unknown state")
            raise SyntheticCoreBackendUncertain(
                "synthetic Core start outcome is unknown; do not retry blindly"
            )
        outcome = (
            SyntheticCoreOutcome.SUCCEEDED
            if observed is CoreProcessObservation.RUNNING
            else SyntheticCoreOutcome.FAILED
        )
        finished_at = self._now()
        with self.store.transaction() as db:
            after = (
                SyntheticCoreState.ACTIVE
                if outcome is SyntheticCoreOutcome.SUCCEEDED
                else binding.state
            )
            generation = (
                next_generation
                if outcome is SyntheticCoreOutcome.SUCCEEDED
                else binding.generation
            )
            detail = (
                "synthetic Core process started"
                if outcome is SyntheticCoreOutcome.SUCCEEDED
                else f"start observed {observed.value}"
            )
            updated = SyntheticCoreBinding(
                owner_id=binding.owner_id,
                core_id=binding.core_id,
                lineage_id=binding.lineage_id,
                generation=generation,
                state=after,
                artifact_sha256=binding.artifact_sha256,
                version=binding.version,
                installed_at=binding.installed_at,
                updated_at=finished_at,
                last_operation=SyntheticCoreOperation.START,
                last_outcome=outcome,
                detail=detail,
            )
            self._write_binding(db, updated)
            self._resolve_pending(
                db, pending, outcome=outcome, observed=observed,
                at=finished_at, detail=detail,
            )
            self._append_event(
                db,
                owner_id=owner,
                core_id=core,
                lineage_id=binding.lineage_id,
                operation=SyntheticCoreOperation.START,
                generation=generation,
                state_before=binding.state,
                state_after=after,
                outcome=outcome,
                artifact_sha256=binding.artifact_sha256,
                occurred_at=finished_at,
                detail=detail,
            )
        if outcome is not SyntheticCoreOutcome.SUCCEEDED:
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core process did not remain running"
            )
        return SyntheticCoreLifecycleReceipt(
            operation=SyntheticCoreOperation.START,
            outcome=outcome,
            owner_id=owner,
            core_id=core,
            lineage_id=binding.lineage_id,
            generation=generation,
            state=after,
            artifact_sha256=binding.artifact_sha256,
            happened_at=finished_at,
            detail=detail,
        )

    def activate(
        self,
        *,
        owner_id: str,
        core_id: str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        """Alias for :meth:`start`; activation remains an explicit operation."""
        return self.start(
            owner_id=owner_id,
            core_id=core_id,
            expected_generation=expected_generation,
        )

    def stop(
        self,
        *,
        owner_id: str,
        core_id: str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        """Stop the active process; repeated stop reports ALREADY_STOPPED."""
        self.reconcile()
        owner = _owner(owner_id)
        core = _canonical_uuid(core_id, "core_id")
        expected = _generation(expected_generation, "expected_generation")
        self._require_no_pending(core)
        binding = self._require_binding(self.store.binding(owner, core), owner, core)
        if binding.state is not SyntheticCoreState.ACTIVE:
            return SyntheticCoreLifecycleReceipt(
                operation=SyntheticCoreOperation.STOP,
                outcome=SyntheticCoreOutcome.ALREADY_STOPPED,
                owner_id=owner,
                core_id=core,
                lineage_id=binding.lineage_id,
                generation=binding.generation,
                state=binding.state,
                artifact_sha256=binding.artifact_sha256,
                happened_at=self._now(),
                detail="synthetic Core has no active process",
            )
        if binding.generation != expected:
            raise SyntheticCoreLifecycleConflict(
                "stale expected generation for synthetic Core stop"
            )
        self._authorize(
            SyntheticCoreOperation.STOP, binding.artifact_sha256, expected
        )
        at = self._now()
        pending = self._begin_pending(
            binding=binding,
            operation=SyntheticCoreOperation.STOP,
            generation=binding.generation,
            expected_generation=expected,
            at=at,
        )
        try:
            raw = self.backend.stop(
                core_id=core,
                lineage_id=binding.lineage_id,
                generation=binding.generation,
            )
            observed = _observation(raw)
            if raw is None:
                observed = _observation(
                    self.backend.observe(
                        core_id=core,
                        lineage_id=binding.lineage_id,
                        generation=binding.generation,
                    )
                )
        except Exception as exc:
            self._record_unknown(
                pending, f"stop outcome unknown: {type(exc).__name__}"
            )
            raise SyntheticCoreBackendUncertain(
                "synthetic Core stop outcome is unknown"
            ) from exc
        if observed is CoreProcessObservation.UNKNOWN:
            self._record_unknown(pending, "stop observed unknown state")
            raise SyntheticCoreBackendUncertain(
                "synthetic Core stop outcome is unknown"
            )
        outcome = (
            SyntheticCoreOutcome.SUCCEEDED
            if observed is CoreProcessObservation.STOPPED
            else SyntheticCoreOutcome.FAILED
        )
        finished_at = self._now()
        with self.store.transaction() as db:
            after = (
                SyntheticCoreState.STOPPED
                if outcome is SyntheticCoreOutcome.SUCCEEDED
                else SyntheticCoreState.ACTIVE
            )
            detail = (
                "synthetic Core process stopped"
                if outcome is SyntheticCoreOutcome.SUCCEEDED
                else f"stop observed {observed.value}"
            )
            updated = SyntheticCoreBinding(
                owner_id=binding.owner_id,
                core_id=binding.core_id,
                lineage_id=binding.lineage_id,
                generation=binding.generation,
                state=after,
                artifact_sha256=binding.artifact_sha256,
                version=binding.version,
                installed_at=binding.installed_at,
                updated_at=finished_at,
                last_operation=SyntheticCoreOperation.STOP,
                last_outcome=outcome,
                detail=detail,
            )
            self._write_binding(db, updated)
            self._resolve_pending(
                db, pending, outcome=outcome, observed=observed,
                at=finished_at, detail=detail,
            )
            self._append_event(
                db,
                owner_id=owner,
                core_id=core,
                lineage_id=binding.lineage_id,
                operation=SyntheticCoreOperation.STOP,
                generation=binding.generation,
                state_before=binding.state,
                state_after=after,
                outcome=outcome,
                artifact_sha256=binding.artifact_sha256,
                occurred_at=finished_at,
                detail=detail,
            )
        if outcome is not SyntheticCoreOutcome.SUCCEEDED:
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core process could not be confirmed stopped"
            )
        return SyntheticCoreLifecycleReceipt(
            operation=SyntheticCoreOperation.STOP,
            outcome=outcome,
            owner_id=owner,
            core_id=core,
            lineage_id=binding.lineage_id,
            generation=binding.generation,
            state=after,
            artifact_sha256=binding.artifact_sha256,
            happened_at=finished_at,
            detail=detail,
        )

    def detach(
        self,
        *,
        owner_id: str,
        core_id: str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        """Detach a stopped synthetic Core without touching Platform identity."""
        self.reconcile()
        owner = _owner(owner_id)
        core = _canonical_uuid(core_id, "core_id")
        expected = _generation(expected_generation, "expected_generation")
        self._require_no_pending(core)
        binding = self._require_binding(self.store.binding(owner, core), owner, core)
        if binding.state is SyntheticCoreState.DETACHED:
            return SyntheticCoreLifecycleReceipt(
                operation=SyntheticCoreOperation.DETACH,
                outcome=SyntheticCoreOutcome.ALREADY_DETACHED,
                owner_id=owner,
                core_id=core,
                lineage_id=binding.lineage_id,
                generation=binding.generation,
                state=binding.state,
                artifact_sha256=binding.artifact_sha256,
                happened_at=self._now(),
                detail="synthetic Core is already detached",
            )
        if binding.state is SyntheticCoreState.ACTIVE:
            raise SyntheticCoreLifecycleConflict(
                "active synthetic Core must be stopped before detach"
            )
        if binding.state is SyntheticCoreState.REMOVED:
            raise SyntheticCoreLifecycleConflict(
                "removed synthetic Core cannot be detached"
            )
        if binding.generation != expected:
            raise SyntheticCoreLifecycleConflict(
                "stale expected generation for synthetic Core detach"
            )
        self._authorize(
            SyntheticCoreOperation.DETACH, binding.artifact_sha256, expected
        )
        at = self._now()
        with self.store.transaction() as db:
            updated = SyntheticCoreBinding(
                owner_id=binding.owner_id,
                core_id=binding.core_id,
                lineage_id=binding.lineage_id,
                generation=binding.generation,
                state=SyntheticCoreState.DETACHED,
                artifact_sha256=binding.artifact_sha256,
                version=binding.version,
                installed_at=binding.installed_at,
                updated_at=at,
                last_operation=SyntheticCoreOperation.DETACH,
                last_outcome=SyntheticCoreOutcome.SUCCEEDED,
                detail="synthetic Core detached; Platform installation unchanged",
            )
            self._write_binding(db, updated)
            self._append_event(
                db,
                owner_id=owner,
                core_id=core,
                lineage_id=binding.lineage_id,
                operation=SyntheticCoreOperation.DETACH,
                generation=binding.generation,
                state_before=binding.state,
                state_after=SyntheticCoreState.DETACHED,
                outcome=SyntheticCoreOutcome.SUCCEEDED,
                artifact_sha256=binding.artifact_sha256,
                occurred_at=at,
                detail=updated.detail,
            )
        return SyntheticCoreLifecycleReceipt(
            operation=SyntheticCoreOperation.DETACH,
            outcome=SyntheticCoreOutcome.SUCCEEDED,
            owner_id=owner,
            core_id=core,
            lineage_id=binding.lineage_id,
            generation=binding.generation,
            state=SyntheticCoreState.DETACHED,
            artifact_sha256=binding.artifact_sha256,
            happened_at=at,
            detail=updated.detail,
        )

    def remove(
        self,
        *,
        owner_id: str,
        core_id: str,
        expected_generation: int,
    ) -> SyntheticCoreLifecycleReceipt:
        """Remove a stopped/detached binding and report Platform independence."""
        self.reconcile()
        owner = _owner(owner_id)
        core = _canonical_uuid(core_id, "core_id")
        expected = _generation(expected_generation, "expected_generation")
        self._require_no_pending(core)
        binding = self._require_binding(self.store.binding(owner, core), owner, core)
        if binding.state is SyntheticCoreState.REMOVED:
            return SyntheticCoreLifecycleReceipt(
                operation=SyntheticCoreOperation.REMOVE,
                outcome=SyntheticCoreOutcome.ALREADY_REMOVED,
                owner_id=owner,
                core_id=core,
                lineage_id=binding.lineage_id,
                generation=binding.generation,
                state=binding.state,
                artifact_sha256=binding.artifact_sha256,
                happened_at=self._now(),
                detail="synthetic Core binding is already removed",
                platform_healthy=self._platform_is_healthy(),
            )
        if binding.state not in (
            SyntheticCoreState.STOPPED,
            SyntheticCoreState.DETACHED,
        ):
            raise SyntheticCoreLifecycleConflict(
                "synthetic Core must be stopped or detached before removal"
            )
        if binding.generation != expected:
            raise SyntheticCoreLifecycleConflict(
                "stale expected generation for synthetic Core removal"
            )
        self._authorize(
            SyntheticCoreOperation.REMOVE, binding.artifact_sha256, expected
        )
        at = self._now()
        with self.store.transaction() as db:
            updated = SyntheticCoreBinding(
                owner_id=binding.owner_id,
                core_id=binding.core_id,
                lineage_id=binding.lineage_id,
                generation=binding.generation,
                state=SyntheticCoreState.REMOVED,
                artifact_sha256=binding.artifact_sha256,
                version=binding.version,
                installed_at=binding.installed_at,
                updated_at=at,
                last_operation=SyntheticCoreOperation.REMOVE,
                last_outcome=SyntheticCoreOutcome.SUCCEEDED,
                detail=(
                    "synthetic Core binding removed; Platform installation "
                    "identity/state remains owned by the Platform"
                ),
            )
            self._write_binding(db, updated)
            self._append_event(
                db,
                owner_id=owner,
                core_id=core,
                lineage_id=binding.lineage_id,
                operation=SyntheticCoreOperation.REMOVE,
                generation=binding.generation,
                state_before=binding.state,
                state_after=SyntheticCoreState.REMOVED,
                outcome=SyntheticCoreOutcome.SUCCEEDED,
                artifact_sha256=binding.artifact_sha256,
                occurred_at=at,
                detail=updated.detail,
            )
        platform_healthy = self._platform_is_healthy()
        return SyntheticCoreLifecycleReceipt(
            operation=SyntheticCoreOperation.REMOVE,
            outcome=SyntheticCoreOutcome.SUCCEEDED,
            owner_id=owner,
            core_id=core,
            lineage_id=binding.lineage_id,
            generation=binding.generation,
            state=SyntheticCoreState.REMOVED,
            artifact_sha256=binding.artifact_sha256,
            happened_at=at,
            detail=updated.detail,
            platform_healthy=platform_healthy,
        )


__all__ = [
    "CoreProcessObservation",
    "SyntheticCoreAuthorizer",
    "SyntheticCoreBackendUncertain",
    "SyntheticCoreBinding",
    "SyntheticCoreFreshness",
    "SyntheticCoreLifecycle",
    "SyntheticCoreLifecycleConflict",
    "SyntheticCoreLifecycleError",
    "SyntheticCoreLifecycleReceipt",
    "SyntheticCoreLifecycleStore",
    "SyntheticCoreOperation",
    "SyntheticCoreOutcome",
    "SyntheticCorePendingOperation",
    "SyntheticCorePendingReconciliation",
    "SyntheticCorePlatformHealth",
    "SyntheticCoreProcessBackend",
    "SyntheticCoreState",
]
