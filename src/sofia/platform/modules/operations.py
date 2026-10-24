"""Durable RUN admission and reconciliation for external module activation."""
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
from typing import TYPE_CHECKING

from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID
from sofia.platform.run.work import (
    DurableWorkStore,
    TaskExecutionManager,
    WorkJob,
    WorkResult,
    WorkStatus,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .adapters import AdapterFactoryRegistry, AdapterInspection
from .compatibility import evaluate_module_compatibility
from .lifecycle import ModuleLifecycle
from .package import OperationProfileKind

if TYPE_CHECKING:
    from sofia.platform.application.module_lifecycle import ModuleLifecycleCommandService


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class ModuleOperationType(str, Enum):
    APPROVE = "approve"
    STAGE = "stage"
    ACTIVATE = "activate"
    PAUSE = "pause"
    RESUME = "resume"
    DISABLE = "disable"
    QUARANTINE = "quarantine"
    UPDATE = "update"
    ROLLBACK = "rollback"
    REMOVE = "remove"


class ModuleCancellationPolicy(str, Enum):
    BEFORE_EXTERNAL_DISPATCH_ONLY = "before_external_dispatch_only"
    COOPERATIVE_SAFE_STOP = "cooperative_safe_stop"


class ModuleAttemptStatus(str, Enum):
    ADMITTED = "admitted"
    RUNNING = "running"
    DENIED = "denied"
    CANCELLED_BEFORE_DISPATCH = "cancelled_before_dispatch"
    FAILED_BEFORE_EXTERNAL_EFFECT = "failed_before_external_effect"
    EXTERNAL_EFFECT_ATTEMPTED = "external_effect_attempted"
    OUTCOME_UNKNOWN = "outcome_unknown"
    EXTERNALLY_VERIFIED_SUCCESS = "externally_verified_success"
    EXTERNALLY_VERIFIED_FAILURE = "externally_verified_failure"


@dataclass(frozen=True, slots=True)
class ModuleOperationRequest:
    request_id: str
    idempotency_key: str
    module_id: str
    package_digest: str
    operation: ModuleOperationType
    expected_revision: int
    source_lifecycle: ModuleLifecycle
    destination_lifecycle: ModuleLifecycle
    profile: OperationProfileKind
    principal: PrincipalContext
    principal_attestation_ref: str
    approval_id: str
    component_id: str
    host_identity: str
    deadline: datetime
    correlation_id: str
    resource_lease_refs: tuple[str, ...]
    device_lease_refs: tuple[str, ...]
    requested_effect: str
    cancellation_policy: ModuleCancellationPolicy

    def __post_init__(self) -> None:
        for label, value in (
            ("request_id", self.request_id),
            ("idempotency_key", self.idempotency_key),
            ("module_id", self.module_id),
            ("principal_attestation_ref", self.principal_attestation_ref),
            ("approval_id", self.approval_id),
            ("component_id", self.component_id),
            ("host_identity", self.host_identity),
            ("correlation_id", self.correlation_id),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded identifier")
        if _DIGEST.fullmatch(self.package_digest) is None:
            raise ValueError("package_digest must be SHA-256")
        if not isinstance(self.operation, ModuleOperationType):
            raise TypeError("operation must be ModuleOperationType")
        if type(self.expected_revision) is not int or self.expected_revision < 1:
            raise ValueError("expected_revision must be positive")
        if not isinstance(self.source_lifecycle, ModuleLifecycle) or not isinstance(
            self.destination_lifecycle, ModuleLifecycle
        ):
            raise TypeError("source/destination lifecycle must be typed")
        if not isinstance(self.profile, OperationProfileKind):
            raise TypeError("profile must be OperationProfileKind")
        if not isinstance(self.principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext")
        if self.principal.audience_kind is not AudienceKind.PRIVATE:
            raise PermissionError("module operation requires private audience")
        for label, refs in (
            ("resource_lease_refs", self.resource_lease_refs),
            ("device_lease_refs", self.device_lease_refs),
        ):
            if type(refs) is not tuple or len(refs) > 32 or any(
                not isinstance(item, str) or _ID.fullmatch(item) is None
                for item in refs
            ):
                raise ValueError(f"{label} must be bounded references")
        if not isinstance(self.requested_effect, str) or not self.requested_effect.strip():
            raise ValueError("requested_effect required")
        if len(self.requested_effect) > 500:
            raise ValueError("requested_effect is too long")
        if not isinstance(self.cancellation_policy, ModuleCancellationPolicy):
            raise TypeError("cancellation_policy must be typed")
        _utc(self.deadline)


@dataclass(frozen=True, slots=True)
class ModuleAttemptEvent:
    event_id: int
    request_id: str
    job_id: str
    status: ModuleAttemptStatus
    attempt_number: int
    detail: str
    evidence_ref: str | None
    occurred_at: datetime


class ModuleOperationCoordinator:
    """Register one reviewed module handler in the existing RUN executor."""

    WORK_KIND = "platform.module.operation"

    def __init__(
        self, *, state_path: Path,
        lifecycle: "ModuleLifecycleCommandService",
        factories: AdapterFactoryRegistry,
        work_store: DurableWorkStore,
        manager: TaskExecutionManager,
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be Path")
        if not all(callable(getattr(lifecycle, name, None)) for name in (
            "describe", "begin_activation", "complete_activation",
        )) or not hasattr(lifecycle, "manager"):
            raise TypeError("lifecycle service required")
        if not isinstance(factories, AdapterFactoryRegistry):
            raise TypeError("adapter factory registry required")
        if not isinstance(work_store, DurableWorkStore) or not isinstance(
            manager, TaskExecutionManager
        ):
            raise TypeError("canonical RUN store and manager required")
        if work_store.path.resolve() != state_path.resolve() or manager.store is not work_store:
            raise ValueError("module operations must share canonical RUN ownership")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.lifecycle = lifecycle
        self.factories = factories
        self.work_store = work_store
        self.manager = manager
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_module_operation_request(
                    request_id TEXT PRIMARY KEY,idempotency_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,job_id TEXT NOT NULL UNIQUE,
                    module_id TEXT NOT NULL,package_digest TEXT NOT NULL,
                    operation TEXT NOT NULL,expected_revision INTEGER NOT NULL,
                    source_lifecycle TEXT NOT NULL,destination_lifecycle TEXT NOT NULL,
                    profile TEXT NOT NULL,principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,audience_kind TEXT NOT NULL,
                    principal_attestation_ref TEXT NOT NULL,approval_id TEXT NOT NULL,
                    component_id TEXT NOT NULL,host_identity TEXT NOT NULL,
                    deadline TEXT NOT NULL,correlation_id TEXT NOT NULL,
                    resource_lease_refs_json TEXT NOT NULL,
                    device_lease_refs_json TEXT NOT NULL,requested_effect TEXT NOT NULL,
                    cancellation_policy TEXT NOT NULL,created_at TEXT NOT NULL,
                    UNIQUE(principal_id,audience_id,idempotency_key));
                CREATE TABLE IF NOT EXISTS platform_module_operation_attempt(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,job_id TEXT NOT NULL,
                    status TEXT NOT NULL,attempt_number INTEGER NOT NULL,
                    detail TEXT NOT NULL,evidence_ref TEXT,occurred_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS platform_module_operation_attempt_request
                    ON platform_module_operation_attempt(request_id,event_id);
                """
            )
        self.manager.register_handler(self.WORK_KIND, self.handler)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _document(request: ModuleOperationRequest) -> dict[str, object]:
        return {
            "approval_id": request.approval_id,
            "audience_id": request.principal.audience_id,
            "audience_kind": request.principal.audience_kind.value,
            "cancellation_policy": request.cancellation_policy.value,
            "component_id": request.component_id,
            "correlation_id": request.correlation_id,
            "deadline": _utc(request.deadline).isoformat(),
            "destination_lifecycle": request.destination_lifecycle.value,
            "device_lease_refs": list(request.device_lease_refs),
            "expected_revision": request.expected_revision,
            "host_identity": request.host_identity,
            "idempotency_key": request.idempotency_key,
            "module_id": request.module_id,
            "operation": request.operation.value,
            "package_digest": request.package_digest,
            "principal_attestation_ref": request.principal_attestation_ref,
            "principal_id": request.principal.principal_id,
            "profile": request.profile.value,
            "request_id": request.request_id,
            "requested_effect": request.requested_effect,
            "resource_lease_refs": list(request.resource_lease_refs),
            "source_lifecycle": request.source_lifecycle.value,
        }

    @classmethod
    def _encoded(cls, request: ModuleOperationRequest) -> tuple[str, str]:
        encoded = json.dumps(
            cls._document(request), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > 64_000:
            raise ValueError("module operation request exceeds 64 KiB")
        return encoded, sha256(encoded.encode("utf-8")).hexdigest()

    def _event(
        self, *, request_id: str, job_id: str, status: ModuleAttemptStatus,
        attempt_number: int, detail: str, now: datetime,
        evidence_ref: str | None = None,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO platform_module_operation_attempt "
                "VALUES(NULL,?,?,?,?,?,?,?)",
                (request_id, job_id, status.value, attempt_number,
                 detail[:500], evidence_ref, _utc(now).isoformat()),
            )

    def submit(self, request: ModuleOperationRequest, *, now: datetime) -> WorkJob:
        if not isinstance(request, ModuleOperationRequest):
            raise TypeError("request must be ModuleOperationRequest")
        moment = _utc(now)
        if moment >= _utc(request.deadline):
            raise ValueError("module operation request expired")
        if request.operation is not ModuleOperationType.ACTIVATE:
            raise ValueError(
                "this operation remains synchronous; no external RUN dispatch required"
            )
        encoded, digest = self._encoded(request)
        fingerprint = "module-operation:" + sha256(
            (request.principal.principal_id + "\0" + request.principal.audience_id
             + "\0" + request.idempotency_key).encode("utf-8")
        ).hexdigest()

        def bind(db: sqlite3.Connection, job: WorkJob) -> None:
            existing = db.execute(
                "SELECT request_digest,job_id FROM platform_module_operation_request "
                "WHERE principal_id=? AND audience_id=? AND idempotency_key=?",
                (request.principal.principal_id, request.principal.audience_id,
                 request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing[0] != digest or existing[1] != job.job_id:
                    raise RuntimeError("module operation idempotency key changed request")
                return
            document = json.loads(encoded)
            db.execute(
                "INSERT INTO platform_module_operation_request VALUES("
                + ",".join("?" for _ in range(25)) + ")",
                (
                    request.request_id, request.idempotency_key, digest, job.job_id,
                    request.module_id, request.package_digest, request.operation.value,
                    request.expected_revision, request.source_lifecycle.value,
                    request.destination_lifecycle.value, request.profile.value,
                    request.principal.principal_id, request.principal.audience_id,
                    request.principal.audience_kind.value,
                    request.principal_attestation_ref, request.approval_id,
                    request.component_id, request.host_identity,
                    document["deadline"], request.correlation_id,
                    json.dumps(document["resource_lease_refs"], separators=(",", ":")),
                    json.dumps(document["device_lease_refs"], separators=(",", ":")),
                    request.requested_effect, request.cancellation_policy.value,
                    moment.isoformat(),
                ),
            )
            db.execute(
                "INSERT INTO platform_module_operation_attempt "
                "VALUES(NULL,?,?,?,0,?,NULL,?)",
                (request.request_id, job.job_id, ModuleAttemptStatus.ADMITTED.value,
                 "durable RUN admission", moment.isoformat()),
            )

        return self.manager.submit(
            kind=self.WORK_KIND, fingerprint=fingerprint,
            payload={"request_id": request.request_id, "request_digest": digest},
            priority=70, resource_cost=20, risk="protected",
            completion_condition="verified module adapter observation",
            now=moment, deadline=request.deadline, after_enqueue=bind,
        )

    @staticmethod
    def _request(row: sqlite3.Row) -> ModuleOperationRequest:
        return ModuleOperationRequest(
            request_id=row["request_id"], idempotency_key=row["idempotency_key"],
            module_id=row["module_id"], package_digest=row["package_digest"],
            operation=ModuleOperationType(row["operation"]),
            expected_revision=int(row["expected_revision"]),
            source_lifecycle=ModuleLifecycle(row["source_lifecycle"]),
            destination_lifecycle=ModuleLifecycle(row["destination_lifecycle"]),
            profile=OperationProfileKind(row["profile"]),
            principal=PrincipalContext(
                row["principal_id"], row["audience_id"],
                AudienceKind(row["audience_kind"]),
            ),
            principal_attestation_ref=row["principal_attestation_ref"],
            approval_id=row["approval_id"], component_id=row["component_id"],
            host_identity=row["host_identity"],
            deadline=datetime.fromisoformat(row["deadline"]),
            correlation_id=row["correlation_id"],
            resource_lease_refs=tuple(json.loads(row["resource_lease_refs_json"])),
            device_lease_refs=tuple(json.loads(row["device_lease_refs_json"])),
            requested_effect=row["requested_effect"],
            cancellation_policy=ModuleCancellationPolicy(row["cancellation_policy"]),
        )

    def _load_request(self, job: WorkJob) -> ModuleOperationRequest:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_module_operation_request WHERE job_id=?",
                (job.job_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("RUN job has no bound module operation")
        request = self._request(row)
        _, digest = self._encoded(request)
        if digest != job.payload.get("request_digest"):
            raise RuntimeError("module operation request digest changed")
        return request

    def _request_for_id(self, request_id: str) -> tuple[ModuleOperationRequest, WorkJob]:
        DurableWorkStore._validate_id(request_id, "request_id")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_module_operation_request WHERE request_id=?",
                (request_id,),
            ).fetchone()
        if row is None:
            raise LookupError("module operation request does not exist")
        request = self._request(row)
        job = self.work_store.get(row["job_id"])
        _, digest = self._encoded(request)
        if digest != job.payload.get("request_digest"):
            raise RuntimeError("module operation request digest changed")
        return request, job

    @staticmethod
    def _verified_inspection(
        request: ModuleOperationRequest, inspection: AdapterInspection,
        *, now: datetime | None = None,
    ) -> bool:
        moment = datetime.now(timezone.utc) if now is None else _utc(now)
        observed = _utc(inspection.observed_at)
        return (
            inspection.module_id == request.module_id
            and inspection.package_digest == request.package_digest
            and inspection.component_id == request.component_id
            and inspection.host_identity == request.host_identity
            and inspection.state.value == "running"
            and inspection.ready
            and bool(inspection.evidence_ref)
            and moment - timedelta(minutes=5) <= observed <= moment + timedelta(seconds=5)
        )

    def _reconstruct(self, request: ModuleOperationRequest):
        """Rebuild only the reviewed, inert inspection boundary."""
        package = self.lifecycle.manager.reopen_staged_package(request.module_id)
        factory = self.factories.resolve(
            module_id=request.module_id, package_digest=request.package_digest,
            profile=request.profile, component_id=request.component_id,
            host_identity=request.host_identity,
        )
        adapter = factory.reconstruct_for_inspection(
            package=package, profile=request.profile,
            component_id=request.component_id,
            host_identity=request.host_identity,
        )
        compatibility = evaluate_module_compatibility(
            package.manifest, profile=request.profile,
            target=factory.platform_target,
        )
        if not compatibility.compatible:
            raise PermissionError("authoritative target compatibility failed")
        registrations = adapter.capability_registrations()
        self.lifecycle.manager.capability_system.validate_batch(registrations)
        return package, adapter, compatibility, registrations

    def handler(self, job: WorkJob, cancel: Event) -> WorkResult:
        now = datetime.now(timezone.utc)
        request = self._load_request(job)
        attempt = max(1, job.attempt_count)
        self._event(
            request_id=request.request_id, job_id=job.job_id,
            status=ModuleAttemptStatus.RUNNING, attempt_number=attempt,
            detail="reviewed RUN handler claimed request", now=now,
        )
        if cancel.is_set():
            self._event(
                request_id=request.request_id, job_id=job.job_id,
                status=ModuleAttemptStatus.CANCELLED_BEFORE_DISPATCH,
                attempt_number=attempt, detail="cancelled before authority consumption",
                now=now,
            )
            return WorkResult(WorkStatus.FAILED, {}, "cancelled_before_dispatch")
        try:
            if now >= request.deadline:
                raise PermissionError("module operation expired")
            if request.principal.principal_id != SPARKS_PRINCIPAL_ID:
                raise PermissionError("only authenticated owner module operation admitted")
            if request.principal_attestation_ref != request.approval_id:
                raise PermissionError("principal authority reference differs from approval")
            current = self.lifecycle.describe(request.module_id)
            if current is None:
                raise LookupError("module lifecycle does not exist")
            if (
                current.revision != request.expected_revision
                or current.lifecycle is not request.source_lifecycle
                or current.package_digest != request.package_digest
                or request.destination_lifecycle is not ModuleLifecycle.ACTIVE
            ):
                raise RuntimeError("module lifecycle precondition changed")
            package, adapter, compatibility, registrations = self._reconstruct(request)
            before = adapter.inspect()
            if before.package_digest != request.package_digest:
                raise PermissionError("adapter inspection package identity mismatch")
            if cancel.is_set():
                raise InterruptedError("cancelled before authority consumption")
            activating = self.lifecycle.begin_activation(
                package, expected_revision=request.expected_revision,
                profile=request.profile, compatibility=compatibility,
                registrations=registrations, approval_id=request.approval_id,
                now=datetime.now(timezone.utc),
            )
        except InterruptedError:
            self._event(
                request_id=request.request_id, job_id=job.job_id,
                status=ModuleAttemptStatus.CANCELLED_BEFORE_DISPATCH,
                attempt_number=attempt, detail="cancelled before external dispatch",
                now=datetime.now(timezone.utc),
            )
            return WorkResult(WorkStatus.FAILED, {}, "cancelled_before_dispatch")
        except PermissionError as exc:
            self._event(
                request_id=request.request_id, job_id=job.job_id,
                status=ModuleAttemptStatus.DENIED, attempt_number=attempt,
                detail=str(exc), now=datetime.now(timezone.utc),
            )
            return WorkResult(WorkStatus.FAILED, {}, "module_operation_denied")
        except Exception as exc:
            self._event(
                request_id=request.request_id, job_id=job.job_id,
                status=ModuleAttemptStatus.FAILED_BEFORE_EXTERNAL_EFFECT,
                attempt_number=attempt, detail=type(exc).__name__,
                now=datetime.now(timezone.utc),
            )
            return WorkResult(
                WorkStatus.FAILED, {"error_type": type(exc).__name__},
                "module_operation_validation_failed",
            )

        dispatch_at = datetime.now(timezone.utc)
        self._event(
            request_id=request.request_id, job_id=job.job_id,
            status=ModuleAttemptStatus.EXTERNAL_EFFECT_ATTEMPTED,
            attempt_number=attempt,
            detail="adapter start dispatched; absence of receipt is not failure proof",
            now=dispatch_at,
        )
        try:
            adapter.start(epoch=attempt)
            if cancel.is_set():
                raise RuntimeError("cancelled_after_external_dispatch")
            observed = adapter.inspect()
        except Exception as exc:
            self._event(
                request_id=request.request_id, job_id=job.job_id,
                status=ModuleAttemptStatus.OUTCOME_UNKNOWN,
                attempt_number=attempt, detail=type(exc).__name__,
                now=datetime.now(timezone.utc),
            )
            return WorkResult(
                WorkStatus.UNCERTAIN,
                {"module_request_id": request.request_id,
                 "lifecycle_revision": activating.revision},
                "external_module_activation_outcome_unknown",
            )
        if not self._verified_inspection(request, observed):
            self._event(
                request_id=request.request_id, job_id=job.job_id,
                status=ModuleAttemptStatus.OUTCOME_UNKNOWN,
                attempt_number=attempt,
                detail="post-start observation did not prove ready identity",
                evidence_ref=observed.evidence_ref,
                now=datetime.now(timezone.utc),
            )
            return WorkResult(
                WorkStatus.UNCERTAIN,
                {"module_request_id": request.request_id,
                 "lifecycle_revision": activating.revision},
                "external_module_activation_not_verified",
            )
        completed = self.lifecycle.complete_activation(
            package, expected_revision=activating.revision,
            profile=request.profile, compatibility=compatibility,
            registrations=registrations, approval_id=request.approval_id,
            now=datetime.now(timezone.utc),
        )
        self._event(
            request_id=request.request_id, job_id=job.job_id,
            status=ModuleAttemptStatus.EXTERNALLY_VERIFIED_SUCCESS,
            attempt_number=attempt, detail="adapter identity and readiness verified",
            evidence_ref=observed.evidence_ref,
            now=datetime.now(timezone.utc),
        )
        return WorkResult(
            WorkStatus.COMPLETED,
            {"module_request_id": request.request_id,
             "module_id": request.module_id,
             "lifecycle_revision": completed.revision,
             "evidence_ref": observed.evidence_ref},
            "external_module_activation_verified",
        )

    def reconcile(self, request_id: str, *, now: datetime) -> ModuleAttemptStatus:
        """Probe an uncertain activation without ever replaying its start effect.

        RUN's UNCERTAIN receipt remains immutable history.  A fresh trusted
        observation may settle the module lifecycle, while the append-only
        attempt stream records that later reconciliation separately.
        """
        moment = _utc(now)
        request, job = self._request_for_id(request_id)
        if job.status is not WorkStatus.UNCERTAIN:
            raise RuntimeError("only an uncertain module operation can be reconciled")
        current = self.lifecycle.describe(request.module_id)
        if (
            current is None
            or current.lifecycle is not ModuleLifecycle.ACTIVATING
            or current.package_digest != request.package_digest
        ):
            raise RuntimeError("uncertain activation lifecycle no longer matches")
        try:
            package, adapter, compatibility, registrations = self._reconstruct(request)
            observed = adapter.inspect()
        except Exception as exc:
            self._event(
                request_id=request.request_id, job_id=job.job_id,
                status=ModuleAttemptStatus.OUTCOME_UNKNOWN,
                attempt_number=job.attempt_count,
                detail="reconciliation probe unavailable:" + type(exc).__name__,
                now=moment,
            )
            return ModuleAttemptStatus.OUTCOME_UNKNOWN
        if self._verified_inspection(request, observed, now=moment):
            self.lifecycle.complete_activation(
                package, expected_revision=current.revision,
                profile=request.profile, compatibility=compatibility,
                registrations=registrations, approval_id=request.approval_id,
                now=moment,
            )
            status = ModuleAttemptStatus.EXTERNALLY_VERIFIED_SUCCESS
            detail = "post-crash inspection verified the original activation"
        elif observed.state.value in {"stopped", "failed"} and not observed.ready:
            self.lifecycle.manager.quarantine_uncertain_activation(
                request.module_id, expected_revision=current.revision,
                operation_ref=request.request_id,
                reason="verified adapter not running after uncertain activation",
                now=moment,
            )
            status = ModuleAttemptStatus.EXTERNALLY_VERIFIED_FAILURE
            detail = "post-crash inspection verified the component is not running"
        else:
            status = ModuleAttemptStatus.OUTCOME_UNKNOWN
            detail = "post-crash inspection could not settle external outcome"
        self._event(
            request_id=request.request_id, job_id=job.job_id, status=status,
            attempt_number=job.attempt_count, detail=detail,
            evidence_ref=observed.evidence_ref, now=moment,
        )
        return status

    def attempts(self, request_id: str) -> tuple[ModuleAttemptEvent, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM platform_module_operation_attempt "
                "WHERE request_id=? ORDER BY event_id",
                (request_id,),
            ).fetchall()
        return tuple(ModuleAttemptEvent(
            int(row["event_id"]), row["request_id"], row["job_id"],
            ModuleAttemptStatus(row["status"]), int(row["attempt_number"]),
            row["detail"], row["evidence_ref"],
            datetime.fromisoformat(row["occurred_at"]),
        ) for row in rows)
