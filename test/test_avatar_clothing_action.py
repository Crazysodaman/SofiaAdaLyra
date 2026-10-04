"""Authoritative natural-language clothing action acceptance tests."""
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from sofia.avatar.clothing_action import ClothingActionService
from sofia.avatar.wardrobe_autonomy import (
    WardrobeAutonomyContext,
    WardrobeAutonomyDecision,
    WardrobeAutonomyPolicy,
)
from sofia.avatar.presentation import AppearanceState, AttireMode, PresentationAuthority
from sofia.avatar.presentation_store import (
    PresentationStore,
    PresentationStoreError,
)
from sofia.avatar.presentation_runtime import PresentationRuntimeBundle
from sofia.avatar.wardrobe import Layer, Wardrobe, normalize_slots
from sofia.avatar.wardrobe_planner import (
    Activity,
    EmotionStyleInfluence,
    Season,
    WardrobeContext,
    Weather,
    WeatherObservation,
)
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.cognition.matrix import (
    ContextualInfluenceMatrix,
    InfluenceSurface,
)
from sofia.personality.influence import ContinuityInfluence
from sofia.safe.operator_stop import OperatorStopStore
from sofia.safe.permissions import PermissionStore
from sofia.social.principals import local_sparks_principal


def bundle(tmp_path, *, catalog=None):
    catalog = build_starter_wardrobe() if catalog is None else catalog
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits={
            plan.outfit_id: plan.item_ids
            for plan in catalog.presets
        },
        canonical_daily_outfit_id="day.default",
        initial_appearance=AppearanceState(
            hairstyle="canonical default",
            hair_color="deep crimson",
            tail_color="dark violet",
            style_tags=("canonical", "engineer"),
        ),
    )
    store = PresentationStore(tmp_path / "sofia.db")
    store.save(authority)
    return PresentationRuntimeBundle(authority, store, catalog)


def persisted_authority(runtime_bundle):
    return runtime_bundle.store.load(
        runtime_bundle.catalog.wardrobe,
        outfits={
            plan.outfit_id: plan.item_ids
            for plan in runtime_bundle.catalog.presets
        },
    )


def autonomy_context(
    *,
    hour: int = 14,
    season: Season = Season.AUTUMN,
    weather: Weather | None = None,
    emotion: str | None = None,
    intensity: float = 0.0,
) -> WardrobeAutonomyContext:
    now = datetime(2026, 10, 2, hour, 0, tzinfo=timezone.utc)
    refs = () if emotion is None else ("emotion:test-context",)
    continuity = ContinuityInfluence(
        daypart=(
            "morning"
            if 5 <= hour < 12
            else "afternoon"
            if 12 <= hour < 17
            else "evening"
            if 17 <= hour < 22
            else "night"
        ),
        season=season.value,
        daylight="day" if 7 <= hour < 19 else "night",
        weather_condition=None if weather is None else weather.value,
        temperature_c=None,
        weather_freshness="missing" if weather is None else "current",
        location_freshness="current",
        primary_emotion_evidence_refs=refs,
        emotional_tone="steady" if emotion is None else "warm",
        primary_emotion=emotion,
        primary_intensity=intensity,
        active_emotions=() if emotion is None else (emotion,),
        daypart_evidence_refs=("runtime.clock",),
        season_evidence_refs=("runtime.clock",),
        weather_evidence_refs=(
            ()
            if weather is None
            else ("environment.weather:weather.test",)
        ),
    )
    emotion_influences = ()
    if emotion is not None:
        tags = (
            ("soft", "cozy")
            if emotion == "fondness"
            else ("contextual",)
        )
        emotion_influences = (
            EmotionStyleInfluence(
                emotion=emotion,
                intensity=intensity,
                style_tags=tags,
                evidence_refs=refs,
            ),
        )
    wardrobe = WardrobeContext(
        now=now,
        season=season,
        activity=Activity.CONVERSATION,
        weather=(
            None
            if weather is None
            else WeatherObservation(
                condition=weather,
                observed_at=now,
                source_id="weather.test",
            )
        ),
        emotion_influences=emotion_influences,
    )
    return WardrobeAutonomyContext(
        continuity=continuity,
        influence_plan=ContextualInfluenceMatrix().plan(
            InfluenceSurface.WARDROBE_REQUEST_AUTONOMY,
            continuity,
        ),
        wardrobe_context=wardrobe,
    )



