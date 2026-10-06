"""Production bridge from canonical subsystem evidence into NEURO attention."""
from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from sofia.emotion.model import CurrentEmotionalState
from sofia.environment.model import EnvironmentSnapshot
from sofia.ops.model import HostTelemetry
from sofia.voice import TTSStatus
from sofia.state.plane import StatePlane

from .adapters import (
    _signal,
    avatar_signals,
    body_signals,
    emotion_signals,
    environment_signals,
    recency_value,
    telemetry_signals,
    voice_signals,
)
from .model import NeuralSignal, NeuroStateSnapshot
from .runtime import NeuroRuntime


CURRENT_STATE_KINDS = frozenset({
    "environment", "emotion", "ops", "fleet", "memory", "habit",
    "relationship", "goal", "run", "interaction", "avatar", "voice",
    "body",
})


def _ref(value: object) -> str:
    return sha256(str(value).encode("utf-8")).hexdigest()[:16]


class NeuroInputCoordinator:
    """Read-only orchestration over state owners; never executes selected goals."""

    def __init__(
        self,
        runtime: NeuroRuntime,
        state_path: str | Path,
        *,
        state_plane: StatePlane | None = None,
    ) -> None:
        if not isinstance(runtime, NeuroRuntime):
            raise TypeError("runtime must be NeuroRuntime")
        self.runtime = runtime
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("canonical state database is required")
        if state_plane is not None and not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be StatePlane or None")
        self.state_plane = state_plane
        self.last_error: str | None = None

    def _connect(self) -> sqlite3.Connection:
        uri = self.path.resolve().as_uri() + "?mode=ro"
        db = sqlite3.connect(uri, uri=True, timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _has_table(db: sqlite3.Connection, name: str) -> bool:
        return db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone() is not None

    def _durable_signals(
        self,
        *,
        now: datetime,
        session_id: str | None,
    ) -> tuple[NeuralSignal, ...]:
        result: list[NeuralSignal] = []
        with closing(self._connect()) as db:
            if self._has_table(db, "distributed_node_identity"):
                active = db.execute(
                    "SELECT COUNT(*) FROM distributed_node_identity WHERE retired=0"
                ).fetchone()[0]
                if active:
                    result.append(_signal(
                        kind="fleet", source="nodes:enrolled",
                        value=min(1.0, 0.25 + active * 0.08), confidence=1.0,
                        novelty=0.2, urgency=0.15, observed_at=now,
                        ttl_seconds=600.0,
                    ))
            if self._has_table(db, "ops_fleet_reconciliation"):
                drift = db.execute(
                    "SELECT COUNT(*) FROM ops_fleet_reconciliation WHERE active=1"
                ).fetchone()[0]
                if drift:
                    result.append(_signal(
                        kind="fleet", source="reconciliation:drift",
                        value=min(1.0, 0.55 + drift * 0.08), confidence=1.0,
                        novelty=0.7, urgency=min(1.0, 0.6 + drift * 0.07),
                        observed_at=now, ttl_seconds=600.0,
                    ))
            if self._has_table(db, "ops_workload_instance"):
                failed = db.execute(
                    "SELECT COUNT(*) FROM ops_workload_instance WHERE phase='failed'"
                ).fetchone()[0]
                if failed:
                    result.append(_signal(
                        kind="fleet", source="workload:failed",
                        value=min(1.0, 0.65 + failed * 0.08), confidence=1.0,
                        novelty=0.75, urgency=min(1.0, 0.72 + failed * 0.06),
                        observed_at=now, ttl_seconds=300.0,
                    ))
            if self._has_table(db, "application_background_claims"):
                working = db.execute(
                    "SELECT COUNT(*) FROM application_background_claims WHERE status='working'"
                ).fetchone()[0]
                recent_cutoff = (now - timedelta(hours=24)).isoformat()
                failed = db.execute("""
                    SELECT COUNT(*) FROM application_background_claims
                    WHERE status='failed' AND finished_at>=?
                """, (recent_cutoff,)).fetchone()[0]
                if working:
                    result.append(_signal(
                        kind="run", source="background:working",
                        value=min(1.0, 0.35 + working * 0.1), confidence=1.0,
                        novelty=0.3, urgency=0.35, observed_at=now,
                        ttl_seconds=180.0,
                    ))
                if failed:
                    result.append(_signal(
                        kind="run", source="background:failed",
                        value=min(1.0, 0.65 + failed * 0.08), confidence=1.0,
                        novelty=0.7, urgency=min(1.0, 0.7 + failed * 0.06),
                        observed_at=now, ttl_seconds=600.0,
                    ))
            if (
                self._has_table(db, "run_application_heartbeat")
                and self._has_table(db, "run_application_heartbeat_current")
            ):
                row = db.execute("""
                    SELECT h.ready,h.database_writable,h.background_running
                    FROM run_application_heartbeat_current c
                    JOIN run_application_heartbeat h
                      ON h.instance_id=c.instance_id
                    WHERE c.singleton=1
                """).fetchone()
                if row is not None and not all(bool(value) for value in row):
                    result.append(_signal(
                        kind="run", source="application:degraded",
                        value=0.85, confidence=1.0, novelty=0.7,
                        urgency=0.82, observed_at=now, ttl_seconds=180.0,
                    ))
            if session_id and self._has_table(db, "interaction_session_controls"):
                row = db.execute(
                    "SELECT stopped FROM interaction_session_controls WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                if row and row[0]:
                    result.append(_signal(
                        kind="interaction", source="session:stopped",
                        value=1.0, confidence=1.0, novelty=0.4, urgency=1.0,
                        observed_at=now, ttl_seconds=900.0,
                    ))
            if self._has_table(db, "interact_queued_messages"):
                queued = db.execute(
                    "SELECT COUNT(*) FROM interact_queued_messages WHERE status='queued'"
                ).fetchone()[0]
                if queued:
                    result.append(_signal(
                        kind="run", source="outreach:queued",
                        value=min(1.0, 0.45 + queued * 0.08), confidence=1.0,
                        novelty=0.4, urgency=min(0.8, 0.4 + queued * 0.06),
                        observed_at=now, ttl_seconds=300.0,
                    ))
            if self._has_table(db, "act_system_notice"):
                row = db.execute("""
                    SELECT COUNT(*),MAX(salience) FROM act_system_notice
                    WHERE status='queued' AND expires_at>?
                """, (now.isoformat(),)).fetchone()
                if row and row[0]:
                    salience = max(0.0, min(1.0, float(row[1] or 0.5)))
                    result.append(_signal(
                        kind="run", source="system-notice:queued",
                        value=salience, confidence=1.0, novelty=0.55,
                        urgency=max(0.45, salience), observed_at=now,
                        ttl_seconds=300.0,
                    ))
            if session_id and self._has_table(db, "interaction_evidence"):
                row = db.execute("""
                    SELECT status,occurred_at FROM interaction_evidence
                    WHERE session_id=? ORDER BY occurred_at DESC LIMIT 1
                """, (session_id,)).fetchone()
                if row is not None:
                    try:
                        occurred = datetime.fromisoformat(row[1]).astimezone(timezone.utc)
                    except (TypeError, ValueError):
                        occurred = now
                    result.append(_signal(
                        kind="interaction", source=f"recent:{row[0]}",
                        value=0.55, confidence=1.0, novelty=0.35, urgency=0.3,
                        observed_at=min(occurred, now), ttl_seconds=600.0,
                    ))
        return tuple(result)

    def _fleet_state_signals(self, *, now: datetime) -> tuple[NeuralSignal, ...]:
        if self.state_plane is None:
            return ()
        severity = {
            "candidate": (0.55, 0.5),
            "degraded": (0.8, 0.78),
            "maintenance": (0.45, 0.3),
            "draining": (0.6, 0.5),
            "quarantined": (0.9, 0.88),
            "offline": (1.0, 0.95),
        }
        result: list[NeuralSignal] = []
        for record in self.state_plane.list_namespace("ops-fleet-host"):
            try:
                payload = json.loads(record.value.decode("utf-8"))
                lifecycle = str(payload["lifecycle"])
                trusted = bool(payload["trusted"])
                host_id = payload["host_id"]
            except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
                result.append(_signal(
                    kind="fleet", source="registry:invalid-record",
                    value=0.9, confidence=1.0, novelty=0.8, urgency=0.9,
                    observed_at=now, ttl_seconds=600.0,
                ))
                continue
            if lifecycle in severity:
                value, urgency = severity[lifecycle]
                label = (
                    "candidate-untrusted"
                    if lifecycle == "candidate" and not trusted
                    else lifecycle
                )
                result.append(_signal(
                    kind="fleet", source=f"{label}:{_ref(host_id)}",
                    value=value, confidence=1.0, novelty=0.65,
                    urgency=urgency, observed_at=now, ttl_seconds=600.0,
                ))
        return tuple(result)

    def refresh(
        self,
        *,
        now: datetime,
        environment: EnvironmentSnapshot,
        emotion: CurrentEmotionalState | None = None,
        telemetry: HostTelemetry | None = None,
        voice: TTSStatus | None = None,
        avatar: dict | None = None,
        memories: tuple[object, ...] = (),
        habits: tuple[object, ...] = (),
        relationship: object | None = None,
        goal_priorities: tuple[tuple[object, float], ...] = (),
        session_id: str | None = None,
    ) -> NeuroStateSnapshot:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        signals: list[NeuralSignal] = [
            *environment_signals(environment),
            *body_signals(environment),
        ]
        if emotion is not None:
            signals.extend(emotion_signals(emotion))
        if telemetry is not None:
            signals.extend(telemetry_signals(telemetry))
        if voice is not None:
            signals.extend(voice_signals(voice, observed_at=now))
        if avatar is not None:
            signals.extend(avatar_signals(avatar, observed_at=now))
        for index, memory in enumerate(memories[:5]):
            memory_id = getattr(memory, "id", index)
            signals.append(_signal(
                kind="memory", source=f"candidate:{_ref(memory_id)}",
                value=max(0.35, 0.85 - index * 0.1), confidence=1.0,
                novelty=max(0.25, 0.65 - index * 0.08), urgency=0.35,
                observed_at=now, ttl_seconds=300.0,
            ))
        for pattern in habits[:8]:
            confidence = float(getattr(pattern, "confidence", 0.0))
            if confidence <= 0.0:
                continue
            signals.append(_signal(
                kind="habit",
                source=f"pattern:{_ref(getattr(pattern, 'pattern_id', pattern))}",
                value=confidence, confidence=1.0, novelty=0.25,
                urgency=min(0.6, 0.2 + confidence * 0.35),
                observed_at=now, ttl_seconds=900.0,
            ))
        if relationship is not None:
            occurred = getattr(relationship, "occurred_at", None)
            if isinstance(occurred, datetime):
                value = recency_value(
                    occurred_at=occurred.astimezone(timezone.utc), now=now,
                    half_life_hours=24.0,
                )
                signals.append(_signal(
                    kind="relationship", source="contact:recent",
                    value=value, confidence=1.0, novelty=0.25,
                    urgency=0.2 + value * 0.25, observed_at=now,
                    ttl_seconds=1800.0,
                ))
        if (
            not isinstance(goal_priorities, tuple)
            or len(goal_priorities) > 32
        ):
            raise ValueError("goal priorities must be a bounded tuple")
        for item in goal_priorities:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("goal priority entries must be (goal, priority)")
            goal, priority = item
            if (
                isinstance(priority, bool)
                or not isinstance(priority, (int, float))
                or not 0.0 <= float(priority) <= 1.0
            ):
                raise ValueError("goal priority must be in 0..1")
            goal_id = getattr(goal, "id", None)
            status = getattr(getattr(goal, "status", None), "value", None)
            confidence = getattr(goal, "confidence", None)
            if (
                not isinstance(goal_id, str)
                or status != "active"
                or isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
            ):
                raise ValueError("only typed active goals may enter NEURO")
            level = min(0.9, float(priority))
            signals.append(_signal(
                kind="goal", source=f"active:{_ref(goal_id)}",
                value=level, confidence=float(confidence),
                novelty=0.35, urgency=min(0.85, level),
                observed_at=now, ttl_seconds=180.0,
            ))
        signals.extend(self._durable_signals(now=now, session_id=session_id))
        signals.extend(self._fleet_state_signals(now=now))
        bounded_signals = tuple(
            signal
            if signal.observed_at <= now
            else replace(signal, observed_at=now)
            for signal in signals
        )
        try:
            snapshot = self.runtime.replace_signals(
                kinds=CURRENT_STATE_KINDS,
                signals=bounded_signals,
                now=now,
            )
            self.last_error = None
            return snapshot
        except Exception as exc:
            self.last_error = type(exc).__name__
            raise

    def observe_reflex(self, signal: NeuralSignal) -> NeuroStateSnapshot:
        """Accept a trusted Gaia/BODY reflex summary, never a motor command."""
        if not isinstance(signal, NeuralSignal) or signal.kind != "body":
            raise ValueError("reflex bridge accepts only a typed body signal")
        return self.runtime.observe_signal(signal)
