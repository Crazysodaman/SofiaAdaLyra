"""Durable PLAT-04 effect envelope over canonical RUN and CapabilityGateway."""
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
from threading import Event
from typing import Callable
from uuid import uuid4

from sofia.platform.capability.gateway import CapabilityGateway
from sofia.platform.capability.model import CapabilityProposal, CapabilityResultKind
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.core.social.model import PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .work import DurableWorkStore, WorkJob, WorkResult, WorkStatus


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class EffectStatus(str, Enum):
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OUTCOME_UNKNOWN = "outcome_unknown"
    SUCCEEDED_REPORTED_UNVERIFIED = "succeeded_reported_unverified"
    SUCCEEDED_VERIFIED = "succeeded_verified"


@dataclass(frozen=True, slots=True)
class EffectRequest:
    request_id: str
    idempotency_key: str
    principal: PrincipalContext
    principal_attestation_ref: str
    proposal: CapabilityProposal
    expected_effect: str
    expires_at: datetime
    correlation_id: str
    risk: str
    priority: int = 50
    resource_cost: int = 10

    def __post_init__(self) -> None:
        for label, value in (
            ("request_id", self.request_id),
            ("idempotency_key", self.idempotency_key),
            ("principal_attestation_ref", self.principal_attestation_ref),
            ("correlation_id", self.correlation_id),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded identifier")
        if not isinstance(self.principal, PrincipalContext):
            raise TypeError("principal must be authenticated PrincipalContext")
        if not isinstance(self.proposal, CapabilityProposal):
            raise TypeError("proposal must be CapabilityProposal")
        if not isinstance(self.expected_effect, str) or not self.expected_effect.strip():
            raise ValueError("expected_effect required")
        _utc(self.expires_at)
        if self.risk not in {"read_only", "isolated_change", "protected"}:
            raise ValueError("unsupported risk")
        if type(self.priority) is not int or not 0 <= self.priority <= 100:
            raise ValueError("priority must be in 0..100")
        if type(self.resource_cost) is not int or not 1 <= self.resource_cost <= 100:
            raise ValueError("resource_cost must be in 1..100")


@dataclass(frozen=True, slots=True)
class EffectReceipt:
    request_id: str
    job_id: str
    attempt_id: str
    status: EffectStatus
    capability: str
    principal_id: str
    audience_id: str
    observed_effect: str | None
    verification_method: str | None
    evidence_ref: str | None
    error_class: str | None
    retry_safe: bool
    completed_at: datetime


PrincipalAttestationVerifier = Callable[[PrincipalContext, str, datetime], bool]
EffectVerifier = Callable[[EffectRequest, object], tuple[bool, str | None]]


class EffectBroker:
    """Create and settle effects through existing RUN and capability owners."""

    WORK_KIND = "platform.effect"

    def __init__(
        self,
        *,
        state_path: Path,
        work_store: DurableWorkStore,
        gateway: CapabilityGateway,
        operator_stop: OperatorStopStore,
        principal_verifier: PrincipalAttestationVerifier,
        effect_verifier: EffectVerifier | None = None,
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be Path")
        if not isinstance(work_store, DurableWorkStore):
            raise TypeError("work_store must be DurableWorkStore")
        if work_store.path.resolve() != state_path.resolve():
            raise ValueError("effect broker and RUN must share canonical state")
        if not isinstance(gateway, CapabilityGateway):
            raise TypeError("gateway must be CapabilityGateway")
        if not isinstance(operator_stop, OperatorStopStore):
            raise TypeError("operator_stop must be OperatorStopStore")
        if not callable(principal_verifier):
            raise TypeError("principal_verifier must be callable")
        if effect_verifier is not None and not callable(effect_verifier):
            raise TypeError("effect_verifier must be callable or None")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.work_store = work_store
        self.gateway = gateway
        self.operator_stop = operator_stop
        self.principal_verifier = principal_verifier
        self.effect_verifier = effect_verifier
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_effect_request(
                    request_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    audience_kind TEXT NOT NULL,
                    attestation_ref TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    requested_scope_json TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    expected_effect TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(principal_id,audience_id,idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS platform_effect_receipt(
                    attempt_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    job_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    observed_effect TEXT,
                    verification_method TEXT,
                    evidence_ref TEXT,
                    error_class TEXT,
                    retry_safe INTEGER NOT NULL CHECK(retry_safe IN (0,1)),
                    completed_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _document(request: EffectRequest) -> dict[str, object]:
        return {
            "audience_id": request.principal.audience_id,
            "audience_kind": request.principal.audience_kind.value,
            "capability": request.proposal.capability_name,
            "correlation_id": request.correlation_id,
            "expected_effect": request.expected_effect,
            "expires_at": request.expires_at.astimezone(timezone.utc).isoformat(),
            "idempotency_key": request.idempotency_key,
            "parameters": request.proposal.parameters,
            "requested_scope": request.proposal.requested_scope,
            "principal_id": request.principal.principal_id,
            "rationale": request.proposal.rationale,
            "request_id": request.request_id,
        }

    @classmethod
    def _encoded(cls, request: EffectRequest) -> tuple[str, str]:
        try:
            encoded = json.dumps(
                cls._document(request), sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("effect request must be canonical JSON data") from exc
        if len(encoded.encode("utf-8")) > 64_000:
            raise ValueError("effect request exceeds 64-KiB bound")
        return encoded, sha256(encoded.encode("utf-8")).hexdigest()

    def submit(self, request: EffectRequest, *, now: datetime) -> WorkJob:
        if not isinstance(request, EffectRequest):
            raise TypeError("request must be EffectRequest")
        moment = _utc(now)
        if moment >= _utc(request.expires_at):
            raise ValueError("expired effect request")
        encoded, digest = self._encoded(request)
        fingerprint = "effect:" + sha256(
            (request.principal.principal_id + "\0" + request.principal.audience_id
             + "\0" + request.idempotency_key).encode("utf-8")
        ).hexdigest()

        def bind(db: sqlite3.Connection, job: WorkJob) -> None:
            row = db.execute(
                """SELECT request_id,request_digest,job_id FROM platform_effect_request
                WHERE principal_id=? AND audience_id=? AND idempotency_key=?""",
                (request.principal.principal_id, request.principal.audience_id,
                 request.idempotency_key),
            ).fetchone()
            if row is not None:
                if row[1] != digest or row[2] != job.job_id:
                    raise RuntimeError("effect idempotency key changed request")
                return
            db.execute(
                """INSERT INTO platform_effect_request VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (request.request_id, request.idempotency_key, digest, job.job_id,
                 request.principal.principal_id, request.principal.audience_id,
                 request.principal.audience_kind.value,
                 request.principal_attestation_ref,
                 request.proposal.capability_name,
                 json.dumps(request.proposal.parameters, sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False),
                 json.dumps(request.proposal.requested_scope, sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False),
                 request.proposal.rationale, request.expected_effect,
                 request.expires_at.astimezone(timezone.utc).isoformat(),
                 request.correlation_id, moment.isoformat()),
            )

        try:
            return self.work_store.enqueue(
                kind=self.WORK_KIND, fingerprint=fingerprint,
                payload={"request_id": request.request_id, "request_digest": digest},
                priority=request.priority, resource_cost=request.resource_cost,
                risk=request.risk, completion_condition="verified effect receipt",
                now=moment, deadline=request.expires_at, after_enqueue=bind,
            )
        except RuntimeError as exc:
            if "fingerprint collision" in str(exc):
                raise RuntimeError(
                    "effect idempotency key changed the original request"
                ) from exc
            raise

    def _load_request(self, job: WorkJob) -> EffectRequest:
        from sofia.core.social.model import AudienceKind
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_effect_request WHERE job_id=?",
                (job.job_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("RUN job has no bound effect request")
        principal = PrincipalContext(
            row["principal_id"], row["audience_id"],
            AudienceKind(row["audience_kind"]),
        )
        proposal = CapabilityProposal(
            row["capability"], json.loads(row["parameters_json"]),
            row["rationale"],
            requested_scope=json.loads(row["requested_scope_json"]),
        )
        return EffectRequest(
            request_id=row["request_id"], idempotency_key=row["idempotency_key"],
            principal=principal, principal_attestation_ref=row["attestation_ref"],
            proposal=proposal, expected_effect=row["expected_effect"],
            expires_at=datetime.fromisoformat(row["expires_at"]),
            correlation_id=row["correlation_id"], risk=job.risk,
            priority=job.priority, resource_cost=job.resource_cost,
        )

    def _persist_receipt(self, receipt: EffectReceipt) -> EffectReceipt:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM platform_effect_receipt WHERE request_id=?",
                (receipt.request_id,),
            ).fetchone()
            if existing is not None:
                return self._receipt(existing)
            db.execute(
                """INSERT INTO platform_effect_receipt VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (receipt.attempt_id, receipt.request_id, receipt.job_id,
                 receipt.status.value, receipt.capability, receipt.principal_id,
                 receipt.audience_id, receipt.observed_effect,
                 receipt.verification_method, receipt.evidence_ref,
                 receipt.error_class, int(receipt.retry_safe),
                 receipt.completed_at.isoformat()),
            )
        return receipt

    @staticmethod
    def _receipt(row: sqlite3.Row) -> EffectReceipt:
        return EffectReceipt(
            row["request_id"], row["job_id"], row["attempt_id"],
            EffectStatus(row["status"]), row["capability"], row["principal_id"],
            row["audience_id"], row["observed_effect"],
            row["verification_method"], row["evidence_ref"], row["error_class"],
            bool(row["retry_safe"]), datetime.fromisoformat(row["completed_at"]),
        )

    def inspect(self, request_id: str) -> EffectReceipt | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_effect_receipt WHERE request_id=?",
                (request_id,),
            ).fetchone()
        return None if row is None else self._receipt(row)

    def handler(self, job: WorkJob, cancel: Event) -> WorkResult:
        """Reviewed handler registered with the existing TaskExecutionManager."""
        now = datetime.now(timezone.utc)
        request = self._load_request(job)
        status: EffectStatus
        observed: str | None = None
        verification: str | None = None
        evidence_ref: str | None = None
        error_class: str | None = None
        retry_safe = True
        if cancel.is_set():
            status = EffectStatus.CANCELLED
        elif now >= request.expires_at:
            status = EffectStatus.DENIED
            error_class = "request_expired"
        elif self.operator_stop.current().active:
            status = EffectStatus.DENIED
            error_class = "operator_stop"
        else:
            try:
                principal_current = self.principal_verifier(
                    request.principal, request.principal_attestation_ref, now,
                )
            except Exception:
                principal_current = False
                error_class = "principal_attestation_unavailable"
            if not principal_current:
                status = EffectStatus.DENIED
                error_class = error_class or "principal_attestation_invalid"
                result = None
            else:
                result = self.gateway.execute(request.proposal)
            if result is None:
                pass
            elif cancel.is_set():
                status = EffectStatus.OUTCOME_UNKNOWN
                error_class = "cancelled_after_dispatch"
                retry_safe = False
            elif result.kind in {
                CapabilityResultKind.UNAUTHORIZED, CapabilityResultKind.DENIED,
            }:
                status = EffectStatus.DENIED
                error_class = result.kind.value
            elif result.kind is CapabilityResultKind.UNAVAILABLE:
                status = EffectStatus.UNAVAILABLE
                error_class = "capability_unavailable"
            elif result.kind is CapabilityResultKind.FAILED:
                status = EffectStatus.OUTCOME_UNKNOWN
                error_class = "capability_failed_after_dispatch"
                retry_safe = False
            else:
                status = EffectStatus.SUCCEEDED_REPORTED_UNVERIFIED
                observed = request.expected_effect
                if self.effect_verifier is not None:
                    try:
                        verified, reference = self.effect_verifier(
                            request, result.evidence,
                        )
                    except Exception:
                        verified, reference = False, None
                        error_class = "effect_verification_unavailable"
                    if verified and isinstance(reference, str) and reference.strip():
                        status = EffectStatus.SUCCEEDED_VERIFIED
                        verification = "independent_effect_verifier"
                        evidence_ref = reference
        receipt = self._persist_receipt(EffectReceipt(
            request.request_id, job.job_id, f"attempt:{uuid4()}", status,
            request.proposal.capability_name, request.principal.principal_id,
            request.principal.audience_id, observed, verification, evidence_ref,
            error_class, retry_safe, now,
        ))
        if receipt.status is EffectStatus.SUCCEEDED_VERIFIED:
            work_status = WorkStatus.COMPLETED
        elif receipt.status is EffectStatus.OUTCOME_UNKNOWN:
            work_status = WorkStatus.UNCERTAIN
        elif receipt.status is EffectStatus.CANCELLED:
            # WorkResult intentionally cannot self-award CANCELLED: the RUN
            # executor owns that transition and records a running cancellation
            # as uncertain. The effect receipt may still precisely prove this
            # handler observed cancellation before capability dispatch.
            work_status = WorkStatus.FAILED
        else:
            work_status = WorkStatus.FAILED
        return WorkResult(
            work_status,
            {"effect_request_id": receipt.request_id,
             "effect_status": receipt.status.value,
             "attempt_id": receipt.attempt_id},
            receipt.error_class or receipt.status.value,
        )

    def reconcile(self, *, now: datetime) -> int:
        """Mark interrupted RUN effects unknown; never replay them."""
        self.work_store.recover(now=now)
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT r.*,j.status FROM platform_effect_request r
                JOIN autonomous_work_job j ON j.job_id=r.job_id
                LEFT JOIN platform_effect_receipt p ON p.request_id=r.request_id
                WHERE j.status='uncertain' AND p.request_id IS NULL"""
            ).fetchall()
        for row in rows:
            self._persist_receipt(EffectReceipt(
                row["request_id"], row["job_id"], f"attempt:{uuid4()}",
                EffectStatus.OUTCOME_UNKNOWN, row["capability"],
                row["principal_id"], row["audience_id"], None, None, None,
                "process_restarted_during_execution", False, _utc(now),
            ))
        return len(rows)
