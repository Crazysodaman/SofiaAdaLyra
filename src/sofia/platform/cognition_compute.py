"""Verified Platform operations around the existing model lifecycle manager."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable

from sofia.core.cognition.model_lifecycle import (
    CognitiveModelRole, ModelLifecycleManager, ModelResidency,
)
from sofia.platform.ops.resources import ResourceArbiter, ResourceObservation
from sofia.core.social.model import PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ComputeOperationStatus(str, Enum):
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    SUCCEEDED_VERIFIED = "succeeded_verified"


@dataclass(frozen=True, slots=True)
class ModelIdentityObservation:
    provider: str
    model: str
    digest: str
    host_id: str
    observed_at: datetime

    def __post_init__(self) -> None:
        for value, label in ((self.provider, "provider"), (self.model, "model"),
                             (self.host_id, "host_id")):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} required")
        if not isinstance(self.digest, str) or _DIGEST.fullmatch(self.digest) is None:
            raise ValueError("model digest must be SHA-256")
        if (not isinstance(self.observed_at, datetime)
                or self.observed_at.tzinfo is None
                or self.observed_at.utcoffset() is None):
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ComputeOperationReceipt:
    request_id: str
    operation: str
    role: CognitiveModelRole
    provider: str
    model: str
    model_digest: str
    host_id: str
    status: ComputeOperationStatus
    evidence_ref: str | None
    error_class: str | None
    resource_reservation_id: str | None
    completed_at: datetime
    retry_safe: bool


ComputeAuthorizer = Callable[
    [PrincipalContext, str, CognitiveModelRole, str, str, datetime], bool
]
IdentityProbe = Callable[[CognitiveModelRole, datetime], ModelIdentityObservation]


class ModelComputeOrchestrator:
    """Record and independently verify explicit load/unload operations."""

    def __init__(self, state_path: Path, *, manager: ModelLifecycleManager,
                 resource_arbiter: ResourceArbiter, authorizer: ComputeAuthorizer,
                 identity_probe: IdentityProbe,
                 max_identity_age: timedelta = timedelta(minutes=2)) -> None:
        if not isinstance(state_path, Path) or not isinstance(manager, ModelLifecycleManager):
            raise TypeError("state_path and ModelLifecycleManager required")
        if not isinstance(resource_arbiter, ResourceArbiter):
            raise TypeError("resource_arbiter required")
        if not callable(authorizer) or not callable(identity_probe):
            raise TypeError("authorizer and identity_probe required")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.manager = manager
        self.resource_arbiter = resource_arbiter
        self.authorizer = authorizer
        self.identity_probe = identity_probe
        self.max_identity_age = max_identity_age
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_compute_operation(
                    request_id TEXT PRIMARY KEY,idempotency_key TEXT NOT NULL UNIQUE,
                    request_digest TEXT NOT NULL,operation TEXT NOT NULL,
                    role TEXT NOT NULL,provider TEXT NOT NULL,model TEXT NOT NULL,
                    model_digest TEXT NOT NULL,host_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,audience_id TEXT NOT NULL,
                    authority_ref TEXT NOT NULL,status TEXT NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS platform_compute_receipt(
                    request_id TEXT PRIMARY KEY,operation TEXT NOT NULL,
                    role TEXT NOT NULL,provider TEXT NOT NULL,model TEXT NOT NULL,
                    model_digest TEXT NOT NULL,host_id TEXT NOT NULL,status TEXT NOT NULL,
                    evidence_ref TEXT,error_class TEXT,reservation_id TEXT,
                    completed_at TEXT NOT NULL,retry_safe INTEGER NOT NULL);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("time must be timezone-aware")
        return value.astimezone(timezone.utc)

    def probe(self, role: CognitiveModelRole, *, now: datetime) -> ModelIdentityObservation:
        moment = self._utc(now)
        observed = self.identity_probe(role, moment)
        if not isinstance(observed, ModelIdentityObservation):
            raise TypeError("identity probe returned invalid observation")
        selected = self.manager.provider_for(role)
        age = moment - observed.observed_at.astimezone(timezone.utc)
        if age < -timedelta(seconds=5) or age > self.max_identity_age:
            raise RuntimeError("model identity observation is stale or from the future")
        if observed.provider != selected.provider or observed.model != selected.model:
            raise PermissionError("observed model differs from configured selection")
        return observed

    @staticmethod
    def _receipt(row: sqlite3.Row) -> ComputeOperationReceipt:
        return ComputeOperationReceipt(
            row["request_id"], row["operation"], CognitiveModelRole(row["role"]),
            row["provider"], row["model"], row["model_digest"], row["host_id"],
            ComputeOperationStatus(row["status"]), row["evidence_ref"],
            row["error_class"], row["reservation_id"],
            datetime.fromisoformat(row["completed_at"]), bool(row["retry_safe"]),
        )

    def inspect(self, request_id: str) -> ComputeOperationReceipt | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_compute_receipt WHERE request_id=?",
                (request_id,),
            ).fetchone()
        return None if row is None else self._receipt(row)

    def _begin(self, *, request_id: str, idempotency_key: str, operation: str,
               role: CognitiveModelRole, identity: ModelIdentityObservation,
               principal: PrincipalContext, authority_ref: str,
               now: datetime) -> ComputeOperationReceipt | None:
        for value, label in ((request_id, "request_id"),
                             (idempotency_key, "idempotency_key"),
                             (authority_ref, "authority_ref")):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"invalid {label}")
        document = {
            "operation": operation, "role": role.value,
            "provider": identity.provider, "model": identity.model,
            "digest": identity.digest, "host": identity.host_id,
            "principal": principal.principal_id, "audience": principal.audience_id,
            "authority": authority_ref,
        }
        digest = sha256(json.dumps(
            document, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT request_id,request_digest FROM platform_compute_operation WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is not None:
                if row["request_digest"] != digest:
                    raise RuntimeError("compute idempotency key changed operation")
                receipt = db.execute(
                    "SELECT * FROM platform_compute_receipt WHERE request_id=?",
                    (row["request_id"],),
                ).fetchone()
                if receipt is None:
                    raise RuntimeError("prior compute outcome is unresolved")
                return self._receipt(receipt)
            db.execute(
                """INSERT INTO platform_compute_operation VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,'started',?)""",
                (request_id, idempotency_key, digest, operation, role.value,
                 identity.provider, identity.model, identity.digest,
                 identity.host_id, principal.principal_id, principal.audience_id,
                 authority_ref, now.isoformat()),
            )
        return None

    def _finish(self, receipt: ComputeOperationReceipt) -> ComputeOperationReceipt:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM platform_compute_receipt WHERE request_id=?",
                (receipt.request_id,),
            ).fetchone()
            if existing is not None:
                return self._receipt(existing)
            db.execute(
                """INSERT INTO platform_compute_receipt VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (receipt.request_id, receipt.operation, receipt.role.value,
                 receipt.provider, receipt.model, receipt.model_digest,
                 receipt.host_id, receipt.status.value, receipt.evidence_ref,
                 receipt.error_class, receipt.resource_reservation_id,
                 receipt.completed_at.isoformat(), int(receipt.retry_safe)),
            )
            db.execute(
                "UPDATE platform_compute_operation SET status=? WHERE request_id=?",
                (receipt.status.value, receipt.request_id),
            )
        return receipt

    def load(self, *, request_id: str, idempotency_key: str,
             role: CognitiveModelRole, principal: PrincipalContext,
             authority_ref: str, resource: ResourceObservation,
             resource_amounts: tuple[tuple[str, int], ...],
             now: datetime, expires_at: datetime) -> ComputeOperationReceipt:
        moment = self._utc(now)
        identity = self.probe(role, now=moment)
        replay = self._begin(
            request_id=request_id, idempotency_key=idempotency_key,
            operation="load", role=role, identity=identity,
            principal=principal, authority_ref=authority_ref, now=moment,
        )
        if replay is not None:
            return replay
        if not self.authorizer(
            principal, "load", role, identity.model, authority_ref, moment,
        ):
            return self._finish(ComputeOperationReceipt(
                request_id, "load", role, identity.provider, identity.model,
                identity.digest, identity.host_id, ComputeOperationStatus.DENIED,
                None, "authorization_denied", None, moment, True,
            ))
        reservation_id = f"compute:{request_id}"
        try:
            self.resource_arbiter.reserve(
                resource, reservation_id=reservation_id,
                workload_id=(
                    "model:" + sha256(identity.model.encode("utf-8")).hexdigest()
                ),
                principal_id=principal.principal_id, audience=principal.audience_id,
                amounts=resource_amounts, authority_ref=authority_ref,
                now=moment, expires_at=expires_at, background=False,
            )
        except Exception as exc:
            return self._finish(ComputeOperationReceipt(
                request_id, "load", role, identity.provider, identity.model,
                identity.digest, identity.host_id, ComputeOperationStatus.UNAVAILABLE,
                None, f"resource:{type(exc).__name__}", None, moment, True,
            ))
        status = ComputeOperationStatus.OUTCOME_UNKNOWN
        evidence_ref = None
        error_class = None
        retry_safe = False
        try:
            loaded = self.manager.load(role)
            confirmed = self.probe(role, now=moment)
            if loaded.state is not ModelResidency.READY or confirmed.digest != identity.digest:
                raise RuntimeError("model load verification failed")
            status = ComputeOperationStatus.SUCCEEDED_VERIFIED
            evidence_ref = f"model-probe:{identity.host_id}:{identity.digest}"
            retry_safe = True
        except Exception as exc:
            error_class = f"load:{type(exc).__name__}"
        try:
            self.resource_arbiter.release(
                reservation_id, principal_id=principal.principal_id,
                authority_ref=authority_ref, now=moment,
            )
        except Exception as exc:
            status = ComputeOperationStatus.OUTCOME_UNKNOWN
            evidence_ref = None
            retry_safe = False
            error_class = f"resource_release:{type(exc).__name__}"
        return self._finish(ComputeOperationReceipt(
            request_id, "load", role, identity.provider, identity.model,
            identity.digest, identity.host_id, status, evidence_ref, error_class,
            reservation_id, moment, retry_safe,
        ))

    def unload(self, *, request_id: str, idempotency_key: str,
               role: CognitiveModelRole, principal: PrincipalContext,
               authority_ref: str, now: datetime) -> ComputeOperationReceipt:
        moment = self._utc(now)
        identity = self.probe(role, now=moment)
        replay = self._begin(
            request_id=request_id, idempotency_key=idempotency_key,
            operation="unload", role=role, identity=identity,
            principal=principal, authority_ref=authority_ref, now=moment,
        )
        if replay is not None:
            return replay
        if not self.authorizer(
            principal, "unload", role, identity.model, authority_ref, moment,
        ):
            return self._finish(ComputeOperationReceipt(
                request_id, "unload", role, identity.provider, identity.model,
                identity.digest, identity.host_id, ComputeOperationStatus.DENIED,
                None, "authorization_denied", None, moment, True,
            ))
        try:
            unloaded = self.manager.unload(role)
            if unloaded.state is not ModelResidency.UNLOADED:
                raise RuntimeError("model unload verification failed")
            status = ComputeOperationStatus.SUCCEEDED_VERIFIED
            evidence_ref = f"model-unloaded:{identity.host_id}:{identity.digest}"
            error_class = None
            retry_safe = True
        except Exception as exc:
            status = ComputeOperationStatus.OUTCOME_UNKNOWN
            evidence_ref = None
            error_class = f"unload:{type(exc).__name__}"
            retry_safe = False
        return self._finish(ComputeOperationReceipt(
            request_id, "unload", role, identity.provider, identity.model,
            identity.digest, identity.host_id, status, evidence_ref, error_class,
            None, moment, retry_safe,
        ))

    def reconcile(self, *, now: datetime) -> int:
        moment = self._utc(now)
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM platform_compute_operation o
                LEFT JOIN platform_compute_receipt r ON r.request_id=o.request_id
                WHERE o.status='started' AND r.request_id IS NULL"""
            ).fetchall()
        for row in rows:
            self._finish(ComputeOperationReceipt(
                row["request_id"], row["operation"], CognitiveModelRole(row["role"]),
                row["provider"], row["model"], row["model_digest"], row["host_id"],
                ComputeOperationStatus.OUTCOME_UNKNOWN, None,
                "process_restarted_during_model_operation", None, moment, False,
            ))
        return len(rows)
