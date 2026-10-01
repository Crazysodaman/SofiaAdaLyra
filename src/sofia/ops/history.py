"""Durable append-only fleet telemetry history."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
import json,os
from pathlib import Path
import sqlite3
from .model import HostTelemetry

class TelemetryHistory:
    def __init__(self,path:Path)->None: self.path=path
    def append(self,host_id:str,telemetry:HostTelemetry)->None:
        if not host_id.strip(): raise ValueError("host_id required")
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload=asdict(telemetry); payload["observed_at"]=telemetry.observed_at.isoformat(); payload["host_id"]=host_id
        with self.path.open("a",encoding="utf-8") as fh:
            fh.write(json.dumps(payload,sort_keys=True)+"\n"); fh.flush(); os.fsync(fh.fileno())
    def latest(self,host_id:str)->HostTelemetry|None:
        if not self.path.exists(): return None
        found=None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            raw=json.loads(line)
            if raw.pop("host_id")!=host_id: continue
            raw["observed_at"]=datetime.fromisoformat(raw["observed_at"]); found=HostTelemetry(**raw)
        return found


class SQLiteTelemetryHistory:
    """Canonical SQLite append-only Fleet telemetry history."""

    def __init__(
        self,
        path: Path,
        *,
        legacy_path: Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=10.0) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS ops_telemetry_history (
                    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(host_id, observed_at, payload_json)
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_ops_telemetry_host_time
                ON ops_telemetry_history(host_id, observed_at DESC)
            """)
            db.commit()
        if legacy_path is not None:
            self._migrate_legacy(Path(legacy_path))

    @staticmethod
    def _payload(host_id: str, telemetry: HostTelemetry) -> dict:
        payload = asdict(telemetry)
        payload["observed_at"] = telemetry.observed_at.isoformat()
        payload["host_id"] = host_id
        return payload

    def append(self, host_id: str, telemetry: HostTelemetry) -> None:
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id required")
        payload = self._payload(host_id, telemetry)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        with sqlite3.connect(self.path, timeout=10.0) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                INSERT OR IGNORE INTO ops_telemetry_history(
                    host_id,observed_at,payload_json
                )
                VALUES(?,?,?)
            """,(
                host_id,
                telemetry.observed_at.isoformat(),
                encoded,
            ))
            db.commit()

    def latest(self, host_id: str) -> HostTelemetry | None:
        with sqlite3.connect(self.path, timeout=10.0) as db:
            row = db.execute("""
                SELECT payload_json
                FROM ops_telemetry_history
                WHERE host_id=?
                ORDER BY observed_at DESC, row_id DESC
                LIMIT 1
            """,(host_id,)).fetchone()
        if row is None:
            return None
        raw = json.loads(row[0])
        raw.pop("host_id", None)
        raw["observed_at"] = datetime.fromisoformat(
            raw["observed_at"]
        )
        return HostTelemetry(**raw)

    def _migrate_legacy(self, legacy_path: Path) -> None:
        if not legacy_path.is_file():
            return
        rows = []
        for line in legacy_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            host_id = raw.pop("host_id")
            raw["observed_at"] = datetime.fromisoformat(
                raw["observed_at"]
            )
            telemetry = HostTelemetry(**raw)
            rows.append((host_id, telemetry))
            self.append(host_id, telemetry)

        for host_id, telemetry in rows:
            latest = self.latest(host_id)
            if latest is None:
                raise RuntimeError(
                    "legacy OPS telemetry migration did not verify"
                )

        destination = legacy_path.with_name(
            legacy_path.name + ".migrated"
        )
        index = 1
        while destination.exists():
            destination = legacy_path.with_name(
                legacy_path.name + f".migrated.{index}"
            )
            index += 1
        legacy_path.replace(destination)
