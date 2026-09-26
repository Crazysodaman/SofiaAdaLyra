"""Host foreground-activity evidence and durable operator overrides.

OPS uses this signal for placement/maintenance decisions. A manual override is
operator policy, not inferred truth. AUTO delegates to the freshest recorded
observation. Importing this module starts no process inspection or scheduler.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from sofia.system.model import ProcessInspection


class ActivityMode(str, Enum):
    AUTO = "auto"
    NORMAL = "normal"
    GAMING = "gaming"
    BUSY = "busy"
    DO_NOT_DISTURB = "do_not_disturb"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HostActivityObservation:
    host_id: str
    mode: ActivityMode
    observed_at: datetime
    source: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.host_id, str) or not self.host_id.strip():
            raise ValueError("host_id required")
        if not isinstance(self.mode, ActivityMode) or self.mode is ActivityMode.AUTO:
            raise ValueError("observations require a concrete activity mode")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source required")
        if self.detail is not None and (not isinstance(self.detail, str) or len(self.detail) > 500):
            raise ValueError("detail must be bounded text or None")


@dataclass(frozen=True)
class HostActivityState:
    host_id: str
    override: ActivityMode
    effective: ActivityMode
    observed_at: datetime | None
    source: str

    @property
    def interactive_pressure(self) -> int:
        return {
            ActivityMode.GAMING: 3,
            ActivityMode.DO_NOT_DISTURB: 2,
            ActivityMode.BUSY: 1,
        }.get(self.effective, 0)


class HostActivityStore:
    """Durable per-host manual override and latest observation."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS ops_activity_override (
                        host_id TEXT PRIMARY KEY,
                        mode TEXT NOT NULL,
                        changed_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS ops_activity_observation (
                        host_id TEXT PRIMARY KEY,
                        mode TEXT NOT NULL,
                        observed_at TEXT NOT NULL,
                        source TEXT NOT NULL,
                        detail TEXT
                    );
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _time(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone-aware timestamp required")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _host(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError("bounded host_id required")
        return value.strip()

    def set_override(self, host_id: str, mode: ActivityMode, *, at: datetime) -> None:
        host_id = self._host(host_id)
        if not isinstance(mode, ActivityMode) or mode is ActivityMode.UNKNOWN:
            raise ValueError("override must be AUTO, NORMAL, GAMING, BUSY, or DO_NOT_DISTURB")
        moment = self._time(at)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    INSERT INTO ops_activity_override(host_id, mode, changed_at)
                    VALUES (?,?,?)
                    ON CONFLICT(host_id) DO UPDATE SET
                        mode=excluded.mode, changed_at=excluded.changed_at
                    """,
                    (host_id, mode.value, moment.isoformat()),
                )

    def record(self, observation: HostActivityObservation) -> None:
        if not isinstance(observation, HostActivityObservation):
            raise TypeError("HostActivityObservation required")
        moment = self._time(observation.observed_at)
        with closing(self._connect()) as db:
            with db:
                current = db.execute(
                    "SELECT observed_at FROM ops_activity_observation WHERE host_id=?",
                    (observation.host_id,),
                ).fetchone()
                if current is not None:
                    previous = datetime.fromisoformat(current[0]).astimezone(timezone.utc)
                    if moment < previous:
                        raise ValueError("stale activity observation refused")
                db.execute(
                    """
                    INSERT INTO ops_activity_observation
                    (host_id, mode, observed_at, source, detail)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(host_id) DO UPDATE SET
                        mode=excluded.mode, observed_at=excluded.observed_at,
                        source=excluded.source, detail=excluded.detail
                    """,
                    (
                        observation.host_id,
                        observation.mode.value,
                        moment.isoformat(),
                        observation.source,
                        observation.detail,
                    ),
                )

    def state(self, host_id: str) -> HostActivityState:
        host_id = self._host(host_id)
        with closing(self._connect()) as db:
            override_row = db.execute(
                "SELECT mode FROM ops_activity_override WHERE host_id=?",
                (host_id,),
            ).fetchone()
            observation_row = db.execute(
                """
                SELECT mode, observed_at, source
                FROM ops_activity_observation WHERE host_id=?
                """,
                (host_id,),
            ).fetchone()
        override = ActivityMode(override_row[0]) if override_row else ActivityMode.AUTO
        observed_mode = ActivityMode.UNKNOWN
        observed_at = None
        source = "no-observation"
        if observation_row is not None:
            observed_mode = ActivityMode(observation_row[0])
            observed_at = datetime.fromisoformat(observation_row[1]).astimezone(timezone.utc)
            source = observation_row[2]
        if override is not ActivityMode.AUTO:
            return HostActivityState(
                host_id=host_id,
                override=override,
                effective=override,
                observed_at=observed_at,
                source="operator-override",
            )
        return HostActivityState(
            host_id=host_id,
            override=override,
            effective=observed_mode,
            observed_at=observed_at,
            source=source,
        )


_STEAM_NON_GAMES = frozenset({
    "steam.exe",
    "steamservice.exe",
    "steamwebhelper.exe",
    "gameoverlayui.exe",
    "crashhandler64.exe",
    "crashhandler.exe",
})


def detect_windows_game(
    processes: tuple[ProcessInspection, ...],
    *,
    known_game_executables: frozenset[str] = frozenset(),
) -> tuple[bool, str | None]:
    """Infer gaming from observed process paths/names without Steam web access."""

    if not isinstance(processes, tuple):
        raise TypeError("processes must be a tuple")
    known = frozenset(value.casefold() for value in known_game_executables)

    for process in processes:
        if not isinstance(process, ProcessInspection):
            raise TypeError("processes must contain ProcessInspection values")
        name = (process.name or "").casefold()
        executable = (process.executable or "").replace("/", "\\").casefold()
        if name in known:
            return True, process.name
        if (
            "\\steamapps\\common\\" in executable
            and name
            and name not in _STEAM_NON_GAMES
        ):
            return True, process.name
    return False, None
