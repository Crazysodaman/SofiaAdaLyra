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
import math
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable

from sofia.act.outreach import Importance, OutreachCategory
from sofia.application.act_service import SofiaActService
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


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


class ObservationModality(str, Enum):
    VOICE = "voice"
    SCREEN = "screen"
    ENVIRONMENT = "environment"
    FLEET = "fleet"
    APP = "app"
    WEB = "web"


class OriginalDataAccess(str, Enum):
    VERIFIED_REF = "verified_ref"
    NOT_RETAINED = "not_retained"
    UNAVAILABLE = "unavailable"


class ObservationPrivacy(str, Enum):
    PUBLIC = "public"
    PERSONAL = "personal"
    PRIVATE = "private"
    PROTECTED = "protected"


@dataclass(frozen=True, slots=True)
class CrossModalObservationReceipt:
    """Source-linked metadata, not proof of perception or external authority."""

    observation_id: str
    modality: ObservationModality
    source_id: str
    observed_at: datetime
    received_at: datetime
    expires_at: datetime | None
    original_access: OriginalDataAccess
    original_ref: str | None
    privacy: ObservationPrivacy
    interpretation_confidence: float | None
    epistemic_state: WorldEpistemicState

    def __post_init__(self) -> None:
        for label, value in (
            ("observation ID",self.observation_id),
            ("source ID",self.source_id),
        ):
            if not isinstance(value,str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be bounded machine-safe ID")
        if not isinstance(self.modality, ObservationModality):
            raise TypeError("modality must be an explicit source channel")
        if not isinstance(self.original_access,OriginalDataAccess):
            raise TypeError("original data access must be explicit")
        if not isinstance(self.privacy,ObservationPrivacy):
            raise TypeError("observation privacy must be explicit")
        if not isinstance(self.epistemic_state,WorldEpistemicState):
            raise TypeError("epistemic state must be explicit")
        for value in (self.observed_at,self.received_at):
            if (
                not isinstance(value,datetime)
                or value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("source/host timestamps must be timezone-aware")
        if self.expires_at is not None and (
            not isinstance(self.expires_at,datetime)
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or self.expires_at <= self.observed_at
        ):
            raise ValueError("expiry must follow source observation")
        if self.original_access is OriginalDataAccess.VERIFIED_REF:
            if (
                not isinstance(self.original_ref,str)
                or _ID.fullmatch(self.original_ref) is None
            ):
                raise ValueError("verified original requires bounded source ref")
        elif self.original_ref is not None:
            raise ValueError("unavailable original must not invent source ref")
        confidence = self.interpretation_confidence
        if confidence is not None and (
            isinstance(confidence,bool)
            or not isinstance(confidence,(int,float))
            or not math.isfinite(confidence)
            or not 0.0 <= confidence <= 1.0
        ):
            raise ValueError("interpretation confidence must be finite 0..1")

    def validate(self, observation: WorldObservation) -> None:
        if not isinstance(observation,WorldObservation):
            raise TypeError("canonical WorldObservation required")
        if (
            self.observation_id != observation.observation_id
            or self.source_id != observation.source_id
            or self.observed_at.astimezone(timezone.utc) !=
                observation.observed_at.astimezone(timezone.utc)
            or self.epistemic_state is not observation.epistemic_state
        ):
            raise ValueError("cross-modal metadata disagrees with source observation")
        if (self.expires_at is None) != (observation.expires_at is None):
            raise ValueError("cross-modal expiry disagrees with source observation")
        if (
            self.expires_at is not None
            and self.expires_at.astimezone(timezone.utc) !=
                observation.expires_at.astimezone(timezone.utc)
        ):
            raise ValueError("cross-modal expiry disagrees with source observation")
        if self.original_access is OriginalDataAccess.UNAVAILABLE and (
            observation.epistemic_state is WorldEpistemicState.OBSERVED
        ):
            raise ValueError("unavailable original cannot claim directly observed fact")


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
        self._guard = CanonicalSQLiteGuard(self.path)
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
                CREATE TABLE IF NOT EXISTS presence_cross_modal_receipt (
                    observation_id TEXT PRIMARY KEY,
                    modality TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    expires_at TEXT,
                    original_access TEXT NOT NULL,
                    original_ref TEXT,
                    privacy TEXT NOT NULL,
                    interpretation_confidence REAL,
                    epistemic_state TEXT NOT NULL
                );
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
        # A vanished owner state cannot become an invented second observation
        # and outreach history during background refresh or reconnection.
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    def observe(
        self, observation: WorldObservation, *,
        receipt: CrossModalObservationReceipt | None = None,
    ) -> WorldObservation:
        if not isinstance(observation, WorldObservation):
            raise TypeError("observation must be WorldObservation")
        if receipt is not None:
            if not isinstance(receipt,CrossModalObservationReceipt):
                raise TypeError("cross-modal receipt must be typed")
            receipt.validate(observation)
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
            else:
                db.execute(
                    "INSERT INTO presence_world_observation VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    desired,
                )
            if receipt is not None:
                stamp=lambda value: (
                    None if value is None else
                    value.astimezone(timezone.utc).isoformat()
                )
                record=(
                    receipt.observation_id,receipt.modality.value,
                    receipt.source_id,stamp(receipt.observed_at),
                    stamp(receipt.received_at),stamp(receipt.expires_at),
                    receipt.original_access.value,receipt.original_ref,
                    receipt.privacy.value,receipt.interpretation_confidence,
                    receipt.epistemic_state.value,
                )
                prior=db.execute(
                    "SELECT * FROM presence_cross_modal_receipt "
                    "WHERE observation_id=?", (receipt.observation_id,),
                ).fetchone()
                if prior is not None and tuple(prior) != record:
                    raise ValueError("cross-modal receipt changed for original source")
                if prior is None:
                    db.execute(
                        "INSERT INTO presence_cross_modal_receipt "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",record,
                    )
            db.execute(
                """
                DELETE FROM presence_world_observation WHERE observation_id IN (
                    SELECT observation_id FROM presence_world_observation
                    ORDER BY observed_at DESC,observation_id DESC LIMIT -1 OFFSET 2000
                )
                """
            )
            db.execute(
                "DELETE FROM presence_cross_modal_receipt "
                "WHERE observation_id NOT IN "
                "(SELECT observation_id FROM presence_world_observation)"
            )
        return observation

    def source_receipt(
        self, *, observation_id: str, audience_id: str | None,
    ) -> CrossModalObservationReceipt | None:
        """Return only provenance visible in its original audience scope.

        A private/protected original without an explicit audience binding
        stays inaccessible, including to a client with the same owner ID.
        This does not authorize downloading or displaying original bytes.
        """
        if not isinstance(observation_id,str) or _ID.fullmatch(observation_id) is None:
            raise ValueError("exact bounded observation ID required")
        if audience_id is not None and (
            not isinstance(audience_id,str) or _ID.fullmatch(audience_id) is None
        ):
            raise ValueError("bounded requester audience required")
        with closing(self._connect()) as db:
            row=db.execute(
                "SELECT r.*,o.audience_id AS source_audience "
                "FROM presence_cross_modal_receipt AS r "
                "JOIN presence_world_observation AS o "
                "ON o.observation_id=r.observation_id "
                "WHERE r.observation_id=?", (observation_id,),
            ).fetchone()
        if row is None:
            return None
        if row["privacy"] != ObservationPrivacy.PUBLIC.value:
            if row["source_audience"] is None or row["source_audience"] != audience_id:
                raise PermissionError(
                    "observation provenance not visible in this audience"
                )
        elif row["source_audience"] is not None and (
            row["source_audience"] != audience_id
        ):
            raise PermissionError("observation audience does not match")
        return CrossModalObservationReceipt(
            observation_id=row["observation_id"],
            modality=ObservationModality(row["modality"]),
            source_id=row["source_id"],
            observed_at=datetime.fromisoformat(row["observed_at"]),
            received_at=datetime.fromisoformat(row["received_at"]),
            expires_at=None if row["expires_at"] is None else datetime.fromisoformat(
                row["expires_at"]
            ),
            original_access=OriginalDataAccess(row["original_access"]),
            original_ref=row["original_ref"],
            privacy=ObservationPrivacy(row["privacy"]),
            interpretation_confidence=row["interpretation_confidence"],
            epistemic_state=WorldEpistemicState(row["epistemic_state"]),
        )

    def recent_life_project_outreach(
        self, *, now: datetime, recipient_id: str = SPARKS_PRINCIPAL_ID,
        hours: int = 24,
    ) -> bool:
        """Derived social restraint from the existing ACT opportunity ledger.

        One optional owner-only LIFE celebration per day is plenty. This
        uses persisted original Presence decisions, not a new scheduling or
        notification counter; human opt-out and quiet still apply separately.
        """
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("source-aware outreach clock required")
        if type(hours) is not int or not 1 <= hours <= 168:
            raise ValueError("bounded outreach interval required")
        if not isinstance(recipient_id, str) or _ID.fullmatch(recipient_id) is None:
            raise ValueError("authenticated recipient identity required")
        cutoff = (self._utc(now) - timedelta(hours=hours)).isoformat()
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT 1 FROM presence_initiative_opportunity
                   WHERE recipient_id=? AND trigger_kind='task_completed'
                   AND event_id LIKE 'life-complete:%'
                   AND status='queued' AND created_at>=?
                   LIMIT 1""",
                (recipient_id, cutoff),
            ).fetchone()
        return row is not None

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
        # The application currently has one explicitly configured local
        # Sparks outreach route. A Discord-DM/private-device observation
        # cannot silently be rebroadcast to that other channel. New routes
        # require an exact audience/recipient mapping and approved policy.
        audience = event.observation.audience_id
        scoped_to_local_recipient = audience in {None, "sparks", "local:text"}
        observation_valid_at_event = (
            event.observation.observed_at <= event.created_at
            and (
                event.observation.expires_at is None
                or event.observation.expires_at > event.created_at
            )
        )
        if event.trigger_kind in self._ELIGIBLE_TRIGGERS and not scoped_to_local_recipient:
            reason = "incompatible_observation_audience"
        elif event.trigger_kind in self._ELIGIBLE_TRIGGERS and not observation_valid_at_event:
            reason = "stale_or_future_observation"
        elif event.trigger_kind in self._ELIGIBLE_TRIGGERS and not grounded:
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
                    # Never keep a delivery candidate alive after the
                    # observation that originally justified it expired.
                    expires_at=(
                        event.expires_at
                        if event.observation.expires_at is None
                        else min(event.expires_at, event.observation.expires_at)
                    ),
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