def test_change_into_night_lounge_commits_persists_and_updates_matrix(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)

    reply = service.handle(
        content="change into night lounge outfit",
        previous_user_content=None,
        operation_id="test.night.lounge",
    )

    assert reply is not None
    assert "Late-Night Lounge" in reply
    assert runtime_bundle.authority.current.outfit_id == "night.lounge"

    matrix = runtime_bundle.current_matrix()
    assert (
        matrix.cell(slot="torso", layer=Layer.BASE).garment_id
        == "night.lounge_tee"
    )
    assert (
        matrix.cell(slot="pelvis", layer=Layer.BASE).garment_id
        == "night.running_shorts"
    )
    persisted = persisted_authority(runtime_bundle)
    assert persisted.current.outfit_id == "night.lounge"
    assert persisted.current.item_ids == runtime_bundle.authority.current.item_ids

def test_take_off_jacket_builds_dynamic_outfit_and_persists_it(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)

    reply = service.handle(
        content="take off your jacket",
        previous_user_content=None,
        operation_id="test.remove.jacket",
    )

    assert reply is not None
    assert "Asymmetric engineer jacket" in reply
    current = runtime_bundle.authority.current
    assert current.outfit_id.startswith("dynamic.chat.")
    assert "day.engineer_jacket" not in current.item_ids
    assert runtime_bundle.current_matrix().cell(
        slot="torso",
        layer=Layer.OUTER,
    ) is None

    persisted = persisted_authority(runtime_bundle)
    assert persisted.current.outfit_id == current.outfit_id
    assert "day.engineer_jacket" not in persisted.current.item_ids



def test_swap_boots_keeps_current_pair_when_no_replacement_exists(tmp_path):
    catalog = build_starter_wardrobe()
    preset_ids = {item for plan in catalog.presets for item in plan.item_ids}
    current_boot = next(
        bp.garment
        for bp in catalog.blueprints
        if bp.garment.item_id == "day.work_boots"
    )
    blueprints = tuple(
        bp
        for bp in catalog.blueprints
        if bp.garment.item_id in preset_ids
        and (
            bp.garment.item_id == current_boot.item_id
            or bp.garment.layer is not current_boot.layer
            or frozenset(normalize_slots(bp.garment.slots))
            != frozenset(normalize_slots(current_boot.slots))
        )
    )
    available_ids = {
        bp.garment.item_id
        for bp in blueprints
    }
    presets = tuple(
        plan
        for plan in catalog.presets
        if set(plan.item_ids) <= available_ids
    )
    catalog = replace(
        catalog,
        blueprints=blueprints,
        wardrobe=Wardrobe(tuple(bp.garment for bp in blueprints)),
        presets=presets,
    )
    runtime_bundle = bundle(tmp_path, catalog=catalog)
    service = ClothingActionService(runtime_bundle)

    reply = service.handle(
        content="swap your boots",
        previous_user_content=None,
        operation_id="test.swap.boots",
    )

    assert reply is not None
    assert "don't have a compatible public replacement" in reply
    assert "day.work_boots" in runtime_bundle.authority.current.item_ids


def test_hypothetical_does_not_mutate_but_do_it_executes_prior_request(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)
    original = runtime_bundle.authority.current

    hypothetical = "if i asked you to change into the night lounge outfit will you"
    reply = service.handle(
        content=hypothetical,
        previous_user_content=None,
        operation_id="test.hypothetical",
    )

    assert reply is not None
    assert "request itself" in reply
    assert runtime_bundle.authority.current == original

    followup = service.handle(
        content="do it",
        previous_user_content=hypothetical,
        operation_id="test.followup",
    )

    assert followup is not None
    assert runtime_bundle.authority.current.outfit_id == "night.lounge"

