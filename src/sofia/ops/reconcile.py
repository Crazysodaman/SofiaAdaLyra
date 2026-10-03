"""Durable, verified Fleet maintenance reconciliation.

This module does not decide which maintenance should happen and does not expose
arbitrary command execution. It consumes an already-reviewed typed
MaintenanceRequest, enforces MaintenancePolicy, executes through a narrow
backend, independently verifies the result, and persists a no-replay receipt.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3
from typing import Protocol

from .maintenance import MaintenancePolicy, MaintenanceRequest


class MaintenanceReconcileError(RuntimeError):
    pass


class MaintenanceReplayDenied(MaintenanceReconcileError):
    pass


class MaintenanceReceiptOutcome(str, Enum):
    VERIFIED = "verified"
    EXECUTION_FAILED = "execution_failed"
    VERIFICATION_FAILED = "verification_failed"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class MaintenanceExecutionResult:
    request_id: str
    reported_success: bool
    execution_ref: str
    message: str = ""

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id required")
        if type(self.reported_success) is not bool:
            raise TypeError("reported_success must be bool")
        if not self.execution_ref.strip():
            raise ValueError("execution_ref required")
        if not isinstance(self.message, str):
            raise TypeError("message must be str")


@dataclass(frozen=True, slots=True)
class MaintenanceVerification:
    request_id: str
    verified: bool
    evidence_ref: str
    observed: str

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id required")
        if type(self.verified) is not bool:
            raise TypeError("verified must be bool")
        if not self.evidence_ref.strip():
            raise ValueError("evidence_ref required")
        if not isinstance(self.observed, str) or not self.observed.strip():
            raise ValueError("observed must be nonempty")


@dataclass(frozen=True, slots=True)
class MaintenanceReceipt:
    request_id: str
    host_id: str
    operation: str
    target: str | None
    attempted_at: datetime
    completed_at: datetime
    outcome: MaintenanceReceiptOutcome
    execution_ref: str | None
    verification_ref: str | None
    observed: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.request_id, "request_id"),
            (self.host_id, "host_id"),
            (self.operation, "operation"),
            (self.observed, "observed"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        for value, label in (
            (self.attempted_at, "attempted_at"),
            (self.completed_at, "completed_at"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        if self.completed_at < self.attempted_at:
            raise ValueError("completed_at cannot precede attempted_at")
        if not isinstance(self.outcome, MaintenanceReceiptOutcome):
            raise TypeError("outcome must be MaintenanceReceiptOutcome")


class MaintenanceBackend(Protocol):
    def execute(
        self,
        request: MaintenanceRequest,
    ) -> MaintenanceExecutionResult: ...


class MaintenanceVerifier(Protocol):
    def verify(
        self,
        request: MaintenanceRequest,
    ) -> MaintenanceVerification: ...


class MaintenanceReceiptStore:
    def __init__(self, state_path: Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ops_maintenance_receipt (
                    request_id TEXT PRIMARY KEY,
                    host_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    target TEXT,
                    attempted_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    execution_ref TEXT,
                    verification_ref TEXT,
                    observed TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _decode(row) -> MaintenanceReceipt:
        return MaintenanceReceipt(
            request_id=row[0],
            host_id=row[1],
            operation=row[2],
            target=row[3],
            attempted_at=datetime.fromisoformat(row[4]),
            completed_at=datetime.fromisoformat(row[5]),
            outcome=MaintenanceReceiptOutcome(row[6]),
            execution_ref=row[7],
            verification_ref=row[8],
            observed=row[9],
        )

    def get(self, request_id: str) -> MaintenanceReceipt | None:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id required")
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            row = db.execute(
                """
                SELECT request_id,host_id,operation,target,attempted_at,
                       completed_at,outcome,execution_ref,verification_ref,
                       observed
                FROM ops_maintenance_receipt
                WHERE request_id=?
                """,
                (request_id,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def record(self, receipt: MaintenanceReceipt) -> None:
        if not isinstance(receipt, MaintenanceReceipt):
            raise TypeError("receipt must be MaintenanceReceipt")
        try:
            with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
                db.execute("PRAGMA busy_timeout=10000")
                db.execute(
                    """
                    INSERT INTO ops_maintenance_receipt(
                        request_id,host_id,operation,target,attempted_at,
                        completed_at,outcome,execution_ref,verification_ref,
                        observed
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        receipt.request_id,
                        receipt.host_id,
                        receipt.operation,
                        receipt.target,
                        receipt.attempted_at.astimezone(timezone.utc).isoformat(),
                        receipt.completed_at.astimezone(timezone.utc).isoformat(),
                        receipt.outcome.value,
                        receipt.execution_ref,
                        receipt.verification_ref,
                        receipt.observed,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise MaintenanceReplayDenied(
                "maintenance request already has a durable receipt"
            ) from exc


class MaintenanceReconciler:
    def __init__(
        self,
        *,
        policy: MaintenancePolicy,
        backend: MaintenanceBackend,
        verifier: MaintenanceVerifier,
        receipts: MaintenanceReceiptStore,
    ) -> None:
        self.policy = policy
        self.backend = backend
        self.verifier = verifier
        self.receipts = receipts

    def reconcile(
        self,
        request: MaintenanceRequest,
        *,
        now: datetime | None = None,
    ) -> MaintenanceReceipt:
        if not isinstance(request, MaintenanceRequest):
            raise TypeError("request must be MaintenanceRequest")
        if self.receipts.get(request.request_id) is not None:
            raise MaintenanceReplayDenied(
                "maintenance request already completed or attempted"
            )

        self.policy.require(request)
        attempted = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        try:
            execution = self.backend.execute(request)
        except Exception as exc:
            receipt = MaintenanceReceipt(
                request_id=request.request_id,
                host_id=request.host_id,
                operation=request.operation.value,
                target=request.target,
                attempted_at=attempted,
                completed_at=attempted,
                outcome=MaintenanceReceiptOutcome.UNCERTAIN,
                execution_ref=None,
                verification_ref=None,
                observed=(
                    "execution outcome uncertain; implicit retry is forbidden"
                ),
            )
            self.receipts.record(receipt)
            raise MaintenanceReconcileError(
                "maintenance execution outcome is uncertain; do not retry"
            ) from exc

        if execution.request_id != request.request_id:
            receipt = MaintenanceReceipt(
                request_id=request.request_id,
                host_id=request.host_id,
                operation=request.operation.value,
                target=request.target,
                attempted_at=attempted,
                completed_at=attempted,
                outcome=MaintenanceReceiptOutcome.UNCERTAIN,
                execution_ref=execution.execution_ref,
                verification_ref=None,
                observed="execution result request identity mismatch",
            )
            self.receipts.record(receipt)
            raise MaintenanceReconcileError(
                "maintenance execution identity mismatch"
            )

        if not execution.reported_success:
            receipt = MaintenanceReceipt(
                request_id=request.request_id,
                host_id=request.host_id,
                operation=request.operation.value,
                target=request.target,
                attempted_at=attempted,
                completed_at=attempted,
                outcome=MaintenanceReceiptOutcome.EXECUTION_FAILED,
                execution_ref=execution.execution_ref,
                verification_ref=None,
                observed=execution.message or "backend reported failure",
            )
            self.receipts.record(receipt)
            return receipt

        verification = self.verifier.verify(request)
        if verification.request_id != request.request_id:
            receipt = MaintenanceReceipt(
                request_id=request.request_id,
                host_id=request.host_id,
                operation=request.operation.value,
                target=request.target,
                attempted_at=attempted,
                completed_at=attempted,
                outcome=MaintenanceReceiptOutcome.VERIFICATION_FAILED,
                execution_ref=execution.execution_ref,
                verification_ref=verification.evidence_ref,
                observed="verification request identity mismatch",
            )
            self.receipts.record(receipt)
            return receipt

        outcome = (
            MaintenanceReceiptOutcome.VERIFIED
            if verification.verified
            else MaintenanceReceiptOutcome.VERIFICATION_FAILED
        )
        receipt = MaintenanceReceipt(
            request_id=request.request_id,
            host_id=request.host_id,
            operation=request.operation.value,
            target=request.target,
            attempted_at=attempted,
            completed_at=attempted,
            outcome=outcome,
            execution_ref=execution.execution_ref,
            verification_ref=verification.evidence_ref,
            observed=verification.observed,
        )
        self.receipts.record(receipt)
        return receipt
