"""Durable append-only fleet telemetry history."""
from __future__ import annotations
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
from sofia.platform.state.atomic_file import retire_legacy_file
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from pathlib import Path
import sqlite3
from .model import HostTelemetry

class SQLiteTelemetryHistory:
    """Canonical SQLite append-only Fleet telemetry history."""

    def __init__(
        self,
        path: Path,
        *,
        legacy_path: Path | None = None,
    ) -> None:
        self.path = Path(path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
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

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10.0)

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
        with closing(self._connect()) as db, db:
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
        with closing(self._connect()) as db, db:
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

    def observations(
        self,
        host_id: str,
        *,
        through: datetime,
        limit: int = 64,
    ) -> tuple[HostTelemetry, ...]:
        """Return a bounded chronological point-in-time telemetry window."""
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id required")
        if through.tzinfo is None or through.utcoffset() is None:
            raise ValueError("through must be timezone-aware")
        if type(limit) is not int or not 1 <= limit <= 512:
            raise ValueError("limit must be in [1, 512]")
        cutoff = through.astimezone(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT payload_json FROM ops_telemetry_history "
                "WHERE host_id=? AND observed_at<=? "
                "ORDER BY observed_at DESC,row_id DESC LIMIT ?",
                (host_id, cutoff, limit),
            ).fetchall()
        result = []
        for row in reversed(rows):
            raw = json.loads(row[0])
            raw.pop("host_id", None)
            raw["observed_at"] = datetime.fromisoformat(raw["observed_at"])
            result.append(HostTelemetry(**raw))
        return tuple(result)

    def ingestion_window(
        self,
        host_id: str,
        *,
        through: datetime,
        limit: int = 64,
    ) -> tuple[HostTelemetry, ...]:
        """Return a bounded point-in-time window in source ingestion order.

        Forecast labels must not silently reorder late or replayed telemetry.
        This view lets a consumer reject a non-monotonic source sequence while
        ``observations`` remains the canonical chronological query for OPS UI.
        """
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id required")
        if through.tzinfo is None or through.utcoffset() is None:
            raise ValueError("through must be timezone-aware")
        if type(limit) is not int or not 1 <= limit <= 512:
            raise ValueError("limit must be in [1, 512]")
        cutoff = through.astimezone(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT payload_json FROM ("
                "SELECT row_id,payload_json FROM ops_telemetry_history "
                "WHERE host_id=? AND observed_at<=? ORDER BY row_id DESC LIMIT ?"
                ") ORDER BY row_id",
                (host_id, cutoff, limit),
            ).fetchall()
        result = []
        for row in rows:
            raw = json.loads(row[0])
            raw.pop("host_id", None)
            raw["observed_at"] = datetime.fromisoformat(raw["observed_at"])
            result.append(HostTelemetry(**raw))
        return tuple(result)

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

        with closing(self._connect()) as db, db:
            for host_id, telemetry in rows:
                payload = self._payload(host_id, telemetry)
                encoded = json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                present = db.execute("""
                    SELECT 1
                    FROM ops_telemetry_history
                    WHERE host_id=? AND observed_at=? AND payload_json=?
                """,(
                    host_id,
                    telemetry.observed_at.isoformat(),
                    encoded,
                )).fetchone()
                if present is None:
                    raise RuntimeError(
                        "legacy OPS telemetry migration did not verify"
                    )

        retire_legacy_file(legacy_path)
