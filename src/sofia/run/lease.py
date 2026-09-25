"""Durable local singleton lease for one Sofía runtime process.

This is a same-state-store fencing primitive for local supervision. It is NOT a
cross-host consensus system and must not be used to claim partition-safe HA.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


@dataclass(frozen=True)
class RunLease:
    owner_id: str
    epoch: int
    acquired_at: datetime
    renewed_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class LeaseResult:
    status: str
    lease: RunLease | None = None
    holder_id: str | None = None
    holder_epoch: int | None = None


class RunLeaseError(RuntimeError):
    pass


class LocalRunLeaseStore:
    """SQLite-backed local singleton lease with monotonic epochs."""

    def __init__(self, state_path: str | Path) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("state_path required")
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS run_local_lease (
                        lease_key TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        epoch INTEGER NOT NULL CHECK(epoch > 0),
                        acquired_at TEXT NOT NULL,
                        renewed_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        released_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS run_local_lease_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        epoch INTEGER NOT NULL,
                        occurred_at TEXT NOT NULL,
                        detail TEXT NOT NULL
                    );
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _ttl(ttl_seconds: int) -> int:
        if type(ttl_seconds) is not int or not 5 <= ttl_seconds <= 300:
            raise ValueError("ttl_seconds must be an integer in 5..300")
        return ttl_seconds

    @staticmethod
    def _row_to_lease(row: tuple) -> RunLease:
        return RunLease(
            owner_id=row[0],
            epoch=row[1],
            acquired_at=datetime.fromisoformat(row[2]).astimezone(timezone.utc),
            renewed_at=datetime.fromisoformat(row[3]).astimezone(timezone.utc),
            expires_at=datetime.fromisoformat(row[4]).astimezone(timezone.utc),
        )

    @staticmethod
    def _event(
        db: sqlite3.Connection,
        event_type: str,
        owner_id: str,
        epoch: int,
        at: datetime,
        detail: str,
    ) -> None:
        db.execute(
            """
            INSERT INTO run_local_lease_events
            (event_type, owner_id, epoch, occurred_at, detail)
            VALUES (?,?,?,?,?)
            """,
            (event_type, owner_id, epoch, at.isoformat(), detail),
        )

    def acquire(
        self,
        *,
        owner_id: str,
        now: datetime,
        ttl_seconds: int = 30,
    ) -> LeaseResult:
        owner = _id(owner_id, "owner_id")
        moment = _utc(now)
        ttl = self._ttl(ttl_seconds)
        expires = moment + timedelta(seconds=ttl)

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT owner_id, epoch, acquired_at, renewed_at, expires_at, released_at
                    FROM run_local_lease WHERE lease_key='runtime'
                    """
                ).fetchone()
                if row is None:
                    epoch = 1
                    db.execute(
                        """
                        INSERT INTO run_local_lease
                        (lease_key, owner_id, epoch, acquired_at, renewed_at, expires_at, released_at)
                        VALUES ('runtime',?,?,?,?,?,NULL)
                        """,
                        (
                            owner,
                            epoch,
                            moment.isoformat(),
                            moment.isoformat(),
                            expires.isoformat(),
                        ),
                    )
                    self._event(db, "acquired", owner, epoch, moment, "initial")
                    return LeaseResult(
                        "acquired",
                        RunLease(owner, epoch, moment, moment, expires),
                    )

                current = self._row_to_lease(row[:5])
                released_at = row[5]
                if moment < current.renewed_at:
                    return LeaseResult(
                        "clock_uncertain",
                        holder_id=current.owner_id,
                        holder_epoch=current.epoch,
                    )

                active = released_at is None and moment < current.expires_at
                if active and current.owner_id != owner:
                    return LeaseResult(
                        "held_by_other",
                        holder_id=current.owner_id,
                        holder_epoch=current.epoch,
                    )

                if active and current.owner_id == owner:
                    db.execute(
                        """
                        UPDATE run_local_lease
                        SET renewed_at=?, expires_at=?
                        WHERE lease_key='runtime' AND owner_id=? AND epoch=? AND released_at IS NULL
                        """,
                        (
                            moment.isoformat(),
                            expires.isoformat(),
                            owner,
                            current.epoch,
                        ),
                    )
                    self._event(
                        db,
                        "renewed",
                        owner,
                        current.epoch,
                        moment,
                        "same-owner acquire",
                    )
                    return LeaseResult(
                        "renewed",
                        RunLease(
                            owner,
                            current.epoch,
                            current.acquired_at,
                            moment,
                            expires,
                        ),
                    )

                epoch = current.epoch + 1
                detail = (
                    f"replaced:{current.owner_id}:{current.epoch}:"
                    f"{'released' if released_at is not None else 'expired'}"
                )
                db.execute(
                    """
                    UPDATE run_local_lease
                    SET owner_id=?, epoch=?, acquired_at=?, renewed_at=?,
                        expires_at=?, released_at=NULL
                    WHERE lease_key='runtime'
                    """,
                    (
                        owner,
                        epoch,
                        moment.isoformat(),
                        moment.isoformat(),
                        expires.isoformat(),
                    ),
                )
                self._event(db, "acquired", owner, epoch, moment, detail)
                return LeaseResult(
                    "acquired",
                    RunLease(owner, epoch, moment, moment, expires),
                )

    def renew(
        self,
        lease: RunLease,
        *,
        now: datetime,
        ttl_seconds: int = 30,
    ) -> LeaseResult:
        if not isinstance(lease, RunLease):
            raise TypeError("RunLease required")
        moment = _utc(now)
        ttl = self._ttl(ttl_seconds)
        if moment < lease.renewed_at:
            return LeaseResult("clock_uncertain")
        expires = moment + timedelta(seconds=ttl)

        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT owner_id, epoch, acquired_at, renewed_at, expires_at, released_at
                    FROM run_local_lease WHERE lease_key='runtime'
                    """
                ).fetchone()
                if row is None:
                    return LeaseResult("stale")
                current = self._row_to_lease(row[:5])
                if (
                    row[5] is not None
                    or current.owner_id != lease.owner_id
                    or current.epoch != lease.epoch
                    or moment >= current.expires_at
                ):
                    return LeaseResult(
                        "stale",
                        holder_id=current.owner_id,
                        holder_epoch=current.epoch,
                    )
                changed = db.execute(
                    """
                    UPDATE run_local_lease
                    SET renewed_at=?, expires_at=?
                    WHERE lease_key='runtime' AND owner_id=? AND epoch=? AND released_at IS NULL
                    """,
                    (
                        moment.isoformat(),
                        expires.isoformat(),
                        lease.owner_id,
                        lease.epoch,
                    ),
                )
                if changed.rowcount != 1:
                    return LeaseResult("stale")
                self._event(
                    db,
                    "renewed",
                    lease.owner_id,
                    lease.epoch,
                    moment,
                    "explicit renew",
                )
                return LeaseResult(
                    "renewed",
                    RunLease(
                        lease.owner_id,
                        lease.epoch,
                        current.acquired_at,
                        moment,
                        expires,
                    ),
                )

    def release(
        self,
        lease: RunLease,
        *,
        now: datetime,
    ) -> LeaseResult:
        if not isinstance(lease, RunLease):
            raise TypeError("RunLease required")
        moment = _utc(now)
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT owner_id, epoch, acquired_at, renewed_at, expires_at, released_at
                    FROM run_local_lease WHERE lease_key='runtime'
                    """
                ).fetchone()
                if row is None:
                    return LeaseResult("stale")
                current = self._row_to_lease(row[:5])
                if current.owner_id != lease.owner_id or current.epoch != lease.epoch:
                    return LeaseResult(
                        "stale",
                        holder_id=current.owner_id,
                        holder_epoch=current.epoch,
                    )
                if row[5] is not None:
                    return LeaseResult("released", current)
                if moment < current.renewed_at:
                    return LeaseResult("clock_uncertain")
                db.execute(
                    """
                    UPDATE run_local_lease
                    SET expires_at=?, released_at=?
                    WHERE lease_key='runtime' AND owner_id=? AND epoch=?
                    """,
                    (
                        moment.isoformat(),
                        moment.isoformat(),
                        lease.owner_id,
                        lease.epoch,
                    ),
                )
                self._event(
                    db,
                    "released",
                    lease.owner_id,
                    lease.epoch,
                    moment,
                    "explicit release",
                )
                return LeaseResult(
                    "released",
                    RunLease(
                        lease.owner_id,
                        lease.epoch,
                        current.acquired_at,
                        current.renewed_at,
                        moment,
                    ),
                )

    def current(self, *, now: datetime) -> RunLease | None:
        moment = _utc(now)
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT owner_id, epoch, acquired_at, renewed_at, expires_at, released_at
                FROM run_local_lease WHERE lease_key='runtime'
                """
            ).fetchone()
        if row is None or row[5] is not None:
            return None
        lease = self._row_to_lease(row[:5])
        if moment < lease.renewed_at or moment >= lease.expires_at:
            return None
        return lease

    def holds(self, lease: RunLease, *, now: datetime) -> bool:
        if not isinstance(lease, RunLease):
            raise TypeError("RunLease required")
        current = self.current(now=now)
        return (
            current is not None
            and current.owner_id == lease.owner_id
            and current.epoch == lease.epoch
        )

    def events(self) -> tuple[tuple[str, str, int, str, str], ...]:
        with closing(self._connect()) as db:
            return tuple(
                db.execute(
                    """
                    SELECT event_type, owner_id, epoch, occurred_at, detail
                    FROM run_local_lease_events ORDER BY event_id
                    """
                )
            )
