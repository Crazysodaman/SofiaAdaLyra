"""Cross-workstream composition: canonical profiles through real chat routing."""
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from sofia.core.multicore.conversation import MultiCoreConversation
from sofia.core.multicore.profiles import mack_core_profile, nova_core_profile
from sofia.platform.chat import ChatEngine, MembershipStatus

NOW = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


def _engine(tmp_path):
    path = tmp_path / "multicore.db"
    with sqlite3.connect(path):
        pass
    return ChatEngine(
        path, owner_id="platform:owner", platform_id="platform:artemis",
        clock=lambda: NOW,
    )


def _responder(text):
    def respond(_request):
        return text

    return respond


def test_mack_and_nova_register_as_distinct_real_profiles(tmp_path):
    engine = _engine(tmp_path)
    conversation = MultiCoreConversation(engine)
    mack = mack_core_profile(uuid4())
    nova = nova_core_profile(uuid4())

    mack_identity = conversation.register_profile(
        mack, platform_id="platform:artemis", generation=1, responder=_responder("Mack reply"),
    )
    nova_identity = conversation.register_profile(
        nova, platform_id="platform:artemis", generation=1, responder=_responder("Nova reply"),
    )

    assert mack_identity.core_id != nova_identity.core_id
    assert mack_identity.display_name == "Mack Fuller"
    assert nova_identity.display_name == "Nova Arden"
    assert conversation.engine.core_identity(
        mack_identity.core_id_text
    ).platform_id == "platform:artemis"
    assert conversation.engine.membership(
        conversation.owner_actor(), "general", mack_identity.core_id_text,
    ).status is MembershipStatus.ACTIVE


def test_general_chat_routes_only_mentioned_core_and_keeps_authors_distinct(tmp_path):
    engine = _engine(tmp_path)
    conversation = MultiCoreConversation(engine)
    mack = conversation.register_profile(
        mack_core_profile(uuid4()), platform_id="platform:artemis", generation=1,
        responder=_responder("Mack data"),
    )
    nova = conversation.register_profile(
        nova_core_profile(uuid4()), platform_id="platform:artemis", generation=1,
        responder=_responder("Nova data"),
    )

    result = conversation.post_and_route(
        conversation.owner_actor(), "general",
        "Mack, what do you think?", mentions=[mack.core_id_text],
    )

    assert result.responded_core_ids == (mack.core_id_text,)
    assert result.replies[0].body == "Mack data"
    assert conversation.author(result.replies[0]).display_name == "Mack Fuller"
    decision = {item.core_id: item for item in result.decisions}
    assert decision[nova.core_id_text].should_respond is False


def test_owner_direct_to_nova_is_not_visible_to_mack(tmp_path):
    engine = _engine(tmp_path)
    conversation = MultiCoreConversation(engine)
    mack = conversation.register_profile(
        mack_core_profile(uuid4()), platform_id="platform:artemis", generation=1,
    )
    nova = conversation.register_profile(
        nova_core_profile(uuid4()), platform_id="platform:artemis", generation=1,
    )
    direct = conversation.open_owner_direct(nova.core_id_text)

    conversation.post(conversation.owner_actor(), direct.room_id, "Private to Nova")

    try:
        conversation.history(
            conversation.actor(mack.core_id_text), direct.room_id,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Mack must not read Nova's owner-direct history")
