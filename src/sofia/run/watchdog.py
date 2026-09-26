"""Independent local watchdog policy over durable RUN health evidence.

This module does not run inside Sofía automatically. A separate host process or
service owns the watchdog loop and injects an OS-service controller. The
watchdog never calls cognition, ACT, or runtime internals.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from .health import RunHealthObservation, RunHealthState, RunHeartbeatStore
from .lifecycle import RunLifecycleState, RunLifecycleStore


class HostServiceState(str, Enum):
    STOPPED = "stopped"
    START_PENDING = "start_pending"
    RUNNING = "running"
    STOP_PENDING = "stop_pending"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HostServiceObservation:
    state: HostServiceState
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, HostServiceState):
            raise TypeError("state must be HostServiceState")
        if not isinstance(self.detail, str) or len(self.detail) > 500:
            raise ValueError("detail must be bounded text")


class HostServiceController(ABC):
    @abstractmethod
    def observe(self) -> HostServiceObservation:
        raise NotImplementedError

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def restart(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class WatchdogPolicy:
    heartbeat_stale_after: timedelta = timedelta(seconds=30)
    startup_grace: timedelta = timedelta(seconds=120)
    restart_cooldown: timedelta = timedelta(seconds=30)
    restart_window: timedelta = timedelta(minutes=10)
    max_restarts_in_window: int = 3

    def __post_init__(self) -> None:
        for label, value, minimum, maximum in (
            ("heartbeat_stale_after", self.heartbeat_stale_after, timedelta(seconds=5), timedelta(minutes=10)),
            ("startup_grace", self.startup_grace, timedelta(seconds=10), timedelta(minutes=10)),
            ("restart_cooldown", self.restart_cooldown, timedelta(seconds=1), timedelta(minutes=10)),
            ("restart_window", self.restart_window, timedelta(minutes=1), timedelta(hours=24)),
        ):
            if not isinstance(value, timedelta) or not minimum <= value <= maximum:
                raise ValueError(f"{label} is outside the supported range")
        if type(self.max_restarts_in_window) is not int or not 1 <= self.max_restarts_in_window <= 20:
            raise ValueError("max_restarts_in_window must be in 1..20")


@dataclass(frozen=True, slots=True)
class WatchdogResult:
    action: str
    service: HostServiceObservation
    health: RunHealthObservation
    detail: str = ""


def _utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


class IndependentRunWatchdog:
    """One deterministic external watchdog reconciliation step."""

    def __init__(
        self,
        *,
        state_path: str | Path,
        heartbeat_store: RunHeartbeatStore,
        lifecycle_store: RunLifecycleStore,
        controller: HostServiceController,
        policy: WatchdogPolicy = WatchdogPolicy(),
    ) -> None:
        self.state_path = Path(state_path)
        if not self.state_path.is_file():
            raise FileNotFoundError("existing application state database required")
        if not isinstance(heartbeat_store, RunHeartbeatStore):
            raise TypeError("RunHeartbeatStore required")
        if not isinstance(lifecycle_store, RunLifecycleStore):
            raise TypeError("RunLifecycleStore required")
        if heartbeat_store.path.resolve() != self.state_path.resolve():
            raise ValueError("heartbeat store must use watchdog state database")
        if lifecycle_store.path.resolve() != self.state_path.resolve():
            raise ValueError("lifecycle store must use watchdog state database")
        if not isinstance(controller, HostServiceController):
            raise TypeError("HostServiceController required")
        if not isinstance(policy, WatchdogPolicy):
            raise TypeError("WatchdogPolicy required")

        self.heartbeat_store = heartbeat_store
        self.lifecycle_store = lifecycle_store
        self.controller = controller
        self.policy = policy
        with closing(self._connect()) as db:
            with db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS run_watchdog_state (
                        watchdog_key TEXT PRIMARY KEY,
                        last_action_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS run_watchdog_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        occurred_at TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        service_state TEXT NOT NULL,
                        health_state TEXT NOT NULL,
                        detail TEXT NOT NULL
                    );
                    INSERT OR IGNORE INTO run_watchdog_state
                    (watchdog_key, last_action_at)
                    VALUES ('local', NULL);
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.state_path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _event(
        self,
        *,
        now: datetime,
        event_type: str,
        service: HostServiceObservation,
        health: RunHealthObservation,
        detail: str,
        action: bool = False,
    ) -> None:
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    INSERT INTO run_watchdog_events
                    (occurred_at, event_type, service_state, health_state, detail)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        now.isoformat(),
                        event_type,
                        service.state.value,
                        health.state.value,
                        detail[:500],
                    ),
                )
                if action:
                    db.execute(
                        """
                        UPDATE run_watchdog_state SET last_action_at=?
                        WHERE watchdog_key='local'
                        """,
                        (now.isoformat(),),
                    )

    def _restart_count(self, now: datetime) -> int:
        cutoff = now - self.policy.restart_window
        with closing(self._connect()) as db:
            return int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM run_watchdog_events
                    WHERE event_type IN ('service_start','service_restart')
                      AND occurred_at>=?
                    """,
                    (cutoff.isoformat(),),
                ).fetchone()[0]
            )

    def _cooldown_active(self, now: datetime) -> bool:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT last_action_at FROM run_watchdog_state
                WHERE watchdog_key='local'
                """
            ).fetchone()
        if row is None or row[0] is None:
            return False
        return now < (
            datetime.fromisoformat(row[0]).astimezone(timezone.utc)
            + self.policy.restart_cooldown
        )

    def _can_recover(self, now: datetime) -> tuple[bool, str]:
        if self._cooldown_active(now):
            return False, "watchdog recovery cooldown active"
        if self._restart_count(now) >= self.policy.max_restarts_in_window:
            return False, "watchdog restart window limit reached"
        return True, ""

    def reconcile(
        self,
        *,
        now: datetime,
        desired_running: bool = True,
    ) -> WatchdogResult:
        if not isinstance(desired_running, bool):
            raise TypeError("desired_running must be boolean")
        moment = _utc(now)
        service = self.controller.observe()
        if not isinstance(service, HostServiceObservation):
            raise TypeError("controller.observe must return HostServiceObservation")
        health = self.heartbeat_store.assess(
            now=moment,
            stale_after=self.policy.heartbeat_stale_after,
        )
        lifecycle = self.lifecycle_store.current()

        if lifecycle.state is RunLifecycleState.FENCED:
            if service.state in (HostServiceState.RUNNING, HostServiceState.START_PENDING):
                self.controller.stop()
                self._event(
                    now=moment,
                    event_type="fenced_stop",
                    service=service,
                    health=health,
                    detail="service stopped because RUN lifecycle is fenced",
                    action=True,
                )
                return WatchdogResult("fenced_stopped", service, health)
            return WatchdogResult(
                "fenced",
                service,
                health,
                "fenced RUN lifecycle blocks automatic start",
            )

        if not desired_running:
            if service.state in (HostServiceState.RUNNING, HostServiceState.START_PENDING):
                self.controller.stop()
                self._event(
                    now=moment,
                    event_type="desired_stop",
                    service=service,
                    health=health,
                    detail="operator/policy requested service stop",
                    action=True,
                )
                return WatchdogResult("stopped", service, health)
            return WatchdogResult("already_stopped", service, health)

        if service.state is HostServiceState.UNKNOWN:
            return WatchdogResult(
                "unknown_service",
                service,
                health,
                "watchdog refuses recovery while service state is unknown",
            )

        if service.state is HostServiceState.STOP_PENDING:
            return WatchdogResult("waiting_stop", service, health)

        if service.state is HostServiceState.START_PENDING:
            age = moment - lifecycle.updated_at
            if age <= self.policy.startup_grace:
                return WatchdogResult("waiting_start", service, health)
            allowed, reason = self._can_recover(moment)
            if not allowed:
                return WatchdogResult("recovery_blocked", service, health, reason)
            self.controller.restart()
            self._event(
                now=moment,
                event_type="service_restart",
                service=service,
                health=health,
                detail="service exceeded startup grace",
                action=True,
            )
            return WatchdogResult("restarted", service, health, "startup grace exceeded")

        if service.state is HostServiceState.STOPPED:
            allowed, reason = self._can_recover(moment)
            if not allowed:
                return WatchdogResult("recovery_blocked", service, health, reason)
            self.controller.start()
            self._event(
                now=moment,
                event_type="service_start",
                service=service,
                health=health,
                detail="desired service was stopped",
                action=True,
            )
            return WatchdogResult("started", service, health)

        assert service.state is HostServiceState.RUNNING

        if health.state in (
            RunHealthState.HEALTHY,
            RunHealthState.DEGRADED,
            RunHealthState.STARTING,
            RunHealthState.STOPPING,
        ):
            return WatchdogResult("healthy", service, health)

        if health.state is RunHealthState.UNKNOWN:
            age = moment - lifecycle.updated_at
            if lifecycle.state in (
                RunLifecycleState.STARTING,
                RunLifecycleState.RECOVERING,
            ) and age <= self.policy.startup_grace:
                return WatchdogResult("waiting_heartbeat", service, health)

        if health.state in (
            RunHealthState.STALE,
            RunHealthState.FAILED,
            RunHealthState.UNKNOWN,
        ):
            allowed, reason = self._can_recover(moment)
            if not allowed:
                return WatchdogResult("recovery_blocked", service, health, reason)
            self.controller.restart()
            self._event(
                now=moment,
                event_type="service_restart",
                service=service,
                health=health,
                detail=f"unhealthy service evidence: {health.state.value}",
                action=True,
            )
            return WatchdogResult(
                "restarted",
                service,
                health,
                f"health={health.state.value}",
            )

        return WatchdogResult(
            "observe_only",
            service,
            health,
            f"no automatic action for health={health.state.value}",
        )

    def events(self) -> tuple[tuple[str, str, str, str, str], ...]:
        with closing(self._connect()) as db:
            return tuple(
                db.execute(
                    """
                    SELECT occurred_at, event_type, service_state,
                           health_state, detail
                    FROM run_watchdog_events ORDER BY event_id
                    """
                )
            )
