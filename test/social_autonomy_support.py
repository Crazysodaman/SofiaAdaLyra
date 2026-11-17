"""Deterministic fakes for the autonomous social behavior tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sofia.platform.social.autonomy.contracts import (
    ChatMessage,
    CoreIdentity,
    SocialAction,
    SocialProposal,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


class RecordingTransport:
    def __init__(self) -> None:
        self.decisions = []
        self.fail = False

    def deliver(self, decision) -> str | None:
        if self.fail:
            raise RuntimeError("transport unavailable")
        self.decisions.append(decision)
        return f"delivery:{len(self.decisions)}"

    @property
    def actions(self) -> list[SocialAction]:
        return [item.action for item in self.decisions]


class RecordingScheduler:
    def __init__(self) -> None:
        self.wakes = []

    def wake(self, *, core_id, reason, due_at, event_id) -> None:
        self.wakes.append(
            {
                "core_id": core_id,
                "reason": reason,
                "due_at": due_at,
                "event_id": event_id,
            }
        )


class FakeStop:
    def __init__(self, active: bool = False) -> None:
        self.active = active

    def is_operator_stopped(self) -> bool:
        return self.active


class AllowAuthorization:
    def __init__(
        self,
        allowed: set[tuple[UUID, SocialAction]] | None = None,
        *,
        allow_all: bool = True,
    ) -> None:
        self.allowed = allowed or set()
        self.allow_all = allow_all
        self.calls = []

    def authorize(
        self,
        *,
        core,
        action,
        room_id,
        target_core_id,
        audience,
    ) -> bool:
        self.calls.append(
            {
                "core": core,
                "action": action,
                "room_id": room_id,
                "target_core_id": target_core_id,
                "audience": audience,
            }
        )
        if self.allow_all:
            return True
        return (core.core_id, action) in self.allowed


class StaticPlanner:
    def __init__(self, proposal: SocialProposal | None) -> None:
        self.proposal = proposal
        self.calls = []

    def propose(self, *, core, event, context):
        self.calls.append({"core": core, "event": event, "context": context})
        return self.proposal


class SequencePlanner:
    def __init__(self, proposals) -> None:
        self.proposals = list(proposals)
        self.calls = []

    def propose(self, *, core, event, context):
        self.calls.append({"core": core, "event": event, "context": context})
        if not self.proposals:
            return None
        return self.proposals.pop(0)


def identity(name: str, *, core_id: UUID | None = None) -> CoreIdentity:
    return CoreIdentity(
        core_id=core_id or uuid4(),
        platform_id=f"platform-{name}",
        generation=1,
        display_name=name,
    )


def message(
    sender: CoreIdentity,
    *,
    message_id: str,
    body: str = "A substantive message.",
    room_id: str = "general-1",
    audience: str = "public",
    now: datetime | None = None,
    reply_to: str | None = None,
    sequence: int = 1,
    origin: str = "peer",
    provenance: str = "test",
) -> ChatMessage:
    return ChatMessage(
        message_id=message_id,
        room_id=room_id,
        sender_core_id=sender.core_id,
        audience=audience,
        body=body,
        created_at=now or datetime(2026, 1, 1, tzinfo=timezone.utc),
        reply_to=reply_to,
        origin=origin,
        sequence=sequence,
        provenance=provenance,
    )


def proposal(
    action: SocialAction,
    *,
    relevance: float = 0.9,
    meaningful: bool = True,
    body: str | None = "Grounded Core-authored content.",
    topic: str | None = None,
    room_id: str | None = None,
    audience: str | None = "private",
    target_core_id: UUID | None = None,
    evidence_refs: tuple[str, ...] = (),
) -> SocialProposal:
    return SocialProposal(
        action=action,
        relevance=relevance,
        meaningful=meaningful,
        body=body,
        topic=topic,
        room_id=room_id,
        audience=audience,
        target_core_id=target_core_id,
        evidence_refs=evidence_refs,
    )


def state_path(tmp_path):
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    return path
