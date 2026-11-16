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
from typing import Callable, Protocol

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

_UUID_TEXT = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_SHA256 = re.compile(r"[0-9a-f]{64}")

DEFAULT_POLICY_FRESHNESS_SECONDS = 900


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


class CoreStartupState(str, Enum):
    """Platform-level summary; zero enabled Cores is a valid healthy state."""

    ZERO_CORE_HEALTHY = "ZERO_CORE_HEALTHY"
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

    @property
    def zero_core_healthy(self) -> bool:
        return self.startup_state is CoreStartupState.ZERO_CORE_HEALTHY


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


class CoreStartupReconciler:
    """Start enabled, fresh, authorized Cores at most once per generation.

    All failures are contained here and become FAILED/OUTCOME_UNKNOWN evidence.
    The Platform service remains healthy with zero enabled Cores and after any
    bounded Core start failure.
    """

    def __init__(
        self, *,
        store: CoreAutostartPolicyStore,
        start_core: StartCoreCallback,
        is_stopped: Callable[[], bool],
        freshness_seconds: int = DEFAULT_POLICY_FRESHNESS_SECONDS,
        is_authorized: Callable[[CoreAutostartPolicy], bool] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(store, CoreAutostartPolicyStore):
            raise TypeError("CoreAutostartPolicyStore required")
        if not callable(start_core):
            raise TypeError("service-owned start_core callback required")
        if not callable(is_stopped):
            raise TypeError("STOP observation callback required")
        if (
            type(freshness_seconds) is not int
            or freshness_seconds < 1
            or freshness_seconds > 86_400
        ):
            raise ValueError("freshness_seconds must be an integer in 1..86400")
        if is_authorized is not None and not callable(is_authorized):
            raise TypeError("is_authorized must be callable")
        self.store = store
        self._start_core = start_core
        self._is_stopped = is_stopped
        self._freshness_seconds = freshness_seconds
        self._is_authorized = is_authorized or (lambda _policy: True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        return _utc(self._clock())

    def _is_fresh(self, policy: CoreAutostartPolicy, now: datetime) -> bool:
        age = (now - policy.updated_at).total_seconds()
        return -5.0 <= age <= self._freshness_seconds

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
        """Reconcile enabled policies; never raise out of Platform startup."""
        if type(expected_generation) is not int or expected_generation < 0:
            expected_generation = 0
        try:
            now = self._now()
            policies = self.store.policies()
        except Exception:
            return CoreStartupReport(
                startup_state=CoreStartupState.UNKNOWN,
                results=(),
                reconciled_at=datetime.now(timezone.utc),
                enabled_count=0,
                active_count=0,
            )
        enabled = tuple(policy for policy in policies if policy.enabled)
        results: list[CoreReconciliationResult] = []
        active = 0
        failures = 0
        unknowns = 0
        try:
            stopped = self._is_stopped() is True
        except Exception:
            stopped = True
        if not enabled:
            return CoreStartupReport(
                startup_state=CoreStartupState.ZERO_CORE_HEALTHY,
                results=(),
                reconciled_at=now,
                enabled_count=0,
                active_count=0,
            )
        for policy in enabled:
            if stopped:
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
                continue
            try:
                authorized = self._is_authorized(policy) is True
            except Exception:
                authorized = False
            if not authorized:
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id, outcome=None, started=False,
                    reason="approval revoked", error_code="REVOKED",
                ))
                continue
            if not self._is_fresh(policy, now):
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id, outcome=None, started=False,
                    reason="policy stale", error_code="STALE_POLICY",
                ))
                continue
            if (
                policy.last_outcome is CoreAutostartOutcome.STARTED
                and policy.last_started_generation == expected_generation
            ):
                active += 1
                results.append(CoreReconciliationResult(
                    core_id=policy.core_id,
                    outcome=CoreAutostartOutcome.STARTED,
                    started=False,
                    reason="already started for this generation",
                ))
                continue
            approval_ref = (
                f"core-autostart:{policy.core_id}:{policy.approved_revision}"
            )
            try:
                raw = self._start_core(
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
        elif failures:
            state = CoreStartupState.DEGRADED
        elif active == len(enabled):
            state = CoreStartupState.HEALTHY
        else:
            state = CoreStartupState.DEGRADED
        return CoreStartupReport(
            startup_state=state,
            results=tuple(results),
            reconciled_at=now,
            enabled_count=len(enabled),
            active_count=active,
        )
