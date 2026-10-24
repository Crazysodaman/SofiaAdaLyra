"""Durable, authority-neutral resource and device reservations."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _amounts(value: tuple[tuple[str, int], ...]) -> tuple[tuple[str, int], ...]:
    if type(value) is not tuple or not value or any(
        not isinstance(name, str) or _IDENTIFIER.fullmatch(name) is None
        or type(amount) is not int or amount <= 0
        for name, amount in value
    ) or len({name for name, _ in value}) != len(value):
        raise ValueError("resource amounts must be unique positive integer pairs")
    return tuple(sorted(value))


@dataclass(frozen=True, slots=True)
class ResourceObservation:
    resource_id: str
    host_id: str
    resource_kind: str
    capacity: tuple[tuple[str, int], ...]
    observed_at: datetime
    exclusive: bool = False

    def __post_init__(self) -> None:
        for label, value in (("resource_id", self.resource_id),
                             ("host_id", self.host_id),
                             ("resource_kind", self.resource_kind)):
            if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
                raise ValueError(f"invalid {label}")
        object.__setattr__(self, "capacity", _amounts(self.capacity))
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))
        if type(self.exclusive) is not bool:
            raise TypeError("exclusive must be bool")


@dataclass(frozen=True, slots=True)
class ResourceReservation:
    reservation_id: str
    workload_id: str
    principal_id: str
    audience: str
    resource_id: str
    amounts: tuple[tuple[str, int], ...]
    created_at: datetime
    expires_at: datetime
    status: str
    authority_ref: str


ReservationAuthorizer = Callable[[str, str, str, str, datetime], bool]


class ResourceArbiter:
    """Serialize bounded reservations; reservations never grant authority."""

    def __init__(self, state_path: Path, *, authorizer: ReservationAuthorizer,
                 max_observation_age: timedelta = timedelta(minutes=2)) -> None:
        if not isinstance(state_path, Path) or not callable(authorizer):
            raise TypeError("state_path and authorizer are required")
        if not isinstance(max_observation_age, timedelta) or max_observation_age <= timedelta(0):
            raise ValueError("max_observation_age must be positive")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.authorizer = authorizer
        self.max_observation_age = max_observation_age
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_resource_reservation(
                    reservation_id TEXT PRIMARY KEY,workload_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,audience TEXT NOT NULL,
                    resource_id TEXT NOT NULL,amounts_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,expires_at TEXT NOT NULL,
                    status TEXT NOT NULL,authority_ref TEXT NOT NULL,
                    released_at TEXT);
                CREATE INDEX IF NOT EXISTS platform_resource_active
                    ON platform_resource_reservation(resource_id,status,expires_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _validate_id(value: str, label: str) -> None:
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise ValueError(f"invalid {label}")

    @staticmethod
    def _record(row: sqlite3.Row) -> ResourceReservation:
        return ResourceReservation(
            row["reservation_id"], row["workload_id"], row["principal_id"],
            row["audience"], row["resource_id"],
            tuple((str(name), int(amount)) for name, amount in json.loads(row["amounts_json"])),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["expires_at"]), row["status"],
            row["authority_ref"],
        )

    def reserve(self, observation: ResourceObservation, *, reservation_id: str,
                workload_id: str, principal_id: str, audience: str,
                amounts: tuple[tuple[str, int], ...], authority_ref: str,
                now: datetime, expires_at: datetime,
                background: bool = False, interactive_pressure: int = 0) -> ResourceReservation:
        if not isinstance(observation, ResourceObservation):
            raise TypeError("observation must be ResourceObservation")
        for value, label in ((reservation_id, "reservation_id"),
                             (workload_id, "workload_id"),
                             (principal_id, "principal_id"),
                             (audience, "audience"),
                             (authority_ref, "authority_ref")):
            self._validate_id(value, label)
        requested = _amounts(amounts)
        moment, expiry = _utc(now, "now"), _utc(expires_at, "expires_at")
        if not moment < expiry <= moment + timedelta(hours=24):
            raise ValueError("reservation expiry must be within 24 hours")
        age = moment - observation.observed_at
        if age < -timedelta(seconds=5) or age > self.max_observation_age:
            raise RuntimeError("resource observation is stale or from the future")
        if background and interactive_pressure > 0:
            raise RuntimeError("background reservation deferred for foreground activity")
        if not self.authorizer(principal_id, audience, observation.resource_id,
                               authority_ref, moment):
            raise PermissionError("resource reservation is not authorized")
        capacity = dict(observation.capacity)
        if any(name not in capacity or amount > capacity[name] for name, amount in requested):
            raise RuntimeError("requested resource capacity is unavailable")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """UPDATE platform_resource_reservation SET status='expired',released_at=?
                WHERE status='active' AND expires_at<=?""",
                (moment.isoformat(), moment.isoformat()),
            )
            duplicate = db.execute(
                "SELECT * FROM platform_resource_reservation WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if duplicate is not None:
                existing = self._record(duplicate)
                if (
                    existing.workload_id == workload_id
                    and existing.principal_id == principal_id
                    and existing.audience == audience
                    and existing.resource_id == observation.resource_id
                    and existing.amounts == requested
                    and existing.expires_at == expiry
                    and existing.authority_ref == authority_ref
                    and existing.status == "active"
                ):
                    return existing
                raise RuntimeError("reservation ID already has different semantics")
            rows = db.execute(
                """SELECT amounts_json FROM platform_resource_reservation
                WHERE resource_id=? AND status='active' AND expires_at>?""",
                (observation.resource_id, moment.isoformat()),
            ).fetchall()
            if observation.exclusive and rows:
                raise RuntimeError("exclusive device is already leased")
            used: dict[str, int] = {}
            for row in rows:
                for name, amount in json.loads(row["amounts_json"]):
                    used[name] = used.get(name, 0) + int(amount)
            if any(used.get(name, 0) + amount > capacity[name] for name, amount in requested):
                raise RuntimeError("resource capacity is already reserved")
            db.execute(
                """INSERT INTO platform_resource_reservation VALUES(
                ?,?,?,?,?,?,?,?,'active',?,NULL)""",
                (reservation_id, workload_id, principal_id, audience,
                 observation.resource_id,
                 json.dumps(requested, separators=(",", ":")),
                 moment.isoformat(), expiry.isoformat(), authority_ref),
            )
        return self.inspect(reservation_id)  # type: ignore[return-value]

    def release(self, reservation_id: str, *, principal_id: str,
                authority_ref: str, now: datetime) -> ResourceReservation:
        moment = _utc(now, "now")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM platform_resource_reservation WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if row is None:
                raise LookupError("unknown reservation")
            record = self._record(row)
            if record.status != "active":
                return record
            # Releasing capacity narrows effects. Require the exact principal
            # and original authority reference, but do not let later grant
            # revocation strand a resource lease indefinitely.
            if (
                record.principal_id != principal_id
                or record.authority_ref != authority_ref
            ):
                raise PermissionError("resource release is not authorized")
            db.execute(
                """UPDATE platform_resource_reservation SET status='released',released_at=?
                WHERE reservation_id=? AND status='active'""",
                (moment.isoformat(), reservation_id),
            )
        return self.inspect(reservation_id)  # type: ignore[return-value]

    def inspect(self, reservation_id: str) -> ResourceReservation | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_resource_reservation WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
        return None if row is None else self._record(row)

    def acquire_device_lease(self, observation: ResourceObservation, **kwargs) -> ResourceReservation:
        if not observation.exclusive:
            raise ValueError("device lease requires an exclusive resource observation")
        return self.reserve(observation, amounts=(("units", 1),), **kwargs)

    def release_device_lease(self, reservation_id: str, *, principal_id: str,
                             authority_ref: str, now: datetime) -> ResourceReservation:
        return self.release(
            reservation_id, principal_id=principal_id,
            authority_ref=authority_ref, now=now,
        )
