"""Owner-established, durable Aegis autonomy policy.

The policy is a protected authorization boundary, not a capability grant and
not an owner credential. Establishment consumes one exact, one-use owner
approval through the existing SAFE verifier. A policy whose owner proof was
revoked, rotated or tampered with resolves as unavailable and every dependent
automatic action fails closed.
"""
from __future__ import annotations

from contextlib import closing, nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import secrets
import sqlite3

from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import (
    ExecutionApprovalVerifier,
    OWNER_PRINCIPAL_ID,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

AUTONOMY_POLICY_SCHEMA = "aegis.safe.autonomy-policy.v1"
AUTONOMY_POLICY_CAPABILITY = "safe.autonomy.policy.change"

PROFILE_OBSERVE = "observe"
PROFILE_ADAPTIVE = "adaptive"
PROFILE_HIGH_AUTONOMY = "high_autonomy"
_PROFILES = frozenset({PROFILE_OBSERVE, PROFILE_ADAPTIVE, PROFILE_HIGH_AUTONOMY})

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_FIELDS = frozenset({
    "schema",
    "policy_id",
    "revision",
    "profile",
    "established_at",
    "established_by",
    "automatic_fleet_admission",
    "automatic_core_migration",
    "mutable_identity_self_development",
    "signed_installation_provenance_required",
    "admission_signer_key_ids",
    "max_initial_permission_level",
    "quarantine_unverified",
    "verified_backup_required_for_migration",
})


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: object, name: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be a bounded identifier")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")
    return value


@dataclass(frozen=True)
class AutonomyPolicy:
    """One exact owner-established autonomy boundary revision."""

    policy_id: str
    revision: int
    profile: str
    established_at: datetime
    established_by: str
    automatic_fleet_admission: bool
    automatic_core_migration: bool
    mutable_identity_self_development: bool
    signed_installation_provenance_required: bool
    admission_signer_key_ids: tuple[str, ...]
    max_initial_permission_level: int
    quarantine_unverified: bool
    verified_backup_required_for_migration: bool

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if self.profile not in _PROFILES:
            raise ValueError("unsupported autonomy profile")
        _aware(self.established_at, "established_at")
        if self.established_by != OWNER_PRINCIPAL_ID:
            raise PermissionError("autonomy policy requires the canonical owner principal")
        for name in (
            "automatic_fleet_admission",
            "automatic_core_migration",
            "mutable_identity_self_development",
            "signed_installation_provenance_required",
            "quarantine_unverified",
            "verified_backup_required_for_migration",
        ):
            _boolean(getattr(self, name), name)
        if type(self.max_initial_permission_level) is not int or not (
            1 <= self.max_initial_permission_level <= 3
        ):
            raise ValueError("automatic admission cannot assign protected authority")
        if type(self.admission_signer_key_ids) is not tuple:
            raise TypeError("admission_signer_key_ids must be a tuple")
        signers = tuple(
            _identifier(value, "admission_signer_key_id")
            for value in self.admission_signer_key_ids
        )
        if len(set(signers)) != len(signers):
            raise ValueError("admission signer key IDs must be unique")
        object.__setattr__(self, "admission_signer_key_ids", signers)
        if self.profile != PROFILE_HIGH_AUTONOMY:
            if self.automatic_fleet_admission or self.automatic_core_migration:
                raise ValueError(
                    "automatic admission and migration require the high-autonomy profile"
                )
        if self.automatic_fleet_admission:
            if not self.signed_installation_provenance_required:
                raise ValueError(
                    "automatic admission requires signed installation provenance"
                )
            if not signers:
                raise ValueError(
                    "automatic admission requires an owner-approved signer key set"
                )
        if self.automatic_core_migration and not (
            self.verified_backup_required_for_migration
        ):
            raise ValueError("automatic migration requires verified backup readiness")

    def to_payload(self) -> dict:
        return {
            "schema": AUTONOMY_POLICY_SCHEMA,
            "policy_id": self.policy_id,
            "revision": self.revision,
            "profile": self.profile,
            "established_at": self.established_at.isoformat(),
            "established_by": self.established_by,
            "automatic_fleet_admission": self.automatic_fleet_admission,
            "automatic_core_migration": self.automatic_core_migration,
            "mutable_identity_self_development": self.mutable_identity_self_development,
            "signed_installation_provenance_required": (
                self.signed_installation_provenance_required
            ),
            "admission_signer_key_ids": list(self.admission_signer_key_ids),
            "max_initial_permission_level": self.max_initial_permission_level,
            "quarantine_unverified": self.quarantine_unverified,
            "verified_backup_required_for_migration": (
                self.verified_backup_required_for_migration
            ),
        }

    def to_parameters(self) -> dict:
        """Exact JSON bound by the owner approval fingerprint."""
        return self.to_payload()