def test_undress_and_do_it_fail_closed_without_private_grant(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)
    original = runtime_bundle.authority.current

    hypothetical = "if i asked you to undress will you"
    reply = service.handle(
        content=hypothetical,
        previous_user_content=None,
        operation_id="test.undress.question",
    )
    assert reply is not None
    assert "private presentation" in reply
    assert runtime_bundle.authority.current == original

    followup = service.handle(
        content="do it",
        previous_user_content=hypothetical,
        operation_id="test.undress.followup",
    )
    assert followup is not None
    assert "keeping my current outfit" in followup
    assert runtime_bundle.authority.current == original
    assert persisted_authority(runtime_bundle).current == original


class DeclinePublicChange(WardrobeAutonomyPolicy):
    def decide(self, *, intent, candidate_item_ids, private_only):
        return WardrobeAutonomyDecision(
            False,
            "I prefer to keep this outfit right now",
        )


def test_autonomy_policy_can_decline_public_change_without_mutation(tmp_path):
    runtime_bundle = bundle(tmp_path)
    original = runtime_bundle.authority.current
    service = ClothingActionService(
        runtime_bundle,
        autonomy=DeclinePublicChange(),
    )

    reply = service.handle(
        content="wear night lounge outfit",
        previous_user_content=None,
        operation_id="test.decline",
    )

    assert reply is not None
    assert "keeping my current outfit" in reply
    assert "prefer to keep this outfit" in reply
    assert runtime_bundle.authority.current == original
    assert persisted_authority(runtime_bundle).current == original



def test_contextual_autonomy_counter_proposes_during_lounge_window(tmp_path):
    runtime_bundle = bundle(tmp_path)
    original = runtime_bundle.authority.current
    context = autonomy_context(
        hour=23,
        season=Season.AUTUMN,
    )
    service = ClothingActionService(
        runtime_bundle,
        context_provider=lambda: context,
    )

    reply = service.handle(
        content="wear signature engineer outfit",
        previous_user_content=None,
        operation_id="test.context.daypart",
    )

    assert reply is not None
    assert "lounge window" in reply
    assert "I'd rather wear" in reply
    assert runtime_bundle.authority.current == original


def test_contextual_autonomy_can_counter_propose_from_strong_modeled_emotion(tmp_path):
    runtime_bundle = bundle(tmp_path)
    original = runtime_bundle.authority.current
    context = autonomy_context(
        hour=14,
        season=Season.AUTUMN,
        emotion="fondness",
        intensity=0.90,
    )
    service = ClothingActionService(
        runtime_bundle,
        context_provider=lambda: context,
    )

    reply = service.handle(
        content="wear signature engineer outfit",
        previous_user_content=None,
        operation_id="test.context.emotion",
    )

    assert reply is not None
    assert "modeled emotional style preference" in reply
    assert "I'd rather wear" in reply
    assert runtime_bundle.authority.current == original



def test_contextual_autonomy_still_accepts_compatible_requested_outfit(tmp_path):
    runtime_bundle = bundle(tmp_path)
    context = autonomy_context(
        hour=23,
        season=Season.AUTUMN,
    )
    service = ClothingActionService(
        runtime_bundle,
        context_provider=lambda: context,
    )

    reply = service.handle(
        content="wear night lounge outfit",
        previous_user_content=None,
        operation_id="test.context.accept",
    )

    assert reply is not None
    assert "Late-Night Lounge" in reply
    assert runtime_bundle.authority.current.outfit_id == "night.lounge"

def test_unrelated_text_is_not_a_clothing_action(tmp_path):
    service = ClothingActionService(bundle(tmp_path))

    assert service.handle(
        content="how are you",
        previous_user_content=None,
        operation_id="test.unrelated",
    ) is None


