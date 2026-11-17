"""Bounded optional Core-initiated social behavior tests."""
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.conversation import MultiCoreConversation
from sofia.core.multicore.social import (
    InitiativeAction,
    InitiativeLimits,
    MultiCoreSocial,
    ProposalStatus,
)
from sofia.platform.chat import ChatActor, ChatEngine, CoreIdentity, MembershipStatus


NOW = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=NOW):
        self.now_value = now

    def __call__(self):
        return self.now_value

    def advance(self, delta):
        self.now_value += delta


def make_core(name):
    return CoreIdentity(uuid4(), f"platform:{name.lower()}", 1, name)


def responder(text):
    return lambda request: text


@pytest.fixture
def runtime(tmp_path):
    path = tmp_path / "social.db"
    with sqlite3.connect(path):
        pass
    clock = Clock()
    engine = ChatEngine(path, owner_id="platform:owner", clock=clock)
    conversation = MultiCoreConversation(engine, clock=clock)
    ada = conversation.register_core(make_core("Ada"), responder=responder("Ada data"))
    bea = conversation.register_core(make_core("Bea"), responder=responder("Bea data"))
    social = MultiCoreSocial(conversation, clock=clock)
    return conversation, social, ada, bea, clock


def history_text(conversation, core_id="general"):
    return [
        message.body
        for message in conversation.history(
            conversation.owner_actor(), core_id, limit=100
        ).messages
    ]


def test_core_proposal_is_inert_until_executed_and_posts_as_that_core(runtime):
    conversation, social, ada, bea, clock = runtime
    proposal = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="I would like to raise a design point.",
        rationale="relevance",
    )

    assert proposal.status is ProposalStatus.PROPOSED
    assert proposal.permitted is True
    assert proposal.grants_authority is False
    assert history_text(conversation) == []

    execution = social.execute(proposal.proposal_id)
    assert execution.status is ProposalStatus.EXECUTED
    assert execution.grants_authority is False
    assert execution.message_id is not None
    assert history_text(conversation) == ["I would like to raise a design point."]

    page = conversation.history(conversation.owner_actor(), "general")
    assert page.messages[0].sender_core_id == ada.core_id_text
    assert proposal.as_data()["grants_authority"] is False


def test_inactive_or_stopped_core_manufactures_no_activity(runtime):
    conversation, social, ada, bea, clock = runtime
    social.stop_core(ada.core_id_text)

    proposal = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="This must not be said.",
    )
    assert proposal.status is ProposalStatus.STOPPED
    assert proposal.permitted is False
    assert history_text(conversation) == []
    with pytest.raises(ValueError):
        social.execute(proposal.proposal_id)

    social.resume_core(ada.core_id_text)
    social.stop_all()
    blocked = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="Also not said.",
    )
    assert blocked.status is ProposalStatus.STOPPED
    assert history_text(conversation) == []


def test_duplicate_follow_ups_are_bounded_and_suppressed(tmp_path):
    path = tmp_path / "followups.db"
    with sqlite3.connect(path):
        pass
    clock = Clock()
    engine = ChatEngine(path, owner_id="platform:owner", clock=clock)
    conversation = MultiCoreConversation(engine, clock=clock)
    ada = conversation.register_core(make_core("Ada"), responder=responder("Ada data"))
    social = MultiCoreSocial(
        conversation,
        clock=clock,
        limits=InitiativeLimits(
            cooldown=timedelta(0),
            duplicate_window=timedelta(hours=1),
            max_follow_ups_per_chain=1,
            max_open_proposals_per_core=5,
        ),
    )

    first = social.propose(
        ada.core_id_text,
        InitiativeAction.FOLLOW_UP,
        room_id="general",
        body="First follow-up.",
        chain_id="chain:topic",
    )
    assert first.status is ProposalStatus.PROPOSED

    too_many = social.propose(
        ada.core_id_text,
        InitiativeAction.FOLLOW_UP,
        room_id="general",
        body="Second follow-up.",
        chain_id="chain:topic",
    )
    assert too_many.status is ProposalStatus.BLOCKED
    assert "follow-up" in too_many.rationale

    duplicate = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="A thought.",
    )
    assert duplicate.status is ProposalStatus.PROPOSED
    repeated = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="A   thought.",
    )
    assert repeated.status is ProposalStatus.BLOCKED
    assert "duplicate" in repeated.rationale


