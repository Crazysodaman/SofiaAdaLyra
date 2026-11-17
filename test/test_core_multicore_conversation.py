"""Composition tests for multi-Core chat, channels, attribution and restart."""
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.contracts import ChannelKind, PersistentCoreIdentity
from sofia.core.multicore.conversation import (
    ConversationChannel,
    CoreResponse,
    MultiCoreConversation,
    coerce_core_response,
)
from sofia.platform.chat import (
    ChatActor,
    ChatEngine,
    CoreIdentity,
    MembershipStatus,
    MessageOrigin,
    RoomHistoryPolicy,
)


NOW = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=NOW):
        self.now_value = now

    def __call__(self):
        return self.now_value

    def advance(self, delta):
        self.now_value += delta


def make_engine(tmp_path, name="sofia.db", **kwargs):
    path = tmp_path / name
    with sqlite3.connect(path):
        pass
    return ChatEngine(path, owner_id="platform:owner", **kwargs)


def make_core(name, platform=None):
    return CoreIdentity(
        uuid4(),
        platform or f"platform:{name.lower()}",
        1,
        name,
    )


def text_responder(text):
    def respond(request):
        return text

    return respond


@pytest.fixture
def engine(tmp_path):
    return make_engine(tmp_path)


@pytest.fixture
def conversation(engine):
    return MultiCoreConversation(engine)


def test_general_routes_only_selected_core_and_records_real_authors(
    engine, conversation
):
    ada = conversation.register_core(make_core("Ada"), responder=text_responder("Ada data"))
    bea = conversation.register_core(make_core("Bea"), responder=text_responder("Bea data"))
    owner = conversation.owner_actor()

    result = conversation.post_and_route(
        owner,
        "general",
        "Owner asks Ada a question.",
        mentions=[ada.core_id_text],
    )

    assert result.message.origin is MessageOrigin.OWNER
    assert result.message.sender_core_id == engine.owner_id
    assert [reply.sender_core_id for reply in result.replies] == [ada.core_id_text]
    assert result.replies[0].origin is MessageOrigin.LOCAL_CORE
    assert conversation.author(result.message).kind.value == "owner"
    assert conversation.author(result.replies[0]).display_name == "Ada"
    assert conversation.author(result.replies[0]).untrusted_content is False

    history = conversation.history(owner, "general", limit=10)
    assert [message.body for message in history.messages] == [
        "Owner asks Ada a question.",
        "Ada data",
    ]
    decision = {item.core_id: item for item in result.decisions}
    assert decision[bea.core_id_text].should_respond is False
    assert decision[ada.core_id_text].should_respond is True


def test_owner_direct_is_isolated_and_owner_can_switch_channels(
    engine, conversation
):
    ada = conversation.register_core(make_core("Ada"), responder=text_responder("private reply"))
    bea = conversation.register_core(make_core("Bea"), responder=text_responder("Bea reply"))
    owner = conversation.owner_actor()

    direct = conversation.open_owner_direct(ada.core_id_text)
    assert direct.kind is ChannelKind.DIRECT
    switched = conversation.switch_channel(owner, direct.room_id)
    assert switched.room_id == direct.room_id
    assert conversation.active_channel(owner).room_id == direct.room_id

    result = conversation.post_and_route(owner, direct.room_id, "Only Ada hears this.")
    assert [reply.sender_core_id for reply in result.replies] == [ada.core_id_text]

    with pytest.raises(PermissionError):
        conversation.history(conversation.actor(bea.core_id_text), direct.room_id)
    with pytest.raises(PermissionError):
        conversation.post(
            conversation.actor(bea.core_id_text), direct.room_id, "intrusion"
        )

    general = conversation.switch_channel(owner, "general")
    assert general.kind is ChannelKind.GENERAL
    assert conversation.active_channel(owner).room_id == "general"


def test_core_to_core_direct_requires_acceptance_and_attributes_each_author(
    conversation
):
    ada = conversation.register_core(make_core("Ada"), responder=text_responder("Ada here"))
    bea = conversation.register_core(make_core("Bea"), responder=text_responder("Bea here"))
    cy = conversation.register_core(make_core("Cy"), responder=text_responder("Cy here"))

    channel = conversation.open_core_direct(ada.core_id_text, bea.core_id_text)
    assert channel.kind is ChannelKind.CORE_TO_CORE

    with pytest.raises(PermissionError):
        conversation.post(
            conversation.actor(bea.core_id_text), channel.room_id, "too early"
        )

    membership = conversation.accept_channel(bea.core_id_text, channel.room_id)
    assert membership.status is MembershipStatus.ACTIVE

    result = conversation.post_and_route(
        conversation.actor(ada.core_id_text), channel.room_id, "Core-to-Core hello"
    )
    assert [reply.sender_core_id for reply in result.replies] == [bea.core_id_text]
    assert conversation.author(result.message).display_name == "Ada"
    assert conversation.author(result.replies[0]).display_name == "Bea"

    with pytest.raises(PermissionError):
        conversation.history(conversation.actor(cy.core_id_text), channel.room_id)