def new_autonomy_policy(
    *,
    profile: str = PROFILE_OBSERVE,
    revision: int = 1,
    now: datetime | None = None,
    policy_id: str | None = None,
    automatic_fleet_admission: bool = False,
    automatic_core_migration: bool = False,
    mutable_identity_self_development: bool = True,
    signed_installation_provenance_required: bool = True,
    admission_signer_key_ids: tuple[str, ...] = (),
    max_initial_permission_level: int = 1,
    quarantine_unverified: bool = True,
    verified_backup_required_for_migration: bool = True,
) -> AutonomyPolicy:
    return AutonomyPolicy(
        policy_id=policy_id or f"autonomy-{secrets.token_hex(16)}",
        revision=revision,
        profile=profile,
        established_at=_aware(now or datetime.now(timezone.utc), "now"),
        established_by=OWNER_PRINCIPAL_ID,
        automatic_fleet_admission=automatic_fleet_admission,
        automatic_core_migration=automatic_core_migration,
        mutable_identity_self_development=mutable_identity_self_development,
        signed_installation_provenance_required=(
            signed_installation_provenance_required
        ),
        admission_signer_key_ids=tuple(admission_signer_key_ids),
        max_initial_permission_level=max_initial_permission_level,
        quarantine_unverified=quarantine_unverified,
        verified_backup_required_for_migration=(
            verified_backup_required_for_migration
        ),
    )


def _policy_from_payload(payload: object) -> AutonomyPolicy:
    if type(payload) is not dict or set(payload) != _FIELDS:
        raise PermissionError("autonomy policy payload schema is unsupported")
    if payload["schema"] != AUTONOMY_POLICY_SCHEMA:
        raise PermissionError("autonomy policy schema is unsupported")
    try:
        return AutonomyPolicy(
            policy_id=payload["policy_id"],
            revision=payload["revision"],
            profile=payload["profile"],
            established_at=datetime.fromisoformat(payload["established_at"]),
            established_by=payload["established_by"],
            automatic_fleet_admission=payload["automatic_fleet_admission"],
            automatic_core_migration=payload["automatic_core_migration"],
            mutable_identity_self_development=(
                payload["mutable_identity_self_development"]
            ),
            signed_installation_provenance_required=(
                payload["signed_installation_provenance_required"]
            ),
            admission_signer_key_ids=tuple(payload["admission_signer_key_ids"]),
            max_initial_permission_level=payload["max_initial_permission_level"],
            quarantine_unverified=payload["quarantine_unverified"],
            verified_backup_required_for_migration=(
                payload["verified_backup_required_for_migration"]
            ),
        )
    except PermissionError:
        raise
    except (TypeError, ValueError) as exc:
        raise PermissionError("autonomy policy payload is invalid") from exc


