from __future__ import annotations

from datetime import datetime, timezone

from sofia.avatar.presentation import (
    AppearanceState,
    PresentationAuthority,
    PrivatePresentationGrant,
)
from sofia.avatar.presentation_routine import HeadlessPresentationRoutine
from sofia.avatar.presentation_store import PresentationStore
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_routine import (
    Activity,
    EmotionStyleInfluence,
    OutfitPlanner,
    Season,
    WardrobeContext,
)


def setup(tmp_path):
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            "long layered", "#8B1E3F", "#3A245C", ("engineer",)
        ),
    )
    store = PresentationStore(tmp_path / "presentation.json")
    store.save(authority)
    return authority, HeadlessPresentationRoutine(
        authority=authority,
        store=store,
        planner=OutfitPlanner(catalog.wardrobe, catalog.presets),
    )


def test_late_night_context_changes_daily_outfit_to_lounge(tmp_path):
    authority, routine = setup(tmp_path)
    context = WardrobeContext(
        datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc),
        Season.AUTUMN,
        Activity.CONVERSATION,
    )
    result = routine.evaluate(context, operation_id="daily.2026-09-25")
    assert result.changed
    assert authority.last_daily.outfit_id == "lounge.relaxed"


def test_daytime_context_keeps_engineer_without_churn(tmp_path):
    authority, routine = setup(tmp_path)
    context = WardrobeContext(
        datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc),
        Season.AUTUMN,
        Activity.CONVERSATION,
    )
    result = routine.evaluate(context, operation_id="daily.day")
    assert not result.changed
    assert result.reason == "daily_outfit_already_current"
    assert authority.current.revision == 1


def test_emotion_can_nudge_daily_choice(tmp_path):
    authority, routine = setup(tmp_path)
    context = WardrobeContext(
        datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc),
        Season.AUTUMN,
        Activity.CONVERSATION,
        emotion_influences=(
            EmotionStyleInfluence(
                "contentment",
                1.0,
                ("relaxed",),
                ("emotion:event:daily",),
            ),
        ),
    )
    result = routine.evaluate(context, operation_id="daily.emotion")
    assert result.changed
    assert authority.last_daily.outfit_id == "lounge.relaxed"
    assert "modeled_emotion_influence" in result.proposal.reasons


def test_private_nude_state_defers_daily_rotation(tmp_path):
    authority, routine = setup(tmp_path)
    grant = PrivatePresentationGrant(True, True, True, True, False)
    authority.propose_nude(
        operation_id="private.nude",
        expected_revision=1,
        reason="private presentation",
        grant=grant,
    )
    authority.commit_text(
        operation_id="private.nude",
        renderer_unavailable=True,
        grant=grant,
    )
    context = WardrobeContext(
        datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc),
        Season.AUTUMN,
        Activity.CONVERSATION,
    )
    result = routine.evaluate(context, operation_id="daily.blocked")
    assert result.deferred_private
    assert not result.changed
    assert authority.current.attire.value == "nude"
    assert authority.last_daily.outfit_id == "engineer.signature"