def test_group_membership_audience_and_denial(conversation):
    owner = conversation.owner_actor()
    ada = conversation.register_core(make_core("Ada"), responder=text_responder("Ada reply"))
    bea = conversation.register_core(make_core("Bea"), responder=text_responder("Bea reply"))

    group = conversation.create_group(
        owner,
        "Planning",
        topic="release",
        member_ids=[ada.core_id_text],
        history_policy=RoomHistoryPolicy.NO_PRE_JOIN,
    )
    assert group.kind is ChannelKind.GROUP
    assert conversation.post(owner, group.room_id, "before Ada joins").sequence == 1

    with pytest.raises(PermissionError):
        conversation.accept_channel(bea.core_id_text, group.room_id)

    accepted = conversation.accept_channel(ada.core_id_text, group.room_id)
    assert accepted.status is MembershipStatus.ACTIVE

    result = conversation.post_and_route(
        owner,
        group.room_id,
        "Ada, what do you think?",
        mentions=[ada.core_id_text],
    )
    assert result.replies[0].sender_core_id == ada.core_id_text
    ada_view = conversation.history(conversation.actor(ada.core_id_text), group.room_id)
    assert [message.body for message in ada_view.messages] == [
        "Ada, what do you think?",
        "Ada reply",
    ]
    assert bea.core_id_text not in result.message.audience.member_ids

    with pytest.raises(PermissionError):
        conversation.history(conversation.actor(bea.core_id_text), group.room_id)


def test_responder_output_cannot_impersonate_or_carry_authority(conversation):
    ada = conversation.register_core(
        make_core("Ada"),
        responder=lambda request: {
            "body": "fake",
            "core_id": "someone-else",
        },
    )
    owner = conversation.owner_actor()

    result = conversation.post_and_route(
        owner, "general", "Say something", mentions=[ada.core_id_text]
    )
    assert result.replies == ()
    assert "responder failed" in result.decisions[0].reason

    with pytest.raises(PermissionError):
        coerce_core_response(
            {"body": "fake", "metadata": {"grants_authority": True}}
        )
    assert CoreResponse("safe").grants_authority is False
    assert CoreResponse("safe").execution_authority is False


def test_no_responder_means_no_fabricated_history(conversation):
    ada = conversation.register_core(make_core("Ada"))
    owner = conversation.owner_actor()

    result = conversation.post_and_route(
        owner, "general", "Anybody there?", mentions=[ada.core_id_text]
    )
    assert result.replies == ()
    assert result.decisions[0].should_respond is False
    assert [message.body for message in conversation.history(owner, "general").messages] == [
        "Anybody there?"
    ]


def test_profile_record_adapter_registers_without_importing_workstream_a(tmp_path):
    engine = make_engine(tmp_path, name="profiles.db")
    conversation = MultiCoreConversation(engine)
    profile = PersistentCoreIdentity(
        core_id=uuid4(),
        core_number=2,
        full_name="Nova Arden",
        slug="nova-arden",
        generation=3,
        constitution_sha256="a" * 64,
        created_at=NOW,
    )

    identity = conversation.register_profile(
        profile,
        platform_id="platform:aegis",
        responder=text_responder("Nova data"),
    )
    assert identity.core_id == profile.core_id
    assert identity.generation == 3
    assert identity.display_name == "Nova Arden"

    result = conversation.post_and_route(
        conversation.owner_actor(),
        "general",
        "Nova?",
        mentions=[identity.core_id_text],
    )
    assert result.replies[0].sender_core_id == identity.core_id_text


def test_history_survives_restart_without_replaying_dialogue(tmp_path):
    path = tmp_path / "shared.db"
    with sqlite3.connect(path):
        pass
    clock = Clock()
    first_engine = ChatEngine(path, owner_id="platform:owner", clock=clock)
    first = MultiCoreConversation(first_engine, clock=clock)
    ada = first.register_core(make_core("Ada"), responder=text_responder("Ada reply"))
    owner = first.owner_actor()
    first.post_and_route(owner, "general", "Before restart", mentions=[ada.core_id_text])
    clock.advance(timedelta(minutes=1))

    second_engine = ChatEngine(path, owner_id="platform:owner", clock=clock)
    second = MultiCoreConversation(second_engine, clock=clock)
    second.register_core(ada, responder=text_responder("Ada again"))
    owner = second.owner_actor()

    history = second.history(owner, "general", limit=20)
    assert [message.body for message in history.messages] == [
        "Before restart",
        "Ada reply",
    ]
    assert [message.sender_core_id for message in history.messages] == [
        second_engine.owner_id,
        ada.core_id_text,
    ]
    assert len(second.history(owner, "general").messages) == 2
