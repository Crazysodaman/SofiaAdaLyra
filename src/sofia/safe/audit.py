"""Tamper-evident append-only evidence for protected operations."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class AuditIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    category: str
    actor: str
    occurred_at: datetime
    payload: dict
    previous_digest: str | None = None
    causation_id: str | None = None
    correlation_id: str | None = None
    revision_ref: str | None = None
    grant_ref: str | None = None

    def __post_init__(self) -> None:
        _id(self.event_id, "event_id")
        _id(self.category, "category")
        _id(self.actor, "actor")
        _utc(self.occurred_at)
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dict")
        if self.previous_digest is not None and _DIGEST.fullmatch(
            self.previous_digest
        ) is None:
            raise ValueError("previous_digest must be lowercase SHA-256")
        for label, value in (
            ("causation_id", self.causation_id),
            ("correlation_id", self.correlation_id),
            ("revision_ref", self.revision_ref),
            ("grant_ref", self.grant_ref),
        ):
            if value is not None:
                _id(value, label)

    def canonical_payload(self) -> bytes:
        document = {
            "event_id": self.event_id,
            "category": self.category,
            "actor": self.actor,
            "occurred_at": _utc(self.occurred_at).isoformat(),
            "payload": self.payload,
            "previous_digest": self.previous_digest,
            "causation_id": self.causation_id,
            "correlation_id": self.correlation_id,
            "revision_ref": self.revision_ref,
            "grant_ref": self.grant_ref,
        }
        return json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return sha256(self.canonical_payload()).hexdigest()


class AppendOnlyAuditLog:
    """SQLite-backed chain with DB triggers forbidding row rewrite/removal."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS safe_audit_events (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT NOT NULL UNIQUE,
                        category TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        previous_digest TEXT,
                        digest TEXT NOT NULL UNIQUE,
                        causation_id TEXT,
                        correlation_id TEXT,
                        revision_ref TEXT,
                        grant_ref TEXT
                    );
                    CREATE TRIGGER IF NOT EXISTS safe_audit_no_update
                    BEFORE UPDATE ON safe_audit_events
                    BEGIN
                        SELECT RAISE(ABORT, 'safe_audit_events is append-only');
                    END;
                    CREATE TRIGGER IF NOT EXISTS safe_audit_no_delete
                    BEFORE DELETE ON safe_audit_events
                    BEGIN
                        SELECT RAISE(ABORT, 'safe_audit_events is append-only');
                    END;
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def append(
        self,
        *,
        event_id: str,
        category: str,
        actor: str,
        occurred_at: datetime,
        payload: dict,
        causation_id: str | None = None,
        correlation_id: str | None = None,
        revision_ref: str | None = None,
        grant_ref: str | None = None,
    ) -> AuditEvent:
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                tail = db.execute(
                    "SELECT digest FROM safe_audit_events "
                    "ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                event = AuditEvent(
                    event_id=event_id,
                    category=category,
                    actor=actor,
                    occurred_at=occurred_at,
                    payload=payload,
                    previous_digest=tail[0] if tail is not None else None,
                    causation_id=causation_id,
                    correlation_id=correlation_id,
                    revision_ref=revision_ref,
                    grant_ref=grant_ref,
                )
                try:
                    db.execute(
                        "INSERT INTO safe_audit_events "
                        "(event_id, category, actor, occurred_at, payload_json, "
                        "previous_digest, digest, causation_id, correlation_id, "
                        "revision_ref, grant_ref) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            event.event_id,
                            event.category,
                            event.actor,
                            _utc(event.occurred_at).isoformat(),
                            json.dumps(
                                event.payload,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            event.previous_digest,
                            event.digest,
                            event.causation_id,
                            event.correlation_id,
                            event.revision_ref,
                            event.grant_ref,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise AuditIntegrityError(
                        "audit event ID/digest already exists"
                    ) from exc
        return event

    def verify_chain(self) -> int:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT event_id, category, actor, occurred_at, payload_json, "
                "previous_digest, digest, causation_id, correlation_id, "
                "revision_ref, grant_ref "
                "FROM safe_audit_events ORDER BY sequence"
            ).fetchall()

        previous = None
        count = 0
        for row in rows:
            event = AuditEvent(
                event_id=row[0],
                category=row[1],
                actor=row[2],
                occurred_at=datetime.fromisoformat(row[3]),
                payload=json.loads(row[4]),
                previous_digest=row[5],
                causation_id=row[7],
                correlation_id=row[8],
                revision_ref=row[9],
                grant_ref=row[10],
            )
            if event.previous_digest != previous or event.digest != row[6]:
                raise AuditIntegrityError(
                    f"audit chain verification failed at {event.event_id}"
                )
            previous = row[6]
            count += 1
        return count
