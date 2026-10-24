"""Canonical HNF hardware inventory and live telemetry persistence."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Callable

from sofia.platform.resources.contract import CapabilityFact, EvidenceClass
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


EnrollmentVerifier = Callable[[str, str, datetime], bool]


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _text(value: str, label: str, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value.strip()


def _fact_document(fact: CapabilityFact) -> dict[str, object]:
    return {
        "evidence_class": fact.evidence_class.value,
        "expires_at": None if fact.expires_at is None else fact.expires_at.isoformat(),
        "host_id": fact.host_id,
        "key": fact.key,
        "observed_at": fact.observed_at.isoformat(),
        "resource_id": fact.resource_id,
        "source_ref": fact.source_ref,
        "unit": fact.unit,
        "value": list(fact.value) if isinstance(fact.value, tuple) else fact.value,
        "value_is_set": isinstance(fact.value, tuple),
        "verified": fact.verified,
    }


def _fact_from_document(document: dict[str, object]) -> CapabilityFact:
    value = document["value"]
    if type(document["value_is_set"]) is not bool or type(document["verified"]) is not bool:
        raise ValueError("persisted capability booleans are invalid")
    if document["value_is_set"]:
        if not isinstance(value, list):
            raise ValueError("persisted capability set is invalid")
        value = tuple(str(item) for item in value)
    return CapabilityFact(
        key=str(document["key"]), value=value, unit=document["unit"],  # type: ignore[arg-type]
        host_id=str(document["host_id"]), resource_id=str(document["resource_id"]),
        evidence_class=EvidenceClass(str(document["evidence_class"])),
        source_ref=str(document["source_ref"]),
        observed_at=datetime.fromisoformat(str(document["observed_at"])),
        expires_at=(None if document["expires_at"] is None else
                    datetime.fromisoformat(str(document["expires_at"]))),
        verified=bool(document["verified"]),
    )


def _facts_json(facts: tuple[CapabilityFact, ...]) -> str:
    return json.dumps(
        [_fact_document(fact) for fact in sorted(
            facts, key=lambda item: (item.resource_id, item.key, item.source_ref)
        )], sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )


def _semantic_digest(
    *, host_id: str, display_name: str, manufacturer: str | None,
    model: str | None, parent_host_id: str | None, enrolled: bool,
    trusted: bool, facts: tuple[CapabilityFact, ...],
) -> str:
    semantic_facts = [{key: value for key, value in _fact_document(fact).items()
                       if key not in {"observed_at", "expires_at"}} for fact in facts]
    return sha256(json.dumps({
        "display_name": display_name, "enrolled": enrolled, "facts": semantic_facts,
        "host_id": host_id, "manufacturer": manufacturer, "model": model,
        "parent_host_id": parent_host_id, "trusted": trusted,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    host_id: str
    display_name: str
    manufacturer: str | None
    model: str | None
    parent_host_id: str | None
    enrolled: bool
    trusted: bool
    enrollment_ref: str | None
    revision: int
    facts: tuple[CapabilityFact, ...]
    recorded_at: datetime
    semantic_digest: str


class HardwareInventoryStore:
    """Append-only inventory revisions inside canonical ``sofia.db``."""

    def __init__(self, state_path: Path, *, enrollment_verifier: EnrollmentVerifier) -> None:
        if not isinstance(state_path, Path) or not callable(enrollment_verifier):
            raise TypeError("state_path and enrollment_verifier required")
        self._guard = CanonicalSQLiteGuard(state_path)
        self._verify_enrollment = enrollment_verifier
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS platform_hardware_inventory(
                    host_id TEXT NOT NULL,revision INTEGER NOT NULL,
                    display_name TEXT NOT NULL,manufacturer TEXT,model TEXT,
                    parent_host_id TEXT,enrolled INTEGER NOT NULL,trusted INTEGER NOT NULL,
                    enrollment_ref TEXT,facts_json TEXT NOT NULL,
                    semantic_digest TEXT NOT NULL,recorded_at TEXT NOT NULL,
                    PRIMARY KEY(host_id,revision));
                CREATE TABLE IF NOT EXISTS platform_hardware_inventory_current(
                    host_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,
                    FOREIGN KEY(host_id,revision) REFERENCES platform_hardware_inventory(host_id,revision));
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _record(row: sqlite3.Row) -> InventoryRecord:
        facts = tuple(_fact_from_document(item) for item in json.loads(row["facts_json"]))
        return InventoryRecord(
            row["host_id"], row["display_name"], row["manufacturer"], row["model"],
            row["parent_host_id"], bool(row["enrolled"]), bool(row["trusted"]),
            row["enrollment_ref"], int(row["revision"]), facts,
            datetime.fromisoformat(row["recorded_at"]), row["semantic_digest"],
        )

    def current(self, host_id: str) -> InventoryRecord | None:
        with closing(self._connect()) as db:
            row = db.execute("""SELECT i.* FROM platform_hardware_inventory i
                JOIN platform_hardware_inventory_current c
                ON c.host_id=i.host_id AND c.revision=i.revision
                WHERE i.host_id=?""", (host_id,)).fetchone()
        return None if row is None else self._record(row)

    def history(self, host_id: str, *, limit: int = 100) -> tuple[InventoryRecord, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be in 1..1000")
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT * FROM platform_hardware_inventory
                WHERE host_id=? ORDER BY revision DESC LIMIT ?""", (host_id, limit)).fetchall()
        return tuple(self._record(row) for row in rows)

    def current_records(self, *, limit: int = 256) -> tuple[InventoryRecord, ...]:
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise ValueError("limit must be in 1..1024")
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT i.* FROM platform_hardware_inventory i
                JOIN platform_hardware_inventory_current c
                ON c.host_id=i.host_id AND c.revision=i.revision
                ORDER BY i.host_id LIMIT ?""", (limit,)).fetchall()
        return tuple(self._record(row) for row in rows)

    def record(
        self, *, host_id: str, display_name: str, facts: tuple[CapabilityFact, ...],
        observed_at: datetime, manufacturer: str | None = None,
        model: str | None = None, parent_host_id: str | None = None,
        enrolled: bool = False, trusted: bool = False,
        enrollment_ref: str | None = None, expected_revision: int | None = None,
    ) -> InventoryRecord:
        host_id = _text(host_id, "host_id")
        display_name = _text(display_name, "display_name")
        moment = _utc(observed_at, "observed_at")
        if type(facts) is not tuple or any(
            not isinstance(fact, CapabilityFact) or fact.host_id != host_id for fact in facts
        ) or len(facts) > 4096:
            raise ValueError("facts must be bounded and belong to host")
        if manufacturer is not None:
            manufacturer = _text(manufacturer, "manufacturer")
        if model is not None:
            model = _text(model, "model")
        if parent_host_id is not None:
            parent_host_id = _text(parent_host_id, "parent_host_id")
            if parent_host_id == host_id:
                raise ValueError("host cannot parent itself")
        if enrolled or trusted:
            if not enrolled or not trusted or enrollment_ref is None:
                raise PermissionError("trusted inventory requires enrolled host evidence")
            enrollment_ref = _text(enrollment_ref, "enrollment_ref")
            if not self._verify_enrollment(host_id, enrollment_ref, moment):
                raise PermissionError("host enrollment evidence is not authoritative")
        elif enrollment_ref is not None:
            raise ValueError("unenrolled inventory cannot carry enrollment_ref")
        digest = _semantic_digest(
            host_id=host_id, display_name=display_name, manufacturer=manufacturer,
            model=model, parent_host_id=parent_host_id, enrolled=enrolled,
            trusted=trusted, facts=facts,
        )
        encoded = _facts_json(facts)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT i.* FROM platform_hardware_inventory i
                JOIN platform_hardware_inventory_current c
                ON c.host_id=i.host_id AND c.revision=i.revision
                WHERE i.host_id=?""", (host_id,)).fetchone()
            current = None if row is None else self._record(row)
            actual_revision = 0 if current is None else current.revision
            if expected_revision is not None and expected_revision != actual_revision:
                raise RuntimeError("inventory revision changed")
            if current is not None and (current.enrolled != enrolled or current.trusted != trusted):
                if not (enrolled and trusted and enrollment_ref and
                        self._verify_enrollment(host_id, enrollment_ref, moment)):
                    raise PermissionError("inventory observation cannot alter host trust")
            if current is not None and current.semantic_digest == digest:
                return current
            revision = actual_revision + 1
            db.execute("""INSERT INTO platform_hardware_inventory VALUES(
                ?,?,?,?,?,?,?,?,?,?,?,?)""", (
                host_id, revision, display_name, manufacturer, model, parent_host_id,
                int(enrolled), int(trusted), enrollment_ref, encoded, digest,
                moment.isoformat(),
            ))
            db.execute("""INSERT INTO platform_hardware_inventory_current VALUES(?,?)
                ON CONFLICT(host_id) DO UPDATE SET revision=excluded.revision""",
                (host_id, revision))
        result = self.current(host_id)
        if result is None:
            raise RuntimeError("inventory write was not durable")
        return result


