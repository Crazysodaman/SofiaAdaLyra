"""Durable latest-value store and ENVIRONMENT provider for owner-phone sensors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from sofia.environment.model import (
    LocationEvidenceKind,
    LocationObservation,
    LocationSubject,
    MobileDeviceObservation,
)
from sofia.environment.provider import EnvironmentProviderObservation

from .model import MobileSensorReport


_MAX_AGE = timedelta(minutes=10)


def _source_id(device_id: str) -> str:
    digest = sha256(device_id.encode("utf-8")).hexdigest()[:20]
    return f"mobile:{digest}"


class MobileSensorStore:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS mobile_sensor_latest (
                    device_id TEXT PRIMARY KEY,
                    observed_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(
        self,
        report: MobileSensorReport,
        *,
        received_at: datetime,
    ) -> None:
        if not isinstance(report, MobileSensorReport):
            raise TypeError("report must be MobileSensorReport")
        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        received = received_at.astimezone(timezone.utc)
        if report.observed_at > received + timedelta(minutes=5):
            raise ValueError("mobile report timestamp is too far in the future")
        data = {
            "device_id": report.device_id,
            "observed_at": report.observed_at.isoformat(),
            "timezone": report.timezone_name,
            "latitude": report.latitude,
            "longitude": report.longitude,
            "accuracy_meters": report.accuracy_meters,
            "battery_percent": report.battery_percent,
            "charging": report.charging,
            "network": report.network.value,
            "activity": report.activity.value,
            "ambient_light_lux": report.ambient_light_lux,
            "pressure_hpa": report.pressure_hpa,
            "proximity_near": report.proximity_near,
            "step_counter": report.step_counter,
        }
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO mobile_sensor_latest(
                    device_id, observed_at, received_at, payload_json
                ) VALUES(?,?,?,?)
                ON CONFLICT(device_id) DO UPDATE SET
                    observed_at=excluded.observed_at,
                    received_at=excluded.received_at,
                    payload_json=excluded.payload_json
                WHERE excluded.observed_at >= mobile_sensor_latest.observed_at
                """,
                (
                    report.device_id,
                    report.observed_at.isoformat(),
                    received.isoformat(),
                    encoded,
                ),
            )

    def latest(self) -> MobileSensorReport | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload_json FROM mobile_sensor_latest "
                "ORDER BY received_at DESC, device_id ASC LIMIT 1"
            ).fetchone()
        return None if row is None else MobileSensorReport.from_payload(
            json.loads(row[0])
        )


class MobileSensorProvider:
    name = "authenticated-mobile-sensors"

    def __init__(self, store: MobileSensorStore) -> None:
        if not isinstance(store, MobileSensorStore):
            raise TypeError("store must be MobileSensorStore")
        self.store = store

    def observe(self, *, now: datetime) -> EnvironmentProviderObservation:
        report = self.store.latest()
        if report is None:
            return EnvironmentProviderObservation()
        expires_at = report.observed_at + _MAX_AGE
        location = None
        if report.latitude is not None and report.longitude is not None:
            location = LocationObservation(
                label="Owner phone",
                source_id=_source_id(report.device_id),
                subject=LocationSubject.USER,
                kind=LocationEvidenceKind.CURRENT,
                timezone=report.timezone_name,
                latitude=report.latitude,
                longitude=report.longitude,
                precision_meters=report.accuracy_meters,
                observed_at=report.observed_at,
                expires_at=expires_at,
            )
        mobile = MobileDeviceObservation(
            observed_at=report.observed_at,
            expires_at=expires_at,
            source_id=_source_id(report.device_id),
            timezone=report.timezone_name,
            battery_percent=report.battery_percent,
            charging=report.charging,
            network=report.network,
            activity=report.activity,
            ambient_light_lux=report.ambient_light_lux,
            pressure_hpa=report.pressure_hpa,
            proximity_near=report.proximity_near,
            step_counter=report.step_counter,
        )
        return EnvironmentProviderObservation(
            current_location=location,
            mobile=mobile,
        )
