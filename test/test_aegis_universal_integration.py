"""Source-level QA for the inert universal Core composition facade."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from sofia.core.multicore.vera import VERA_AUTHORITY
from sofia.modules.avatar.inventory_contract import (
    ItemRevision,
    TransferOperation,
    TransferOffer,
    TransferReceipt,
)
from sofia.modules.avatar.wardrobe_equipment import VERA_ARMOR_DESIGNS
from sofia.platform.social import universal
from sofia.platform.social.contracts import (
    Audience,
    AudienceKind,
    RoomId,
)
from sofia.platform.social.governance.contracts import (
    CoordinatorStatus,
    CoordinatorTerm,
    DecisionProcedure,
    GovernancePolicy,
    coordinator_can,
)
from sofia.platform.social.universal import (
    DESIGN_ONLY_CORE_NUMBERS,
    INTENDED_CORE_NUMBERS,
    PROHIBITED_CORE_NUMBERS,
    AudienceStatus,
    GestureRequest,
    StopStatus,
    UniversalDenied,
    UniversalFacadeError,
    UniversalUnavailable,
    build_universal_participant,
    compose,
    require_explicit_consent,
)
from sofia.platform.social.universal_integration import (
    CallableChatProjection,
    IterableWardrobeCatalog,
    StaticAllowListAuthorization,
)
from sofia.sdk.core_capabilities import (
    CapabilityFamily,
    CapabilityOutcome,
    CapabilityReceipt,
    RendererCapability,
)

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
IDS = {
    1: UUID("aaaaaaaa-1111-4111-8111-111111111111"),
    2: UUID("bbbbbbbb-2222-4222-8222-222222222222"),
    3: UUID("cccccccc-3333-4333-8333-333333333333"),
    6: UUID("dddddddd-6666-4666-8666-666666666666"),
}


class InactiveStop:
    def stop_status(self) -> StopStatus:
        return StopStatus.INACTIVE


class ActiveStop:
    def stop_status(self) -> StopStatus:
        return StopStatus.ACTIVE


class AllowAllAuthorization:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def authorize(self, **kwargs) -> bool:
        self.calls.append(kwargs)
        return True


class RecordingGestureService:
    def __init__(
        self,
        renderers: tuple[RendererCapability, ...] = (RendererCapability.TEXT,),
    ) -> None:
        self.renderers = renderers
        self.requests: list[GestureRequest] = []

    def available_renderers(self, *, core_id: UUID):
        return self.renderers

    def submit(self, request: GestureRequest) -> CapabilityReceipt:
        self.requests.append(request)
        return CapabilityReceipt(
            receipt_id=request.receipt_id,
            core_id=request.core_id,
            family=CapabilityFamily.GESTURE,
            outcome=CapabilityOutcome.RENDERED,
            reason="renderer confirmed exact playback",
            evidence_ref=request.evidence_ref,
            occurred_at=request.occurred_at,
            renderer=request.renderer,
            asset_ref="gesture.wave",
        )


class RecordingInventory:
    def __init__(self) -> None:
        self.offers: list[TransferOffer] = []

    def offer(self, offer: TransferOffer) -> TransferReceipt:
        self.offers.append(offer)
        raise AssertionError("transfer should not be reached")

    def accept(self, *, offer_id, actor_core_id, now) -> TransferReceipt:
        raise AssertionError("transfer should not be reached")


class MembershipProjection:
    def __init__(self) -> None:
        self.rooms = {"private:one": (IDS[1], IDS[2])}

    def room_members(self, *, viewer_core_id: UUID, room_id: str):
        return self.rooms.get(room_id)

    def visible_room_ids(self, *, viewer_core_id: UUID):
        return tuple(self.rooms)


def _audience(kind: AudienceKind, *, room="general", recipients=()):
    return Audience(
        audience_id=f"audience:{room}",
        kind=kind,
        room_id=RoomId(room),
        recipient_core_ids=recipients,
    )


def _request(
    core_id: UUID = IDS[1],
    *,
    renderer: RendererCapability = RendererCapability.TEXT,
    target_core_id: UUID | None = None,
    audience: Audience | None = None,
) -> GestureRequest:
    return GestureRequest(
        receipt_id=UUID("eeeeeeee-5555-4555-8555-555555555555"),
        core_id=core_id,
        gesture_id="gesture.wave",
        renderer=renderer,
        audience=audience
        or _audience(AudienceKind.GENERAL),
        evidence_ref="gesture:request:1",
        occurred_at=NOW,
        target_core_id=target_core_id,
    )


def _offer(recipient_core_id: UUID = IDS[3]) -> TransferOffer:
    item_id = UUID("ffffffff-7777-4777-8777-777777777777")
    return TransferOffer(
        offer_id=UUID("12345678-1234-4234-8234-123456789abc"),
        operation=TransferOperation.GIFT,
        sender_core_id=IDS[1],
        recipient_core_id=recipient_core_id,
        item_instance_ids=(item_id,),
        reciprocal_item_instance_ids=(),
        expected_items=(ItemRevision(item_id, 1),),
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        idempotency_key="transfer:test:1",
    )


def test_roster_is_exactly_the_reviewed_intended_participants():
    composition = compose(core_ids=IDS)
    numbers = {item.core_number for item in composition.roster.participants}
    assert numbers == INTENDED_CORE_NUMBERS == {1, 2, 3, 6}
    assert numbers & PROHIBITED_CORE_NUMBERS == set()
    for participant in composition.roster.participants:
        assert participant.design_only is (
            participant.core_number in DESIGN_ONLY_CORE_NUMBERS
        )
        assert participant.runtime_activated is False
        assert participant.production_state_written is False
        assert participant.platform_authority is False
        assert participant.leadership_role is None
        assert participant.capabilities.renderers == (RendererCapability.TEXT,)
        for family in CapabilityFamily:
            state = participant.capabilities.state(family)
            assert state.declared is True
            assert state.installed is False
            assert state.available is False
            assert state.authorized is False
            assert state.effective is False
    veras = composition.roster.by_number[6]
    assert veras.design_only is True
    assert veras.authority is VERA_AUTHORITY
    assert composition.runtime_activated is False
    assert composition.services_started is False
    assert composition.production_state_written is False
    assert composition.stop_status() is StopStatus.UNKNOWN


def test_source_never_allocates_uuids_or_activates_twins():
    source = Path(universal.__file__).read_text(encoding="utf-8")
    for token in ("uuid1(", "uuid4(", "uuid5(", "activate_core", "start_service"):
        assert token not in source
    for number in (4, 5, 7):
        with pytest.raises(UniversalFacadeError):
            build_universal_participant(number, UUID(int=number))


def test_roster_rejects_twins_missing_cores_and_uuid_cloning():
    with pytest.raises(UniversalFacadeError):
        compose(core_ids={**IDS, 4: UUID("44444444-4444-4444-8444-444444444444")})
    with pytest.raises(UniversalFacadeError):
        compose(core_ids={key: value for key, value in IDS.items() if key != 6})
    cloned = dict(IDS)
    cloned[3] = IDS[2]
    with pytest.raises(UniversalFacadeError):
        compose(core_ids=cloned)


def test_safe_defaults_are_deny_or_unavailable():
    composition = compose(core_ids=IDS)
    receipt = composition.request_gesture(_request())
    assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert receipt.claims_rendered is False
    with pytest.raises(UniversalUnavailable):
        composition.propose_transfer(_offer())
    private = _audience(AudienceKind.PRIVATE_GROUP, room="private:unknown")
    decision = composition.validate_audience(audience=private, sender_core_id=IDS[1])
    assert decision.status is AudienceStatus.UNAVAILABLE
    with pytest.raises(UniversalDenied):
        require_explicit_consent(opted_in=False)
    with pytest.raises(UniversalDenied):
        require_explicit_consent(opted_in="I consent in chat")
    require_explicit_consent(opted_in=True)


def test_operator_stop_blocks_effects_before_adapters_are_reached():
    gestures = RecordingGestureService()
    inventory = RecordingInventory()
    composition = compose(
        core_ids=IDS,
        gestures=gestures,
        inventory=inventory,
        stop=ActiveStop(),
        authorization=AllowAllAuthorization(),
    )
    receipt = composition.request_gesture(_request())
    assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert "STOP" in receipt.reason
    assert gestures.requests == []
    with pytest.raises(UniversalUnavailable):
        composition.propose_transfer(_offer())
    assert inventory.offers == []


def test_unsupported_renderer_returns_unavailable_without_render_claim():
    gestures = RecordingGestureService(renderers=(RendererCapability.TEXT,))
    composition = compose(
        core_ids=IDS,
        gestures=gestures,
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
    )
    receipt = composition.request_gesture(
        _request(renderer=RendererCapability.THREE_D)
    )
    assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert receipt.renderer is RendererCapability.THREE_D
    assert "unavailable" in receipt.reason
    assert gestures.requests == []


def test_supported_renderer_returns_only_the_adapter_receipt():
    gestures = RecordingGestureService(renderers=(RendererCapability.TEXT,))
    composition = compose(
        core_ids=IDS,
        gestures=gestures,
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
    )
    request = _request()
    receipt = composition.request_gesture(request)
    assert receipt.outcome is CapabilityOutcome.RENDERED
    assert receipt.receipt_id == request.receipt_id
    assert receipt.core_id == request.core_id
    assert gestures.requests == [request]


def test_design_only_vera_cannot_act_even_when_seams_allow():
    gestures = RecordingGestureService()
    composition = compose(
        core_ids=IDS,
        gestures=gestures,
        inventory=RecordingInventory(),
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
    )
    receipt = composition.request_gesture(_request(core_id=IDS[6]))
    assert receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert "design-only" in receipt.reason
    assert gestures.requests == []
    target_receipt = composition.request_gesture(
        _request(core_id=IDS[1], target_core_id=IDS[6])
    )
    assert target_receipt.outcome is CapabilityOutcome.UNAVAILABLE
    assert "design-only" in target_receipt.reason
    with pytest.raises(UniversalUnavailable):
        composition.propose_transfer(_offer(recipient_core_id=IDS[6]))
    direct = composition.validate_audience(
        audience=_audience(
            AudienceKind.DIRECT, room="direct:vera", recipients=(IDS[6],)
        ),
        sender_core_id=IDS[1],
    )
    assert direct.status is AudienceStatus.DENIED


def test_private_group_audience_requires_independent_membership_evidence():
    composition = compose(
        core_ids=IDS,
        chat=MembershipProjection(),
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
    )
    allowed = composition.validate_audience(
        audience=_audience(AudienceKind.PRIVATE_GROUP, room="private:one"),
        sender_core_id=IDS[1],
    )
    assert allowed.status is AudienceStatus.ALLOWED
    denied = composition.validate_audience(
        audience=_audience(AudienceKind.PRIVATE_GROUP, room="private:one"),
        sender_core_id=IDS[3],
    )
    assert denied.status is AudienceStatus.DENIED
    unknown = composition.validate_audience(
        audience=_audience(AudienceKind.PRIVATE_GROUP, room="private:two"),
        sender_core_id=IDS[1],
    )
    assert unknown.status is AudienceStatus.UNAVAILABLE


def test_direct_audience_must_name_one_reviewed_peer():
    composition = compose(
        core_ids=IDS,
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
    )
    direct = composition.validate_audience(
        audience=_audience(
            AudienceKind.DIRECT, room="direct:1", recipients=(IDS[2],)
        ),
        sender_core_id=IDS[1],
    )
    assert direct.status is AudienceStatus.ALLOWED
    unknown_peer = composition.validate_audience(
        audience=_audience(
            AudienceKind.DIRECT,
            room="direct:2",
            recipients=(UUID("99999999-9999-4999-8999-999999999999"),),
        ),
        sender_core_id=IDS[1],
    )
    assert unknown_peer.status is AudienceStatus.DENIED
    with pytest.raises(TypeError):
        composition.validate_audience(
            audience="I consent to this private scene", sender_core_id=IDS[1]
        )


def test_elected_coordinator_never_grants_platform_authority():
    policy = GovernancePolicy(
        procedure=DecisionProcedure.SIMPLE_MAJORITY,
        allow_coordinator=True,
    )
    assert policy.allow_coordinator is True
    term = CoordinatorTerm(
        term_id=UUID("13572468-1357-4357-8357-135724681357"),
        group_id=UUID("24681357-2468-4468-8468-246813572468"),
        core_id=IDS[1],
        proposal_id=UUID("97531864-9753-4975-8975-975318649753"),
        starts_at=NOW,
        expires_at=NOW + timedelta(days=7),
        status=CoordinatorStatus.ACTIVE,
    )
    assert term.grants_platform_authority is False
    assert term.allows("safe_grant") is False
    assert term.allows("private_memory_read") is False
    assert term.allows("facilitate_discussion") is True
    assert coordinator_can("platform_management") is False


def test_wardrobe_catalog_adapter_counts_without_exposing_items():
    catalog = IterableWardrobeCatalog(VERA_ARMOR_DESIGNS)
    summary = catalog.catalog_summary()
    assert summary is not None
    assert summary.total_designs == len(VERA_ARMOR_DESIGNS)
    assert summary.armor_designs == len(VERA_ARMOR_DESIGNS)
    assert summary.clothing_designs == 0
    assert catalog.inventory_summary(core_id=IDS[1]) is None


def test_allow_list_authorization_is_explicit_and_narrow():
    authorization = StaticAllowListAuthorization({(IDS[1], universal.UniversalAction.GESTURE)})
    composition = compose(
        core_ids=IDS,
        gestures=RecordingGestureService(),
        stop=InactiveStop(),
        authorization=authorization,
    )
    allowed = composition.request_gesture(_request(core_id=IDS[1]))
    assert allowed.outcome is CapabilityOutcome.RENDERED
    denied = composition.request_gesture(_request(core_id=IDS[3]))
    assert denied.outcome is CapabilityOutcome.DECLINED


def test_callable_chat_projection_stays_explicitly_narrow():
    projection = CallableChatProjection(
        lambda core_id, room_id: (IDS[1],) if room_id == "private:one" else None,
        lambda core_id: ("private:one",),
    )
    composition = compose(
        core_ids=IDS,
        chat=projection,
        stop=InactiveStop(),
        authorization=AllowAllAuthorization(),
    )
    decision = composition.validate_audience(
        audience=_audience(AudienceKind.PRIVATE_GROUP, room="private:one"),
        sender_core_id=IDS[1],
    )
    assert decision.status is AudienceStatus.ALLOWED
    assert projection.visible_room_ids(viewer_core_id=IDS[1]) == ("private:one",)
