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
from typing import TYPE_CHECKING, Callable

from sofia.platform.act.outreach import (
    Importance, OutreachCategory, social_content_safety_reason,
)
from sofia.platform.application.act_service import SofiaActService
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

if TYPE_CHECKING:
    from sofia.cognition.v2.contracts import ConversationFocus


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
    correlation_event_id: str | None = None

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
        if self.correlation_event_id is not None and (
            not isinstance(self.correlation_event_id, str)
            or _ID.fullmatch(self.correlation_event_id) is None
        ):
            raise ValueError("correlation event requires bounded identifier")
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


@dataclass(frozen=True, slots=True)
class PendingConversationThread:
    """Source-linked prospective topic; never factual memory or authority."""

    thread_id: str
    principal_id: str
    audience_id: str
    session_id: str
    focus_item_id: str
    source_turn_id: str
    subject_id: str | None
    request_kind: str
    predicate: str | None
    evidence_refs: tuple[str, ...]
    status: str
    created_at: datetime
    eligible_after: datetime
    expires_at: datetime
    updated_at: datetime
    notice_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "thread_id", "principal_id", "audience_id", "session_id",
            "focus_item_id", "source_turn_id", "request_kind",
        ):
            if _ID.fullmatch(str(getattr(self, name))) is None:
                raise ValueError(f"{name} must be a bounded identifier")
        for value in (self.subject_id, self.predicate):
            if value is not None and _ID.fullmatch(value) is None:
                raise ValueError("subject and predicate must be bounded identifiers")
        if self.status not in {
            "pending", "offered", "declined", "resolved", "expired",
        }:
            raise ValueError("invalid pending conversation status")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("pending conversation requires source evidence")
        if any(_ID.fullmatch(value) is None for value in self.evidence_refs):
            raise ValueError("pending conversation evidence must be bounded IDs")
        for value in (
            self.created_at, self.eligible_after, self.expires_at,
            self.updated_at,
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("pending conversation times must be timezone-aware")
        if not self.created_at <= self.eligible_after < self.expires_at:
            raise ValueError("pending conversation time window is invalid")


class PresenceInitiativeEngine:
    """Persist world snapshots and enqueue only reviewed event classes in ACT."""

    _ELIGIBLE_TRIGGERS = frozenset({
        "approval_request", "conversation_followup", "dev_finding",
        "fleet_anomaly", "goal_change", "operational_alert",
        "reflection", "shared_activity_offer", "task_completed",
    })
    _ORDINARY_FEEDBACK_TRIGGERS = frozenset({
        "conversation_followup", "dev_finding", "goal_change", "reflection",
        "shared_activity_offer",
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
                CREATE TABLE IF NOT EXISTS presence_observation_correlation (
                    observation_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS presence_correlation_event
                    ON presence_observation_correlation(event_id);
                CREATE TABLE IF NOT EXISTS presence_observation_conflict (
                    conflict_id TEXT PRIMARY KEY,
                    first_id TEXT NOT NULL,
                    second_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    review_status TEXT NOT NULL CHECK(review_status='pending'),
                    event_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS presence_conflict_audience
                    ON presence_observation_conflict(audience_id);
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
                CREATE TABLE IF NOT EXISTS presence_life_update_feedback (
                    principal_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    feedback TEXT NOT NULL CHECK(
                        feedback IN ('declined','welcomed')
                    ),
                    original_event_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(principal_id,project_id)
                );
                CREATE TABLE IF NOT EXISTS presence_life_update_feedback_event (
                    feedback_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    principal_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    feedback TEXT NOT NULL CHECK(
                        feedback IN ('declined','welcomed')
                    ),
                    original_event_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS presence_update_feedback (
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    trigger_kind TEXT NOT NULL,
                    usefulness TEXT CHECK(
                        usefulness IS NULL OR usefulness IN ('useful','not_useful')
                    ),
                    interruptiveness TEXT CHECK(
                        interruptiveness IS NULL OR interruptiveness IN ('acceptable','too_interruptive')
                    ),
                    original_event_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(principal_id,audience_id,trigger_kind)
                );
                CREATE TABLE IF NOT EXISTS presence_update_feedback_event (
                    feedback_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    trigger_kind TEXT NOT NULL,
                    dimension TEXT NOT NULL CHECK(
                        dimension IN ('usefulness','interruptiveness')
                    ),
                    value TEXT NOT NULL,
                    original_event_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS presence_outreach_response (
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    trigger_kind TEXT NOT NULL,
                    response TEXT NOT NULL CHECK(
                        response IN ('accepted','declined','ignored')
                    ),
                    original_event_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(principal_id,audience_id,trigger_kind)
                );
                CREATE TABLE IF NOT EXISTS presence_outreach_response_event (
                    response_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    trigger_kind TEXT NOT NULL,
                    response TEXT NOT NULL CHECK(
                        response IN ('accepted','declined','ignored','unknown')
                    ),
                    original_event_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS presence_pending_conversation (
                    thread_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    focus_item_id TEXT NOT NULL,
                    source_turn_id TEXT NOT NULL,
                    subject_id TEXT,
                    request_kind TEXT NOT NULL,
                    predicate TEXT,
                    evidence_refs_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'pending','offered','declined','resolved','expired'
                    )),
                    created_at TEXT NOT NULL,
                    eligible_after TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    notice_id TEXT,
                    UNIQUE(principal_id,audience_id,session_id,focus_item_id)
                );
                CREATE INDEX IF NOT EXISTS presence_pending_scope
                    ON presence_pending_conversation(
                        principal_id,audience_id,status,eligible_after
                    );
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
            from sofia.platform.application.presence_conflicts import record_correlation
            record_correlation(
                db, observation=observation, receipt=receipt,
                newly_created=old is None,
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
            from sofia.platform.application.presence_conflicts import prune_orphans
            prune_orphans(db)
        return observation

    def correlated_conflicts(
        self, *, principal: PrincipalContext, limit: int = 20,
    ) -> tuple[dict, ...]:
        """Only source refs in a bound owner's private audience.

        Caller must pass the same authenticated principal object used by the
        application turn; provider-supplied owner IDs or audience strings
        are not authorization to retrieve any private observations.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("bound PrincipalContext required for review")
        if (
            principal.principal_id != SPARKS_PRINCIPAL_ID
            or principal.audience_kind is not AudienceKind.PRIVATE
            or _ID.fullmatch(principal.audience_id) is None
        ):
            raise PermissionError("private owner scope required for review")
        from sofia.platform.application.presence_conflicts import scoped_conflicts
        with closing(self._connect()) as db:
            return scoped_conflicts(
                db, audience_id=principal.audience_id, limit=limit,
            )

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

    def owner_life_update_feedback(
        self, *, project_id: str, principal: PrincipalContext,
    ) -> str | None:
        """Exactly scoped feedback from explicit owner interaction only.

        Absence of a response is UNKNOWN, never disinterest or distress.
        A declined project stays declined across channels and restarts.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated owner principal required")
        if (
            principal.principal_id != SPARKS_PRINCIPAL_ID
            or principal.audience_kind is not AudienceKind.PRIVATE
        ):
            raise PermissionError("owner-only private project feedback")
        if not isinstance(project_id, str) or _ID.fullmatch(project_id) is None:
            raise ValueError("exact bounded LIFE project ID required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT feedback FROM presence_life_update_feedback "
                "WHERE principal_id=? AND project_id=?",
                (principal.principal_id, project_id),
            ).fetchone()
        return None if row is None else str(row[0])

    def record_owner_life_update_feedback(
        self, *, principal: PrincipalContext, project_id: str,
        original_event_id: str, feedback: str, at: datetime,
    ) -> None:
        """Record an explicit owner click/reply for the original LIFE notice.

        Only trusted Desktop/Discord input handlers should call this API.
        Source project ID, original queued notice, and exact owner are
        checked inside one writer transaction. Merely queuing/sending
        cannot manufacture a welcome or decline.
        """
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated owner principal required")
        if (
            principal.principal_id != SPARKS_PRINCIPAL_ID
            or principal.audience_kind is not AudienceKind.PRIVATE
        ):
            raise PermissionError("owner-only private project feedback")
        if (
            not isinstance(project_id, str) or _ID.fullmatch(project_id) is None
            or not isinstance(original_event_id, str)
            or not original_event_id.startswith("life-update:")
            or _ID.fullmatch(original_event_id) is None
        ):
            raise ValueError("original bounded LIFE event and project IDs required")
        if feedback not in {"declined", "welcomed"}:
            raise ValueError("explicit owner welcome or decline required")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("source-aware owner feedback time required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            original = db.execute(
                """SELECT o.recipient_id, o.status, w.audience_id,
                          w.value_json
                   FROM presence_initiative_opportunity AS o
                   JOIN presence_world_observation AS w
                     ON w.observation_id=o.observation_id
                   WHERE o.event_id=? AND o.trigger_kind IN (
                       'task_completed','shared_activity_offer'
                   )""",
                (original_event_id,),
            ).fetchone()
            if (
                original is None
                or original["recipient_id"] != principal.principal_id
                or original["status"] != "queued"
                or original["audience_id"] != "local:text"
            ):
                raise PermissionError("no matching authentic owner LIFE opportunity")
            try:
                content = json.loads(original["value_json"])
            except (ValueError, TypeError) as exc:
                raise PermissionError("original LIFE event is not valid JSON") from exc
            if not isinstance(content, dict) or content.get("project_id") != project_id:
                raise PermissionError("original event concerns a different project")
            existing = db.execute(
                "SELECT feedback FROM presence_life_update_feedback "
                "WHERE principal_id=? AND project_id=?",
                (principal.principal_id, project_id),
            ).fetchone()
            if existing is not None and existing["feedback"] == feedback:
                return
            # The current-state row is only a projection of explicit
            # reviewed human preferences. Every accepted change is also
            # preserved as a source-linked event; no model task can
            # silently change a prior decline.
            stamped = self._utc(at).isoformat()
            db.execute(
                "INSERT INTO presence_life_update_feedback_event"
                "(principal_id,project_id,feedback,original_event_id,recorded_at)"
                " VALUES(?,?,?,?,?)",
                (
                    principal.principal_id, project_id, feedback,
                    original_event_id, stamped,
                ),
            )
            db.execute(
                """INSERT INTO presence_life_update_feedback VALUES(?,?,?,?,?)
                   ON CONFLICT(principal_id,project_id)
                   DO UPDATE SET feedback=excluded.feedback,
                     original_event_id=excluded.original_event_id,
                     updated_at=excluded.updated_at""",
                (
                    principal.principal_id, project_id, feedback,
                    original_event_id, stamped,
                ),
            )

    @staticmethod
    def _require_private_sparks(principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated owner principal required")
        if (
            principal.principal_id != SPARKS_PRINCIPAL_ID
            or principal.audience_kind is not AudienceKind.PRIVATE
        ):
            raise PermissionError("owner-only private update feedback")

    def owner_update_feedback(
        self, *, trigger_kind: str, principal: PrincipalContext,
    ) -> dict[str, str | None]:
        """Return explicit ordinary-update feedback; silence stays unknown."""
        self._require_private_sparks(principal)
        if trigger_kind not in self._ORDINARY_FEEDBACK_TRIGGERS:
            raise ValueError("feedback is limited to ordinary update classes")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT usefulness,interruptiveness FROM presence_update_feedback "
                "WHERE principal_id=? AND audience_id=? AND trigger_kind=?",
                (principal.principal_id, principal.audience_id, trigger_kind),
            ).fetchone()
        return {
            "usefulness": None if row is None else row["usefulness"],
            "interruptiveness": None if row is None else row["interruptiveness"],
        }

    def record_owner_update_feedback(
        self, *, principal: PrincipalContext, original_event_id: str,
        dimension: str, value: str, at: datetime,
    ) -> None:
        """Record one reversible owner judgment about an authentic update.

        Critical operational, Fleet and approval notifications are deliberately
        outside this preference surface. A value of ``unknown`` clears that
        dimension without rewriting its audit history.
        """
        self._require_private_sparks(principal)
        allowed = {
            "usefulness": {"useful", "not_useful", "unknown"},
            "interruptiveness": {"acceptable", "too_interruptive", "unknown"},
        }
        if dimension not in allowed or value not in allowed[dimension]:
            raise ValueError("typed usefulness or interruptiveness feedback required")
        if not isinstance(original_event_id, str) or _ID.fullmatch(original_event_id) is None:
            raise ValueError("exact bounded Presence event ID required")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("source-aware owner feedback time required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            original = db.execute(
                """SELECT o.trigger_kind,o.recipient_id,o.status,w.audience_id
                   FROM presence_initiative_opportunity AS o
                   JOIN presence_world_observation AS w
                     ON w.observation_id=o.observation_id
                   WHERE o.event_id=?""",
                (original_event_id,),
            ).fetchone()
            if (
                original is None
                or original["trigger_kind"] not in self._ORDINARY_FEEDBACK_TRIGGERS
                or original["recipient_id"] != principal.principal_id
                or original["status"] != "queued"
                or original["audience_id"] != principal.audience_id
            ):
                raise PermissionError("no matching authentic ordinary update")
            trigger = original["trigger_kind"]
            current = db.execute(
                "SELECT usefulness,interruptiveness FROM presence_update_feedback "
                "WHERE principal_id=? AND audience_id=? AND trigger_kind=?",
                (principal.principal_id, principal.audience_id, trigger),
            ).fetchone()
            previous = None if current is None else current[dimension]
            projected = None if value == "unknown" else value
            if previous == projected:
                return
            stamped = self._utc(at).isoformat()
            db.execute(
                "INSERT INTO presence_update_feedback_event"
                "(principal_id,audience_id,trigger_kind,dimension,value,original_event_id,recorded_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (principal.principal_id, principal.audience_id, trigger,
                 dimension, value, original_event_id, stamped),
            )
            usefulness = projected if dimension == "usefulness" else (
                None if current is None else current["usefulness"]
            )
            interruptiveness = projected if dimension == "interruptiveness" else (
                None if current is None else current["interruptiveness"]
            )
            if usefulness is None and interruptiveness is None:
                db.execute(
                    "DELETE FROM presence_update_feedback WHERE principal_id=? AND audience_id=? AND trigger_kind=?",
                    (principal.principal_id, principal.audience_id, trigger),
                )
            else:
                db.execute(
                    """INSERT INTO presence_update_feedback VALUES(?,?,?,?,?,?,?)
                       ON CONFLICT(principal_id,audience_id,trigger_kind)
                       DO UPDATE SET usefulness=excluded.usefulness,
                         interruptiveness=excluded.interruptiveness,
                         original_event_id=excluded.original_event_id,
                         updated_at=excluded.updated_at""",
                    (principal.principal_id, principal.audience_id, trigger,
                     usefulness, interruptiveness, original_event_id, stamped),
                )

    def record_owner_outreach_response(
        self, *, principal: PrincipalContext, original_event_id: str,
        response: str, at: datetime,
    ) -> None:
        """Record an explicit response; lack of a record remains unknown.

        ``ignored`` is accepted only as an authenticated user action (for
        example a UI "not now" control). Elapsed silence never writes it and
        positive outcomes never relax ACT spacing or daily limits.
        """
        self._require_private_sparks(principal)
        if response not in {"accepted", "declined", "ignored", "unknown"}:
            raise ValueError("typed owner outreach response required")
        if not isinstance(original_event_id, str) or _ID.fullmatch(original_event_id) is None:
            raise ValueError("exact bounded Presence event ID required")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("source-aware owner response time required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            original = db.execute(
                """SELECT o.trigger_kind,o.recipient_id,o.status,w.audience_id
                   FROM presence_initiative_opportunity AS o
                   JOIN presence_world_observation AS w
                     ON w.observation_id=o.observation_id
                   WHERE o.event_id=?""",
                (original_event_id,),
            ).fetchone()
            if (
                original is None
                or original["trigger_kind"] not in self._ORDINARY_FEEDBACK_TRIGGERS
                or original["recipient_id"] != principal.principal_id
                or original["status"] != "queued"
                or original["audience_id"] != principal.audience_id
            ):
                raise PermissionError("no matching authentic ordinary outreach")
            stamped = self._utc(at).isoformat()
            db.execute(
                "INSERT INTO presence_outreach_response_event("
                "principal_id,audience_id,trigger_kind,response,"
                "original_event_id,recorded_at) VALUES(?,?,?,?,?,?)",
                (principal.principal_id, principal.audience_id,
                 original["trigger_kind"], response, original_event_id, stamped),
            )
            if response == "unknown":
                db.execute(
                    "DELETE FROM presence_outreach_response WHERE principal_id=? "
                    "AND audience_id=? AND trigger_kind=?",
                    (principal.principal_id, principal.audience_id,
                     original["trigger_kind"]),
                )
            else:
                db.execute(
                    """INSERT INTO presence_outreach_response VALUES(?,?,?,?,?,?)
                       ON CONFLICT(principal_id,audience_id,trigger_kind)
                       DO UPDATE SET response=excluded.response,
                         original_event_id=excluded.original_event_id,
                         updated_at=excluded.updated_at""",
                    (principal.principal_id, principal.audience_id,
                     original["trigger_kind"], response,
                     original_event_id, stamped),
                )

    def owner_outreach_response(
        self, *, principal: PrincipalContext, trigger_kind: str,
    ) -> str | None:
        self._require_private_sparks(principal)
        if trigger_kind not in self._ORDINARY_FEEDBACK_TRIGGERS:
            raise ValueError("response is limited to ordinary outreach")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT response FROM presence_outreach_response WHERE "
                "principal_id=? AND audience_id=? AND trigger_kind=?",
                (principal.principal_id, principal.audience_id, trigger_kind),
            ).fetchone()
        return None if row is None else str(row["response"])

    def _ordinary_update_feedback_suppression_reason(
        self, *, trigger_kind: str, recipient_id: str, audience_id: str | None,
    ) -> str | None:
        """Conservative feedback gate, never permission to send.

        Only explicit, audience-bound owner feedback can suppress an ordinary
        update. Unobserved responses remain unknown. A positive response
        cannot make any otherwise-ineligible ACT candidate eligible.
        """
        if trigger_kind not in self._ORDINARY_FEEDBACK_TRIGGERS or audience_id is None:
            return None
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT interruptiveness,usefulness FROM presence_update_feedback "
                "WHERE principal_id=? AND audience_id=? AND trigger_kind=?",
                (recipient_id, audience_id, trigger_kind),
            ).fetchone()
            response = db.execute(
                "SELECT response FROM presence_outreach_response WHERE "
                "principal_id=? AND audience_id=? AND trigger_kind=?",
                (recipient_id, audience_id, trigger_kind),
            ).fetchone()
        if response is not None and response["response"] in {"declined", "ignored"}:
            return f"owner_{response['response']}_ordinary_outreach"
        if row is None:
            return None
        if row["interruptiveness"] == "too_interruptive":
            return "owner_marked_too_interruptive"
        if row["usefulness"] == "not_useful":
            return "owner_marked_not_useful"
        return None

    @staticmethod
    def _pending_from_row(row: sqlite3.Row) -> PendingConversationThread:
        return PendingConversationThread(
            thread_id=row["thread_id"],
            principal_id=row["principal_id"],
            audience_id=row["audience_id"],
            session_id=row["session_id"],
            focus_item_id=row["focus_item_id"],
            source_turn_id=row["source_turn_id"],
            subject_id=row["subject_id"],
            request_kind=row["request_kind"],
            predicate=row["predicate"],
            evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            eligible_after=datetime.fromisoformat(row["eligible_after"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            notice_id=row["notice_id"],
        )

    def project_conversation_focus(
        self, *, focus: "ConversationFocus", principal: PrincipalContext,
        relationship_refs: tuple[str, ...] = (),
        habit_refs: tuple[str, ...] = (), memory_refs: tuple[str, ...] = (),
        now: datetime,
    ) -> tuple[PendingConversationThread, ...]:
        """Derive prospective threads from canonical unresolved v2 focus.

        REL/HABIT/MEM references provide bounded relevance context, but never
        create a topic by themselves. A decline is terminal for the exact
        focus item, and a later restart or projection cannot reopen it.
        """
        from sofia.cognition.v2.contracts import ConversationFocus

        if not isinstance(focus, ConversationFocus):
            raise TypeError("focus must be canonical ConversationFocus")
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if focus.audience_id != principal.audience_id:
            raise PermissionError("conversation focus audience does not match principal")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("projection time must be timezone-aware")
        contextual = tuple(dict.fromkeys(
            (*relationship_refs[-4:], *habit_refs[-4:], *memory_refs[-4:])
        ))
        if any(
            not isinstance(ref, str) or _ID.fullmatch(ref) is None
            for ref in contextual
        ):
            raise ValueError("continuity evidence references must be bounded IDs")
        items = tuple(focus.unresolved_requests)[:16]
        active_ids = {item.request_id for item in items}
        stamp = self._utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            binding = db.execute(
                "SELECT principal_id,audience_id FROM social_session_principal "
                "WHERE session_id=?", (focus.session_id,),
            ).fetchone()
            if binding is None or (
                binding["principal_id"], binding["audience_id"]
            ) != (principal.principal_id, principal.audience_id):
                raise PermissionError("canonical conversation binding is unavailable")
            prior = db.execute(
                "SELECT thread_id,focus_item_id,status FROM "
                "presence_pending_conversation WHERE principal_id=? "
                "AND audience_id=? AND session_id=?",
                (principal.principal_id, principal.audience_id, focus.session_id),
            ).fetchall()
            for row in prior:
                if (
                    row["status"] in {"pending", "offered"}
                    and row["focus_item_id"] not in active_ids
                ):
                    db.execute(
                        "UPDATE presence_pending_conversation SET status='resolved',"
                        "updated_at=? WHERE thread_id=? AND status IN ('pending','offered')",
                        (stamp.isoformat(), row["thread_id"]),
                    )
            for item in items:
                source = db.execute(
                    "SELECT role,created_at FROM conversation_messages "
                    "WHERE id=? AND session_id=?",
                    (item.source_turn_id, focus.session_id),
                ).fetchone()
                if source is None or source["role"] != "user":
                    continue
                created = datetime.fromisoformat(source["created_at"])
                if created.tzinfo is None or created.utcoffset() is None:
                    continue
                created = created.astimezone(timezone.utc)
                if created > stamp:
                    continue
                digest = sha256(
                    (principal.principal_id + "\0" + principal.audience_id + "\0"
                     + focus.session_id + "\0" + item.request_id).encode("utf-8")
                ).hexdigest()[:32]
                thread_id = f"pending-thread:{digest}"
                evidence = tuple(dict.fromkeys((item.source_turn_id, *contextual)))
                eligible = max(stamp, created + timedelta(hours=6))
                expires = created + timedelta(days=7)
                if eligible >= expires:
                    continue
                old = db.execute(
                    "SELECT * FROM presence_pending_conversation WHERE thread_id=?",
                    (thread_id,),
                ).fetchone()
                if old is not None:
                    immutable = (
                        old["principal_id"], old["audience_id"], old["session_id"],
                        old["focus_item_id"], old["source_turn_id"], old["subject_id"],
                        old["request_kind"], old["predicate"], old["created_at"],
                    )
                    desired = (
                        principal.principal_id, principal.audience_id, focus.session_id,
                        item.request_id, item.source_turn_id, item.subject_id,
                        item.request_kind, item.predicate, created.isoformat(),
                    )
                    if immutable != desired:
                        raise ValueError("pending thread identity was reused")
                    if old["status"] in {"declined", "resolved", "expired"}:
                        continue
                    db.execute(
                        "UPDATE presence_pending_conversation SET evidence_refs_json=?,"
                        "updated_at=? WHERE thread_id=?",
                        (json.dumps(evidence), stamp.isoformat(), thread_id),
                    )
                else:
                    db.execute(
                        "INSERT INTO presence_pending_conversation VALUES("
                        "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            thread_id, principal.principal_id, principal.audience_id,
                            focus.session_id, item.request_id, item.source_turn_id,
                            item.subject_id, item.request_kind, item.predicate,
                            json.dumps(evidence), "pending", created.isoformat(),
                            eligible.isoformat(), expires.isoformat(), stamp.isoformat(), None,
                        ),
                    )
            db.execute(
                "UPDATE presence_pending_conversation SET status='expired',updated_at=? "
                "WHERE status='pending' AND expires_at<=?",
                (stamp.isoformat(), stamp.isoformat()),
            )
            rows = db.execute(
                "SELECT * FROM presence_pending_conversation WHERE principal_id=? "
                "AND audience_id=? AND session_id=? ORDER BY created_at,thread_id",
                (principal.principal_id, principal.audience_id, focus.session_id),
            ).fetchall()
        return tuple(self._pending_from_row(row) for row in rows)

    def pending_conversations(
        self, *, principal: PrincipalContext, now: datetime, limit: int = 20,
        include_closed: bool = False,
    ) -> tuple[PendingConversationThread, ...]:
        self._require_private_sparks(principal)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("pending conversation limit must be 1..100")
        stamp = self._utc(now)
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE presence_pending_conversation SET status='expired',updated_at=? "
                "WHERE status='pending' AND expires_at<=?",
                (stamp.isoformat(), stamp.isoformat()),
            )
            query = (
                "SELECT * FROM presence_pending_conversation WHERE principal_id=? "
                "AND audience_id=? "
                + ("" if include_closed else "AND status IN ('pending','offered') ")
                + "ORDER BY updated_at DESC,thread_id LIMIT ?"
            )
            rows = db.execute(
                query, (principal.principal_id, principal.audience_id, limit),
            ).fetchall()
        return tuple(self._pending_from_row(row) for row in rows)

    def decline_pending_conversation(
        self, *, principal: PrincipalContext, thread_id: str, at: datetime,
    ) -> PendingConversationThread:
        self._require_private_sparks(principal)
        if not isinstance(thread_id, str) or _ID.fullmatch(thread_id) is None:
            raise ValueError("exact pending thread ID required")
        stamp = self._utc(at)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM presence_pending_conversation WHERE thread_id=? "
                "AND principal_id=? AND audience_id=?",
                (thread_id, principal.principal_id, principal.audience_id),
            ).fetchone()
            if row is None:
                raise LookupError("pending conversation is unavailable in this scope")
            if row["status"] not in {"resolved", "expired"}:
                db.execute(
                    "UPDATE presence_pending_conversation SET status='declined',updated_at=? "
                    "WHERE thread_id=?", (stamp.isoformat(), thread_id),
                )
            changed = db.execute(
                "SELECT * FROM presence_pending_conversation WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
        return self._pending_from_row(changed)

    def offer_due_pending_conversation(
        self, *, principal: PrincipalContext, now: datetime,
    ) -> InitiativeDecision | None:
        """Queue at most one still-current follow-up through existing ACT."""
        self._require_private_sparks(principal)
        stamp = self._utc(now)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT p.*,f.payload_json FROM presence_pending_conversation AS p "
                "JOIN cognition_v2_conversation_focus AS f "
                "ON f.session_id=p.session_id AND f.audience_id=p.audience_id "
                "WHERE p.principal_id=? AND p.audience_id=? AND p.status='pending' "
                "AND p.eligible_after<=? AND p.expires_at>? "
                "ORDER BY p.created_at,p.thread_id LIMIT 8",
                (principal.principal_id, principal.audience_id,
                 stamp.isoformat(), stamp.isoformat()),
            ).fetchall()
        row = next((candidate for candidate in rows if any(
            item.get("request_id") == candidate["focus_item_id"]
            for item in json.loads(candidate["payload_json"])["unresolved_requests"]
        )), None)
        if row is None:
            return None
        thread = self._pending_from_row(row)
        label = thread.predicate or thread.subject_id or thread.request_kind
        safe_label = " ".join(label.replace("_", " ").replace(".", " ").split())[:96]
        # One durable, immutable opportunity per six-hour retry window.
        # Mutating updated_at must never change the identity of a prior event.
        attempt_window = int(
            (stamp - thread.eligible_after).total_seconds() // (6 * 3600)
        )
        attempted_at = thread.eligible_after + timedelta(hours=6 * attempt_window)
        event_id = "conversation-followup:" + sha256(
            (thread.thread_id + "\0" + str(attempt_window)).encode("utf-8")
        ).hexdigest()[:32]
        observation = WorldObservation(
            observation_id="pending-observed:" + sha256(
                (thread.thread_id + "\0" + thread.created_at.isoformat()).encode("utf-8")
            ).hexdigest()[:32],
            subject_id=thread.subject_id or "conversation:unfinished",
            predicate="conversation.unfinished_thread",
            source_id="cognition:v2-focus",
            observed_at=thread.created_at,
            expires_at=thread.expires_at,
            confidence=1.0,
            epistemic_state=WorldEpistemicState.KNOWN,
            availability=WorldAvailability.NOT_APPLICABLE,
            value={
                "thread_id": thread.thread_id,
                "source_turn_id": thread.source_turn_id,
            },
            audience_id=thread.audience_id,
        )
        decision = self.consider(InitiativeEvent(
            event_id=event_id, trigger_kind="conversation_followup",
            observation=observation,
            content=(
                f"We left {safe_label} unfinished earlier. "
                "Would you like to pick it back up?"
            ),
            created_at=attempted_at, expires_at=thread.expires_at,
            category=OutreachCategory.SOCIAL,
            importance=Importance.ROUTINE, salience=0.55,
            recipient_id=principal.principal_id,
        ))
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE presence_pending_conversation SET status=?,notice_id=?,updated_at=? "
                "WHERE thread_id=? AND status='pending'",
                (
                    "offered" if decision.status == "queued" else "pending",
                    decision.notice_id, stamp.isoformat(), thread.thread_id,
                ),
            )
        return decision

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
                   WHERE recipient_id=? AND trigger_kind IN (
                       'task_completed','shared_activity_offer'
                   )
                   AND event_id LIKE 'life-update:%'
                   AND status='queued' AND created_at>=?
                   LIMIT 1""",
                (recipient_id, cutoff),
            ).fetchone()
        return row is not None

    def consider(self, event: InitiativeEvent) -> InitiativeDecision:
        if not isinstance(event, InitiativeEvent):
            raise TypeError("event must be InitiativeEvent")
        # Check the original decision BEFORE persisting an observation.
        # Otherwise a replay can resurrect a source that was later deleted
        # or pruned, turning a formerly unsupported queued ACT notice into a
        # newly grounded one without any original-source authorization.
        with closing(self._connect()) as db:
            old = db.execute(
                "SELECT observation_id,trigger_kind,recipient_id,"
                "created_at,status,reason,notice_id "
                "FROM presence_initiative_opportunity WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
        if old is not None:
            if (
                old["observation_id"] != event.observation.observation_id
                or old["trigger_kind"] != event.trigger_kind
                or old["recipient_id"] != event.recipient_id
                or old["created_at"] != self._utc(event.created_at).isoformat()
            ):
                raise ValueError("original Presence event ID reused for different source")
            return InitiativeDecision(
                event.event_id, old["status"], old["reason"], old["notice_id"],
            )
        self.observe(event.observation)

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
        if event.trigger_kind == "task_completed" and (
            audience != "local:text"
            or event.recipient_id != SPARKS_PRINCIPAL_ID
        ):
            # Verified private LIFE milestones belong only to the original
            # authenticated local owner audience, not to an implicit/unknown
            # audience or another receiver. Operational alerts are separate.
            reason = "private_milestone_requires_exact_local_owner"
        elif event.trigger_kind in self._ELIGIBLE_TRIGGERS and not scoped_to_local_recipient:
            reason = "incompatible_observation_audience"
        elif event.trigger_kind in self._ELIGIBLE_TRIGGERS and not observation_valid_at_event:
            reason = "stale_or_future_observation"
        elif event.trigger_kind in self._ELIGIBLE_TRIGGERS and not grounded:
            reason = "insufficient_grounding"
        elif (feedback_restraint := self._ordinary_update_feedback_suppression_reason(
            trigger_kind=event.trigger_kind,
            recipient_id=event.recipient_id,
            audience_id=event.observation.audience_id,
        )) is not None:
            reason = feedback_restraint
        elif (
            event.category is OutreachCategory.SOCIAL
            and (content_restraint := social_content_safety_reason(event.content))
            is not None
        ):
            reason = content_restraint
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
            db.execute("BEGIN IMMEDIATE")
            # Another canonical Presence worker may have won the same event
            # while this one was evaluating ACT. Never replace a prior
            # decision or leave a unique-key crash after idempotent enqueue.
            db.execute(
                "INSERT OR IGNORE INTO presence_initiative_opportunity "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    event.event_id, event.observation.observation_id,
                    event.trigger_kind, event.recipient_id, status, reason,
                    notice_id, self._utc(event.created_at).isoformat(),
                ),
            )
            persisted = db.execute(
                "SELECT observation_id,trigger_kind,recipient_id,created_at,"
                "status,reason,notice_id FROM presence_initiative_opportunity "
                "WHERE event_id=?", (event.event_id,),
            ).fetchone()
            if (
                persisted is None
                or persisted["observation_id"] != event.observation.observation_id
                or persisted["trigger_kind"] != event.trigger_kind
                or persisted["recipient_id"] != event.recipient_id
                or persisted["created_at"] != self._utc(event.created_at).isoformat()
            ):
                raise ValueError("concurrent Presence event source identity collision")
            return InitiativeDecision(
                event.event_id, persisted["status"],
                persisted["reason"], persisted["notice_id"],
            )

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
