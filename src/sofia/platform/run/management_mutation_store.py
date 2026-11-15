"""Durable idempotency receipts in the canonical Platform-local SQLite file.

This store is an additive consumer of the *existing* Platform state. It never
creates a parallel database, approval ledger, secret store or signer trust.
Every receipt is written in one BEGIN IMMEDIATE transaction together with the
monotonic mutation revision fence.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


@dataclass(frozen=True, slots=True)
class ManagementMutationReceipt:
    idempotency_key: str
    request_fingerprint: str
    receipt_id: str
    request_id: str
    correlation_id: str
    target_platform_id: str
    operation: str
    operation_scope: str
    outcome: str
    current_generation: int
    current_revision: int
    error_code: str | None
    detail: str | None
    created_at: str


class ManagementMutationConflict(RuntimeError):
    """An idempotency key already has a durable receipt."""


class ManagementMutationReceiptStore:
    """One canonical durable receipt/idempotency/revision owner."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_management_mutation_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    revision INTEGER NOT NULL CHECK(revision>=0)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_management_mutation_receipt (
                    idempotency_key TEXT PRIMARY KEY,
                    request_fingerprint TEXT NOT NULL,
                    receipt_id TEXT NOT NULL UNIQUE,
                    request_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    target_platform_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    operation_scope TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK(outcome IN (
                        'SUCCEEDED','DENIED','FAILED','OUTCOME_UNKNOWN'
                    )),
                    current_generation INTEGER NOT NULL CHECK(current_generation>0),
                    current_revision INTEGER NOT NULL CHECK(current_revision>=0),
                    error_code TEXT,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO platform_management_mutation_state "
                "(singleton,revision) VALUES(1,0)"
            )
            revision = db.execute(
                "SELECT revision FROM platform_management_mutation_state "
                "WHERE singleton=1"
            ).fetchone()
            if revision is None or type(revision[0]) is not int or revision[0] < 0:
                raise RuntimeError(
                    "canonical management mutation revision is unavailable"
                )
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def current_revision(self) -> int:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT revision FROM platform_management_mutation_state "
                "WHERE singleton=1"
            ).fetchone()
        if row is None or type(row["revision"]) is not int or row["revision"] < 0:
            raise RuntimeError(
                "canonical management mutation revision is unavailable"
            )
        return row["revision"]

    @staticmethod
    def _to_receipt(row: sqlite3.Row) -> ManagementMutationReceipt:
        return ManagementMutationReceipt(
            idempotency_key=row["idempotency_key"],
            request_fingerprint=row["request_fingerprint"],
            receipt_id=row["receipt_id"],
            request_id=row["request_id"],
            correlation_id=row["correlation_id"],
            target_platform_id=row["target_platform_id"],
            operation=row["operation"],
            operation_scope=row["operation_scope"],
            outcome=row["outcome"],
            current_generation=row["current_generation"],
            current_revision=row["current_revision"],
            error_code=row["error_code"],
            detail=row["detail"],
            created_at=row["created_at"],
        )

    def lookup(self, idempotency_key: str) -> ManagementMutationReceipt | None:
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("bounded idempotency key required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT idempotency_key,request_fingerprint,receipt_id,"
                "request_id,correlation_id,target_platform_id,operation,"
                "operation_scope,outcome,current_generation,current_revision,"
                "error_code,detail,created_at "
                "FROM platform_management_mutation_receipt "
                "WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
        return None if row is None else self._to_receipt(row)

    def record(
        self,
        *,
        idempotency_key: str,
        request_fingerprint: str,
        receipt_id: str,
        request_id: str,
        correlation_id: str,
        target_platform_id: str,
        operation: str,
        operation_scope: str,
        outcome: str,
        current_generation: int,
        error_code: str | None,
        detail: str | None,
        advance_revision: bool,
        now: datetime,
    ) -> ManagementMutationReceipt:
        if outcome not in {"SUCCEEDED", "DENIED", "FAILED", "OUTCOME_UNKNOWN"}:
            raise ValueError("unreviewed management mutation outcome")
        if type(advance_revision) is not bool:
            raise TypeError("advance_revision must be bool")
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("aware receipt time required")
        moment = now.astimezone(timezone.utc)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT 1 FROM platform_management_mutation_receipt "
                "WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                raise ManagementMutationConflict(
                    "idempotency key already has a durable receipt"
                )
            row = db.execute(
                "SELECT revision FROM platform_management_mutation_state "
                "WHERE singleton=1"
            ).fetchone()
            if row is None or type(row["revision"]) is not int:
                raise RuntimeError(
                    "canonical management mutation revision is unavailable"
                )
            revision = row["revision"]
            if advance_revision:
                revision += 1
                changed = db.execute(
                    "UPDATE platform_management_mutation_state SET revision=? "
                    "WHERE singleton=1 AND revision=?",
                    (revision, row["revision"]),
                )
                if changed.rowcount != 1:
                    raise RuntimeError(
                        "canonical management mutation revision changed"
                    )
            db.execute(
                "INSERT INTO platform_management_mutation_receipt ("
                "idempotency_key,request_fingerprint,receipt_id,request_id,"
                "correlation_id,target_platform_id,operation,operation_scope,"
                "outcome,current_generation,current_revision,error_code,detail,"
                "created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    idempotency_key,
                    request_fingerprint,
                    receipt_id,
                    request_id,
                    correlation_id,
                    target_platform_id,
                    operation,
                    operation_scope,
                    outcome,
                    current_generation,
                    revision,
                    error_code,
                    detail,
                    moment.isoformat(),
                ),
            )
            db.commit()
        return ManagementMutationReceipt(
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            receipt_id=receipt_id,
            request_id=request_id,
            correlation_id=correlation_id,
            target_platform_id=target_platform_id,
            operation=operation,
            operation_scope=operation_scope,
            outcome=outcome,
            current_generation=current_generation,
            current_revision=revision,
            error_code=error_code,
            detail=detail,
            created_at=moment.isoformat(),
        )
