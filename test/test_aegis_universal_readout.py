"""Read-only universal readout: honest availability and no leakage."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import UUID

import pytest

from sofia.platform.social.governance.contracts import (
    CoordinatorStatus,
    CoordinatorTerm,
    DecisionProcedure,
    GovernanceGroup,
    GovernancePolicy,
    GroupLifecycle,
    GroupMember,
    MemberState,
)
from sofia.platform.social.universal import (
    InventorySummary,
    StopStatus,
    WardrobeCatalogSummary,
    compose,
)
from sofia.platform.social.universal_readout import (
    Availability,
    READOUT_SCHEMA,
    build_universal_readout,
)
from sofia.sdk.core_capabilities import RendererCapability

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
IDS = {
    1: UUID("aaaaaaaa-1111-4111-8111-111111111111"),
    2: UUID("bbbbbbbb-2222-4222-8222-222222222222"),
    3: UUID("cccccccc-3333-4333-8333-333333333333"),
    6: UUID("dddddddd-6666-4666-8666-666666666666"),
    7: UUID("eeeeeeee-7777-4777-8777-777777777777"),
}


class ActiveStop:
    def stop_status(self) -> StopStatus:
        return StopStatus.ACTIVE


class InactiveStop:
    def stop_status(self) -> StopStatus:
        return StopStatus.INACTIVE


class SpyWardrobe:
    def __init__(self) -> None:
        self.catalog_calls = 0
        self.inventory_calls: list[UUID] = []

    def catalog_summary(self) -> WardrobeCatalogSummary:
        self.catalog_calls += 1
        return WardrobeCatalogSummary(
            total_designs=5,
            clothing_designs=2,
            armor_designs=3,
            public_designs=3,
            private_designs=1,
            adult_designs=1,
        )

    def inventory_summary(self, *, core_id: UUID) -> InventorySummary:
        self.inventory_calls.append(core_id)
        return InventorySummary(
            core_id=core_id,
            owned_count=2,
            held_count=1,
            loaned_count=0,
            equipped_count=1,
        )


class SpyGovernance:
    def __init__(self, group, term) -> None:
        self.group = group
        self.term = term
        self.group_calls = 0
        self.term_calls = 0

    def groups(self):
        self.group_calls += 1
        return (self.group,)

    def coordinator_terms(self):
        self.term_calls += 1
        return (self.term,)


class SpyGesture:
    def __init__(self, renderers=(RendererCapability.TEXT,)) -> None:
        self.renderers = renderers
        self.calls = 0

    def available_renderers(self, *, core_id: UUID):
        self.calls += 1
        return self.renderers


class BrokenGesture:
    def available_renderers(self, *, core_id: UUID):
        raise RuntimeError("renderer inventory is offline")


def _group() -> GovernanceGroup:
    member_one = GroupMember(
        core_id=IDS[1],
        state=MemberState.ACTIVE,
        joined_at=NOW,
        joined_epoch=1,
    )
    member_two = GroupMember(
        core_id=IDS[2],
        state=MemberState.ACTIVE,
        joined_at=NOW,
        joined_epoch=1,
    )
    return GovernanceGroup(
        group_id=UUID("24681357-2468-4468-8468-246813572468"),
        name="Voluntary test group",
        purpose="Source-only governance fixture",
        room_ids=("room:test",),
        revision=1,
        roster_epoch=1,
        lifecycle=GroupLifecycle.ACTIVE,
        policy=GovernancePolicy(procedure=DecisionProcedure.DISCUSSION),
        members=(member_one, member_two),
        founding_member_ids=(IDS[1], IDS[2]),
        created_at=NOW,
        updated_at=NOW,
    )


def _term(group: GovernanceGroup) -> CoordinatorTerm:
    return CoordinatorTerm(
        term_id=UUID("13572468-1357-4357-8357-135724681357"),
        group_id=group.group_id,
        core_id=IDS[1],
        proposal_id=UUID("97531864-9753-4975-8975-975318649753"),
        starts_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=7),
        status=CoordinatorStatus.ACTIVE,
    )


def test_default_readout_is_explicitly_inert_and_unavailable():
    composition = compose(core_ids=IDS)
    readout = build_universal_readout(composition, now=NOW)
    assert readout.stop_status is StopStatus.UNKNOWN
    assert readout.wardrobe.availability is Availability.UNAVAILABLE
    assert readout.wardrobe.total_designs is None
    assert readout.governance.availability is Availability.UNAVAILABLE
    assert readout.governance.terms_availability is Availability.UNAVAILABLE
    assert readout.governance.group_count is None
    assert all(
        inventory.availability is Availability.UNAVAILABLE
        for inventory in readout.wardrobe.inventories
    )
    assert len(readout.cores) == 5
    for core in readout.cores:
        assert core.activated is False
        assert core.runtime_state == "INERT"
        assert core.platform_authority is False
        assert core.leadership_role is None
        renderers = {item.renderer: item.availability for item in core.renderers}
        assert renderers["text"] is Availability.AVAILABLE
        for renderer in ("2d", "3d", "vtube", "haptic"):
            assert renderers[renderer] is Availability.UNAVAILABLE
    assert readout.installed is False
    assert readout.live_verified is False
    assert readout.mutations_performed is False


def test_unknown_stop_and_missing_adapters_are_not_reported_as_off():
    composition = compose(core_ids=IDS, stop=None)
    readout = build_universal_readout(composition, now=NOW)
    assert readout.stop_status is StopStatus.UNKNOWN
    assert readout.adapters.stop is False
    assert readout.adapters.wardrobe is False
    assert readout.adapters.governance is False


def test_active_stop_is_reported_without_turning_it_off():
    composition = compose(core_ids=IDS, stop=ActiveStop())
    readout = build_universal_readout(composition, now=NOW)
    assert readout.stop_status is StopStatus.ACTIVE


def test_synthetic_adapters_produce_explicit_counts_and_terms():
    group = _group()
    wardrobe = SpyWardrobe()
    governance = SpyGovernance(group, _term(group))
    composition = compose(
        core_ids=IDS,
        wardrobe=wardrobe,
        governance=governance,
        gestures=SpyGesture(),
        stop=InactiveStop(),
    )
    readout = build_universal_readout(composition, now=NOW)
    assert readout.wardrobe.availability is Availability.AVAILABLE
    assert readout.wardrobe.total_designs == 5
    assert readout.wardrobe.armor_designs == 3
    assert readout.wardrobe.clothing_designs == 2
    assert readout.wardrobe.private_designs == 1
    assert readout.wardrobe.adult_designs == 1
    assert readout.governance.availability is Availability.AVAILABLE
    assert readout.governance.terms_availability is Availability.AVAILABLE
    assert readout.governance.group_count == 1
    assert readout.governance.active_group_count == 1
    assert readout.governance.coordinator_term_count == 1
    assert readout.governance.active_coordinator_term_count == 1
    summary = readout.governance.groups[0]
    assert summary.group_id == str(group.group_id)
    assert summary.member_count == 2
    assert summary.active_member_count == 2
    assert summary.leaderless is True
    assert summary.coordinator_term_active is True
    assert readout.stop_status is StopStatus.INACTIVE


def test_readout_is_read_only_and_calls_only_read_seams():
    group = _group()
    wardrobe = SpyWardrobe()
    governance = SpyGovernance(group, _term(group))
    gestures = SpyGesture()
    composition = compose(
        core_ids=IDS,
        wardrobe=wardrobe,
        governance=governance,
        gestures=gestures,
        stop=InactiveStop(),
    )
    build_universal_readout(composition, now=NOW)
    assert wardrobe.catalog_calls == 1
    assert wardrobe.inventory_calls == [IDS[1], IDS[2], IDS[3], IDS[6], IDS[7]]
    assert governance.group_calls == 1
    assert governance.term_calls == 1
    assert gestures.calls == 5


def test_unsupported_renderers_are_unavailable_not_rendered():
    composition = compose(
        core_ids=IDS,
        gestures=SpyGesture(renderers=(RendererCapability.TEXT,)),
        stop=InactiveStop(),
    )
    readout = build_universal_readout(composition, now=NOW)
    for core in readout.cores:
        renderers = {item.renderer: item.availability for item in core.renderers}
        assert renderers[RendererCapability.TEXT.value] is Availability.AVAILABLE
        assert renderers[RendererCapability.THREE_D.value] is Availability.UNAVAILABLE


def test_broken_renderer_projection_is_unknown_not_available():
    composition = compose(
        core_ids=IDS,
        gestures=BrokenGesture(),
        stop=InactiveStop(),
    )
    readout = build_universal_readout(composition, now=NOW)
    for core in readout.cores:
        renderers = {item.renderer: item.availability for item in core.renderers}
        assert renderers[RendererCapability.THREE_D.value] is Availability.UNKNOWN


def test_payload_is_json_safe_and_contains_no_private_audience_detail():
    group = _group()
    composition = compose(
        core_ids=IDS,
        wardrobe=SpyWardrobe(),
        governance=SpyGovernance(group, _term(group)),
        gestures=SpyGesture(),
        stop=InactiveStop(),
    )
    payload = build_universal_readout(composition, now=NOW).to_payload()
    assert payload["schema"] == READOUT_SCHEMA
    assert payload["authority"] == "READ_ONLY_NO_AUTHORITY"
    assert payload["mutations_performed"] is False
    assert payload["secrets_included"] is False
    assert payload["private_member_ids_included"] is False
    group_payload = payload["governance"]["groups"][0]
    assert set(group_payload) == {
        "group_id",
        "lifecycle",
        "member_count",
        "active_member_count",
        "leaderless",
        "coordinator_term_active",
    }
    encoded_groups = json.dumps(group_payload, sort_keys=True)
    for forbidden in (
        "asset_ref",
        "ballot",
        "ballots",
        "member_ids",
        "note",
        "proposal_text",
        "memory",
    ):
        assert forbidden not in encoded_groups


def test_readout_rejects_non_composition_and_naive_time():
    with pytest.raises(TypeError):
        build_universal_readout(object())
    composition = compose(core_ids=IDS)
    with pytest.raises(ValueError):
        build_universal_readout(composition, now=datetime(2026, 11, 18, 15, 0))


def test_readout_never_labels_a_social_role_as_platform_authority():
    group = _group()
    composition = compose(
        core_ids=IDS,
        governance=SpyGovernance(group, _term(group)),
        stop=InactiveStop(),
    )
    readout = build_universal_readout(composition, now=NOW)
    assert all(core.platform_authority is False for core in readout.cores)
    assert all(core.leadership_role is None for core in readout.cores)
    assert all(summary.leaderless for summary in readout.governance.groups)


def test_all_five_readouts_declare_every_capability_family_but_none_effective():
    composition = compose(core_ids=IDS)
    readout = build_universal_readout(composition, now=NOW)
    for core in readout.cores:
        assert len(core.capabilities) == 16
        for capability in core.capabilities:
            assert capability.declared is True
            assert capability.installed is False
            assert capability.available is False
            assert capability.authorized is False
            assert capability.effective is False
            assert capability.state == "DECLARED_ONLY"
