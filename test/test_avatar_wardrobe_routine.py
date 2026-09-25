"""Offline metadata and proposal tests; no Blender, weather API or real receipt."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import pytest

from sofia.avatar.wardrobe import Garment, Layer, Wardrobe, WardrobeError
from sofia.avatar.wardrobe_routine import (
    Activity, Cadence, ChangeOrigin, OutfitPlan, OutfitPlanner, Preference,
    PreferenceActor, PreferenceTarget, Season, Sentiment, WardrobeContext,
    Weather, WeatherObservation, WornEvidence, appraise_clothing_change, period_key,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 21, 23, 15, tzinfo=UTC)


def wardrobe():
    items = (
        Garment("tee", "Oversized tee", Layer.BASE, ("torso",), ("torso",), asset_ref="tee_mesh"),
        Garment("sweats", "Sweatpants", Layer.BASE, ("pelvis", "legs"), ("pelvis", "legs"), asset_ref="sweats_mesh"),
        Garment("workshirt", "Work shirt", Layer.BASE, ("torso",), ("torso",), asset_ref="workshirt_mesh"),
        Garment("workpants", "Work pants", Layer.BASE, ("pelvis", "legs"), ("pelvis", "legs"), asset_ref="workpants_mesh"),
        Garment("left_gauntlet", "Leather left gauntlet", Layer.ACCESSORY, ("left_forearm", "left_wrist"), (), asset_ref="left_gauntlet_mesh"),
        Garment("right_gauntlet", "Leather right gauntlet", Layer.ACCESSORY, ("right_forearm", "right_wrist"), (), asset_ref="right_gauntlet_mesh"),
        Garment("underwear", "Underlayer", Layer.UNDERWEAR, ("pelvis",), ("pelvis",)),
    )
    return Wardrobe(items)


def plans():
    all_seasons = frozenset(Season)
    return (
        OutfitPlan("lounge", ("tee", "sweats"), frozenset({Activity.CONVERSATION, Activity.RELAXING, Activity.SLEEP}), all_seasons, lounge=True, style_tags=("oversized", "cozy")),
        OutfitPlan("engineer", ("workshirt", "workpants", "left_gauntlet", "right_gauntlet"), frozenset({Activity.CONVERSATION, Activity.ENGINEERING, Activity.LAB}), all_seasons, weather=frozenset({Weather.COLD, Weather.MILD}), style_tags=("leather_gauntlets", "engineer")),
        OutfitPlan("summer", ("tee", "workpants"), frozenset({Activity.CONVERSATION, Activity.ENGINEERING, Activity.LAB}), frozenset({Season.SUMMER}), weather=frozenset({Weather.HOT})),
    )


def ctx(*, now=NOW, season=Season.AUTUMN, activity=Activity.CONVERSATION, weather=None):
    return WardrobeContext(now, season, activity, weather)


def pref(actor, target, identifier, sentiment, *, reviewed=True):
    return Preference(actor, target, (identifier,), sentiment, "memory_01", reviewed)


def receipt(outfit="engineer", at=NOW - timedelta(days=1), rid="receipt_01"):
    return WornEvidence(outfit, at, rid)


def test_gauntlets_occupy_distinct_body_part_slots():
    outfit = wardrobe().selection(plans()[1].item_ids)
    assert outfit.covered_default and outfit.asset_refs_present
    assert "left_gauntlet" in outfit.item_ids and "right_gauntlet" in outfit.item_ids


def test_auto_late_night_lounge_large_shirt_and_sweats():
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx())
    assert result.outfit_id == "lounge"
    assert result.outfit.item_ids == ("tee", "sweats")
    assert "late_lounge" in result.reasons and result.requires_renderer_verification


def test_work_activity_remains_practical_even_at_night():
    assert OutfitPlanner(wardrobe(), plans()).suggest(ctx(activity=Activity.ENGINEERING)).outfit_id == "engineer"


def test_lounge_daytime_not_forced():
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(now=NOW.replace(hour=14)))
    assert result.outfit_id == "engineer"


def test_summer_weather_prefers_hot_outfit():
    observation = WeatherObservation(Weather.HOT, NOW - timedelta(minutes=5), "weather_01")
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(season=Season.SUMMER, activity=Activity.ENGINEERING, weather=observation))
    assert result.outfit_id == "summer"


def test_stale_weather_is_ignored_and_labelled():
    stale = WeatherObservation(Weather.HOT, NOW - timedelta(hours=7), "weather_01")
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(activity=Activity.ENGINEERING, weather=stale))
    assert result.outfit_id == "engineer"
    assert "weather_missing_or_stale" in result.reasons


def test_future_weather_does_not_count():
    future = WeatherObservation(Weather.HOT, NOW + timedelta(seconds=2), "weather_01")
    assert ctx(weather=future).effective_weather is None


def test_preferences_separate_sparks_and_sofia():
    book = (
        pref(PreferenceActor.SPARKS, PreferenceTarget.OUTFIT, "summer", Sentiment.LOVE),
        pref(PreferenceActor.SOFIA, PreferenceTarget.OUTFIT, "engineer", Sentiment.LOVE),
    )
    assert OutfitPlanner(wardrobe(), plans()).suggest(ctx(now=NOW.replace(hour=13), season=Season.SUMMER, activity=Activity.ENGINEERING), preferences=book).outfit_id == "engineer"


def test_sparks_feedback_can_influence_choice():
    book = (pref(PreferenceActor.SPARKS, PreferenceTarget.OUTFIT, "summer", Sentiment.LOVE),)
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(now=NOW.replace(hour=13), season=Season.SUMMER, activity=Activity.ENGINEERING), preferences=book)
    assert result.outfit_id == "summer"


def test_unreviewed_preference_has_no_effect():
    book = (pref(PreferenceActor.SOFIA, PreferenceTarget.OUTFIT, "summer", Sentiment.LOVE, reviewed=False),)
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(activity=Activity.ENGINEERING), preferences=book)
    assert result.outfit_id == "engineer"


def test_item_and_combination_preferences():
    book = (
        pref(PreferenceActor.SOFIA, PreferenceTarget.ITEM, "left_gauntlet", Sentiment.LOVE),
        Preference(PreferenceActor.SOFIA, PreferenceTarget.COMBINATION, ("left_gauntlet", "right_gauntlet"), Sentiment.LIKE, "source_02", True),
    )
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(activity=Activity.ENGINEERING), preferences=book)
    assert result.outfit_id == "engineer"


def test_hate_affects_score_not_authorization_or_hardcoded_emotion():
    book = (pref(PreferenceActor.SOFIA, PreferenceTarget.OUTFIT, "engineer", Sentiment.HATE),)
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(now=NOW.replace(hour=13), season=Season.SUMMER, activity=Activity.ENGINEERING), preferences=book)
    assert result.outfit_id == "summer"


def test_recent_acknowledged_wear_affects_rotation():
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(now=NOW.replace(hour=13), season=Season.SUMMER, activity=Activity.ENGINEERING), worn=(receipt("summer", NOW.replace(hour=13) - timedelta(days=1)),))
    assert result.outfit_id == "engineer"


def test_same_period_preserves_verified_outfit_when_context_matches():
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(activity=Activity.ENGINEERING), worn=(receipt("engineer", NOW - timedelta(hours=2)),))
    assert result.outfit_id == "engineer"
    assert result.reasons == ("verified_previous_choice",)


def test_same_period_changes_when_weather_becomes_incompatible():
    result = OutfitPlanner(wardrobe(), plans()).suggest(
        ctx(now=NOW.replace(hour=13), season=Season.SUMMER, activity=Activity.ENGINEERING,
            weather=WeatherObservation(Weather.HOT, NOW.replace(hour=13), "source_03")),
        worn=(receipt("engineer", NOW.replace(hour=12)),),
    )
    assert result.outfit_id == "summer"


def test_monthly_same_period_does_not_force_lounge_during_engineering():
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx(activity=Activity.ENGINEERING), cadence=Cadence.MONTHLY, worn=(receipt("lounge", NOW - timedelta(days=3)),))
    assert result.outfit_id == "engineer"


@pytest.mark.parametrize("cadence,key", [(Cadence.DAILY, "2026-09-21"), (Cadence.WEEKLY, "2026-W39"), (Cadence.MONTHLY, "2026-09")])
def test_rotation_periods(cadence, key):
    assert period_key(NOW, cadence) == key


def test_week_boundary_uses_iso_year():
    assert period_key(datetime(2021, 1, 1, tzinfo=UTC), Cadence.WEEKLY) == "2020-W53"


def test_private_only_outfit_not_auto_selected_even_in_lounge():
    private = OutfitPlan("private", ("underwear",), frozenset({Activity.SLEEP}), frozenset(Season), private_only=True)
    result = OutfitPlanner(wardrobe(), plans() + (private,)).suggest(ctx(activity=Activity.SLEEP))
    assert result.outfit_id == "lounge" and result.outfit.covered_default


def test_uncovered_automatic_outfit_rejected():
    unsafe = OutfitPlan("unsafe", ("underwear",), frozenset({Activity.RELAXING}), frozenset(Season))
    with pytest.raises(WardrobeError, match="cover"):
        OutfitPlanner(wardrobe(), (unsafe,))


def test_no_activity_match_fails_without_improvised_outfit():
    with pytest.raises(WardrobeError, match="fallback"):
        OutfitPlanner(wardrobe(), plans()).suggest(ctx(activity=Activity.FORMAL))


def test_choice_and_accident_have_distinct_optional_appraisals():
    bare = wardrobe().selection(("tee",))
    chosen = appraise_clothing_change(origin=ChangeOrigin.CHOSEN, proposed_outfit=bare, private_context=True)
    accident = appraise_clothing_change(origin=ChangeOrigin.UNINTENDED, proposed_outfit=bare, private_context=True)
    assert "possible_excitement" in chosen.cue_candidates
    assert "possible_embarrassment" in accident.cue_candidates
    assert chosen.requires_covered_recovery and accident.requires_covered_recovery
    assert not chosen.may_publish and not accident.may_publish


def test_covered_choice_no_forced_embarrassment():
    clothed = wardrobe().selection(("tee", "sweats"))
    result = appraise_clothing_change(origin=ChangeOrigin.CHOSEN, proposed_outfit=clothed)
    assert not result.requires_covered_recovery and "possible_embarrassment" not in result.cue_candidates


def test_appraisal_never_means_consent():
    unclothed = wardrobe().selection(())
    outcome = appraise_clothing_change(origin=ChangeOrigin.UNINTENDED, proposed_outfit=unclothed)
    assert outcome.requires_covered_recovery and outcome.may_publish is False


@pytest.mark.parametrize("invalid", [None, "2026-09-21", datetime(2026, 9, 21)])
def test_untrusted_or_naive_clock_denied(invalid):
    with pytest.raises(WardrobeError):
        WardrobeContext(invalid, Season.AUTUMN, Activity.CONVERSATION)


def test_invalid_observation_or_future_time_does_not_trigger_fetch():
    with pytest.raises(WardrobeError):
        WeatherObservation(Weather.HOT, NOW, "bad source")
    assert ctx().effective_weather is None


def test_invalid_slot_and_layer_collisions_still_rejected():
    with pytest.raises(WardrobeError):
        Garment("bad", "invalid", Layer.ACCESSORY, ("not_an_actual_slot",), ())
    w = wardrobe()
    assert w.selection(("left_gauntlet", "right_gauntlet")).item_ids == ("left_gauntlet", "right_gauntlet")


def test_preferences_need_source_and_unambiguous_target():
    with pytest.raises(WardrobeError):
        Preference(PreferenceActor.SOFIA, PreferenceTarget.OUTFIT, ("engineer",), Sentiment.LOVE, "")
    with pytest.raises(WardrobeError):
        Preference(PreferenceActor.SOFIA, PreferenceTarget.COMBINATION, ("x", "a"), Sentiment.LOVE, "source")
    with pytest.raises(WardrobeError, match="ambiguous"):
        OutfitPlanner(wardrobe(), plans()).suggest(ctx(), preferences=(
            pref(PreferenceActor.SPARKS, PreferenceTarget.OUTFIT, "summer", Sentiment.LOVE),
            pref(PreferenceActor.SPARKS, PreferenceTarget.OUTFIT, "summer", Sentiment.HATE),
        ))


def test_receipts_are_proposals_not_created_by_selection():
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx())
    with pytest.raises(FrozenInstanceError):
        result.outfit_id = "anything"
    assert result.requires_renderer_verification


def test_duplicate_receipt_denied():
    with pytest.raises(WardrobeError, match="duplicate renderer"):
        OutfitPlanner(wardrobe(), plans()).suggest(ctx(), worn=(receipt(), receipt()))


def test_no_real_asset_proof_from_metadata():
    result = OutfitPlanner(wardrobe(), plans()).suggest(ctx())
    from sofia.avatar.wardrobe import VisibilityDenied
    with pytest.raises(VisibilityDenied):
        wardrobe().require_public_ready(result.outfit)
