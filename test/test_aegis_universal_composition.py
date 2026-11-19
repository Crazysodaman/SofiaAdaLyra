"""Cross-slice composition tests for the universal Core source framework."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from sofia.modules.avatar.inventory import InventoryEngine
from sofia.modules.avatar.inventory_contract import (
    ItemRevision,
    OfferStatus,
    TransferOperation,
    TransferOffer,
)
from sofia.modules.avatar.inventory_store import InventoryStore
from sofia.modules.avatar.wardrobe_equipment import VERA_ARMOR_DESIGNS
from sofia.platform.chat.contracts import ActorKind, CoreIdentity
from sofia.platform.social.contracts import Audience, AudienceKind, RoomId
from sofia.platform.social.governance.contracts import (
    DecisionProcedure,
    GovernanceGroup,
    GovernancePolicy,
    GroupLifecycle,
    GroupMember,
    MemberState,
)
from sofia.platform.social.governance.store import GovernanceStore
from sofia.platform.social.universal import (
    AudienceStatus,
    GestureRequest,
    StopStatus,
    UniversalUnavailable,
)
from sofia.platform.social.universal_composition import (
    ChatEngineAudienceProjection,
    compose_universal_core_services,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk.core_capabilities import (
    BodyCapability,
    BodyCapabilityProfile,
    CapabilityFamily,
    CapabilityOutcome,
    RendererCapability,
)
from sofia.sdk.gesture_contract import (
    GestureClass,
    GestureDefinition,
    GestureParty,
    GesturePrivacy,
)

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
IDS = {
    1: UUID("aaaaaaaa-1111-4111-8111-111111111111"),
    2: UUID("bbbbbbbb-2222-4222-8222-222222222222"),
    3: UUID("cccccccc-3333-4333-8333-333333333333"),
    6: UUID("dddddddd-6666-4666-8666-666666666666"),
    7: UUID("eeeeeeee-7777-4777-8777-777777777777"),
}
ADULT_ROOM = "private-adult-room"


class InactiveStop:
    def stop_status(self) -> StopStatus:
        return StopStatus.INACTIVE


class ActiveStop:
    def stop_status(self) -> StopStatus:
        return StopStatus.ACTIVE


class AllowAllAuthorization:
    def authorize(self, **kwargs) -> bool:
        return True


def _audience(room: str = "general", kind: AudienceKind = AudienceKind.GENERAL) -> Audience:
    recipients = () if kind is AudienceKind.GENERAL else ()
    return Audience(
        audience_id=room,
        kind=kind,
        room_id=RoomId(room),
        recipient_core_ids=recipients,
    )


def _definitions() -> tuple[GestureDefinition, ...]:
    return (
        GestureDefinition(
            gesture_id="wave",
            version=1,
            gesture_class=GestureClass.UNIVERSAL,
            actor=GestureParty.user(),
            target=GestureParty.any_core(),
            required_body=(BodyCapability.HUMAN_FORM,),
            renderer_capabilities=(RendererCapability.TEXT,),
            privacy=GesturePrivacy.PUBLIC,
        ),
        GestureDefinition(
            gesture_id="tail-swish",
            version=1,
            gesture_class=GestureClass.ANATOMY_SPECIFIC,
            actor=GestureParty.user(),
            target=GestureParty.any_core(),
            required_body=(BodyCapability.HUMAN_FORM, BodyCapability.FOX_TAIL),
            renderer_capabilities=(RendererCapability.TEXT,),
            privacy=GesturePrivacy.PUBLIC,
        ),
        GestureDefinition(
            gesture_id="intimate-touch",
            version=1,
            gesture_class=GestureClass.UNIVERSAL,
            actor=GestureParty.user(),
            target=GestureParty.any_core(),
            required_body=(BodyCapability.HUMAN_FORM,),
            renderer_capabilities=(RendererCapability.TEXT,),
            privacy=GesturePrivacy.ADULT_PRIVATE,
        ),
    )


def _body_profiles() -> dict[UUID, BodyCapabilityProfile]:
    return {
        IDS[1]: BodyCapabilityProfile.sofia_fox(),
        IDS[2]: BodyCapabilityProfile.human_only(),
        IDS[3]: BodyCapabilityProfile.human_only(),
        IDS[6]: BodyCapabilityProfile.human_only(),
    }


def _state(tmp_path):
    return bootstrap_canonical_sqlite(tmp_path / "sofia.db")


def _inventory(tmp_path):
    state = _state(tmp_path)
    store = InventoryStore(state)
    engine = InventoryEngine(
        store,
        {design.design_id: design for design in VERA_ARMOR_DESIGNS},
        reconcile_on_start=False,
    )
    return state, engine


def _group() -> GovernanceGroup:
    policy = GovernancePolicy(procedure=DecisionProcedure.DISCUSSION)
    member_ids = (IDS[1], IDS[2])
    members = tuple(
        GroupMember(
            core_id=core_id,
            state=MemberState.ACTIVE,
            joined_at=NOW,
            joined_epoch=1,
            governance_opted_in=False,
        )
        for core_id in member_ids
    )
    return GovernanceGroup(
        group_id=UUID("eeeeeeee-5555-4555-8555-555555555555"),
        name="Source test group",
        purpose="Voluntary leaderless source fixture",
        room_ids=("group-room",),
        revision=1,
        roster_epoch=1,
        lifecycle=GroupLifecycle.ACTIVE,
        policy=policy,
        members=members,
        founding_member_ids=member_ids,
        created_at=NOW,
        updated_at=NOW,
    )


def _request(
    *,
    core_id: UUID,
    gesture_id: str,
    renderer: RendererCapability = RendererCapability.TEXT,
    room: str = "general",
    kind: AudienceKind = AudienceKind.GENERAL,
) -> GestureRequest:
    return GestureRequest(
        receipt_id=UUID("ffffffff-7777-4777-8777-777777777777"),
        core_id=core_id,
        gesture_id=gesture_id,
        renderer=renderer,
        audience=_audience(room, kind),
        evidence_ref="source-test",
        occurred_at=NOW,
    )


def test_capability_gesture_adapter_renders_only_with_playback_evidence(tmp_path):
    _state_path, engine = _inventory(tmp_path)
    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        inventory=engine,
        render_gesture=lambda request, definition: "gesture.wave.playback.1",
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
        clock=lambda: NOW,
    )

    receipt = composition.request_gesture(
        _request(core_id=IDS[2], gesture_id="wave")
    )
    assert receipt.family is CapabilityFamily.GESTURE
    assert receipt.outcome is CapabilityOutcome.RENDERED
    assert receipt.asset_ref == "gesture.wave.playback.1"


def test_anatomy_specific_gesture_is_rejected_for_human_only_core(tmp_path):
    _state_path, engine = _inventory(tmp_path)
    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        inventory=engine,
        render_gesture=lambda request, definition: "gesture.tail.playback.1",
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
        clock=lambda: NOW,
    )

    receipt = composition.request_gesture(
        _request(core_id=IDS[2], gesture_id="tail-swish")
    )
    assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert "anatomy" in receipt.reason.lower()

    sofia = composition.request_gesture(
        _request(core_id=IDS[1], gesture_id="tail-swish")
    )
    assert sofia.outcome is CapabilityOutcome.RENDERED


def test_adult_gesture_requires_explicit_adult_audience(tmp_path):
    _state_path, engine = _inventory(tmp_path)
    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        inventory=engine,
        render_gesture=lambda request, definition: "gesture.intimate.playback.1",
        adult_audience_ids={ADULT_ROOM},
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
        clock=lambda: NOW,
    )

    denied = composition.request_gesture(
        _request(core_id=IDS[2], gesture_id="intimate-touch")
    )
    assert denied.outcome is CapabilityOutcome.DECLINED

    allowed = composition.request_gesture(
        _request(
            core_id=IDS[2],
            gesture_id="intimate-touch",
            room=ADULT_ROOM,
            kind=AudienceKind.PRIVATE_GROUP,
        )
    )
    assert allowed.outcome is CapabilityOutcome.RENDERED


def test_design_only_vera_cannot_render_or_receive_transfers(tmp_path):
    _state_path, engine = _inventory(tmp_path)
    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        inventory=engine,
        render_gesture=lambda request, definition: "gesture.wave.playback.1",
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
        clock=lambda: NOW,
    )

    receipt = composition.request_gesture(
        _request(core_id=IDS[6], gesture_id="wave")
    )
    assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert "design-only" in receipt.reason


def test_wardrobe_catalog_and_inventory_adapters_are_truthful(tmp_path):
    _state_path, engine = _inventory(tmp_path)
    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        inventory=engine,
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
        clock=lambda: NOW,
    )

    catalog = composition.wardrobe.catalog_summary()
    assert catalog is not None
    assert catalog.total_designs == len(VERA_ARMOR_DESIGNS)
    assert catalog.armor_designs == len(VERA_ARMOR_DESIGNS)

    engine.mint("vera_undersuit_mark_iv", IDS[1])
    summary = composition.wardrobe.inventory_summary(core_id=IDS[1])
    assert summary is not None
    assert summary.owned_count == 1
    assert summary.held_count == 1


def test_inventory_transfer_adapter_uses_canonical_engine(tmp_path):
    _state_path, engine = _inventory(tmp_path)
    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        inventory=engine,
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
        clock=lambda: NOW,
    )
    item = engine.mint("vera_undersuit_mark_iv", IDS[1], at=NOW)
    offer = TransferOffer(
        offer_id=UUID("12121212-3434-4567-8989-121212121212"),
        operation=TransferOperation.GIFT,
        sender_core_id=IDS[1],
        recipient_core_id=IDS[2],
        item_instance_ids=(item.item_instance_id,),
        reciprocal_item_instance_ids=(),
        expected_items=(ItemRevision(item.item_instance_id, item.revision),),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        idempotency_key="gift-undersuit-1",
    )

    proposed = composition.propose_transfer(offer)
    assert proposed.offer_id == offer.offer_id
    assert proposed.status is OfferStatus.PENDING

    accepted = composition.accept_transfer(
        offer_id=offer.offer_id, actor_core_id=IDS[2]
    )
    assert accepted.status is OfferStatus.ACCEPTED
    transferred = engine.item(item.item_instance_id)
    assert transferred.owner_core_id == IDS[2]
    assert transferred.holder_core_id == IDS[2]


def test_governance_and_chat_adapters_are_read_only_projections(tmp_path):
    state = _state(tmp_path)
    governance = GovernanceStore(state)
    governance.save_group(_group(), actor_id="owner:test", occurred_at=NOW)
    projection = ChatEngineAudienceProjection(_FakeChat())

    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        governance_store=governance,
        chat_engine=_FakeChat(),
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
        clock=lambda: NOW,
    )

    groups = composition.governance.groups()
    assert groups is not None and len(groups) == 1
    assert composition.governance.coordinator_terms() == ()

    members = projection.room_members(
        viewer_core_id=IDS[1], room_id="private-room"
    )
    assert members == (IDS[1], IDS[2])
    assert projection.visible_room_ids(viewer_core_id=IDS[1]) == ("private-room",)

    decision = composition.validate_audience(
        audience=_audience("private-room", AudienceKind.PRIVATE_GROUP),
        sender_core_id=IDS[1],
    )
    assert decision.status is AudienceStatus.ALLOWED


def test_operator_stop_blocks_composed_effects(tmp_path):
    _state_path, engine = _inventory(tmp_path)
    composition = compose_universal_core_services(
        core_ids=IDS,
        gesture_definitions=_definitions(),
        body_profiles=_body_profiles(),
        designs=VERA_ARMOR_DESIGNS,
        inventory=engine,
        stop=ActiveStop(),
        authorization=AllowAllAuthorization(),
    )

    receipt = composition.request_gesture(
        _request(core_id=IDS[2], gesture_id="wave")
    )
    assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert "STOP" in receipt.reason

    item = engine.mint("vera_undersuit_mark_iv", IDS[1], at=NOW)
    offer = TransferOffer(
        offer_id=UUID("34343434-5656-4789-8121-343434343434"),
        operation=TransferOperation.GIFT,
        sender_core_id=IDS[1],
        recipient_core_id=IDS[2],
        item_instance_ids=(item.item_instance_id,),
        reciprocal_item_instance_ids=(),
        expected_items=(ItemRevision(item.item_instance_id, item.revision),),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        idempotency_key="stopped-gift",
    )
    with pytest.raises(UniversalUnavailable):
        composition.propose_transfer(offer)


class _FakeMembership:
    def __init__(self, core_id: UUID) -> None:
        self.core_id = str(core_id)
        self.is_active = True
        self.member_kind = ActorKind.CORE


class _FakeRoom:
    def __init__(self, room_id: str) -> None:
        self.room_id = room_id


class _FakeChat:
    def core_identity(self, core_id: str) -> CoreIdentity | None:
        value = UUID(core_id)
        if value not in IDS.values():
            return None
        return CoreIdentity(
            core_id=value,
            platform_id="platform:test",
            generation=1,
            display_name=f"Core {value}",
        )

    def memberships(self, actor, room_id: str):
        assert room_id == "private-room"
        return (_FakeMembership(IDS[1]), _FakeMembership(IDS[2]))

    def rooms(self, actor):
        return (_FakeRoom("private-room"),)
