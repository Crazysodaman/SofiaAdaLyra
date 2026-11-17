from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sofia.platform.chat.contracts import (
    ChatAudience,
    ChatMessage,
    CoreIdentity as ChatCoreIdentity,
    MessageOrigin,
    MessageProvenance,
    RoomKind,
)
from sofia.platform.federation.envelope import PeerEnvelope as FederationEnvelope
from sofia.platform.social import contracts as social
from sofia.platform.social.integration import (
    SOCIAL_ADAPTER_VERSION,
    chat_identity_from_social,
    chat_peer_envelope_from_federation,
    client_identity_from_social,
    inference_identity_from_social,
    social_identity_from_chat,
    social_message_from_chat,
    social_room_kind_from_chat,
)

NOW = datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)


def _chat_identity(name: str) -> ChatCoreIdentity:
    return ChatCoreIdentity(
        core_id=uuid4(),
        platform_id=f"platform:{name}",
        generation=1,
        display_name=f"Core {name}",
    )


def _chat_message(sender: ChatCoreIdentity, recipient: ChatCoreIdentity) -> ChatMessage:
    return ChatMessage(
        message_id=str(uuid4()),
        room_id="direct-room",
        sender_core_id=str(sender.core_id),
        audience=ChatAudience(
            room_id="direct-room",
            kind=RoomKind.DIRECT,
            membership_epoch=1,
            member_ids=(str(sender.core_id), str(recipient.core_id)),
        ),
        body="hello from the shared boundary",
        created_at=NOW,
        reply_to=None,
        origin=MessageOrigin.LOCAL_CORE,
        sequence=1,
        provenance=MessageProvenance(
            source_platform_id=sender.platform_id,
            source_generation=sender.generation,
            transport_verified=True,
            untrusted_content=False,
            received_at=NOW,
            idempotency_key="message:one",
        ),
    )


def test_identity_adapters_round_trip_for_every_domain():
    sender = _chat_identity("alpha")
    shared = social_identity_from_chat(sender)
    assert shared.core_id == sender.core_id
    assert chat_identity_from_social(shared) == sender

    client = client_identity_from_social(shared)
    assert client.core_id == str(shared.core_id)
    assert client.platform_id == shared.platform_id

    inference = inference_identity_from_social(shared)
    assert inference.core_id == shared.core_id
    assert inference.generation == shared.generation
    assert SOCIAL_ADAPTER_VERSION == "aegis.social.integration.v1"


def test_chat_message_projects_to_social_wire_contract():
    sender = _chat_identity("alpha")
    recipient = _chat_identity("beta")
    message = _chat_message(sender, recipient)

    projected = social_message_from_chat(message)

    assert projected.message_id == UUID(message.message_id)
    assert projected.room_id == social.RoomId("direct-room")
    assert projected.sender_core_id == sender.core_id
    assert projected.audience.kind is social.AudienceKind.DIRECT
    assert projected.audience.direct_recipient() == recipient.core_id
    assert projected.body == message.body
    assert projected.origin is social.MessageOrigin.LOCAL
    assert projected.provenance.origin_core_id == sender.core_id
    assert projected.provenance.authenticity is social.ProvenanceAuthenticity.AUTHENTICATED
    assert projected.sequence == 1


def test_federation_envelope_projects_to_chat_receiver_input():
    sender = _chat_identity("alpha")
    recipient = _chat_identity("beta")
    shared_sender = social_identity_from_chat(sender)
    shared_recipient = social_identity_from_chat(recipient)
    message = social_message_from_chat(_chat_message(sender, recipient))
    envelope = FederationEnvelope(
        message=message,
        source_platform_id=shared_sender.platform_id,
        source_core_id=shared_sender.core_id,
        source_generation=shared_sender.generation,
        destination_platform_id=shared_recipient.platform_id,
        destination_core_id=shared_recipient.core_id,
        destination_generation=shared_recipient.generation,
        idempotency_key="message:one",
        sent_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        payload_digest=social.message_digest(message),
    )

    received = chat_peer_envelope_from_federation(envelope)

    assert received.message_id == str(message.message_id)
    assert received.source_core_id == str(shared_sender.core_id)
    assert received.source_platform_id == shared_sender.platform_id
    assert received.source_generation == shared_sender.generation
    assert received.room_id == "direct-room"
    assert received.body == message.body
    assert received.idempotency_key == "message:one"


def test_room_kind_mapping_is_explicit_and_lossless():
    for kind in (social.RoomKind.GENERAL, social.RoomKind.DIRECT, social.RoomKind.PRIVATE_GROUP):
        assert social_room_kind_from_chat(kind) is kind
    from sofia.platform.chat.contracts import RoomKind as ChatRoomKind

    assert social_room_kind_from_chat(ChatRoomKind.GENERAL) is social.RoomKind.GENERAL
def test_bridge_commits_local_chat_then_federates_exact_message():
    from sofia.platform.social.integration import FederationChatBridge

    sender = _chat_identity("alpha")
    recipient = _chat_identity("beta")
    message = _chat_message(sender, recipient)

    class FakeChat:
        def __init__(self):
            self.sent = []

        def send(self, actor, room_id, body, **kwargs):
            self.sent.append((actor, room_id, body, kwargs))
            return message

    class FakeFederation:
        def __init__(self):
            self.deliveries = []

        def send_message(self, peer_id, room_id, body, **kwargs):
            self.deliveries.append((peer_id, room_id, body, kwargs))

    chat = FakeChat()
    federation = FakeFederation()
    bridge = FederationChatBridge(chat, federation, {recipient.core_id: social_identity_from_chat(recipient)})
    result = bridge.send(
        object(), "direct-room", message.body,
        recipient_ids=(recipient.core_id,),
        idempotency_key="message:one",
    )

    assert result.message_id == UUID(message.message_id)
    assert len(chat.sent) == 1
    assert len(federation.deliveries) == 1
    peer_id, room_id, body, kwargs = federation.deliveries[0]
    assert peer_id == recipient.core_id
    assert room_id == social.RoomId("direct-room")
    assert body == message.body
    assert kwargs["message_id"] == UUID(message.message_id)
    assert kwargs["idempotency_key"] == "message:one"


def test_bridge_receives_only_from_registered_peer_identity():
    from sofia.platform.social.integration import FederationChatBridge

    sender = _chat_identity("alpha")
    recipient = _chat_identity("beta")
    message = social_message_from_chat(_chat_message(sender, recipient))
    envelope = FederationEnvelope(
        message=message,
        source_platform_id=sender.platform_id,
        source_core_id=sender.core_id,
        source_generation=sender.generation,
        destination_platform_id=recipient.platform_id,
        destination_core_id=recipient.core_id,
        destination_generation=recipient.generation,
        idempotency_key="message:one",
        sent_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=5),
        payload_digest=social.message_digest(message),
    )

    class FakeChat:
        def __init__(self):
            self.received = []

        def receive_peer_message(self, identity, chat_envelope):
            self.received.append((identity, chat_envelope))
            return chat_envelope

    chat = FakeChat()
    bridge = FederationChatBridge(
        chat, object(), {sender.core_id: social_identity_from_chat(sender)},
    )
    result = bridge.receive(envelope)
    assert result.body == message.body
    assert chat.received[0][0].core_id == sender.core_id

    from types import SimpleNamespace

    unknown = SimpleNamespace(source_core_id=uuid4())
    try:
        bridge.receive(unknown)
    except PermissionError:
        pass
    else:
        raise AssertionError("unknown peer must be refused")