def test_verified_private_sparks_session_can_commit_and_restore_nude_state(tmp_path):
    runtime_bundle = bundle(tmp_path)
    PermissionStore(
        runtime_bundle.store.database_path
    ).set_private_adult_authority(
        private_chat=True,
        adult_chat=True,
        adult_avatar=True,
        adult_external_delivery=False,
    )
    service = ClothingActionService(runtime_bundle)

    reply = service.handle(
        content="undress",
        previous_user_content=None,
        operation_id="test.private.nude",
        principal=local_sparks_principal(),
    )

    assert reply is not None
    assert "no clothing" in reply
    assert runtime_bundle.authority.current.attire is AttireMode.NUDE
    assert runtime_bundle.authority.current.private_only is True
    assert runtime_bundle.current_matrix().item_ids == ()

    persisted = persisted_authority(runtime_bundle)
    assert persisted.current.attire is AttireMode.NUDE
    assert persisted.current.item_ids == ()


def test_operator_stop_blocks_private_presentation_even_when_adult_verified(tmp_path):
    runtime_bundle = bundle(tmp_path)
    PermissionStore(
        runtime_bundle.store.database_path
    ).set_private_adult_authority(
        private_chat=True,
        adult_chat=True,
        adult_avatar=True,
        adult_external_delivery=False,
    )
    stop = OperatorStopStore(runtime_bundle.store.database_path)
    stop.set(
        active=True,
        updated_by="Sparks",
        reason="test stop",
    )
    service = ClothingActionService(
        runtime_bundle,
        operator_stop_store=stop,
    )
    original = runtime_bundle.authority.current

    reply = service.handle(
        content="undress",
        previous_user_content=None,
        operation_id="test.private.stopped",
        principal=local_sparks_principal(),
    )

    assert reply is not None
    assert "keeping my current outfit" in reply
    assert runtime_bundle.authority.current == original


def test_ambiguous_outfit_display_name_fails_closed(tmp_path):
    runtime_bundle = bundle(tmp_path)
    catalog = runtime_bundle.catalog
    first = replace(
        catalog.presets[0],
        display_name="Same Outfit",
    )
    second = replace(
        catalog.presets[1],
        display_name="Same Outfit",
    )
    ambiguous_catalog = replace(
        catalog,
        presets=(first, second, *catalog.presets[2:]),
    )
    runtime_bundle = replace(
        runtime_bundle,
        catalog=ambiguous_catalog,
    )
    service = ClothingActionService(runtime_bundle)
    original = runtime_bundle.authority.current

    reply = service.handle(
        content="wear same outfit",
        previous_user_content=None,
        operation_id="test.ambiguous.outfit",
    )

    assert reply is not None
    assert "couldn't resolve" in reply
    assert runtime_bundle.authority.current == original



def test_dynamic_clothing_change_rolls_back_registration_when_save_fails(
    tmp_path,
    monkeypatch,
):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)
    before = runtime_bundle.authority.snapshot()
    before_outfits = runtime_bundle.authority.available_outfit_ids

    def fail_save(_authority):
        raise PresentationStoreError("synthetic clothing save failure")

    monkeypatch.setattr(runtime_bundle.store, "save", fail_save)

    with pytest.raises(PresentationStoreError, match="synthetic"):
        service.handle(
            content="take off your jacket",
            previous_user_content=None,
            operation_id="test.rollback.dynamic",
        )

    assert runtime_bundle.authority.snapshot() == before
    assert runtime_bundle.authority.available_outfit_ids == before_outfits
    assert runtime_bundle.authority.pending is None


def test_swap_boots_uses_expanded_public_inventory(tmp_path):
    runtime_bundle = bundle(tmp_path)
    service = ClothingActionService(runtime_bundle)
    reply = service.handle(content="swap your boots", previous_user_content=None,
                           operation_id="test.swap.expanded.boots")
    assert reply is not None and "The change is committed" in reply
    current = runtime_bundle.authority.current
    assert "day.work_boots" not in current.item_ids
    selection = runtime_bundle.catalog.wardrobe.selection(current.item_ids)
    assert selection.covered_default and not selection.private_only
    assert persisted_authority(runtime_bundle).current == current
