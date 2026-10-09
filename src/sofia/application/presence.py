"""Application-owned world-state snapshots and bounded initiative decisions.

This module does not send messages itself, grant authority, or infer facts from
NEURO. It records host-supplied observations and feeds justified opportunities
into the existing ACT queue.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable

from sofia.act.outreach import Importance, OutreachCategory
from sofia.application.act_service import SofiaActService
from sofia.social.principals import SPARKS_PRINCIPAL_ID


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


class WorldEpistemicState(str, Enum):
    OBSERVED = "observed"
    KNOWN = "known"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class WorldAvailability(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ONLINE = "online"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class WorldObservation:
    observation_id: str
    subject_id: str
    predicate: str
    source_id: str
    observed_at: datetime
    expires_at: datetime | None
    confidence: float
    epistemic_state: WorldEpistemicState
    availability: WorldAvailability
    value: object
    audience_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("observation_id", "subject_id", "predicate", "source_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{name} must be a bounded identifier")
        if (
            self.audience_id is not None
            and (not isinstance(self.audience_id, str) or _ID.fullmatch(self.audience_id) is None)
        ):
            raise ValueError("audience_id must be a bounded identifier or None")
        for name in ("observed_at", "expires_at"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(f"{name} must be timezone-aware")
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("confidence must be in 0..1")
        if not isinstance(self.epistemic_state, WorldEpistemicState):
            raise TypeError("epistemic_state must be WorldEpistemicState")
        if not isinstance(self.availability, WorldAvailability):
            raise TypeError("availability must be WorldAvailability")
        json.dumps(self.value, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True, slots=True)
class InitiativeEvent:
    event_id: str
    trigger_kind: str
    observation: WorldObservation
    content: str
    created_at: datetime
    expires_at: datetime
    category: OutreachCategory
    importance: Importance
    salience: float
    recipient_id: str = SPARKS_PRINCIPAL_ID

    def __post_init__(self) -> None:
        for name in ("event_id", "trigger_kind", "recipient_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{name} must be a bounded identifier")
        if not isinstance(self.observation, WorldObservation):
            raise TypeError("observation must be WorldObservation")
        if not isinstance(self.content, str) or not self.content.strip() or len(self.content) > 640:
            raise ValueError("content must be bounded nonempty text")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if not isinstance(self.category, OutreachCategory):
            raise TypeError("category must be OutreachCategory")
        if not isinstance(self.importance, Importance):
            raise TypeError("importance must be Importance")
        if (
            isinstance(self.salience, bool)
            or not isinstance(self.salience, (int, float))
            or not 0.0 <= float(self.salience) <= 1.0
        ):
            raise ValueError("salience must be in 0..1")


@dataclass(frozen=True, slots=True)
class InitiativeDecision:
    event_id: str
    status: str
    reason: str
    notice_id: str | None


class PresenceInitiativeEngine:
    """Persist world snapshots and enqueue only reviewed event classes in ACT."""

    _ELIGIBLE_TRIGGERS = frozenset({
        "approval_request", "conversation_followup", "dev_finding",
        "fleet_anomaly", "goal_change", "operational_alert",
        "reflection", "task_completed",
    })

    def __init__(
        self,
        *,
        state_path: Path | str,
        act_service: SofiaActService,
        neuro_priority: Callable[[str], float] | None = None,
    ) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        if not isinstance(act_service, SofiaActService):
            raise TypeError("act_service must be SofiaActService")
        if neuro_priority is not None and not callable(neuro_priority):
            raise TypeError("neuro_priority must be callable or None")
        self.act_service = act_service
        self.neuro_priority = neuro_priority
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS presence_world_observation (
                    observation_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    expires_at TEXT,
                    confidence REAL NOT NULL,
                    epistemic_state TEXT NOT NULL,
                    availability TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    audience_id TEXT
                );
                CREATE INDEX IF NOT EXISTS presence_world_subject
                    ON presence_world_observation(subject_id,predicate,observed_at DESC);
                CREATE TABLE IF NOT EXISTS presence_initiative_opportunity (
                    event_id TEXT PRIMARY KEY,
                    observation_id TEXT NOT NULL,
                    trigger_kind TEXT NOT NULL,
                    recipient_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    notice_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS presence_opportunity_recent
                    ON presence_initiative_opportunity(created_at DESC,event_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    def observe(self, observation: WorldObservation) -> WorldObservation:
        if not isinstance(observation, WorldObservation):
            raise TypeError("observation must be WorldObservation")
        desired = (
            observation.observation_id, observation.subject_id,
            observation.predicate, observation.source_id,
            self._utc(observation.observed_at).isoformat(),
            None if observation.expires_at is None else self._utc(observation.expires_at).isoformat(),
            float(observation.confidence), observation.epistemic_state.value,
            observation.availability.value,
            json.dumps(observation.value, ensure_ascii=False, sort_keys=True),
            observation.audience_id,
        )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT * FROM presence_world_observation WHERE observation_id=?",
                (observation.observation_id,),
            ).fetchone()
            if old is not None:
                if tuple(old) != desired:
                    raise ValueError("observation_id reused for different world state")
                return observation
            db.execute(
                "INSERT INTO presence_world_observation VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                desired,
            )
            db.execute(
                """
                DELETE FROM presence_world_observation WHERE observation_id IN (
                    SELECT observation_id FROM presence_world_observation
                    ORDER BY observed_at DESC,observation_id DESC LIMIT -1 OFFSET 2000
                )
                """
            )
        return observation

    def consider(self, event: InitiativeEvent) -> InitiativeDecision:
        if not isinstance(event, InitiativeEvent):
            raise TypeError("event must be InitiativeEvent")
        self.observe(event.observation)
        with closing(self._connect()) as db:
            old = db.execute(
                "SELECT status,reason,notice_id FROM presence_initiative_opportunity "
                "WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
        if old is not None:
            return InitiativeDecision(event.event_id, old[0], old[1], old[2])

        status = "suppressed"
        reason = "unsupported_trigger"
        notice_id = None
        grounded = (
            event.observation.epistemic_state in {
                WorldEpistemicState.OBSERVED, WorldEpistemicState.KNOWN,
            }
            and event.observation.confidence >= 0.6
        )
        if event.trigger_kind in self._ELIGIBLE_TRIGGERS and not grounded:
            reason = "insufficient_grounding"
        elif event.trigger_kind in self._ELIGIBLE_TRIGGERS:
            route = self.act_service.delivery_route
            if route is None:
                reason = "missing_transport"
            else:
                channel, destination = route
                priority = 0.0
                if self.neuro_priority is not None:
                    priority = max(0.0, min(1.0, float(
                        self.neuro_priority("presence_initiative")
                    )))
                salience = max(float(event.salience), priority * 0.5)
                notice_id = "presence:" + sha256(
                    event.event_id.encode("utf-8")
                ).hexdigest()[:32]
                evidence_id = "presence-evidence:" + sha256(
                    event.observation.observation_id.encode("utf-8")
                ).hexdigest()[:32]
                self.act_service.queue_system_notice(
                    notice_id=notice_id,
                    recipient_id=event.recipient_id,
                    channel=channel,
                    destination=destination,
                    evidence_id=evidence_id,
                    content=event.content.strip(),
                    created_at=event.created_at,
                    expires_at=event.expires_at,
                    category=event.category,
                    importance=event.importance,
                    salience=salience,
                )
                status = "queued"
                reason = "evidence_backed_candidate"
        decision = InitiativeDecision(event.event_id, status, reason, notice_id)
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO presence_initiative_opportunity VALUES(?,?,?,?,?,?,?,?)",
                (
                    event.event_id, event.observation.observation_id,
                    event.trigger_kind, event.recipient_id, status, reason,
                    notice_id, self._utc(event.created_at).isoformat(),
                ),
            )
        return decision

    def record_state(
        self,
        *,
        observation_id: str,
        subject_id: str,
        predicate: str,
        source_id: str,
        observed_at: datetime,
        freshness: timedelta | None,
        confidence: float,
        epistemic_state: WorldEpistemicState,
        availability: WorldAvailability,
        value: object,
        audience_id: str | None = None,
    ) -> WorldObservation:
        return self.observe(WorldObservation(
            observation_id=observation_id,
            subject_id=subject_id,
            predicate=predicate,
            source_id=source_id,
            observed_at=observed_at,
            expires_at=(None if freshness is None else observed_at + freshness),
            confidence=confidence,
            epistemic_state=epistemic_state,
            availability=availability,
            value=value,
            audience_id=audience_id,
        ))
