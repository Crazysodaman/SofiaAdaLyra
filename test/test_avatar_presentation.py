from __future__ import annotations

import pytest

from sofia.avatar.presentation import (
    AppearanceState,
    AttireMode,
    AudienceScope,
    PresentationAuthority,
    PresentationConflict,
    PresentationDenied,
    PrivatePresentationGrant,
)
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def authority() -> PresentationAuthority:
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    return PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle="long layered",
            hair_color="#8B1E3F",
            tail_color="#3A245C",
            style_tags=("cyberpunk", "engineer"),
        ),
    )


def private_grant(**changes) -> PrivatePresentationGrant:
    values = {
        "adult_verified": True,
        "owner_verified": True,
        "private_session": True,
        "explicit_current_opt_in": True,
        "external_stop_active": False,
    }
    values.update(changes)
    return PrivatePresentationGrant(**values)


def test_bootstrap_public_daily_is_canonical_engineer():
    state = authority().projection(AudienceScope.PUBLIC)
    assert state.attire is AttireMode.CLOTHED
    assert state.outfit_id == "engineer.signature"
    assert state.private_fallback_used is False


def test_daily_lounge_becomes_public_default_fallback():
    a = authority()
    a.propose_outfit(
        operation_id="op.lounge",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="late evening conversation",
        daily=True,
    )
    lounge = a.commit_text(operation_id="op.lounge", renderer_unavailable=True)
    assert lounge.outfit_id == "lounge.relaxed"
    assert a.last_daily.outfit_id == "lounge.relaxed"

    a.propose_nude(
        operation_id="op.private.nude",
        expected_revision=2,
        reason="private personal presentation",
        grant=private_grant(),
    )
    current = a.commit_text(
        operation_id="op.private.nude",
        renderer_unavailable=True,
        grant=private_grant(),
    )
    assert current.attire is AttireMode.NUDE

    public = a.projection(AudienceScope.PUBLIC)
    assert public.attire is AttireMode.CLOTHED
    assert public.outfit_id == "lounge.relaxed"
    assert public.private_fallback_used is True


def test_private_authorized_projection_can_expose_nude_state():
    a = authority()
    grant = private_grant()
    a.propose_nude(
        operation_id="op.nude",
        expected_revision=1,
        reason="private presentation",
        grant=grant,
    )
    a.commit_text(operation_id="op.nude", renderer_unavailable=True, grant=grant)
    view = a.projection(AudienceScope.PRIVATE, grant=grant)
    assert view.attire is AttireMode.NUDE
    assert view.item_ids == ()
    assert view.private_fallback_used is False


def test_private_state_never_becomes_public_without_explicit_grant():
    a = authority()
    grant = private_grant()
    a.propose_nude(
        operation_id="op.nude",
        expected_revision=1,
        reason="private presentation",
        grant=grant,
    )
    a.commit_text(operation_id="op.nude", renderer_unavailable=True, grant=grant)
    assert a.projection(AudienceScope.PUBLIC).outfit_id == "engineer.signature"
    assert a.projection(AudienceScope.PRIVATE).outfit_id == "engineer.signature"


def test_nude_requires_current_private_authorization():
    a = authority()
    with pytest.raises(PresentationDenied):
        a.propose_nude(
            operation_id="op.nude.denied",
            expected_revision=1,
            reason="private presentation",
            grant=private_grant(explicit_current_opt_in=False),
        )


def test_private_outfit_cannot_replace_daily_fallback():
    a = authority()
    with pytest.raises(PresentationDenied):
        a.propose_outfit(
            operation_id="op.private",
            expected_revision=1,
            outfit_id="lounge.relaxed",
            reason="private experiment",
            private_only=True,
            daily=True,
        )


def test_appearance_changes_share_presentation_revision():
    a = authority()
    appearance = AppearanceState(
        hairstyle="messy side braid",
        hair_color="#A63D5E",
        tail_color="#43265F",
        style_tags=("lounge", "warm"),
    )
    a.propose_appearance(
        operation_id="op.appearance",
        expected_revision=1,
        appearance=appearance,
        reason="trying a warmer late-night look",
    )
    state = a.commit_text(operation_id="op.appearance", renderer_unavailable=True)
    assert state.revision == 2
    assert state.appearance == appearance
    assert a.last_daily.appearance == appearance


def test_snapshot_restore_preserves_private_current_and_last_daily():
    a = authority()
    a.propose_outfit(
        operation_id="op.lounge",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="late evening",
        daily=True,
    )
    a.commit_text(operation_id="op.lounge", renderer_unavailable=True)
    grant = private_grant()
    a.propose_nude(
        operation_id="op.nude",
        expected_revision=2,
        reason="private state",
        grant=grant,
    )
    a.commit_text(operation_id="op.nude", renderer_unavailable=True, grant=grant)
    snapshot = a.snapshot()

    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    restored = PresentationAuthority.restore(
        catalog.wardrobe,
        outfits=outfits,
        snapshot=snapshot,
    )
    assert restored.current.attire is AttireMode.NUDE
    assert restored.last_daily.outfit_id == "lounge.relaxed"
    assert restored.projection(AudienceScope.PUBLIC).outfit_id == "lounge.relaxed"


def test_stale_revision_and_reused_operation_are_rejected():
    a = authority()
    a.propose_outfit(
        operation_id="op.one",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="change",
    )
    a.commit_text(operation_id="op.one", renderer_unavailable=True)
    with pytest.raises(PresentationConflict):
        a.propose_outfit(
            operation_id="op.two",
            expected_revision=1,
            outfit_id="engineer.signature",
            reason="stale",
        )
    with pytest.raises(PresentationConflict):
        a.propose_outfit(
            operation_id="op.one",
            expected_revision=2,
            outfit_id="engineer.signature",
            reason="replay",
        )
