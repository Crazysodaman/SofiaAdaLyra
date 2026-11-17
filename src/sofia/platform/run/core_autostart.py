"""Platform-owned per-Core autostart desired state and startup reconciliation.

Installation is not activation, and activation is not autostart. This module
owns only a Platform-local *desired* policy for each installed Core plus the
bounded evidence of the last startup attempt. It never starts a Core itself:
process start remains a service-owned callback behind the existing lifecycle
and SAFE authority boundaries.

The policy table is additive in the canonical Platform SQLite. No owner
secret, credential or second approval store is created here. Enabling or
disabling autostart requires a caller-supplied one-use approval reference that
is checked by a caller-supplied verifier before any row is written.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from threading import Thread
from typing import Callable, Protocol

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

_UUID_TEXT = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_SHA256 = re.compile(r"[0-9a-f]{64}")

# Durable operator intent is not an authentication proof. Policy age never
# revokes it; only a current owner authorization check can. Reject policy
# timestamps that are meaningfully in the future (clock rollback), allowing a
# small skew window for ordinary time synchronization.
MAX_POLICY_CLOCK_SKEW_SECONDS = 5.0

# A reviewable, bounded per-Core start budget. A hung service-owned callback
# must not block Platform startup indefinitely.
DEFAULT_START_TIMEOUT_SECONDS = 10.0
MIN_START_TIMEOUT_SECONDS = 0.01
MAX_START_TIMEOUT_SECONDS = 60.0


class CoreAutostartError(RuntimeError):
    """A Core autostart contract was violated."""


class CoreAutostartConflict(CoreAutostartError):
    """A stale, duplicate or conflicting policy write was refused."""


class CoreAutostartOutcome(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    STARTED = "STARTED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    STOPPED = "STOPPED"


class CoreObservation(str, Enum):
    """Fresh service-owned process observation for one Core generation."""

    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    UNKNOWN = "UNKNOWN"


class CoreStartupState(str, Enum):
    """Platform-level summary; zero installed Cores is a valid healthy state."""

    ZERO_CORE_HEALTHY = "ZERO_CORE_HEALTHY"
    CORES_DISABLED = "CORES_DISABLED"
    CORES_RUNNING = "CORES_RUNNING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class CoreAutostartApprovalVerifier(Protocol):
    """One-use approval interface supplied by the caller.

    The verifier, not this module, authenticates the approval. It must return
    exactly ``True`` for the bound Core, revision, desired state and
    fingerprint. This module never stores the reference or any secret.
    """

    def __call__(
        self, *,
        approval_ref: str,
        core_id: str,
        revision: int,
        enabled: bool,
        fingerprint: str,
        now: datetime,
    ) -> bool:
        ...


StartCoreCallback = Callable[[str, int, str], object]
ObserveCoreCallback = Callable[[str, int], object]
InstalledCoreIdsCallback = Callable[[], object]


def _utc(value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _core_id(value: object) -> str:
    if not isinstance(value, str) or _UUID_TEXT.fullmatch(value) is None:
        raise ValueError("core_id must be a lowercase canonical UUID")
    if str(value) != value:
        raise ValueError("core_id must be a lowercase canonical UUID")
    return value


def _revision(value: object, label: str = "revision") -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def approval_fingerprint(core_id: str, revision: int, enabled: bool) -> str:
    """Bind one policy decision to an exact Core, revision and desired state."""
    if type(enabled) is not bool:
        raise TypeError("enabled must be bool")
    document = {
        "core_id": _core_id(core_id),
        "revision": _revision(revision),
        "enabled": enabled,
    }
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class _ManagementWriteAuthority:
    """Opaque, module-private capability for the service mutation handler."""

    __slots__ = ()


_MANAGEMENT_WRITE_AUTHORITY = _ManagementWriteAuthority()


@dataclass(frozen=True, slots=True)
class CoreAutostartPolicy:
    """Durable Platform-owned desired state for one Core.

    ``approval_fingerprint`` is a public binding digest, not a secret and not
    an approval credential. The one-use approval reference is never stored.
    """

    core_id: str
    enabled: bool
    approved_revision: int
    approval_fingerprint: str
    updated_at: datetime
    last_outcome: CoreAutostartOutcome = CoreAutostartOutcome.NOT_STARTED
    last_attempt_at: datetime | None = None
    last_error_code: str | None = None
    last_started_generation: int | None = None

    def __post_init__(self) -> None:
        _core_id(self.core_id)
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be bool")
        _revision(self.approved_revision, "approved_revision")
        if (
            not isinstance(self.approval_fingerprint, str)
            or _SHA256.fullmatch(self.approval_fingerprint) is None
        ):
            raise ValueError("approval_fingerprint must be lowercase SHA-256")
        _utc(self.updated_at)
        if not isinstance(self.last_outcome, CoreAutostartOutcome):
            raise TypeError("last_outcome must be a CoreAutostartOutcome")
        if self.last_attempt_at is not None:
            _utc(self.last_attempt_at)
        if self.last_error_code is not None:
            if (
                not isinstance(self.last_error_code, str)
                or not self.last_error_code
                or len(self.last_error_code) > 80
            ):
                raise ValueError("last_error_code must be bounded")
        if self.last_started_generation is not None:
            if (
                type(self.last_started_generation) is not int
                or self.last_started_generation < 0
            ):
                raise ValueError("last_started_generation must be nonnegative")


@dataclass(frozen=True, slots=True)
class CoreReconciliationResult:
    core_id: str
    outcome: CoreAutostartOutcome | None
    started: bool
    reason: str = ""
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class CoreStartupReport:
    """Bounded, non-secret summary of one startup reconciliation pass."""

    startup_state: CoreStartupState
    results: tuple[CoreReconciliationResult, ...]
    reconciled_at: datetime
    enabled_count: int
    active_count: int
    core_count: int = 0

    @property
    def zero_core_healthy(self) -> bool:
        return self.startup_state is CoreStartupState.ZERO_CORE_HEALTHY

    @property
    def cores_disabled(self) -> bool:
        return self.startup_state is CoreStartupState.CORES_DISABLED


class CoreAutostartPolicyStore:
    """Additive canonical-SQLite policy owner for per-Core autostart."""

    def __init__(
        self,
        state_path: Path | str,
        *,
        verify_approval: CoreAutostartApprovalVerifier,
    ) -> None:
        if not callable(verify_approval):
            raise TypeError("one-use approval verifier callback required")
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self._verify_approval = verify_approval
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_core_autostart_policy (
                    core_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                    approved_revision INTEGER NOT NULL
                        CHECK(approved_revision>=1),
                    approval_fingerprint TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_outcome TEXT NOT NULL DEFAULT 'NOT_STARTED',
                    last_attempt_at TEXT,
                    last_error_code TEXT,
                    last_started_generation INTEGER
                        CHECK(last_started_generation IS NULL
                              OR last_started_generation>=0)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _policy(row: sqlite3.Row) -> CoreAutostartPolicy:
        return CoreAutostartPolicy(
            core_id=row["core_id"],
            enabled=bool(row["enabled"]),
            approved_revision=int(row["approved_revision"]),
            approval_fingerprint=row["approval_fingerprint"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_outcome=CoreAutostartOutcome(row["last_outcome"]),
            last_attempt_at=(
                None if row["last_attempt_at"] is None
                else datetime.fromisoformat(row["last_attempt_at"])
            ),
            last_error_code=row["last_error_code"],
            last_started_generation=(
                None if row["last_started_generation"] is None
                else int(row["last_started_generation"])
            ),
        )

    def policy(self, core_id: str) -> CoreAutostartPolicy | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_core_autostart_policy WHERE core_id=?",
                (_core_id(core_id),),
            ).fetchone()
        return None if row is None else self._policy(row)

    def policies(self) -> tuple[CoreAutostartPolicy, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM platform_core_autostart_policy ORDER BY core_id"
            ).fetchall()
        return tuple(self._policy(row) for row in rows)

    def enabled_policies(self) -> tuple[CoreAutostartPolicy, ...]:
        return tuple(policy for policy in self.policies() if policy.enabled)

    def _write_policy(
        self, *,
        core: str,
        enabled: bool,
        expected_revision: int,
        fingerprint: str,
        moment: datetime,
    ) -> CoreAutostartPolicy:
        """Persist one monotonic revision inside one IMMEDIATE transaction."""
        text = moment.isoformat()
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM platform_core_autostart_policy WHERE core_id=?",
                (core,),
            ).fetchone()
            if row is None:
                if expected_revision != 1:
                    raise CoreAutostartConflict(
                        "new Core autostart policy must start at revision one"
                    )
                try:
                    db.execute(
                        "INSERT INTO platform_core_autostart_policy("
                        "core_id,enabled,approved_revision,approval_fingerprint,"
                        "updated_at,last_outcome"
                        ") VALUES(?,?,?,?,?,?)",
                        (
                            core, int(enabled), expected_revision, fingerprint,
                            text, CoreAutostartOutcome.NOT_STARTED.value,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise CoreAutostartConflict(
                        "duplicate Core autostart policy writer"
                    ) from exc
            else:
                current = self._policy(row)
                if expected_revision != current.approved_revision + 1:
                    raise CoreAutostartConflict(
                        "stale or duplicate Core autostart policy revision"
                    )
                changed = db.execute(
                    "UPDATE platform_core_autostart_policy SET "
                    "enabled=?,approved_revision=?,approval_fingerprint=?,"
                    "updated_at=?,last_outcome=?,last_attempt_at=NULL,"
                    "last_error_code=NULL,last_started_generation=NULL "
                    "WHERE core_id=? AND approved_revision=?",
                    (
                        int(enabled), expected_revision, fingerprint, text,
                        CoreAutostartOutcome.NOT_STARTED.value, core,
                        current.approved_revision,
                    ),
                )
                if changed.rowcount != 1:
                    raise CoreAutostartConflict(
                        "duplicate Core autostart policy writer"
                    )
        policy = self.policy(core)
        if policy is None:
            raise CoreAutostartConflict("Core autostart policy was not persisted")
        return policy

    def set_enabled(
        self, *,
        core_id: str,
        enabled: bool,
        revision: int,
        approval_ref: str,
        now: datetime,
    ) -> CoreAutostartPolicy:
        """Write one exact, one-use-approved desired state.

        A duplicate or stale writer is refused. The approval reference is
        verified but never persisted.
        """
        core = _core_id(core_id)
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        expected_revision = _revision(revision)
        moment = _utc(now)
        if (
            not isinstance(approval_ref, str)
            or _ID.fullmatch(approval_ref) is None
        ):
            raise PermissionError(
                "exact one-use approval reference required for Core autostart"
            )
        fingerprint = approval_fingerprint(core, expected_revision, enabled)
        if self._verify_approval(
            approval_ref=approval_ref,
            core_id=core,
            revision=expected_revision,
            enabled=enabled,
            fingerprint=fingerprint,
            now=moment,
        ) is not True:
            raise PermissionError("Core autostart approval denied")
        return self._write_policy(
            core=core, enabled=enabled, expected_revision=expected_revision,
            fingerprint=fingerprint, moment=moment,
        )

    def set_enabled_from_management(
        self, *,
        core_id: str,
        enabled: bool,
        expected_revision: int,
        authorization_fingerprint: str,
        now: datetime,
        _authority: object = None,
    ) -> CoreAutostartPolicy:
        """Write one management-authorized policy revision. SERVICE ONLY.

        Trust boundary
        --------------
        The only legitimate caller is the service-owned management mutation
        handler bound by ``management_autostart_writer``. That handler runs
        only after the existing ``ManagementMutationDispatcher`` has:

        * authenticated the local OS peer;
        * consumed the exact one-use SAFE owner execution approval;
        * fenced operator STOP, Platform generation and mutation revision;
        * resolved replay/idempotency to a durable receipt;
        * revalidated the consumed owner proof after the effect.

        This method therefore does NOT consume a second one-use approval and
        creates no second approval store. ``authorization_fingerprint`` is the
        non-secret semantic request/plan digest supplied by the dispatcher. It
        is recorded as evidence; the owner's approval reference, credential and
        any secret are never accepted or stored here. The module-private
        authority token makes a direct call from a client or SDK fail closed.
        """
        if _authority is not _MANAGEMENT_WRITE_AUTHORITY:
            raise PermissionError(
                "Core autostart management write requires service mutation handler"
            )
        core = _core_id(core_id)
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        revision = _revision(expected_revision, "expected_revision")
        if (
            not isinstance(authorization_fingerprint, str)
            or _SHA256.fullmatch(authorization_fingerprint) is None
        ):
            raise ValueError(
                "authorization_fingerprint must be lowercase SHA-256"
            )
        moment = _utc(now)
        return self._write_policy(
            core=core, enabled=enabled, expected_revision=revision,
            fingerprint=authorization_fingerprint, moment=moment,
        )

    def record_outcome(
        self, *,
        core_id: str,
        outcome: CoreAutostartOutcome,
        now: datetime,
        error_code: str | None = None,
        started_generation: int | None = None,
    ) -> None:
        """Record attempt evidence without changing desired state."""
        if not isinstance(outcome, CoreAutostartOutcome):
            raise TypeError("outcome must be a CoreAutostartOutcome")
        core = _core_id(core_id)
        moment = _utc(now)
        if error_code is not None:
            if (
                not isinstance(error_code, str)
                or not error_code
                or len(error_code) > 80
            ):
                raise ValueError("error_code must be bounded")
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE platform_core_autostart_policy SET "
                "last_outcome=?,last_attempt_at=?,last_error_code=?,"
                "last_started_generation=? WHERE core_id=?",
                (
                    outcome.value, moment.isoformat(), error_code,
                    started_generation, core,
                ),
            )
            if changed.rowcount != 1:
                raise CoreAutostartConflict(
                    "Core autostart policy does not exist"
                )


def management_autostart_writer(
    store: CoreAutostartPolicyStore,
) -> Callable[..., CoreAutostartPolicy]:
    """Return the service-owned writer capability bound to one policy store.

    This factory is composed only by the Platform management mutation backend.
    It hands back a callable carrying the module-private authority token, so a
    client, SDK or arbitrary handler cannot invoke the internal management
    write directly. The returned callable still performs no approval or
    authority check of its own; the dispatcher remains the only authority
    boundary.
    """
    if not isinstance(store, CoreAutostartPolicyStore):
        raise TypeError("canonical CoreAutostartPolicyStore required")

    def write(
        *,
        core_id: str,
        enabled: bool,
        expected_revision: int,
        authorization_fingerprint: str,
        now: datetime,
    ) -> CoreAutostartPolicy:
        return store.set_enabled_from_management(
            core_id=core_id,
            enabled=enabled,
            expected_revision=expected_revision,
            authorization_fingerprint=authorization_fingerprint,
            now=now,
            _authority=_MANAGEMENT_WRITE_AUTHORITY,
        )

    return write


def _normalized_outcome(value: object) -> CoreAutostartOutcome:
    if isinstance(value, CoreAutostartOutcome):
        return value
    text = str(getattr(value, "value", value)).strip().upper()
    if text in {"STARTED", "SUCCEEDED", "RUNNING"}:
        return CoreAutostartOutcome.STARTED
    if text in {"OUTCOME_UNKNOWN", "UNKNOWN"}:
        return CoreAutostartOutcome.OUTCOME_UNKNOWN
    if text == "STOPPED":
        return CoreAutostartOutcome.STOPPED
    if text == "FAILED":
        return CoreAutostartOutcome.FAILED
    return CoreAutostartOutcome.OUTCOME_UNKNOWN


def _normalized_observation(value: object) -> CoreObservation:
    if isinstance(value, CoreObservation):
        return value
    text = str(getattr(value, "value", value)).strip().upper()
    if text in {"RUNNING", "STARTED", "ALIVE", "ACTIVE"}:
        return CoreObservation.RUNNING
    if text in {"STOPPED", "STOP", "EXITED", "DEAD", "NOT_RUNNING"}:
        return CoreObservation.STOPPED
    return CoreObservation.UNKNOWN


_START_TIMEOUT = object()


class CoreStartupReconciler:
    """Observe installed Cores, then start currently authorized enabled Cores.

    Policy age is not an authorization gate: durable operator intent survives
    a reboot. A small future timestamp tolerance fences clock rollback only.
    Every start is preceded by a fresh service-owned process observation and a
    current owner authorization check. A cached STARTED row is never counted
    active unless the fresh observation is RUNNING. Slow or hung callbacks are
    bounded per Core, recorded as OUTCOME_UNKNOWN, and never take Platform
    startup down.
    """

    def __init__(
        self, *,
        store: CoreAutostartPolicyStore,
        start_core: StartCoreCallback,
        observe_core: ObserveCoreCallback,
        installed_core_ids: InstalledCoreIdsCallback,
        is_stopped: Callable[[], bool],
        is_authorized: Callable[[CoreAutostartPolicy], bool],
        start_timeout_seconds: float = DEFAULT_START_TIMEOUT_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(store, CoreAutostartPolicyStore):
            raise TypeError("CoreAutostartPolicyStore required")
        if not callable(start_core):
            raise TypeError("service-owned start_core callback required")
        if not callable(observe_core):
            raise TypeError("service-owned observe_core callback required")
        if not callable(installed_core_ids):
            raise TypeError("service-owned installed_core_ids callback required")
        if not callable(is_stopped):
            raise TypeError("STOP observation callback required")
        if not callable(is_authorized):
            raise TypeError("current owner authorization callback required")
        if (
            type(start_timeout_seconds) not in (int, float)
            or type(start_timeout_seconds) is bool
            or not MIN_START_TIMEOUT_SECONDS
            <= float(start_timeout_seconds)
            <= MAX_START_TIMEOUT_SECONDS
        ):
            raise ValueError("start_timeout_seconds must be bounded")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self.store = store
        self._start_core = start_core
        self._observe_core = observe_core
        self._installed_core_ids = installed_core_ids
        self._is_stopped = is_stopped
        self._is_authorized = is_authorized
        self._start_timeout_seconds = float(start_timeout_seconds)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        return _utc(self._clock())

    def _installed_ids(self) -> frozenset[str]:
        raw = self._installed_core_ids()
        if isinstance(raw, (str, bytes)) or not hasattr(raw, "__iter__"):
            raise TypeError("installed Core inventory must be iterable")
        return frozenset(_core_id(core) for core in raw)

    def installed_ids(self) -> tuple[str, ...]:
        """Fresh installed-Core inventory snapshot for service projections."""
        return tuple(sorted(self._installed_ids()))

    def _observe(
        self, core_id: str, generation: int,
    ) -> CoreObservation:
        try:
            return _normalized_observation(
                self._observe_core(core_id, generation)
            )
        except Exception:
            return CoreObservation.UNKNOWN

    def _start_bounded(
        self, core_id: str, generation: int, approval_ref: str,
    ) -> object:
        outcome: dict[str, object] = {}

        def invoke() -> None:
            try:
                outcome["raw"] = self._start_core(
                    core_id, generation, approval_ref,
                )
            except BaseException as exc:  # contained as evidence below
                outcome["error"] = exc

        worker = Thread(
            target=invoke, name="AegisCoreStart", daemon=True,
        )
        worker.start()
        worker.join(self._start_timeout_seconds)
        if worker.is_alive():
            return _START_TIMEOUT
        error = outcome.get("error")
        if error is not None:
            raise error
        return outcome.get("raw")

    def _record(
        self, core_id: str, outcome: CoreAutostartOutcome, now: datetime,
        *, error_code: str | None = None, started_generation: int | None = None,
    ) -> None:
        try:
            self.store.record_outcome(
                core_id=core_id, outcome=outcome, now=now,
                error_code=error_code, started_generation=started_generation,
            )
        except Exception:
            # Evidence loss must not take Platform startup down. The next
            # reconciliation observes durable state again.
            pass

    def reconcile(
        self, *, expected_generation: int = 0,
    ) -> CoreStartupReport:
        """Reconcile installed/enabled policies; never raise out of startup."""
        if type(expected_generation) is not int or expected_generation < 0:
            expected_generation = 0
        try:
            now = self._now()
        except Exception:
            now = datetime.now(timezone.utc)
            return CoreStartupReport(
                startup_state=CoreStartupState.UNKNOWN,
                results=(),
                reconciled_at=now,
                enabled_count=0,
                active_count=0,
                core_count=0,
            )
        try:
            installed = self._installed_ids()
        except Exception:
            return CoreStartupReport(
                startup_state=CoreStartupState.UNKNOWN,
                results=(),
                reconciled_at=now,
                enabled_count=0,
                active_count=0,
                core_count=0,
            )
        core_count = len(installed)
        if core_count == 0:
            return CoreStartupReport(
                startup_state=CoreStartupState.ZERO_CORE_HEALTHY,
                results=(),
                reconciled_at=now,
                enabled_count=0,
                active_count=0,
                core_count=0,
            )
        try:
            policies = self.store.policies()
        except Exception:
            return CoreStartupReport(
                startup_state=CoreStartupState.UNKNOWN,
                results=(),
                reconciled_at=now,
                enabled_count=0,
                active_count=0,
                core_count=core_count,
            )
        enabled = tuple(
            policy for policy in policies
            if policy.enabled and policy.core_id in installed
        )
        orphaned = tuple(
            policy for policy in policies
            if policy.enabled and policy.core_id not in installed
        )
        results: list[CoreReconciliationResult] = []
        active = 0
        failures = 0
        unknowns = 0
        for policy in orphaned:
            failures += 1
            results.append(CoreReconciliationResult(
                core_id=policy.core_id, outcome=None, started=False,
                reason="enabled policy Core is not installed",
                error_code="NOT_INSTALLED",
            ))
        if not enabled and not orphaned:
            return CoreStartupReport(
                startup_state=CoreStartupState.CORES_DISABLED,
                results=(),
                reconciled_at=now,
                enabled_count=0,
                active_count=0,
                core_count=core_count,
            )
        try:
            stopped = self._is_stopped() is True
        except Exception:
            stopped = True
        if stopped:
            for policy in enabled:
                self._record(
                    policy.core_id, CoreAutostartOutcome.STOPPED, now,
                    error_code="OPERATOR_STOP",
                )
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id,
                    outcome=CoreAutostartOutcome.STOPPED,
                    started=False,
                    reason="operator STOP",
                    error_code="OPERATOR_STOP",
                ))
            if unknowns:
                state = CoreStartupState.UNKNOWN
            else:
                state = CoreStartupState.DEGRADED
            return CoreStartupReport(
                startup_state=state,
                results=tuple(results),
                reconciled_at=now,
                enabled_count=len(enabled),
                active_count=0,
                core_count=core_count,
            )
        for policy in enabled:
            try:
                authorized = self._is_authorized(policy) is True
            except Exception:
                authorized = False
            if not authorized:
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id, outcome=None, started=False,
                    reason="current owner authorization denied",
                    error_code="REVOKED",
                ))
                continue
            age = (now - policy.updated_at).total_seconds()
            if age < -MAX_POLICY_CLOCK_SKEW_SECONDS:
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id, outcome=None, started=False,
                    reason="policy timestamp is in the future",
                    error_code="CLOCK_ROLLBACK",
                ))
                continue
            same_generation = (
                policy.last_started_generation == expected_generation
            )
            prior_attempt = policy.last_outcome in {
                CoreAutostartOutcome.STARTED,
                CoreAutostartOutcome.OUTCOME_UNKNOWN,
            }
            if prior_attempt:
                observation = self._observe(
                    policy.core_id, expected_generation,
                )
                if observation is CoreObservation.RUNNING:
                    active += 1
                    if (policy.last_outcome is not CoreAutostartOutcome.STARTED
                            or not same_generation):
                        self._record(
                            policy.core_id, CoreAutostartOutcome.STARTED, now,
                            started_generation=expected_generation,
                        )
                    results.append(CoreReconciliationResult(
                        core_id=policy.core_id,
                        outcome=CoreAutostartOutcome.STARTED,
                        started=False,
                        reason="fresh process observation is RUNNING",
                    ))
                    continue
                if observation is CoreObservation.UNKNOWN:
                    unknowns += 1
                    self._record(
                        policy.core_id,
                        CoreAutostartOutcome.OUTCOME_UNKNOWN, now,
                        error_code="OBSERVE_UNKNOWN",
                    )
                    results.append(CoreReconciliationResult(
                        core_id=policy.core_id,
                        outcome=CoreAutostartOutcome.OUTCOME_UNKNOWN,
                        started=False,
                        reason="fresh process observation is UNKNOWN",
                        error_code="OBSERVE_UNKNOWN",
                    ))
                    continue
                # A definitive STOPPED observation for this same generation
                # is a crash/zombie: record it truthfully and never reuse the
                # cached STARTED row as active. A stale prior generation is
                # eligible for a fresh, bounded start below.
                if same_generation:
                    self._record(
                        policy.core_id, CoreAutostartOutcome.STOPPED, now,
                        error_code="NOT_RUNNING",
                    )
                    results.append(CoreReconciliationResult(
                        core_id=policy.core_id,
                        outcome=CoreAutostartOutcome.STOPPED,
                        started=False,
                        reason="cached STARTED generation is not running",
                        error_code="NOT_RUNNING",
                    ))
                    continue
            approval_ref = (
                f"core-autostart:{policy.core_id}:{policy.approved_revision}"
            )
            try:
                raw = self._start_bounded(
                    policy.core_id, expected_generation, approval_ref,
                )
            except Exception as exc:
                outcome = CoreAutostartOutcome.FAILED
                error_code = f"EXC_{type(exc).__name__}"[:80]
                self._record(
                    policy.core_id, outcome, now, error_code=error_code,
                )
                failures += 1
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id, outcome=outcome, started=False,
                    reason="start raised", error_code=error_code,
                ))
                continue
            if raw is _START_TIMEOUT:
                unknowns += 1
                self._record(
                    policy.core_id, CoreAutostartOutcome.OUTCOME_UNKNOWN, now,
                    error_code="START_TIMEOUT",
                )
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id,
                    outcome=CoreAutostartOutcome.OUTCOME_UNKNOWN,
                    started=False,
                    reason="start exceeded the bounded per-Core timeout",
                    error_code="START_TIMEOUT",
                ))
                continue
            outcome = _normalized_outcome(raw)
            if outcome is CoreAutostartOutcome.STARTED:
                active += 1
                self._record(
                    policy.core_id, outcome, now,
                    started_generation=expected_generation,
                )
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id, outcome=outcome, started=True,
                ))
            elif outcome is CoreAutostartOutcome.OUTCOME_UNKNOWN:
                unknowns += 1
                self._record(
                    policy.core_id, outcome, now,
                    error_code="OUTCOME_UNKNOWN",
                )
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id, outcome=outcome, started=False,
                    reason="start outcome unknown", error_code="OUTCOME_UNKNOWN",
                ))
            elif outcome is CoreAutostartOutcome.STOPPED:
                self._record(
                    policy.core_id, CoreAutostartOutcome.STOPPED, now,
                    error_code="START_STOPPED",
                )
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id,
                    outcome=CoreAutostartOutcome.STOPPED,
                    started=False, reason="start reported stopped",
                    error_code="START_STOPPED",
                ))
            else:
                failures += 1
                error_code = outcome.value
                self._record(
                    policy.core_id, CoreAutostartOutcome.FAILED, now,
                    error_code=error_code,
                )
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id,
                    outcome=CoreAutostartOutcome.FAILED,
                    started=False, reason="start failed",
                    error_code=error_code,
                ))
        if unknowns:
            state = CoreStartupState.UNKNOWN
        elif failures or not enabled or active != len(enabled):
            state = CoreStartupState.DEGRADED
        else:
            state = CoreStartupState.CORES_RUNNING
        return CoreStartupReport(
            startup_state=state,
            results=tuple(results),
            reconciled_at=now,
            enabled_count=len(enabled),
            active_count=active,
            core_count=core_count,
        )
