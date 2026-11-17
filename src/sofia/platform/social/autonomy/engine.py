"""Autonomous but bounded social choice for one independently identified Core.

The engine never generates dialogue itself. A Core's own planner proposes an
inert intention; this layer enforces relevance, budgets, turn caps, cooldowns,
duplicate suppression, boundaries, STOP and Platform authorization. Strong
interpersonal trust cannot bypass those gates, and no decision carries
execution authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sofia.platform.social.autonomy.contracts import (
    AutonomyLimits,
    Clock,
    CoreIdentity,
    InferenceScheduler,
    RoomKind,
    SocialAction,
    SocialAuthorization,
    SocialContext,
    SocialDecision,
    SocialEvent,
    SocialEventKind,
    SocialPlanner,
    SocialProposal,
    SocialProfileSource,
    SocialTransport,
    StopAuthority,
    SystemClock,
)
from sofia.platform.social.autonomy.evidence import EvidenceCategory, EvidenceRecord
from sofia.platform.social.autonomy.models import (
    BoundaryKind,
    EmotionalAppraisal,
    FacetStance,
    PeerFacet,
    PeerRelationship,
    TopicStatus,
    UnresolvedTopic,
)
from sofia.platform.social.autonomy.store import SocialAutonomyStore


_EXTERNAL_ACTIONS = frozenset({
    SocialAction.SEND_MESSAGE,
    SocialAction.REPLY,
    SocialAction.JOIN,
    SocialAction.INVITE,
    SocialAction.START_PRIVATE,
    SocialAction.CONTINUE_TOPIC,
    SocialAction.DECLINE,
    SocialAction.SHARE,
})

_BODY_ACTIONS = frozenset({
    SocialAction.SEND_MESSAGE,
    SocialAction.REPLY,
    SocialAction.INVITE,
    SocialAction.START_PRIVATE,
    SocialAction.CONTINUE_TOPIC,
    SocialAction.DECLINE,
    SocialAction.SHARE,
})

_COOLDOWN_ACTIONS = frozenset({
    SocialAction.SEND_MESSAGE.value,
    SocialAction.REPLY.value,
    SocialAction.INVITE.value,
    SocialAction.START_PRIVATE.value,
    SocialAction.CONTINUE_TOPIC.value,
    SocialAction.DECLINE.value,
})


def _utc(value: datetime, name: str = "timestamp") -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _day_key(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).date().isoformat()


def _next_day(moment: datetime) -> datetime:
    start = moment.astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start + timedelta(days=1)


class AutonomousSocialEngine:
    def __init__(
        self,
        identity: CoreIdentity,
        store: SocialAutonomyStore,
        *,
        stop: StopAuthority,
        authorization: SocialAuthorization,
        clock: Clock | None = None,
        transport: SocialTransport | None = None,
        scheduler: InferenceScheduler | None = None,
        limits: AutonomyLimits | None = None,
        profile_source: SocialProfileSource | None = None,
    ) -> None:
        if not isinstance(identity, CoreIdentity):
            raise TypeError("identity must be CoreIdentity")
        if not isinstance(store, SocialAutonomyStore):
            raise TypeError("store must be SocialAutonomyStore")
        self.identity = identity
        self._store = store
        self._stop = stop
        self._authorization = authorization
        self._clock = clock or SystemClock()
        self._transport = transport
        self._scheduler = scheduler
        self._limits = limits or AutonomyLimits()
        self._profile_source = profile_source

    @property
    def store(self) -> SocialAutonomyStore:
        return self._store

    @property
    def limits(self) -> AutonomyLimits:
        return self._limits

    def _now(self) -> datetime:
        return _utc(self._clock.now(), "clock.now()")

    def _event_peer(self, event: SocialEvent) -> UUID | None:
        if event.peer_core_id is not None:
            return event.peer_core_id
        if event.message is not None:
            return event.message.sender_core_id
        return None

    def _chain(self, event: SocialEvent) -> str:
        if event.chain_id is not None:
            return event.chain_id
        if event.room_id is not None:
            return f"room:{event.room_id}"
        return f"event:{event.event_id}"

    def _room(self, event: SocialEvent) -> str | None:
        if event.room_id is not None:
            return event.room_id
        if event.message is not None:
            return event.message.room_id
        return None

    def _mark(self, event: SocialEvent, now: datetime) -> None:
        self._store.mark_event(
            core_id=self.identity.core_id, event_id=event.event_id, now=now
        )

    def _silence(
        self,
        event: SocialEvent,
        now: datetime,
        reason: str,
        *,
        duplicate: bool = False,
        deferred_until: datetime | None = None,
    ) -> SocialDecision:
        self._mark(event, now)
        return SocialDecision(
            action=(
                SocialAction.DEFER
                if deferred_until is not None
                else SocialAction.SILENCE
            ),
            core_id=self.identity.core_id,
            target_core_id=self._event_peer(event),
            room_id=self._room(event),
            reason=reason,
            permitted=False,
            duplicate_suppressed=duplicate,
            deferred_until=deferred_until,
        )

    def _refused(self, reason: str, event: SocialEvent | None = None) -> SocialDecision:
        return SocialDecision(
            action=SocialAction.REFUSED,
            core_id=self.identity.core_id,
            target_core_id=None if event is None else self._event_peer(event),
            room_id=None if event is None else self._room(event),
            reason=reason,
            permitted=False,
        )

    def _wake(
        self,
        *,
        reason: str,
        due_at: datetime,
        event_id: str,
    ) -> None:
        if self._scheduler is None:
            return
        self._scheduler.wake(
            core_id=self.identity.core_id,
            reason=reason,
            due_at=due_at,
            event_id=event_id,
        )

    def _context(
        self,
        event: SocialEvent,
        now: datetime,
        *,
        peer: UUID | None,
        remaining_contacts: int,
        remaining_inference: int,
    ) -> SocialContext:
        relationship = (
            self._store.relationship(self.identity.core_id, peer)
            if peer is not None
            else None
        )
        if self._profile_source is not None:
            interests = self._profile_source.interests(
                core_id=self.identity.core_id
            )
            goals = self._profile_source.goals(core_id=self.identity.core_id)
            boundaries = self._profile_source.boundaries(
                core_id=self.identity.core_id, peer_core_id=peer
            )
        else:
            interests = self._store.interests(self.identity.core_id)
            goals = self._store.goals(self.identity.core_id)
            boundaries = (
                ()
                if peer is None
                else self._store.boundaries(
                    self.identity.core_id, peer_core_id=peer
                )
            )
        return SocialContext(
            now=now,
            event=event,
            relationship=relationship,
            interests=interests,
            goals=goals,
            boundaries=boundaries,
            unresolved_topics=(
                ()
                if peer is None
                else self._store.topics(
                    self.identity.core_id,
                    peer_core_id=peer,
                    status=TopicStatus.OPEN,
                )
            ),
            active_evidence=self._store.active_evidence(
                self.identity.core_id, peer_core_id=peer
            ),
            recent_messages=event.recent_messages,
            remaining_contacts=remaining_contacts,
            remaining_inference=remaining_inference,
            room_kind=event.room_kind,
        )

    def receive(
        self,
        event: SocialEvent,
        *,
        planner: SocialPlanner | None = None,
    ) -> SocialDecision:
        if not isinstance(event, SocialEvent):
            raise TypeError("event must be SocialEvent")
        if event.core_id != self.identity.core_id:
            raise ValueError("event belongs to a different Core identity")
        now = self._now()
        if self._store.event_processed(self.identity.core_id, event.event_id):
            return self._silence(event, now, "duplicate event suppressed")
        if self._stop.is_operator_stopped():
            return self._refused("operator stop is active", event)

        peer = self._event_peer(event)
        message = event.message
        if message is not None and message.sender_core_id == self.identity.core_id:
            return self._silence(event, now, "refusing self chat")
        if peer is not None and peer == self.identity.core_id:
            return self._silence(event, now, "refusing self chat")
        if peer is not None and not self._store.contact_allowed(
            core_id=self.identity.core_id,
            peer_core_id=peer,
            room_id=self._room(event),
            private=(
                event.room_kind in {RoomKind.DIRECT, RoomKind.PRIVATE_GROUP}
                or (message is not None and message.audience == "private")
            ),
        ):
            return self._silence(event, now, "local boundary forbids contact")

        if event.kind is SocialEventKind.TOPIC_DUE:
            topic = self._store.topic(self.identity.core_id, event.topic_key or "")
            if topic is None or not topic.unresolved:
                return self._silence(event, now, "no unresolved topic to continue")
            if topic.next_revisit_at > now:
                self._wake(
                    reason="topic_revisit_due",
                    due_at=topic.next_revisit_at,
                    event_id=f"wake:{self.identity.core_id}:{event.topic_key}:{topic.revision}",
                )
                return self._silence(
                    event,
                    now,
                    "topic revisit is not due",
                    deferred_until=topic.next_revisit_at,
                )

        if message is not None:
            if self._store.is_seen(
                self.identity.core_id, message.room_id, message.message_id
            ):
                return self._silence(
                    event, now, "duplicate message suppressed", duplicate=True
                )

        chain = self._chain(event)
        if self._store.turn_count(self.identity.core_id, chain) >= (
            self._limits.max_chain_turns
        ):
            return self._silence(event, now, "turn chain cap reached")

        if peer is not None:
            until = self._store.cooldown_until(
                core_id=self.identity.core_id,
                peer_core_id=peer,
                action=SocialAction.SEND_MESSAGE.value,
                now=now,
            )
            if until is not None:
                self._wake(
                    reason="contact_cooldown_expired",
                    due_at=until,
                    event_id=f"wake:{self.identity.core_id}:{peer}:{until.isoformat()}",
                )
                return self._silence(
                    event,
                    now,
                    "contact cooldown is active",
                    deferred_until=until,
                )

        day = _day_key(now)
        contacts_used, inference_used = self._store.budget_usage(
            self.identity.core_id, day
        )
        remaining_contacts = self._limits.max_contacts_per_day - contacts_used
        remaining_inference = (
            self._limits.max_inference_units_per_day - inference_used
        )
        if remaining_contacts <= 0:
            tomorrow = _next_day(now)
            self._wake(
                reason="daily_contact_budget_exhausted",
                due_at=tomorrow,
                event_id=f"wake:{self.identity.core_id}:contacts:{day}",
            )
            return self._silence(
                event,
                now,
                "daily contact budget exhausted",
                deferred_until=tomorrow,
            )
        if remaining_inference <= 0:
            tomorrow = _next_day(now)
            self._wake(
                reason="daily_inference_budget_exhausted",
                due_at=tomorrow,
                event_id=f"wake:{self.identity.core_id}:inference:{day}",
            )
            return self._silence(
                event,
                now,
                "daily inference budget exhausted",
                deferred_until=tomorrow,
            )

        if message is not None:
            self._store.record_evidence(
                core_id=self.identity.core_id,
                peer_core_id=peer,
                category=EvidenceCategory.OBSERVED,
                claim=message.body[:1000],
                evidence_ref=message.message_id,
                recorded_at=now,
                message_id=message.message_id,
            )
            self._store.mark_seen(
                core_id=self.identity.core_id,
                room_id=message.room_id,
                message_id=message.message_id,
                now=now,
            )

        if planner is None:
            return self._silence(
                event, now, "no meaningful addition; choosing silence"
            )

        try:
            proposal = planner.propose(
                core=self.identity,
                event=event,
                context=self._context(
                    event,
                    now,
                    peer=peer,
                    remaining_contacts=remaining_contacts,
                    remaining_inference=remaining_inference,
                ),
            )
        except Exception:
            self._store.consume_budget(
                core_id=self.identity.core_id,
                day=day,
                contacts=0,
                inference_units=1,
                now=now,
            )
            return self._silence(event, now, "planner unavailable; failing closed")

        self._store.consume_budget(
            core_id=self.identity.core_id,
            day=day,
            contacts=0,
            inference_units=1,
            now=now,
        )

        if proposal is None:
            return self._silence(
                event, now, "no meaningful addition; choosing silence"
            )
        if not isinstance(proposal, SocialProposal):
            return self._silence(event, now, "invalid proposal; failing closed")
        if not proposal.meaningful:
            return self._silence(
                event, now, "proposal is not meaningful; choosing silence"
            )
        if proposal.relevance < self._limits.relevance_threshold:
            return self._silence(
                event, now, "relevance below threshold; choosing silence"
            )
        if proposal.action is SocialAction.SILENCE:
            return self._silence(
                event, now, (proposal.body or "chosen silence")[:600]
            )
        if proposal.action is SocialAction.DEFER:
            due = now + self._limits.topic_revisit_after
            self._wake(
                reason="deferred_social_choice",
                due_at=due,
                event_id=f"wake:{self.identity.core_id}:defer:{event.event_id}",
            )
            return self._silence(
                event, now, (proposal.body or "deferred")[:600],
                deferred_until=due,
            )

        target = proposal.target_core_id or peer
        room_id = proposal.room_id or self._room(event)
        audience = proposal.audience
        if proposal.action is SocialAction.START_PRIVATE:
            if target is None or audience != "private":
                return self._silence(
                    event,
                    now,
                    "private discussion requires a target and private audience",
                )
        if proposal.action in _EXTERNAL_ACTIONS:
            permitted = self._authorization.authorize(
                core=self.identity,
                action=proposal.action,
                room_id=room_id,
                target_core_id=target,
                audience=audience,
            )
            if not permitted:
                self._mark(event, now)
                return self._refused(
                    "platform authorization denied the social action", event
                )
        if proposal.action in _BODY_ACTIONS and not proposal.body:
            return self._silence(
                event, now, "no Core-authored content; refusing to script speech"
            )

        decision = SocialDecision(
            action=proposal.action,
            core_id=self.identity.core_id,
            target_core_id=target,
            room_id=room_id,
            body=proposal.body,
            reason=proposal.action.value,
            permitted=True,
        )

        if proposal.action is SocialAction.BLOCK:
            if target is None:
                return self._silence(event, now, "block requires a target peer")
            self._store.set_boundary(
                self.identity.core_id,
                target,
                BoundaryKind.NO_CONTACT,
                None,
                now,
            )
            self._mark(event, now)
            return decision
        if proposal.action is SocialAction.PAUSE:
            if target is not None:
                until = now + self._limits.contact_cooldown
                self._store.set_cooldown(
                    core_id=self.identity.core_id,
                    peer_core_id=target,
                    action=SocialAction.SEND_MESSAGE.value,
                    until_at=until,
                    reason=(proposal.body or "chosen pause")[:600],
                    now=now,
                )
            self._mark(event, now)
            return decision
        if proposal.action is SocialAction.LEAVE:
            self._mark(event, now)
            if self._transport is not None:
                decision = _with_delivery(
                    decision, self._transport.deliver(decision)
                )
            return decision

        if self._transport is not None:
            try:
                delivery_ref = self._transport.deliver(decision)
            except Exception:
                return self._silence(
                    event, now, "delivery unavailable; not claiming success"
                )
            decision = _with_delivery(decision, delivery_ref)

        if message is not None:
            self._store.mark_seen(
                core_id=self.identity.core_id,
                room_id=message.room_id,
                message_id=message.message_id,
                now=now,
            )
        self._store.bump_turn(
            core_id=self.identity.core_id,
            chain_id=chain,
            room_id=room_id or "room",
            message_id=message.message_id if message is not None else None,
            now=now,
        )
        self._store.consume_budget(
            core_id=self.identity.core_id,
            day=day,
            contacts=1,
            inference_units=0,
            now=now,
        )
        if target is not None:
            self._store.set_cooldown(
                core_id=self.identity.core_id,
                peer_core_id=target,
                action=SocialAction.SEND_MESSAGE.value,
                until_at=now + self._limits.contact_cooldown,
                reason="post-contact cooldown",
                now=now,
            )
        if proposal.action is SocialAction.CONTINUE_TOPIC:
            topic_key = proposal.topic or event.topic_key
            if topic_key:
                existing = self._store.topic(self.identity.core_id, topic_key)
                if existing is not None:
                    self._store.set_topic(
                        core_id=self.identity.core_id,
                        topic_key=topic_key,
                        peer_core_id=existing.peer_core_id,
                        room_id=existing.room_id,
                        summary=existing.summary,
                        status=TopicStatus.OPEN,
                        now=now,
                        next_revisit_at=now + self._limits.topic_revisit_after,
                    )
        self._mark(event, now)
        return decision

    def initiate(
        self,
        peer_core_id: UUID,
        *,
        topic_key: str,
        room_id: str,
        planner: SocialPlanner,
        audience: str = "private",
        room_kind=None,
    ) -> SocialDecision:
        now = self._now()
        event = SocialEvent(
            event_id=f"event:initiate:{uuid4()}",
            core_id=self.identity.core_id,
            kind=SocialEventKind.INITIATION,
            occurred_at=now,
            room_id=room_id,
            chain_id=f"initiate:{peer_core_id}:{topic_key}:{_day_key(now)}",
            peer_core_id=peer_core_id,
            topic_key=topic_key,
            room_kind=room_kind or RoomKind.DIRECT,
        )
        return self.receive(event, planner=planner)

    def consider_room(
        self,
        room_id: str,
        messages: tuple,
        *,
        planner: SocialPlanner,
        room_kind=None,
    ) -> SocialDecision:
        if not messages:
            raise ValueError("room activity requires at least one message")
        now = self._now()
        last = messages[-1]
        event = SocialEvent(
            event_id=f"event:room:{uuid4()}",
            core_id=self.identity.core_id,
            kind=SocialEventKind.ROOM_ACTIVITY,
            occurred_at=now,
            room_id=room_id,
            chain_id=f"room:{room_id}:{_day_key(now)}",
            peer_core_id=last.sender_core_id,
            recent_messages=tuple(messages),
            room_kind=room_kind or RoomKind.GENERAL,
        )
        return self.receive(event, planner=planner)

    def continue_topic(
        self,
        topic_key: str,
        *,
        planner: SocialPlanner,
    ) -> SocialDecision:
        topic = self._store.topic(self.identity.core_id, topic_key)
        if topic is None:
            raise LookupError("unknown social topic")
        now = self._now()
        event = SocialEvent(
            event_id=f"event:topic:{uuid4()}",
            core_id=self.identity.core_id,
            kind=SocialEventKind.TOPIC_DUE,
            occurred_at=now,
            room_id=topic.room_id,
            chain_id=f"topic:{topic_key}:{_day_key(now)}",
            peer_core_id=topic.peer_core_id,
            topic_key=topic_key,
            room_kind=RoomKind.DIRECT,
        )
        return self.receive(event, planner=planner)

    def block_peer(self, peer_core_id: UUID, *, reason: str) -> SocialDecision:
        now = self._now()
        if self._stop.is_operator_stopped():
            return self._refused("operator stop is active")
        self._store.set_boundary(
            self.identity.core_id,
            peer_core_id,
            BoundaryKind.NO_CONTACT,
            None,
            now,
        )
        return SocialDecision(
            action=SocialAction.BLOCK,
            core_id=self.identity.core_id,
            target_core_id=peer_core_id,
            reason=reason,
            permitted=True,
        )

    def pause_peer(
        self, peer_core_id: UUID, *, until_at: datetime, reason: str
    ) -> SocialDecision:
        now = self._now()
        if self._stop.is_operator_stopped():
            return self._refused("operator stop is active")
        self._store.set_cooldown(
            core_id=self.identity.core_id,
            peer_core_id=peer_core_id,
            action=SocialAction.SEND_MESSAGE.value,
            until_at=until_at,
            reason=reason,
            now=now,
        )
        return SocialDecision(
            action=SocialAction.PAUSE,
            core_id=self.identity.core_id,
            target_core_id=peer_core_id,
            reason=reason,
            permitted=True,
            deferred_until=until_at,
        )

    def leave_room(self, room_id: str, *, reason: str) -> SocialDecision:
        if self._stop.is_operator_stopped():
            return self._refused("operator stop is active")
        return SocialDecision(
            action=SocialAction.LEAVE,
            core_id=self.identity.core_id,
            room_id=room_id,
            reason=reason,
            permitted=True,
        )

    def choose_silence(self, reason: str) -> SocialDecision:
        return SocialDecision(
            action=SocialAction.SILENCE,
            core_id=self.identity.core_id,
            reason=reason,
        )

    def propose_disclosure(
        self,
        peer_core_id: UUID,
        *,
        item_ref: str,
        classification: str,
        room_id: str | None = None,
        audience: str = "private",
    ) -> SocialDecision:
        if self._stop.is_operator_stopped():
            return self._refused("operator stop is active")
        if not isinstance(item_ref, str) or not item_ref.strip() or len(
            item_ref
        ) > 160:
            raise ValueError("item_ref must be bounded nonempty text")
        if not isinstance(classification, str) or not classification.strip() or (
            len(classification) > 200
        ):
            raise ValueError("classification must be bounded nonempty text")
        if not self._store.contact_allowed(
            core_id=self.identity.core_id,
            peer_core_id=peer_core_id,
            room_id=room_id,
            private=True,
        ):
            return self._refused("local boundary forbids disclosure", None)
        permitted = self._authorization.authorize(
            core=self.identity,
            action=SocialAction.SHARE,
            room_id=room_id,
            target_core_id=peer_core_id,
            audience=audience,
        )
        if not permitted:
            return self._refused(
                "platform authorization denied the disclosure", None
            )
        return SocialDecision(
            action=SocialAction.SHARE,
            core_id=self.identity.core_id,
            target_core_id=peer_core_id,
            room_id=room_id,
            reason=classification,
            permitted=True,
            payload_ref=item_ref,
        )

    def record_evidence(
        self,
        *,
        category: EvidenceCategory,
        claim: str,
        evidence_ref: str,
        peer_core_id: UUID | None = None,
        message_id: str | None = None,
        supersedes: str | None = None,
    ) -> EvidenceRecord:
        return self._store.record_evidence(
            core_id=self.identity.core_id,
            peer_core_id=peer_core_id,
            category=category,
            claim=claim,
            evidence_ref=evidence_ref,
            recorded_at=self._now(),
            message_id=message_id,
            supersedes=supersedes,
        )

    def correct_evidence(
        self,
        evidence_id: str,
        *,
        claim: str,
        evidence_ref: str,
    ) -> EvidenceRecord:
        return self.record_evidence(
            category=EvidenceCategory.CORRECTION,
            claim=claim,
            evidence_ref=evidence_ref,
            supersedes=evidence_id,
        )

    def withdraw_evidence(
        self,
        evidence_id: str,
        *,
        reason: str,
        evidence_ref: str,
    ) -> EvidenceRecord:
        return self.record_evidence(
            category=EvidenceCategory.WITHDRAWAL,
            claim=reason,
            evidence_ref=evidence_ref,
            supersedes=evidence_id,
        )

    def active_evidence(
        self,
        *,
        peer_core_id: UUID | None = None,
        category: EvidenceCategory | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        return self._store.active_evidence(
            self.identity.core_id,
            peer_core_id=peer_core_id,
            category=category,
        )

    def appraisals(
        self, peer_core_id: UUID | None = None
    ) -> tuple[EmotionalAppraisal, ...]:
        return self._store.appraisals(
            self.identity.core_id, peer_core_id=peer_core_id
        )

    def topics(
        self,
        *,
        peer_core_id: UUID | None = None,
        status: TopicStatus | None = None,
    ) -> tuple[UnresolvedTopic, ...]:
        return self._store.topics(
            self.identity.core_id,
            peer_core_id=peer_core_id,
            status=status,
        )

    def set_facet(
        self,
        peer_core_id: UUID,
        facet: PeerFacet,
        *,
        level: float,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> FacetStance:
        return self._store.set_facet(
            core_id=self.identity.core_id,
            peer_core_id=peer_core_id,
            facet=facet,
            level=level,
            reason=reason,
            evidence_refs=evidence_refs,
            recorded_at=self._now(),
        )

    def relationship(self, peer_core_id: UUID) -> PeerRelationship:
        return self._store.relationship(self.identity.core_id, peer_core_id)

    def record_appraisal(
        self,
        *,
        labels: tuple[str, ...],
        valence: float,
        intensity: float,
        evidence_ref: str,
        peer_core_id: UUID | None = None,
        topic: str | None = None,
    ) -> EmotionalAppraisal:
        return self._store.record_appraisal(
            EmotionalAppraisal(
                appraisal_id=self._store.new_appraisal_id(),
                core_id=self.identity.core_id,
                peer_core_id=peer_core_id,
                topic=topic,
                labels=labels,
                valence=valence,
                intensity=intensity,
                evidence_ref=evidence_ref,
                recorded_at=self._now(),
            )
        )

    def set_interest(self, name: str, strength: float) -> None:
        self._store.set_interest(
            self.identity.core_id, name, strength, self._now()
        )

    def record_opinion(
        self,
        *,
        topic: str,
        statement: str,
        stance: float,
        confidence: float,
        evidence_refs: tuple[str, ...],
        peer_core_id: UUID | None = None,
    ):
        return self._store.record_opinion(
            core_id=self.identity.core_id,
            peer_core_id=peer_core_id,
            topic=topic,
            statement=statement,
            stance=stance,
            confidence=confidence,
            evidence_refs=evidence_refs,
            recorded_at=self._now(),
        )

    def opinions(self, peer_core_id: UUID | None = None):
        return self._store.opinions(
            self.identity.core_id, peer_core_id=peer_core_id
        )

    def set_goal(
        self,
        goal_id: str,
        description: str,
        priority: float,
        *,
        active: bool = True,
    ) -> None:
        self._store.set_goal(
            self.identity.core_id,
            goal_id,
            description,
            priority,
            active=active,
            at=self._now(),
        )

    def set_boundary(
        self,
        peer_core_id: UUID | None,
        kind: BoundaryKind,
        value: str | None = None,
    ) -> None:
        self._store.set_boundary(
            self.identity.core_id, peer_core_id, kind, value, self._now()
        )

    def set_topic(
        self,
        topic_key: str,
        *,
        summary: str,
        peer_core_id: UUID | None = None,
        room_id: str | None = None,
        next_revisit_at: datetime | None = None,
    ) -> UnresolvedTopic:
        now = self._now()
        return self._store.set_topic(
            core_id=self.identity.core_id,
            topic_key=topic_key,
            peer_core_id=peer_core_id,
            room_id=room_id,
            summary=summary,
            status=TopicStatus.OPEN,
            now=now,
            next_revisit_at=next_revisit_at
            or now + self._limits.topic_revisit_after,
        )


def _with_delivery(
    decision: SocialDecision, delivery_ref: str | None
) -> SocialDecision:
    return SocialDecision(
        action=decision.action,
        core_id=decision.core_id,
        target_core_id=decision.target_core_id,
        room_id=decision.room_id,
        body=decision.body,
        reason=decision.reason,
        permitted=decision.permitted,
        duplicate_suppressed=decision.duplicate_suppressed,
        deferred_until=decision.deferred_until,
        delivery_ref=delivery_ref,
        payload_ref=decision.payload_ref,
    )
