from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.platform.chat import (
    ChatActor,
    CoreIdentity,
    MessageOrigin,
    PEER_ENVELOPE_SCHEMA,
    PeerEnvelope,
    RoomKind,
    RoomMembership,
    MembershipStatus,
)


T0 = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def identity(name="Ada", generation=1, platform="platform:a"):
    return CoreIdentity(uuid4(), platform, generation, name)


def test_core_identity_is_typed_and_immutable():
    value = identity()
    assert value.core_id_text == str(value.core_id)
    assert ChatActor.core(value).actor_id == value.core_id_text
    assert ChatActor.owner("platform:owner").kind.value == "owner"
    with pytest.raises(FrozenInstanceError):
        value.display_name = "other"  # type: ignore[misc]
    with pytest.raises(ValueError):
        CoreIdentity(value.core_id, "", 1, "Ada")
    with pytest.raises(ValueError):
        CoreIdentity(value.core_id, "platform:a", 0, "Ada")
    with pytest.raises(TypeError):
        CoreIdentity(str(value.core_id), "platform:a", 1, "Ada")  # type: ignore[arg-type]


def test_room_kinds_are_stable_contract_values():
    assert {kind.value for kind in RoomKind} == {
        "general",
        "direct",
        "private_group",
    }


def test_membership_requires_bounded_active_history_floor():
    with pytest.raises(ValueError):
        RoomMembership(
            room_id="r",
            core_id="c",
            epoch=1,
            status=MembershipStatus.ACTIVE,
            joined_at=T0,
            history_from_sequence=None,
        )
    with pytest.raises(ValueError):
        RoomMembership(
            room_id="r",
            core_id="c",
            epoch=1,
            status=MembershipStatus.ACTIVE,
            joined_at=None,
            history_from_sequence=1,
        )


def test_peer_envelope_rejects_unexpected_authority_fields():
    payload = {
        "schema": PEER_ENVELOPE_SCHEMA,
        "message_id": "m1",
        "source_core_id": str(uuid4()),
        "source_platform_id": "platform:b",
        "source_generation": 1,
        "room_id": "general",
        "body": "hello",
        "created_at": T0.isoformat(),
    }
    envelope = PeerEnvelope.from_payload(payload)
    assert envelope.message_id == "m1"
    with pytest.raises(ValueError):
        PeerEnvelope.from_payload({**payload, "audience": ["someone-else"]})
    with pytest.raises(ValueError):
        PeerEnvelope.from_payload({**payload, "schema": "other"})


def test_message_origin_values_are_inert():
    assert {origin.value for origin in MessageOrigin} == {
        "owner",
        "local_core",
        "peer_core",
    }
