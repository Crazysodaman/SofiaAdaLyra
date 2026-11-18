"""Bounded participation policy for independent multi-Core conversation.

The router decides *whether* a Core is willing and permitted to take a turn.
It never speaks for a Core, never creates chat history and never grants
execution authority.  Decisions are inert data consumed by the conversation
composition layer, which persists only text produced by the Core's own
injected responder.

Safety rails here are deterministic and local: explicit mentions, relevance,
availability, commitments, preferences, budgets, cooldowns, rate limits,
bounded chain turns, duplicate suppression, loop detection, cancellation and
owner termination controls.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import re
from typing import Callable, Iterable, Mapping

from sofia.platform.chat import ChatMessage


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_WHITESPACE = re.compile(r"\s+")


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _positive_int(value: object, label: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _ratio(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return number


def _text(value: object, label: str, *, maximum: int = 600) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value


def _fingerprint(body: str, sender_id: str | None = None) -> str:
    normalized = _WHITESPACE.sub(" ", body.strip().casefold())
    material = normalized if sender_id is None else f"{sender_id}|{normalized}"
    return sha256(material.encode("utf-8")).hexdigest()


class ParticipationAction(str, Enum):
    RESPOND = "respond"
    SILENCE = "silence"
    DECLINE = "decline"
    DEFER = "defer"
    SUPPRESSED_DUPLICATE = "suppressed_duplicate"
    LOOP_DETECTED = "loop_detected"
    CANCELLED = "cancelled"
    TERMINATED = "terminated"


@dataclass(frozen=True, slots=True)
class RoutingLimits:
    """Bounded defaults; a host may tighten but not bypass owner controls."""

    relevance_threshold: float = 0.5
    max_cores_per_message: int = 3
    max_chain_turns: int = 6
    cooldown: timedelta = timedelta(seconds=2)
    rate_window: timedelta = timedelta(minutes=1)
    max_responses_per_window: int = 6
    duplicate_window: timedelta = timedelta(minutes=2)
    loop_repeat_threshold: int = 3
    default_budget: int = 40
    commitment_bonus: float = 0.25
    max_tracked_messages: int = 1024
    max_tracked_chains: int = 512

    def __post_init__(self) -> None:
        _ratio(self.relevance_threshold, "relevance_threshold")
        _ratio(self.commitment_bonus, "commitment_bonus")
        for label in (
            "max_cores_per_message",
            "max_chain_turns",
            "max_responses_per_window",
            "loop_repeat_threshold",
            "default_budget",
            "max_tracked_messages",
            "max_tracked_chains",
        ):
            _positive_int(getattr(self, label), label)
        for label in ("cooldown", "rate_window", "duplicate_window"):
            value = getattr(self, label)
            if not isinstance(value, timedelta) or value < timedelta(0):
                raise ValueError(f"{label} must be a non-negative timedelta")


@dataclass(frozen=True, slots=True)
class ParticipationDecision:
    """One inert participation outcome; no authority is carried."""

    core_id: str
    action: ParticipationAction
    reason: str
    relevance: float
    mentioned: bool
    notify: bool
    chain_id: str
    defer_until: datetime | None = None
    rank: int | None = None

    def __post_init__(self) -> None:
        _identifier(self.core_id, "core_id")
        if not isinstance(self.action, ParticipationAction):
            raise TypeError("action must be a ParticipationAction")
        _text(self.reason, "reason")
        _ratio(self.relevance, "relevance")
        if type(self.mentioned) is not bool:
            raise TypeError("mentioned must be bool")
        if type(self.notify) is not bool:
            raise TypeError("notify must be bool")
        _identifier(self.chain_id, "chain_id")
        if self.defer_until is not None:
            _utc(self.defer_until, "defer_until")
        if self.rank is not None and (type(self.rank) is not int or self.rank < 0):
            raise ValueError("rank must be a non-negative integer")

    @property
    def should_respond(self) -> bool:
        return self.action is ParticipationAction.RESPOND

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def execution_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ParticipationStatus:
    core_id: str
    enabled: bool
    available: bool
    notify: bool
    declined: bool
    muted: bool
    preference_weight: float
    remaining_budget: int
    commitments: tuple[str, ...]
    terminated: bool


@dataclass(slots=True)
class _CoreState:
    enabled: bool = True
    available: bool = True
    notify: bool = True
    declined: bool = False
    muted: bool = False
    weight: float = 1.0
    remaining_budget: int = 40
    commitments: set[str] = field(default_factory=set)
    last_response_at: datetime | None = None
    response_times: deque[datetime] = field(default_factory=deque)
    terminated: bool = False


@dataclass(slots=True)
class _ChainState:
    cancelled: bool = False
    terminated: bool = False
    turns: int = 0
    fingerprints: list[str] = field(default_factory=list)
    seen_message_ids: set[str] = field(default_factory=set)
    responders: list[str] = field(default_factory=list)


class ParticipationRouter:
    """Deterministic, in-memory participation scheduler.

    It deliberately owns no durable history.  Chat history remains canonical in
    :class:`sofia.platform.chat.ChatEngine`; this object only bounds live turn
    selection and can be rebuilt on restart without inventing messages.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        limits: RoutingLimits | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        if limits is None:
            limits = RoutingLimits()
        if not isinstance(limits, RoutingLimits):
            raise TypeError("limits must be RoutingLimits")
        self._clock = clock
        self._limits = limits
        self._states: dict[str, _CoreState] = {}
        self._chains: dict[str, _ChainState] = {}
        self._seen_message_ids: deque[str] = deque(
            maxlen=limits.max_tracked_messages
        )
        self._seen_id_set: set[str] = set()
        self._content_seen: dict[str, deque[tuple[str, datetime]]] = {}
        self._terminate_all = False

    @property
    def limits(self) -> RoutingLimits:
        return self._limits

    def _now(self) -> datetime:
        value = self._clock() if self._clock is not None else datetime.now(timezone.utc)
        return _utc(value, "clock result")

    def _state(self, core_id: str) -> _CoreState:
        _identifier(core_id, "core_id")
        state = self._states.get(core_id)
        if state is None:
            state = _CoreState(remaining_budget=self._limits.default_budget)
            self._states[core_id] = state
        return state

    def _chain(self, chain_id: str) -> _ChainState:
        _identifier(chain_id, "chain_id")
        chain = self._chains.get(chain_id)
        if chain is None:
            chain = _ChainState()
            self._chains[chain_id] = chain
            while len(self._chains) > self._limits.max_tracked_chains:
                self._chains.pop(next(iter(self._chains)))
        return chain

    # ------------------------------------------------------------------
    # Owner participation and notification controls
    # ------------------------------------------------------------------
    def set_participation(
        self,
        core_id: str,
        enabled: bool,
        *,
        notify: bool | None = None,
    ) -> None:
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        if notify is not None and type(notify) is not bool:
            raise TypeError("notify must be bool")
        state = self._state(core_id)
        state.enabled = enabled
        if notify is not None:
            state.notify = notify

    def set_notification(self, core_id: str, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        self._state(core_id).notify = enabled

    def set_availability(self, core_id: str, available: bool) -> None:
        if type(available) is not bool:
            raise TypeError("available must be bool")
        self._state(core_id).available = available

    def set_declined(self, core_id: str, declined: bool = True) -> None:
        if type(declined) is not bool:
            raise TypeError("declined must be bool")
        self._state(core_id).declined = declined

    def set_preference(
        self,
        core_id: str,
        *,
        weight: float | None = None,
        muted: bool | None = None,
    ) -> None:
        state = self._state(core_id)
        if weight is not None:
            state.weight = _ratio(weight, "weight")
        if muted is not None:
            if type(muted) is not bool:
                raise TypeError("muted must be bool")
            state.muted = muted

    def set_budget(self, core_id: str, remaining: int) -> None:
        self._state(core_id).remaining_budget = _positive_int(
            remaining, "remaining", minimum=0
        )

    def grant_budget(self, core_id: str, amount: int) -> int:
        _positive_int(amount, "amount")
        state = self._state(core_id)
        state.remaining_budget += amount
        return state.remaining_budget

    def set_commitment(
        self, core_id: str, topic: str, *, active: bool = True
    ) -> None:
        _identifier(topic, "topic")
        if type(active) is not bool:
            raise TypeError("active must be bool")
        state = self._state(core_id)
        if active:
            state.commitments.add(topic)
        else:
            state.commitments.discard(topic)

    def cancel_chain(self, chain_id: str) -> None:
        self._chain(chain_id).cancelled = True

    def terminate(self, core_id: str) -> None:
        self._state(core_id).terminated = True

    def resume(self, core_id: str) -> None:
        self._state(core_id).terminated = False

    def terminate_all(self) -> None:
        self._terminate_all = True

    def resume_all(self) -> None:
        self._terminate_all = False
        for state in self._states.values():
            state.terminated = False

    def status(self, core_id: str) -> ParticipationStatus:
        state = self._state(core_id)
        return ParticipationStatus(
            core_id=core_id,
            enabled=state.enabled,
            available=state.available,
            notify=state.notify,
            declined=state.declined,
            muted=state.muted,
            preference_weight=state.weight,
            remaining_budget=state.remaining_budget,
            commitments=tuple(sorted(state.commitments)),
            terminated=state.terminated or self._terminate_all,
        )

    def statuses(self) -> tuple[ParticipationStatus, ...]:
        return tuple(self.status(core_id) for core_id in sorted(self._states))

    def chain_turns(self, chain_id: str) -> int:
        _identifier(chain_id, "chain_id")
        chain = self._chains.get(chain_id)
        return 0 if chain is None else chain.turns

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def _remember_message(self, message_id: str) -> bool:
        if message_id in self._seen_id_set:
            return False
        if len(self._seen_message_ids) == self._seen_message_ids.maxlen:
            evicted = self._seen_message_ids.popleft()
            self._seen_id_set.discard(evicted)
        self._seen_message_ids.append(message_id)
        self._seen_id_set.add(message_id)
        return True

    def evaluate(
        self,
        *,
        trigger: ChatMessage,
        candidates: Iterable[str],
        mentions: Iterable[str] = (),
        relevance: Mapping[str, float] | None = None,
        chain_id: str | None = None,
        topics: Iterable[str] = (),
        responders_available: Mapping[str, bool] | None = None,
    ) -> tuple[ParticipationDecision, ...]:
        """Return one bounded decision per candidate Core."""
        if not isinstance(trigger, ChatMessage):
            raise TypeError("trigger must be a ChatMessage")
        ids = tuple(dict.fromkeys(_identifier(item, "candidate") for item in candidates))
        if not ids:
            return ()
        chain_key = trigger.message_id if chain_id is None else chain_id
        chain = self._chain(chain_key)
        now = self._now()
        mentioned = {item for item in mentions}
        relevance_map = dict(relevance or {})
        available_map = dict(responders_available or {})
        topic_set = set(topics)
        sender_id = trigger.sender_core_id

        def decision(
            core_id: str,
            action: ParticipationAction,
            reason: str,
            *,
            value: float = 0.0,
            was_mentioned: bool = False,
            defer_until: datetime | None = None,
        ) -> ParticipationDecision:
            return ParticipationDecision(
                core_id=core_id,
                action=action,
                reason=reason,
                relevance=value,
                mentioned=was_mentioned,
                notify=self._state(core_id).notify,
                chain_id=chain_key,
                defer_until=defer_until,
            )

        duplicate = trigger.message_id in chain.seen_message_ids or (
            trigger.message_id in self._seen_id_set
        )
        if duplicate:
            return tuple(
                decision(
                    core_id,
                    ParticipationAction.SUPPRESSED_DUPLICATE,
                    "duplicate message delivery was already evaluated",
                )
                for core_id in ids
            )

        self._remember_message(trigger.message_id)
        chain.seen_message_ids.add(trigger.message_id)
        fingerprint = _fingerprint(trigger.body, sender_id)
        repeats = chain.fingerprints.count(fingerprint)
        loop = (
            chain.terminated
            or chain.turns >= self._limits.max_chain_turns
            or repeats >= self._limits.loop_repeat_threshold - 1
        )
        if chain.cancelled:
            return tuple(
                decision(core_id, ParticipationAction.CANCELLED, "chain cancelled")
                for core_id in ids
            )
        if loop:
            chain.terminated = True
            return tuple(
                decision(
                    core_id,
                    ParticipationAction.LOOP_DETECTED,
                    "bounded turn chain or repeated loop was detected",
                )
                for core_id in ids
            )

        remaining_turns = max(
            0, self._limits.max_chain_turns - chain.turns
        )
        slot_limit = min(self._limits.max_cores_per_message, remaining_turns)
        eligible: list[tuple[str, float, bool, bool]] = []
        results: dict[str, ParticipationDecision] = {}

        for core_id in ids:
            state = self._state(core_id)
            value = min(
                1.0, max(0.0, float(relevance_map.get(core_id, 0.0)))
            )
            was_mentioned = core_id in mentioned
            commitment_hit = bool(state.commitments & topic_set)
            if was_mentioned:
                value = 1.0
            elif commitment_hit:
                value = max(value, self._limits.relevance_threshold)

            if core_id == sender_id:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.SILENCE,
                    "the sender does not answer itself",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            elif self._terminate_all or state.terminated:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.TERMINATED,
                    "owner terminated this Core's participation",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            elif not state.enabled:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.SILENCE,
                    "owner disabled participation for this Core",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            elif not state.available:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.SILENCE,
                    "Core is unavailable",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            elif state.declined:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.DECLINE,
                    "Core declined participation",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            elif state.muted:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.SILENCE,
                    "Core preference mutes this room",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            elif state.remaining_budget <= 0:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.SILENCE,
                    "Core participation budget is exhausted",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            elif not available_map.get(core_id, True):
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.SILENCE,
                    "no responder is available for this Core",
                    value=value,
                    was_mentioned=was_mentioned,
                )
            else:
                recent = [
                    item
                    for item in state.response_times
                    if now - item < self._limits.rate_window
                ]
                if len(recent) >= self._limits.max_responses_per_window:
                    defer_until = recent[0] + self._limits.rate_window
                    results[core_id] = decision(
                        core_id,
                        ParticipationAction.DEFER,
                        "Core rate limit reached",
                        value=value,
                        was_mentioned=was_mentioned,
                        defer_until=defer_until,
                    )
                elif (
                    state.last_response_at is not None
                    and now - state.last_response_at < self._limits.cooldown
                ):
                    results[core_id] = decision(
                        core_id,
                        ParticipationAction.DEFER,
                        "Core cooldown is active",
                        value=value,
                        was_mentioned=was_mentioned,
                        defer_until=state.last_response_at + self._limits.cooldown,
                    )
                else:
                    weighted = value * state.weight
                    if not was_mentioned and not commitment_hit and (
                        weighted < self._limits.relevance_threshold
                    ):
                        results[core_id] = decision(
                            core_id,
                            ParticipationAction.SILENCE,
                            "message is below this Core's relevance threshold",
                            value=weighted,
                            was_mentioned=was_mentioned,
                        )
                    else:
                        eligible.append(
                            (core_id, weighted, was_mentioned, commitment_hit)
                        )

        eligible.sort(key=lambda item: (not item[2], not item[3], -item[1], item[0]))
        for rank, (core_id, value, was_mentioned, commitment_hit) in enumerate(
            eligible
        ):
            if rank >= slot_limit:
                results[core_id] = decision(
                    core_id,
                    ParticipationAction.SILENCE,
                    "bounded turn or response budget reached for this message",
                    value=value,
                    was_mentioned=was_mentioned,
                )
                continue
            reason = (
                "explicit mention"
                if was_mentioned
                else "active commitment"
                if commitment_hit
                else "relevance threshold met"
            )
            results[core_id] = replace(
                decision(
                    core_id,
                    ParticipationAction.RESPOND,
                    reason,
                    value=value,
                    was_mentioned=was_mentioned,
                ),
                rank=rank,
            )

        chain.fingerprints.append(fingerprint)
        if len(chain.fingerprints) > self._limits.max_tracked_messages:
            del chain.fingerprints[: -self._limits.max_tracked_messages]
        return tuple(results[core_id] for core_id in ids)

    # ------------------------------------------------------------------
    # Response accounting and duplicate suppression
    # ------------------------------------------------------------------
    def content_is_duplicate(
        self,
        core_id: str,
        body: str,
        *,
        room_id: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        _identifier(core_id, "core_id")
        if not isinstance(body, str):
            raise TypeError("body must be text")
        if room_id is not None:
            _identifier(room_id, "room_id")
        at = self._now() if now is None else _utc(now, "now")
        key = core_id if room_id is None else f"{core_id}|{room_id}"
        recent = self._content_seen.get(key)
        if not recent:
            return False
        cutoff = at - self._limits.duplicate_window
        while recent and recent[0][1] < cutoff:
            recent.popleft()
        digest = _fingerprint(body)
        return any(item[0] == digest for item in recent)

    def record_response(
        self,
        core_id: str,
        *,
        chain_id: str,
        body: str | None = None,
        room_id: str | None = None,
        now: datetime | None = None,
    ) -> None:
        _identifier(core_id, "core_id")
        chain = self._chain(chain_id)
        state = self._state(core_id)
        at = self._now() if now is None else _utc(now, "now")
        if state.remaining_budget > 0:
            state.remaining_budget -= 1
        state.last_response_at = at
        state.response_times.append(at)
        cutoff = at - self._limits.rate_window
        while state.response_times and state.response_times[0] < cutoff:
            state.response_times.popleft()
        chain.turns += 1
        chain.responders.append(core_id)
        if chain.turns >= self._limits.max_chain_turns:
            chain.terminated = True
        if body is not None:
            if not isinstance(body, str):
                raise TypeError("body must be text")
            key = core_id if room_id is None else f"{core_id}|{room_id}"
            recent = self._content_seen.setdefault(key, deque())
            recent.append((_fingerprint(body), at))
            while recent and recent[0][1] < at - self._limits.duplicate_window:
                recent.popleft()


__all__ = [
    "ParticipationAction",
    "ParticipationDecision",
    "ParticipationRouter",
    "ParticipationStatus",
    "RoutingLimits",
]