class HardwareTelemetryStore:
    """Bounded append-only live facts; missing metrics remain absent/UNKNOWN."""

    def __init__(self, state_path: Path, *, retention_per_host: int = 256) -> None:
        if type(retention_per_host) is not int or not 8 <= retention_per_host <= 4096:
            raise ValueError("retention_per_host must be in 8..4096")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.retention_per_host = retention_per_host
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS platform_hardware_telemetry(
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,host_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,source_ref TEXT NOT NULL,facts_json TEXT NOT NULL)""")
            db.execute("""CREATE INDEX IF NOT EXISTS platform_hardware_telemetry_host
                ON platform_hardware_telemetry(host_id,observation_id DESC)""")

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(self, *, host_id: str, facts: tuple[CapabilityFact, ...],
               source_ref: str, observed_at: datetime) -> int:
        host_id, source_ref = _text(host_id, "host_id"), _text(source_ref, "source_ref")
        moment = _utc(observed_at, "observed_at")
        if type(facts) is not tuple or not facts or any(
            fact.host_id != host_id or fact.evidence_class is not EvidenceClass.OBSERVED
            or fact.observed_at != moment for fact in facts
        ):
            raise ValueError("telemetry requires same-host observed facts at exact time")
        with closing(self._connect()) as db, db:
            cursor = db.execute("INSERT INTO platform_hardware_telemetry(host_id,observed_at,source_ref,facts_json) VALUES(?,?,?,?)",
                (host_id, moment.isoformat(), source_ref, _facts_json(facts)))
            observation_id = int(cursor.lastrowid)
            db.execute("""DELETE FROM platform_hardware_telemetry WHERE host_id=?
                AND observation_id NOT IN (SELECT observation_id FROM platform_hardware_telemetry
                WHERE host_id=? ORDER BY observation_id DESC LIMIT ?)""",
                (host_id, host_id, self.retention_per_host))
        return observation_id

    def latest(self, host_id: str) -> tuple[CapabilityFact, ...]:
        with closing(self._connect()) as db:
            row = db.execute("""SELECT facts_json FROM platform_hardware_telemetry
                WHERE host_id=? ORDER BY observation_id DESC LIMIT 1""", (host_id,)).fetchone()
        if row is None:
            return ()
        return tuple(_fact_from_document(item) for item in json.loads(row["facts_json"]))