class AutonomyPolicyStore:
    """Canonical owner-authenticated autonomy policy revisions."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        self.verifier = ExecutionApprovalVerifier(self.path)
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_autonomy_policy (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    policy_json TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK(revision>0),
                    approval_id TEXT NOT NULL UNIQUE,
                    established_at TEXT NOT NULL,
                    established_by TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self.guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _row_policy(
        self, db: sqlite3.Connection, row: sqlite3.Row | None,
    ) -> AutonomyPolicy | None:
        if row is None:
            return None
        try:
            payload = json.loads(row["policy_json"])
        except (TypeError, ValueError) as exc:
            raise PermissionError("autonomy policy is corrupt") from exc
        policy = _policy_from_payload(payload)
        if (
            policy.revision != row["revision"]
            or policy.established_at.astimezone(timezone.utc).isoformat()
            != datetime.fromisoformat(row["established_at"]).astimezone(
                timezone.utc
            ).isoformat()
            or policy.established_by != row["established_by"]
        ):
            raise PermissionError("autonomy policy columns disagree with payload")
        if not ExecutionApprovalVerifier.owner_proof_remains_current_in_connection(
            db,
            approval_id=row["approval_id"],
            capability=AUTONOMY_POLICY_CAPABILITY,
            parameters=policy.to_parameters(),
        ):
            raise PermissionError("autonomy policy owner proof is not current")
        return policy

    def resolve(
        self,
        *,
        now: datetime | None = None,
        _transaction_db: sqlite3.Connection | None = None,
    ) -> AutonomyPolicy | None:
        """Return the active owner-bound policy, or None when never established."""
        _aware(now or datetime.now(timezone.utc), "now")
        context = (
            closing(self._connect())
            if _transaction_db is None
            else nullcontext(_transaction_db)
        )
        with context as db:
            previous = db.row_factory
            db.row_factory = sqlite3.Row
            try:
                row = db.execute(
                    "SELECT policy_json,revision,approval_id,established_at,"
                    "established_by FROM safe_autonomy_policy WHERE singleton=1"
                ).fetchone()
                return self._row_policy(db, row)
            finally:
                db.row_factory = previous

    def establish(
        self,
        policy: AutonomyPolicy,
        *,
        approval_id: str,
        now: datetime | None = None,
    ) -> AutonomyPolicy:
        if not isinstance(policy, AutonomyPolicy):
            raise TypeError("policy must be an AutonomyPolicy")
        moment = _aware(now or datetime.now(timezone.utc), "now")
        if abs((moment - policy.established_at).total_seconds()) > 300:
            raise PermissionError("autonomy policy establishment window expired")
        with closing(self._connect()) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision FROM safe_autonomy_policy WHERE singleton=1"
            ).fetchone()
            expected = 1 if row is None else int(row["revision"]) + 1
            if policy.revision != expected:
                raise PermissionError(
                    "autonomy policy revision is stale or out of sequence"
                )
            approved = self.verifier.consume(
                approval_id=approval_id,
                capability=AUTONOMY_POLICY_CAPABILITY,
                parameters=policy.to_parameters(),
                now=moment,
                _transaction_db=db,
            )
            if approved.principal_id != OWNER_PRINCIPAL_ID:
                raise PermissionError("autonomy policy requires owner approval")
            db.execute(
                """
                INSERT INTO safe_autonomy_policy (
                    singleton,policy_json,revision,approval_id,
                    established_at,established_by
                ) VALUES(1,?,?,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                    policy_json=excluded.policy_json,
                    revision=excluded.revision,
                    approval_id=excluded.approval_id,
                    established_at=excluded.established_at,
                    established_by=excluded.established_by
                """,
                (
                    json.dumps(
                        policy.to_payload(), sort_keys=True, separators=(",", ":"),
                        ensure_ascii=False, allow_nan=False,
                    ),
                    policy.revision,
                    approval_id,
                    policy.established_at.isoformat(),
                    policy.established_by,
                ),
            )
            self.audit.append_in_transaction(
                db,
                actor_id=OWNER_PRINCIPAL_ID,
                event_type="autonomy.policy.established",
                payload={
                    "policy_id": policy.policy_id,
                    "revision": policy.revision,
                    "profile": policy.profile,
                    "automatic_fleet_admission": policy.automatic_fleet_admission,
                    "automatic_core_migration": policy.automatic_core_migration,
                },
                occurred_at=moment,
                event_id=f"autonomy-policy:{approval_id}",
            )
        return policy


def approval_parameters(policy: AutonomyPolicy) -> dict:
    """Exact owner approval parameters for one policy revision."""
    if not isinstance(policy, AutonomyPolicy):
        raise TypeError("policy must be an AutonomyPolicy")
    return policy.to_parameters()