def test_invitation_is_declined_and_decline_is_respected(runtime):
    conversation, social, ada, bea, clock = runtime
    group = conversation.create_group(ChatActor.core(ada), "Ada's room")

    proposal = social.propose(
        ada.core_id_text,
        InitiativeAction.INVITE,
        room_id=group.room_id,
        target_core_id=bea.core_id_text,
    )
    assert proposal.status is ProposalStatus.PROPOSED
    execution = social.execute(proposal.proposal_id)
    assert execution.status is ProposalStatus.EXECUTED
    assert execution.invitation_id is not None

    declined = social.decline_invitation(
        proposal.proposal_id, by_core_id=bea.core_id_text
    )
    assert declined.status is ProposalStatus.DECLINED
    membership = conversation.engine.membership(
        ChatActor.core(ada),
        group.room_id,
        bea.core_id_text,
    )
    assert membership.status is MembershipStatus.DECLINED

    retry = social.propose(
        ada.core_id_text,
        InitiativeAction.INVITE,
        room_id=group.room_id,
        target_core_id=bea.core_id_text,
    )
    assert retry.status is ProposalStatus.BLOCKED
    assert "declined" in retry.rationale


def test_budget_aware_initiative_and_owner_inspection_stop(runtime):
    conversation, social, ada, bea, clock = runtime
    social.set_budget(ada.core_id_text, 1)

    first = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="Budgeted initiative.",
    )
    assert social.execute(first.proposal_id).status is ProposalStatus.EXECUTED

    exhausted = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="Another initiative.",
    )
    assert exhausted.status is ProposalStatus.BLOCKED
    assert "budget" in exhausted.rationale

    visible = social.inspect(core_id=ada.core_id_text)
    assert {item.proposal_id for item in visible} >= {
        first.proposal_id,
        exhausted.proposal_id,
    }
    social.stop_all()
    stopped = social.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="Stopped initiative.",
    )
    assert stopped.status is ProposalStatus.STOPPED
    assert stopped.proposal_id in {
        item.proposal_id for item in social.inspect()
    }


def test_leave_executes_and_expired_proposals_do_not_execute(runtime):
    conversation, social, ada, bea, clock = runtime
    owner = conversation.owner_actor()
    group = conversation.create_group(
        owner, "Shared", member_ids=[ada.core_id_text]
    )
    conversation.accept_channel(ada.core_id_text, group.room_id)
    leave = social.propose(
        ada.core_id_text,
        InitiativeAction.LEAVE,
        room_id=group.room_id,
    )
    assert leave.status is ProposalStatus.PROPOSED
    assert social.execute(leave.proposal_id).status is ProposalStatus.EXECUTED
    with pytest.raises(PermissionError):
        conversation.history(conversation.actor(ada.core_id_text), group.room_id)

    limited = MultiCoreSocial(
        conversation,
        clock=clock,
        limits=InitiativeLimits(proposal_expiry=timedelta(seconds=1)),
    )
    proposal = limited.propose(
        ada.core_id_text,
        InitiativeAction.PROPOSE,
        room_id="general",
        body="Short lived.",
    )
    assert proposal.status is ProposalStatus.PROPOSED
    clock.advance(timedelta(seconds=2))
    assert limited.expire() == 1
    assert limited.proposal(proposal.proposal_id).status is ProposalStatus.EXPIRED
    with pytest.raises(ValueError):
        limited.execute(proposal.proposal_id)
