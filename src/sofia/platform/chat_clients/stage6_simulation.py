"""Deterministic seven-Core Stage 6 simulation.

This is a synthetic, in-process harness. It is evidence for deterministic
coordination and client behavior only. It is not seven installed production
Cores, not a process-boundary integration test, and it never invokes Ollama.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Sequence
from uuid import UUID, uuid5

from sofia.platform.chat_clients.contracts import (
    ChatEvent,
    ChatMessage,
    ChatOffline,
    ChatPermissionDenied,
    ChatRoom,
    ConnectionState,
    CoreIdentity,
    MembershipStatus,
    MessageOrigin,
    MessagePage,
    RoomKind,
    RoomMembership,
    SendReceipt,
    SendStatus,
    normalize_core_id,
)

_SYNTHETIC_NAMESPACE = UUID("3f0d9f5a-6f7e-4c3b-8a51-0d2f4c0e9a71")
_MAX_BODY = 16_000
_MAX_HISTORY_PER_ROOM = 4_000
_MAX_EVENTS = 8_000
_MAX_OWNER_REVIEWS = 128


class EvidenceCategory(str, Enum):
    DETERMINISTIC_SIMULATION = "deterministic_simulation"
    PROCESS_INTEGRATION = "process_integration"
    REAL_OLLAMA = "real_ollama"
    INSTALLED_HOST_ACCEPTANCE = "installed_host_acceptance"


@dataclass(frozen=True, slots=True)
class ScenarioEvidence:
    name: str
    category: EvidenceCategory
    passed: bool
    details: str


@dataclass(frozen=True, slots=True)
class Stage6Report:
    scenarios: tuple[ScenarioEvidence, ...]
    synthetic_core_count: int
    installed_production_core_count: int = 0
    real_ollama_invoked: bool = False
    process_boundaries_exercised: bool = False
    installed_host_acceptance: bool = False

    @property
    def category(self) -> EvidenceCategory:
        return EvidenceCategory.DETERMINISTIC_SIMULATION

    @property
    def all_passed(self) -> bool:
        return bool(self.scenarios) and all(item.passed for item in self.scenarios)

    def claim_boundary(self) -> str:
        return (
            "deterministic synthetic simulation only; "
            "do not claim installed Cores, process isolation, real Ollama, "
            "real audio or installed-host acceptance"
        )


@dataclass(slots=True)
class DeterministicModelPolicy:
    policy_id: str
    response_prefix: str
    temperature_band: str
    defers_background_to_gaming: bool = True

    def render(self, body: str) -> str:
        return f"{self.response_prefix}{body}"


@dataclass(slots=True)
class SyntheticCoreState:
    identity: CoreIdentity
    model_policy: DeterministicModelPolicy
    impressions: dict[str, dict[str, int]] = field(default_factory=dict)
    private_token: str = ""

    def normalized_id(self) -> str:
        return self.identity.normalized_core_id


@dataclass(slots=True)
class InferenceJob:
    job_id: str
    core_id: str
    category: str
    priority: int
    deferred_by_gaming: int = 0
    completed: bool = False


class SharedInferenceQueue:
    def __init__(self, *, max_jobs: int = 128) -> None:
        if type(max_jobs) is not int or not 1 <= max_jobs <= 1024:
            raise ValueError("max_jobs must be 1..1024")
        self._max_jobs = max_jobs
        self._jobs: list[InferenceJob] = []
        self._counter = 0

    @property
    def max_jobs(self) -> int:
        return self._max_jobs

    def __len__(self) -> int:
        return len(self._jobs)

    def enqueue(self, core_id: str, *, category: str = "background",
                priority: int = 0) -> InferenceJob:
        core = normalize_core_id(core_id).lower()
        if not isinstance(category, str) or not category:
            raise ValueError("category must be nonempty")
        if type(priority) is not int or not 0 <= priority <= 100:
            raise ValueError("priority must be 0..100")
        if len(self._jobs) >= self._max_jobs:
            raise RuntimeError("shared inference queue is full")
        self._counter += 1
        job = InferenceJob(
            job_id=f"job.{self._counter}.{core[:8]}",
            core_id=core, category=category, priority=priority,
        )
        self._jobs.append(job)
        return job

    def step(
        self, *, gaming_active: bool, capacity: int = 1
    ) -> tuple[InferenceJob, ...]:
        if type(gaming_active) is not bool:
            raise TypeError("gaming_active must be bool")
        if type(capacity) is not int or not 1 <= capacity <= 16:
            raise ValueError("capacity must be 1..16")
        if gaming_active:
            candidates = [
                job for job in self._jobs if job.category == "interactive"
            ]
            for job in self._jobs:
                if job.category != "interactive":
                    job.deferred_by_gaming += 1
        else:
            candidates = list(self._jobs)
        candidates.sort(key=lambda job: (-job.priority, job.job_id))
        processed = tuple(candidates[:capacity])
        for job in processed:
            job.completed = True
            self._jobs.remove(job)
        return processed

    def snapshot(self) -> tuple[dict[str, object], ...]:
        return tuple({
            "job_id": job.job_id,
            "core_id": job.core_id,
            "category": job.category,
            "priority": job.priority,
            "deferred_by_gaming": job.deferred_by_gaming,
            "completed": job.completed,
        } for job in self._jobs)


@dataclass(frozen=True, slots=True)
class OwnerReviewRecord:
    reviewing_core_id: str
    room_id: str
    requested_at: datetime
    message_count: int


class SyntheticStage6World:
    CORE_NAMES = (
        "Lyra", "Roland", "Lyda", "John", "Mira", "Tess", "Oriel",
    )

    def __init__(self, *, clock=None) -> None:
        self._clock = clock if clock is not None else (
            lambda: datetime.now(timezone.utc)
        )
        self._created_at = self._clock()
        self._cores: dict[str, SyntheticCoreState] = {}
        for index, name in enumerate(self.CORE_NAMES, start=1):
            core_id = str(uuid5(_SYNTHETIC_NAMESPACE, f"core:{index}:{name}"))
            identity = CoreIdentity(
                core_id=core_id,
                platform_id=f"platform.synthetic.{index}",
                generation=1,
                display_name=name,
            )
            self._cores[core_id] = SyntheticCoreState(
                identity=identity,
                model_policy=DeterministicModelPolicy(
                    policy_id=f"synthetic.policy.{index}",
                    response_prefix=f"[{name}] ",
                    temperature_band=f"band-{index}",
                ),
                private_token=f"synthetic-private-{index}-{core_id[:8]}",
            )
        self._rooms: dict[str, ChatRoom] = {}
        self._memberships: dict[str, dict[str, RoomMembership]] = {}
        self._messages: dict[str, list[ChatMessage]] = {}
        self._sequences: dict[str, int] = {}
        self._events: list[ChatEvent] = []
        self._revision = 0
        self._receipts: dict[tuple[str, str, str], SendReceipt] = {}
        self._online = set(self._cores)
        self._revoked: set[str] = set()
        self._stopped = False
        self._allowed_operations: dict[str, frozenset[str] | None] = {}
        self._owner_review_authorized = False
        self._owner_reviews: list[OwnerReviewRecord] = []
        self.inference = SharedInferenceQueue()
        self._gaming_active = False
        self._room_counter = 0
        general = self._make_room(
            room_id="room.general", kind=RoomKind.GENERAL,
            title="general", created_by=None,
        )
        for core_id in self._cores:
            self._add_membership(
                general.room_id, core_id, MembershipStatus.ACTIVE,
                history_from_sequence=0, epoch=1,
            )

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def gaming_active(self) -> bool:
        return self._gaming_active

    def now(self) -> datetime:
        return self._clock()

    def identities(self) -> tuple[CoreIdentity, ...]:
        return tuple(state.identity for state in self._cores.values())

    def identity(self, core_id: str) -> CoreIdentity:
        core = normalize_core_id(core_id).lower()
        state = self._cores.get(core)
        if state is None:
            raise ChatPermissionDenied("CORE_NOT_ENROLLED", "unknown Core")
        return state.identity

    def core_state(self, core_id: str) -> SyntheticCoreState:
        core = normalize_core_id(core_id).lower()
        try:
            return self._cores[core]
        except KeyError as error:
            raise ChatPermissionDenied(
                "CORE_NOT_ENROLLED", "unknown Core"
            ) from error

    def list_cores(self) -> tuple[CoreIdentity, ...]:
        return self.identities()

    def connection_state(self, core_id: str) -> ConnectionState:
        core = normalize_core_id(core_id).lower()
        if core in self._revoked:
            return ConnectionState.REVOKED
        if core not in self._online:
            return ConnectionState.OFFLINE
        if self._stopped:
            return ConnectionState.DEGRADED
        return ConnectionState.CONNECTED

    def list_rooms(self, core_id: str) -> tuple[ChatRoom, ...]:
        core = normalize_core_id(core_id).lower()
        self._require_enrolled(core)
        result = []
        for room_id, members in self._memberships.items():
            membership = members.get(core)
            if membership is not None and membership.status in {
                MembershipStatus.ACTIVE, MembershipStatus.INVITED,
            }:
                result.append(self._rooms[room_id])
        return tuple(sorted(result, key=lambda room: (
            0 if room.kind is RoomKind.GENERAL else
            1 if room.kind is RoomKind.DIRECT else 2,
            room.title.casefold(), room.room_id,
        )))

    def memberships(
        self, core_id: str, room_id: str
    ) -> tuple[RoomMembership, ...]:
        core = normalize_core_id(core_id).lower()
        self._require_enrolled(core)
        members = self._memberships.get(room_id)
        if members is None or core not in members:
            raise ChatPermissionDenied(
                "ROOM_NOT_VISIBLE", "room is not visible to the selected Core"
            )
        status = members[core].status
        if status not in {MembershipStatus.ACTIVE, MembershipStatus.INVITED}:
            raise ChatPermissionDenied(
                "MEMBERSHIP_INACTIVE", "selected Core is not an active member"
            )
        return tuple(
            members[key] for key in sorted(members)
        )

    def history_page(
        self, core_id: str, room_id: str, *,
        before_sequence: int | None = None, limit: int = 50,
    ) -> MessagePage:
        core = normalize_core_id(core_id).lower()
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        membership = self._active_membership(core, room_id)
        messages = [
            message for message in self._messages.get(room_id, ())
            if message.sequence >= membership.history_from_sequence
        ]
        if before_sequence is not None:
            if type(before_sequence) is not int or before_sequence < 0:
                raise ValueError("before_sequence must be nonnegative")
            messages = [
                message for message in messages
                if message.sequence < before_sequence
            ]
        page = messages[-limit:]
        has_more = len(messages) > len(page)
        return MessagePage(
            messages=tuple(page),
            before_sequence=before_sequence,
            has_more=has_more,
            oldest_sequence=page[0].sequence if page else None,
            newest_sequence=page[-1].sequence if page else None,
        )

    def send_message(
        self, core_id: str, room_id: str, body: str, *,
        client_message_id: str, reply_to: str | None = None,
        audience: str | None = None, generation: int | None = None,
    ) -> SendReceipt:
        core = normalize_core_id(core_id).lower()
        if not isinstance(client_message_id, str) or not client_message_id.strip():
            raise ValueError("client_message_id must be nonempty")
        if not isinstance(body, str) or not body.strip():
            raise ValueError("body must not be blank")
        if len(body) > _MAX_BODY:
            raise ValueError("body exceeds bound")
        self._require_operational(core, "chat.send")
        if generation is not None:
            self._require_generation(core, generation)
        self._active_membership(core, room_id)
        if reply_to is not None:
            if not any(
                message.message_id == reply_to
                for message in self._messages.get(room_id, ())
            ):
                raise ChatPermissionDenied(
                    "REPLY_TARGET_INVALID", "reply target is not visible"
                )
        key = (core, room_id, client_message_id)
        existing = self._receipts.get(key)
        if existing is not None:
            return existing
        room = self._rooms[room_id]
        if audience is None:
            audience = self._default_audience(room)
        sequence = self._next_sequence(room_id)
        message = ChatMessage(
            message_id=f"msg.{uuid5(_SYNTHETIC_NAMESPACE, f'{room_id}:{sequence}').hex}",
            room_id=room_id,
            sender_core_id=core,
            audience=audience,
            body=body,
            created_at=self._clock(),
            reply_to=reply_to,
            origin=MessageOrigin.CORE,
            sequence=sequence,
            provenance=(
                f"synthetic:core:{core}:generation:"
                f"{self._cores[core].identity.generation}"
            ),
        )
        self._messages.setdefault(room_id, []).append(message)
        self._trim_history(room_id)
        self._emit_message_events(room, message)
        receipt = SendReceipt(
            client_message_id=client_message_id,
            room_id=room_id,
            status=SendStatus.SENT_CONFIRMED,
            message=message,
        )
        self._receipts[key] = receipt
        return receipt

    def owner_send(self, room_id: str, body: str) -> ChatMessage:
        if not isinstance(body, str) or not body.strip():
            raise ValueError("body must not be blank")
        if room_id not in self._rooms:
            raise ChatPermissionDenied("ROOM_NOT_VISIBLE", "unknown room")
        sequence = self._next_sequence(room_id)
        message = ChatMessage(
            message_id=f"msg.{uuid5(_SYNTHETIC_NAMESPACE, f'owner:{room_id}:{sequence}').hex}",
            room_id=room_id,
            sender_core_id=None,
            audience=self._default_audience(self._rooms[room_id]),
            body=body,
            created_at=self._clock(),
            reply_to=None,
            origin=MessageOrigin.OWNER,
            sequence=sequence,
            provenance="synthetic:owner:review",
        )
        self._messages.setdefault(room_id, []).append(message)
        self._trim_history(room_id)
        self._emit_message_events(self._rooms[room_id], message)
        return message

    def system_send(self, room_id: str, body: str) -> ChatMessage:
        if not isinstance(body, str) or not body.strip():
            raise ValueError("body must not be blank")
        if room_id not in self._rooms:
            raise ChatPermissionDenied("ROOM_NOT_VISIBLE", "unknown room")
        sequence = self._next_sequence(room_id)
        message = ChatMessage(
            message_id=f"msg.{uuid5(_SYNTHETIC_NAMESPACE, f'system:{room_id}:{sequence}').hex}",
            room_id=room_id,
            sender_core_id=None,
            audience=self._default_audience(self._rooms[room_id]),
            body=body,
            created_at=self._clock(),
            reply_to=None,
            origin=MessageOrigin.SYSTEM,
            sequence=sequence,
            provenance="synthetic:system",
        )
        self._messages.setdefault(room_id, []).append(message)
        self._emit_message_events(self._rooms[room_id], message)
        return message

    def initiate_direct(self, core_id: str, peer_core_id: str) -> ChatRoom:
        core = normalize_core_id(core_id).lower()
        peer = normalize_core_id(peer_core_id).lower()
        self._require_operational(core, "chat.initiate")
        self._require_operational(peer, "chat.receive")
        if core == peer:
            raise ValueError("a Core cannot open a direct room with itself")
        for room_id, members in self._memberships.items():
            room = self._rooms[room_id]
            if room.kind is not RoomKind.DIRECT:
                continue
            if (
                members.get(core) is not None
                and peer in members
                and members[core].status is MembershipStatus.ACTIVE
                and members[peer].status is MembershipStatus.ACTIVE
            ):
                return room
        self._room_counter += 1
        title = f"DM {self._cores[core].identity.display_name} / {self._cores[peer].identity.display_name}"
        room = self._make_room(
            room_id=f"dm.{self._room_counter}.{core[:8]}.{peer[:8]}",
            kind=RoomKind.DIRECT,
            title=title[:120],
            created_by=core,
        )
        joined = self._clock()
        for member in (core, peer):
            self._add_membership(
                room.room_id, member, MembershipStatus.ACTIVE,
                history_from_sequence=0, epoch=1, joined_at=joined,
            )
        return room

    def initiate_direct_message(
        self, core_id: str, peer_core_id: str, body: str, *,
        client_message_id: str | None = None,
    ) -> SendReceipt:
        room = self.initiate_direct(core_id, peer_core_id)
        return self.send_message(
            core_id, room.room_id, body,
            client_message_id=client_message_id or f"init.{uuid5(_SYNTHETIC_NAMESPACE, body).hex}",
        )

    def create_private_group(
        self, core_id: str, *, title: str, member_core_ids: Sequence[str],
    ) -> ChatRoom:
        core = normalize_core_id(core_id).lower()
        self._require_operational(core, "chat.group.create")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("group title must be nonempty")
        members = []
        for member in member_core_ids:
            normalized = normalize_core_id(member).lower()
            self._require_enrolled(normalized)
            if normalized == core:
                continue
            if normalized not in members:
                members.append(normalized)
        if not members:
            raise ValueError("a private group needs at least one other Core")
        self._room_counter += 1
        room = self._make_room(
            room_id=f"group.{self._room_counter}.{uuid5(_SYNTHETIC_NAMESPACE, title).hex[:12]}",
            kind=RoomKind.PRIVATE_GROUP,
            title=title[:120],
            created_by=core,
        )
        self._add_membership(
            room.room_id, core, MembershipStatus.ACTIVE,
            history_from_sequence=0, epoch=1, joined_at=self._clock(),
        )
        for member in members:
            self._add_membership(
                room.room_id, member, MembershipStatus.INVITED,
                history_from_sequence=0, epoch=1, joined_at=None,
            )
        return room

    def invite_to_group(
        self, core_id: str, room_id: str, invited_core_id: str
    ) -> RoomMembership:
        core = normalize_core_id(core_id).lower()
        invited = normalize_core_id(invited_core_id).lower()
        self._require_operational(core, "chat.group.invite")
        self._require_enrolled(invited)
        room = self._rooms.get(room_id)
        if room is None or room.kind is not RoomKind.PRIVATE_GROUP:
            raise ChatPermissionDenied(
                "NOT_PRIVATE_GROUP", "invites apply only to private groups"
            )
        membership = self._active_membership(core, room_id)
        del membership
        existing = self._memberships[room_id].get(invited)
        if existing is not None and existing.status is MembershipStatus.ACTIVE:
            return existing
        epoch = (existing.epoch + 1) if existing is not None else 1
        joined_at = None
        row = RoomMembership(
            room_id=room_id,
            core_id=invited,
            epoch=epoch,
            status=MembershipStatus.INVITED,
            joined_at=joined_at,
            history_from_sequence=self._sequences.get(room_id, 0),
        )
        self._memberships[room_id][invited] = row
        self._emit_membership_event(invited, room_id)
        return row

    def respond_to_invite(
        self, core_id: str, room_id: str, *, accept: bool
    ) -> RoomMembership:
        core = normalize_core_id(core_id).lower()
        self._require_operational(core, "chat.group.respond")
        if type(accept) is not bool:
            raise TypeError("accept must be bool")
        member = self._memberships.get(room_id, {}).get(core)
        if member is None or member.status is not MembershipStatus.INVITED:
            raise ChatPermissionDenied(
                "NO_ACTIVE_INVITE", "there is no pending invite for this Core"
            )
        status = (
            MembershipStatus.ACTIVE if accept else MembershipStatus.DECLINED
        )
        joined_at = self._clock() if accept else None
        row = RoomMembership(
            room_id=room_id,
            core_id=core,
            epoch=member.epoch,
            status=status,
            joined_at=joined_at,
            history_from_sequence=member.history_from_sequence,
        )
        self._memberships[room_id][core] = row
        self._emit_membership_event(core, room_id)
        return row

    def leave_room(self, core_id: str, room_id: str) -> RoomMembership:
        core = normalize_core_id(core_id).lower()
        self._require_operational(core, "chat.leave")
        member = self._active_membership(core, room_id)
        row = RoomMembership(
            room_id=room_id,
            core_id=core,
            epoch=member.epoch + 1,
            status=MembershipStatus.LEFT,
            joined_at=member.joined_at,
            history_from_sequence=self._sequences.get(room_id, 0) + 1,
        )
        self._memberships[room_id][core] = row
        self._emit_membership_event(core, room_id)
        return row

    def revoke_core(self, core_id: str) -> None:
        core = normalize_core_id(core_id).lower()
        self._require_enrolled(core)
        self._revoked.add(core)
        self._online.discard(core)
        for room_id, members in self._memberships.items():
            member = members.get(core)
            if member is None or member.status is not MembershipStatus.ACTIVE:
                continue
            members[core] = RoomMembership(
                room_id=room_id,
                core_id=core,
                epoch=member.epoch + 1,
                status=MembershipStatus.REVOKED,
                joined_at=member.joined_at,
                history_from_sequence=self._sequences.get(room_id, 0) + 1,
            )
            self._emit_membership_event(core, room_id)

    def set_offline(self, core_id: str) -> None:
        core = normalize_core_id(core_id).lower()
        self._require_enrolled(core)
        self._online.discard(core)

    def reconnect_core(self, core_id: str) -> CoreIdentity:
        core = normalize_core_id(core_id).lower()
        self._require_enrolled(core)
        if core in self._revoked:
            raise ChatPermissionDenied("CORE_REVOKED", "Core access is revoked")
        self._online.add(core)
        self._emit_membership_event(core, "room.general")
        return self._cores[core].identity

    def restart(self) -> None:
        for state in self._cores.values():
            state.identity = CoreIdentity(
                core_id=state.identity.core_id,
                platform_id=state.identity.platform_id,
                generation=state.identity.generation + 1,
                display_name=state.identity.display_name,
            )
        self._online.clear()

    def stop(self) -> None:
        self._stopped = True

    def resume(self) -> None:
        self._stopped = False

    def restrict_core(self, core_id: str, operations: Sequence[str]) -> None:
        core = normalize_core_id(core_id).lower()
        self._require_enrolled(core)
        if not operations:
            raise ValueError("operations must not be empty")
        self._allowed_operations[core] = frozenset(operations)

    def grant_owner_review(self, enabled: bool = True) -> None:
        if type(enabled) is not bool:
            raise TypeError("enabled must be bool")
        self._owner_review_authorized = enabled

    def owner_review(
        self, core_id: str, room_id: str, *,
        before_sequence: int | None = None, limit: int = 50,
    ) -> MessagePage:
        core = normalize_core_id(core_id).lower()
        self._require_enrolled(core)
        if not self._owner_review_authorized:
            raise ChatPermissionDenied(
                "OWNER_REVIEW_NOT_AUTHORIZED",
                "owner history review requires explicit authorization",
            )
        if room_id not in self._rooms:
            raise ChatPermissionDenied("ROOM_NOT_VISIBLE", "unknown room")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("limit must be 1..200")
        messages = self._messages.get(room_id, ())
        if before_sequence is not None:
            messages = [
                item for item in messages if item.sequence < before_sequence
            ]
        page = tuple(messages[-limit:])
        self._owner_reviews.append(OwnerReviewRecord(
            reviewing_core_id=core,
            room_id=room_id,
            requested_at=self._clock(),
            message_count=len(page),
        ))
        del self._owner_reviews[:-_MAX_OWNER_REVIEWS]
        return MessagePage(
            messages=page,
            before_sequence=before_sequence,
            has_more=len(messages) > len(page),
            oldest_sequence=page[0].sequence if page else None,
            newest_sequence=page[-1].sequence if page else None,
        )

    def owner_reviews(self) -> tuple[OwnerReviewRecord, ...]:
        return tuple(self._owner_reviews)

    def set_impression(
        self, core_id: str, peer_core_id: str, *,
        respect: int = 50, skepticism: int = 50, trust: int = 50,
    ) -> None:
        core = normalize_core_id(core_id).lower()
        peer = normalize_core_id(peer_core_id).lower()
        self._require_enrolled(core)
        self._require_enrolled(peer)
        for label, value in (
            ("respect", respect), ("skepticism", skepticism), ("trust", trust),
        ):
            if type(value) is not int or not 0 <= value <= 100:
                raise ValueError(f"{label} must be 0..100")
        self._cores[core].impressions[peer] = {
            "respect": respect, "skepticism": skepticism, "trust": trust,
        }

    def impressions(self, core_id: str) -> dict[str, dict[str, int]]:
        core = normalize_core_id(core_id).lower()
        return deepcopy(self._cores[core].impressions)

    def model_policy(self, core_id: str) -> DeterministicModelPolicy:
        return deepcopy(self._cores[normalize_core_id(core_id).lower()].model_policy)

    def private_token(self, core_id: str) -> str:
        return self._cores[normalize_core_id(core_id).lower()].private_token

    def set_gaming(self, active: bool) -> None:
        if type(active) is not bool:
            raise TypeError("active must be bool")
        self._gaming_active = active

    def request_inference(
        self, core_id: str, *, category: str = "background", priority: int = 0
    ) -> InferenceJob:
        core = normalize_core_id(core_id).lower()
        self._require_operational(core, "inference.request")
        if category == "background":
            policy = self._cores[core].model_policy
            if self._gaming_active and policy.defers_background_to_gaming:
                job = self.inference.enqueue(
                    core, category="background", priority=priority
                )
                job.deferred_by_gaming += 1
                return job
        return self.inference.enqueue(core, category=category, priority=priority)

    def run_inference_step(self, *, capacity: int = 1) -> tuple[InferenceJob, ...]:
        return self.inference.step(
            gaming_active=self._gaming_active, capacity=capacity
        )

    def events(
        self, *, after_revision: int, core_id: str | None = None
    ) -> tuple[ChatEvent, ...]:
        if type(after_revision) is not int or after_revision < 0:
            raise ValueError("after_revision must be nonnegative")
        core = (
            normalize_core_id(core_id).lower() if core_id is not None else None
        )
        return tuple(
            event for event in self._events
            if event.revision > after_revision
            and (core is None or event.core_id.lower() == core)
        )

    def message_count(self, room_id: str) -> int:
        return len(self._messages.get(room_id, ()))

    def list_room_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._rooms))

    def sequence(self, room_id: str) -> int:
        return self._sequences.get(room_id, 0)

    def _make_room(
        self, *, room_id: str, kind: RoomKind, title: str,
        created_by: str | None,
    ) -> ChatRoom:
        room = ChatRoom(
            room_id=room_id,
            kind=kind,
            title=title,
            created_by_core_id=created_by,
            created_at=self._clock(),
        )
        self._rooms[room_id] = room
        self._memberships[room_id] = {}
        self._messages[room_id] = []
        self._sequences[room_id] = 0
        return room

    def _add_membership(
        self, room_id: str, core_id: str, status: MembershipStatus, *,
        history_from_sequence: int, epoch: int,
        joined_at: datetime | None = None,
    ) -> RoomMembership:
        row = RoomMembership(
            room_id=room_id,
            core_id=core_id,
            epoch=epoch,
            status=status,
            joined_at=joined_at,
            history_from_sequence=history_from_sequence,
        )
        self._memberships[room_id][core_id] = row
        return row

    def _active_membership(
        self, core_id: str, room_id: str
    ) -> RoomMembership:
        members = self._memberships.get(room_id)
        if members is None:
            raise ChatPermissionDenied("ROOM_NOT_VISIBLE", "unknown room")
        member = members.get(core_id)
        if member is None:
            raise ChatPermissionDenied(
                "ROOM_NOT_VISIBLE", "room is not visible to the selected Core"
            )
        if member.status is not MembershipStatus.ACTIVE:
            raise ChatPermissionDenied(
                "MEMBERSHIP_INACTIVE", "selected Core is not an active member"
            )
        return member

    def _require_enrolled(self, core_id: str) -> SyntheticCoreState:
        state = self._cores.get(core_id)
        if state is None:
            raise ChatPermissionDenied("CORE_NOT_ENROLLED", "unknown Core")
        return state

    def _require_operational(self, core_id: str, operation: str) -> None:
        self._require_enrolled(core_id)
        if core_id in self._revoked:
            raise ChatPermissionDenied("CORE_REVOKED", "Core access is revoked")
        if self._stopped:
            raise ChatPermissionDenied("STOP_ACTIVE", "operator STOP is active")
        if core_id not in self._online:
            raise ChatOffline("Core connection is offline")
        allowed = self._allowed_operations.get(core_id)
        if allowed is not None and operation not in allowed:
            raise ChatPermissionDenied(
                "OPERATION_NOT_AUTHORIZED",
                f"operation {operation} is not authorized",
            )

    def _require_generation(self, core_id: str, generation: int) -> None:
        current = self._cores[core_id].identity.generation
        if generation != current:
            raise ChatPermissionDenied(
                "STALE_GENERATION", "Core identity generation is not current"
            )

    def _next_sequence(self, room_id: str) -> int:
        self._sequences[room_id] = self._sequences.get(room_id, 0) + 1
        return self._sequences[room_id]

    def _trim_history(self, room_id: str) -> None:
        messages = self._messages.get(room_id, [])
        if len(messages) > _MAX_HISTORY_PER_ROOM:
            del messages[:-_MAX_HISTORY_PER_ROOM]

    def _default_audience(self, room: ChatRoom) -> str:
        if room.kind is RoomKind.GENERAL:
            return "room:general"
        return f"room:{room.room_id}"

    def _mentions(
        self, body: str, recipients: Sequence[str]
    ) -> tuple[str, ...]:
        found = []
        lowered = body.casefold()
        for core_id in recipients:
            name = self._cores[core_id].identity.display_name.casefold()
            if re.search(rf"@{re.escape(name)}\b", lowered):
                found.append(core_id)
        return tuple(found)

    def _active_recipients(self, room_id: str) -> tuple[str, ...]:
        members = self._memberships.get(room_id, {})
        return tuple(
            core for core in sorted(members)
            if members[core].status is MembershipStatus.ACTIVE
            and core not in self._revoked
        )

    def _emit_message_events(
        self, room: ChatRoom, message: ChatMessage,
    ) -> ChatEvent | None:
        recipients = self._active_recipients(room.room_id)
        mentions = self._mentions(message.body, recipients)
        emitted = None
        for core_id in recipients:
            self._revision += 1
            event = ChatEvent(
                revision=self._revision,
                core_id=core_id,
                room_id=room.room_id,
                message=message,
                kind="message",
                mentioned_core_ids=(core_id,) if core_id in mentions else (),
            )
            self._events.append(event)
            emitted = event
        del self._events[:-_MAX_EVENTS]
        return emitted

    def _emit_membership_event(self, core_id: str, room_id: str) -> None:
        self._revision += 1
        self._events.append(ChatEvent(
            revision=self._revision,
            core_id=core_id,
            room_id=room_id,
            message=None,
            kind="membership",
        ))
        del self._events[:-_MAX_EVENTS]


class Stage6ScenarioRunner:
    def __init__(self) -> None:
        self._results: list[ScenarioEvidence] = []

    def _record(self, name: str, passed: bool, details: str) -> None:
        self._results.append(ScenarioEvidence(
            name=name,
            category=EvidenceCategory.DETERMINISTIC_SIMULATION,
            passed=bool(passed),
            details=details,
        ))

    def run(self) -> Stage6Report:
        self._results = []
        self._seven_cores_in_general()
        self._simultaneous_inbound()
        self._direct_and_group()
        self._core_initiated()
        self._invite_leave_decline()
        self._independent_relationships()
        self._owner_history_review()
        self._denial_and_revocation()
        self._inference_queue_and_gaming()
        self._restart_and_reconnect()
        self._stop_and_authorization()
        self._bounded_long_autonomy()
        self._seven_core_scale_no_leakage()
        world = SyntheticStage6World()
        return Stage6Report(
            scenarios=tuple(self._results),
            synthetic_core_count=len(world.identities()),
        )

    def _seven_cores_in_general(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        rooms = world.list_rooms(ids[0])
        general = next(
            room for room in rooms if room.kind is RoomKind.GENERAL
        )
        rows = world.memberships(ids[0], general.room_id)
        active = [
            row for row in rows if row.status is MembershipStatus.ACTIVE
        ]
        world.send_message(
            ids[0], general.room_id, "hello all",
            client_message_id="scenario.general.1",
        )
        visible = all(
            world.history_page(core, general.room_id).messages
            for core in ids
        )
        self._record(
            "seven_cores_in_general",
            len(ids) == 7 and len(active) == 7 and visible,
            f"cores={len(ids)} active_general_members={len(active)} visible={visible}",
        )

    def _simultaneous_inbound(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        for index, core in enumerate(ids):
            world.send_message(
                core, "room.general", f"inbound {index}",
                client_message_id=f"scenario.inbound.{index}",
            )
        counts = {
            core: len(world.history_page(core, "room.general").messages)
            for core in ids
        }
        self._record(
            "simultaneous_inbound",
            all(count == 7 for count in counts.values()),
            f"history_counts={sorted(set(counts.values()))}",
        )

    def _direct_and_group(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        dm = world.initiate_direct(ids[0], ids[1])
        world.send_message(
            ids[0], dm.room_id, "direct hello",
            client_message_id="scenario.dm.1",
        )
        group = world.create_private_group(
            ids[0], title="research", member_core_ids=[ids[2]],
        )
        world.respond_to_invite(ids[2], group.room_id, accept=True)
        world.send_message(
            ids[0], group.room_id, "group hello",
            client_message_id="scenario.group.1",
        )
        dm_ok = bool(world.history_page(ids[1], dm.room_id).messages)
        group_ok = bool(world.history_page(ids[2], group.room_id).messages)
        denied = False
        try:
            world.history_page(ids[3], dm.room_id)
        except ChatPermissionDenied:
            denied = True
        self._record(
            "direct_and_group",
            dm_ok and group_ok and denied,
            f"dm={dm_ok} group={group_ok} third_party_denied={denied}",
        )

    def _core_initiated(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        receipts = []
        for index, core in enumerate(ids):
            peer = ids[(index + 1) % len(ids)]
            receipts.append(world.initiate_direct_message(
                core, peer, f"question from {index}",
                client_message_id=f"scenario.initiate.{index}",
            ))
        self._record(
            "core_initiated_conversations",
            all(item.status is SendStatus.SENT_CONFIRMED for item in receipts),
            f"initiated={len(receipts)}",
        )

    def _invite_leave_decline(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        group = world.create_private_group(
            ids[0], title="temporary",
            member_core_ids=[ids[1], ids[2]],
        )
        accepted = world.respond_to_invite(ids[1], group.room_id, accept=True)
        declined = world.respond_to_invite(ids[2], group.room_id, accept=False)
        left = world.leave_room(ids[1], group.room_id)
        denied = False
        try:
            world.send_message(
                ids[1], group.room_id, "after leave",
                client_message_id="scenario.leave.1",
            )
        except ChatPermissionDenied:
            denied = True
        self._record(
            "invite_leave_decline",
            accepted.status is MembershipStatus.ACTIVE
            and declined.status is MembershipStatus.DECLINED
            and left.status is MembershipStatus.LEFT and denied,
            f"accepted={accepted.status.value} declined={declined.status.value} "
            f"left={left.status.value} send_after_leave_denied={denied}",
        )

    def _independent_relationships(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        world.set_impression(ids[0], ids[1], respect=85, skepticism=20, trust=70)
        world.set_impression(ids[2], ids[1], respect=30, skepticism=80, trust=25)
        first = world.impressions(ids[0])[ids[1]]
        second = world.impressions(ids[2])[ids[1]]
        first_snapshot = dict(first)
        first["trust"] = 1
        unchanged = world.impressions(ids[0])[ids[1]]["trust"] == 70
        self._record(
            "independent_relationships",
            first_snapshot != second and unchanged,
            f"core0={first_snapshot} core2={second} copy_isolated={unchanged}",
        )

    def _owner_history_review(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        dm = world.initiate_direct(ids[0], ids[1])
        world.send_message(
            ids[0], dm.room_id, "private note",
            client_message_id="scenario.review.1",
        )
        denied = False
        try:
            world.owner_review(ids[0], dm.room_id)
        except ChatPermissionDenied:
            denied = True
        world.grant_owner_review()
        page = world.owner_review(ids[0], dm.room_id)
        self._record(
            "owner_history_review",
            denied and bool(page.messages) and len(world.owner_reviews()) == 1,
            f"unauthorized_denied={denied} reviewed={len(page.messages)}",
        )

    def _denial_and_revocation(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        world.revoke_core(ids[6])
        send_denied = False
        history_denied = False
        try:
            world.send_message(
                ids[6], "room.general", "should fail",
                client_message_id="scenario.revoke.1",
            )
        except ChatPermissionDenied:
            send_denied = True
        try:
            world.history_page(ids[6], "room.general")
        except ChatPermissionDenied:
            history_denied = True
        self._record(
            "denial_and_revocation",
            send_denied and history_denied
            and world.connection_state(ids[6]) is ConnectionState.REVOKED,
            f"send_denied={send_denied} history_denied={history_denied}",
        )

    def _inference_queue_and_gaming(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        for core in ids:
            world.request_inference(core, category="background", priority=10)
        world.set_gaming(True)
        during = world.run_inference_step(capacity=7)
        deferred = [
            job for job in world.inference.snapshot()
            if job["deferred_by_gaming"] > 0
        ]
        world.set_gaming(False)
        after = world.run_inference_step(capacity=7)
        self._record(
            "shared_inference_queue_and_gaming",
            during == () and len(deferred) == 7 and len(after) == 7,
            f"processed_during_gaming={len(during)} deferred={len(deferred)} "
            f"processed_after={len(after)}",
        )

    def _restart_and_reconnect(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        world.send_message(
            ids[0], "room.general", "before restart",
            client_message_id="scenario.restart.1",
        )
        old = tuple(world.identities())
        world.restart()
        new = tuple(world.identities())
        reconnect = [world.reconnect_core(core) for core in ids]
        stale_denied = False
        try:
            world.send_message(
                ids[0], "room.general", "stale attempt",
                client_message_id="scenario.restart.2",
                generation=old[0].generation,
            )
        except ChatPermissionDenied:
            stale_denied = True
        history_ok = all(
            world.history_page(core, "room.general").messages
            for core in ids
        )
        self._record(
            "restart_and_reconnect",
            all(item.generation == 2 for item in new)
            and stale_denied and len(reconnect) == 7 and history_ok,
            f"generations={sorted({item.generation for item in new})} "
            f"stale_denied={stale_denied} history_preserved={history_ok}",
        )

    def _stop_and_authorization(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        world.stop()
        stop_denied = False
        inference_denied = False
        try:
            world.send_message(
                ids[0], "room.general", "stop test",
                client_message_id="scenario.stop.1",
            )
        except ChatPermissionDenied:
            stop_denied = True
        try:
            world.request_inference(ids[0])
        except ChatPermissionDenied:
            inference_denied = True
        world.resume()
        world.restrict_core(ids[1], ["chat.receive"])
        authorization_denied = False
        try:
            world.send_message(
                ids[1], "room.general", "restricted",
                client_message_id="scenario.stop.2",
            )
        except ChatPermissionDenied:
            authorization_denied = True
        self._record(
            "stop_and_authorization",
            stop_denied and inference_denied and authorization_denied,
            f"stop_denied={stop_denied} inference_denied={inference_denied} "
            f"authorization_denied={authorization_denied}",
        )

    def _bounded_long_autonomy(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        for cycle in range(240):
            core = ids[cycle % len(ids)]
            peer = ids[(cycle + 1) % len(ids)]
            world.initiate_direct_message(
                core, peer, f"cycle {cycle}",
                client_message_id=f"scenario.long.{cycle}",
            )
            try:
                world.request_inference(core, category="background")
            except RuntimeError:
                world.run_inference_step(capacity=2)
            world.run_inference_step(capacity=2)
        queue_bound = len(world.inference) <= world.inference.max_jobs
        histories_bound = all(
            world.message_count(room_id) <= _MAX_HISTORY_PER_ROOM
            for room_id in world.list_room_ids()
        )
        self._record(
            "bounded_long_autonomy",
            queue_bound and histories_bound,
            f"queue_bound={queue_bound} histories_bound={histories_bound} "
            f"queue={len(world.inference)}",
        )

    def _seven_core_scale_no_leakage(self) -> None:
        world = SyntheticStage6World()
        ids = [item.core_id for item in world.identities()]
        rooms = []
        for index in range(7):
            peer = ids[(index + 1) % 7]
            room = world.initiate_direct(ids[index], peer)
            rooms.append(room)
            world.send_message(
                ids[index], room.room_id, f"secret {index}",
                client_message_id=f"scenario.scale.{index}",
            )
        leaks = 0
        for index, room in enumerate(rooms):
            outsider = ids[(index + 2) % 7]
            try:
                world.owner_review(outsider, room.room_id)
            except ChatPermissionDenied:
                pass
            try:
                world.history_page(outsider, room.room_id)
            except ChatPermissionDenied:
                leaks += 1
        tokens = {world.private_token(core) for core in ids}
        self._record(
            "seven_core_scale_without_identity_leakage",
            leaks == 7 and len(tokens) == 7,
            f"third_party_denials={leaks} distinct_private_tokens={len(tokens)}",
        )


def run_stage6_deterministic_suite() -> Stage6Report:
    return Stage6ScenarioRunner().run()
