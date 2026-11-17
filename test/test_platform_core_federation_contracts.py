"""AEGIS social contract v1 immutable validation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.social.contracts import (
    SOCIAL_CONTRACT_VERSION,
    Audience,
    AudienceKind,
    ChatMessage,
    CoreIdentity,
    InferenceRequest,
    InferenceWorkload,
    MembershipStatus,
    MessageOrigin,
    Provenance,
    ProvenanceAuthenticity,
    ResourceReservationRef,
    RoomId,
    RoomKind,
    RoomMembership,
    canonical_json,
    message_digest,
    payload_digest,
)


NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
CORE_A = uuid4()
CORE_B = uuid4()


def core_identity(**changes) -> CoreIdentity:
    payload = dict(
        core_id=CORE_A,
        platform_id="platform:venus",
        generation=3,
        display_name="Sofía Ada Lyra",
    )
    payload.update(changes)
    return CoreIdentity(**payload)


def provenance(**changes) -> Provenance:
    payload = dict(
        origin_platform_id="platform:venus",
        origin_core_id=CORE_A,
        envelope_digest="a" * 64,
        authenticity=ProvenanceAuthenticity.AUTHENTICATED,
    )
    payload.update(changes)
    return Provenance(**payload)


def message(**changes) -> ChatMessage:
    room = RoomId("room:direct:a-b")
    payload = dict(
        message_id=uuid4(),
        room_id=room,
        sender_core_id=CORE_A,
        audience=Audience(
            audience_id="audience:direct:a-b",
            kind=AudienceKind.DIRECT,
            room_id=room,
            recipient_core_ids=(CORE_B,),
        ),
        body="A bounded public finding.",
        created_at=NOW,
        reply_to=None,
        origin=MessageOrigin.LOCAL,
        sequence=1,
        provenance=provenance(),
    )
    payload.update(changes)
    return ChatMessage(**payload)


def test_contract_version_and_core_identity_round_trip():
    assert SOCIAL_CONTRACT_VERSION == "aegis.social.contract.v1"
    identity = core_identity()
    assert CoreIdentity.from_payload(identity.to_payload()) == identity
    assert identity.to_payload()["schema"] == "aegis.social.core_identity.v1"


@pytest.mark.parametrize(
    "changes",
    [
        {"generation": 0},
        {"generation": True},
        {"platform_id": ""},
        {"display_name": "   "},
        {"display_name": "bad\nname"},
        {"core_id": 0},
    ],
)
def test_core_identity_rejects_invalid_identity(changes):
    with pytest.raises((ValueError, TypeError)):
        core_identity(**changes)


def test_core_identity_strictly_rejects_unknown_or_missing_fields():
    payload = core_identity().to_payload()
    payload["authority"] = "root"
    with pytest.raises(ValueError):
        CoreIdentity.from_payload(payload)
    payload = core_identity().to_payload()
    del payload["generation"]
    with pytest.raises(ValueError):
        CoreIdentity.from_payload(payload)


def test_audience_direct_requires_exact_recipient_and_group_has_no_list():
    room = RoomId("room:direct:a-b")
    direct = Audience(
        audience_id="audience:direct", kind=AudienceKind.DIRECT, room_id=room,
        recipient_core_ids=(CORE_B,),
    )
    assert direct.direct_recipient() == CORE_B
    with pytest.raises(ValueError):
        Audience(
            audience_id="audience:direct", kind=AudienceKind.DIRECT, room_id=room,
            recipient_core_ids=(),
        )
    with pytest.raises(ValueError):
        Audience(
            audience_id="audience:direct", kind=AudienceKind.DIRECT, room_id=room,
            recipient_core_ids=(CORE_A, CORE_B),
        )
    with pytest.raises(ValueError):
        Audience(
            audience_id="audience:group", kind=AudienceKind.PRIVATE_GROUP, room_id=room,
            recipient_core_ids=(CORE_B,),
        )


def test_chat_message_round_trip_and_has_no_authority_field():
    original = message()
    decoded = ChatMessage.from_payload(original.to_payload())
    assert decoded == original
    assert not hasattr(decoded, "capability")
    assert not hasattr(decoded, "grant")
    assert not hasattr(decoded, "instruction_authority")
    assert decoded.body == "A bounded public finding."


def test_chat_message_rejects_audience_room_mismatch_and_self_reply():
    with pytest.raises(ValueError):
        message(
            audience=Audience(
                audience_id="audience:other", kind=AudienceKind.DIRECT,
                room_id=RoomId("room:other"), recipient_core_ids=(CORE_B,),
            ),
        )
    identifier = uuid4()
    with pytest.raises(ValueError):
        message(message_id=identifier, reply_to=identifier)


def test_chat_message_rejects_non_aware_time_oversize_and_bad_sequence():
    with pytest.raises(ValueError):
        message(created_at=datetime(2026, 11, 17, 12, 0))
    with pytest.raises(ValueError):
        message(body="")
    with pytest.raises(ValueError):
        message(body="x" * (256 * 1024 + 1))
    with pytest.raises(ValueError):
        message(sequence=0)


def test_chat_message_payload_is_strict():
    payload = message().to_payload()
    payload["body"] = "changed"
    payload["privilege"] = "admin"
    with pytest.raises(ValueError):
        ChatMessage.from_payload(payload)
    payload = message().to_payload()
    del payload["provenance"]
    with pytest.raises(ValueError):
        ChatMessage.from_payload(payload)


def test_message_digest_is_canonical_and_ignores_self_reference():
    first = message(provenance=provenance(envelope_digest="a" * 64))
    second = message(
        message_id=first.message_id,
        provenance=provenance(envelope_digest="b" * 64),
    )
    assert message_digest(first) == message_digest(second)
    payload = first.to_payload()
    reordered = dict(reversed(list(payload.items())))
    assert canonical_json(payload) == canonical_json(reordered)
    assert payload_digest(payload) == payload_digest(reordered)


def test_provenance_requires_exact_digest_and_typed_authenticity():
    with pytest.raises(ValueError):
        provenance(envelope_digest="short")
    with pytest.raises(TypeError):
        provenance(authenticity="authenticated")
    with pytest.raises(ValueError):
        provenance(received_at=datetime(2026, 11, 17, 12, 0))


def test_room_membership_epoch_status_and_history_boundary_round_trip():
    membership = RoomMembership(
        room_id=RoomId("room:general:engineering"),
        core_id=CORE_A,
        epoch=4,
        status=MembershipStatus.ACTIVE,
        joined_at=NOW,
        history_from_sequence=7,
    )
    assert RoomMembership.from_payload(membership.to_payload()) == membership
    with pytest.raises(ValueError):
        RoomMembership(
            room_id=membership.room_id, core_id=CORE_A, epoch=0,
            status=MembershipStatus.ACTIVE, joined_at=NOW, history_from_sequence=0,
        )
    with pytest.raises(ValueError):
        RoomMembership(
            room_id=membership.room_id, core_id=CORE_A, epoch=1,
            status=MembershipStatus.ACTIVE, joined_at=NOW, history_from_sequence=-1,
        )


def test_room_kind_values_remain_stable():
    assert {kind.value for kind in RoomKind} == {"general", "direct", "private_group"}


def test_inference_workload_and_request_bind_reservation_identity():
    workload_id = uuid4()
    reservation = ResourceReservationRef(
        reservation_id="reservation:gpu-7",
        node_id="node:artemis",
        workload_id=workload_id,
        expires_at=NOW + timedelta(minutes=5),
    )
    workload = InferenceWorkload(
        workload_id=workload_id,
        model_id="model:qwen3-30b",
        model_digest="1" * 64,
        input_digest="2" * 64,
        requester_core_id=CORE_A,
        purpose="bounded engineering review",
        max_output_tokens=2048,
        created_at=NOW,
        resource_reservation=reservation,
    )
    request = InferenceRequest(
        request_id=uuid4(),
        workload=workload,
        idempotency_key="inference:request:1",
        expires_at=NOW + timedelta(minutes=10),
    )
    assert InferenceWorkload.from_payload(workload.to_payload()) == workload
    assert InferenceRequest.from_payload(request.to_payload()) == request
    with pytest.raises(ValueError):
        InferenceRequest(
            request_id=uuid4(), workload=workload,
            idempotency_key="inference:request:2", expires_at=NOW,
        )
    with pytest.raises(ValueError):
        InferenceWorkload(
            workload_id=workload_id,
            model_id="model:qwen3-30b",
            model_digest="1" * 64,
            input_digest="2" * 64,
            requester_core_id=CORE_A,
            purpose="mismatched reservation",
            max_output_tokens=2048,
            created_at=NOW,
            resource_reservation=ResourceReservationRef(
                reservation_id="reservation:gpu-7",
                node_id="node:artemis",
                workload_id=uuid4(),
                expires_at=NOW + timedelta(minutes=5),
            ),
        )


def test_group_audience_requires_matching_room_and_no_recipient_escalation():
    room = RoomId("room:general:engineering")
    audience = Audience(
        audience_id="audience:engineering",
        kind=AudienceKind.GENERAL,
        room_id=room,
    )
    payload = audience.to_payload()
    payload["recipient_core_ids"] = [str(CORE_B)]
    with pytest.raises(ValueError):
        Audience.from_payload(payload)
