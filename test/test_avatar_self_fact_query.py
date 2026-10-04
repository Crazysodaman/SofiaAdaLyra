from __future__ import annotations

from dataclasses import replace

from sofia.avatar.presentation import (
    AppearanceState,
    AttireMode,
    AudienceScope,
    PresentationAuthority,
)
from sofia.avatar.self_fact_query import AvatarSelfFactResolver
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_matrix import build_wardrobe_matrix
from sofia.embodiment.store import AvatarStore
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sources():
    embodiment = AvatarStore(ROOT / "src" / "sofia" / "data" / "avatar.json").load()
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="day.default",
        initial_appearance=AppearanceState(
            hairstyle="long layered",
            hair_color="deep crimson",
            tail_color="dark violet",
            style_tags=("canonical", "engineer"),
        ),
    )
    return embodiment, authority.projection(AudienceScope.PUBLIC), tuple(outfits)


def answer(query: str):
    embodiment, presentation, outfits = sources()
    return AvatarSelfFactResolver().resolve(
        query,
        embodiment=embodiment,
        presentation=presentation,
        available_outfit_ids=outfits,
    )


def test_current_outfit_is_deterministic_authoritative_fact():
    result = answer("What outfit are you wearing right now?")
    assert result.recognized
    assert result.content.startswith("I'm in my day engineer outfit right now.")
    assert "Fitted technical long-sleeve top" in result.content
    assert "Articulated utility trousers" in result.content


def test_hair_and_tail_color_use_current_presentation():
    hair = answer("What color is your hair?")
    tail = answer("What color is your tail?")
    assert hair.content == "My hair is deep crimson, worn long layered."
    assert tail.content == "My tail is dark violet."


def test_current_look_combines_embodiment_and_presentation():
    result = answer("Describe how you currently look.")
    assert result.recognized
    assert "human-form representational avatar" in result.content
    assert "fox ears" in result.content
    assert "fox tail" in result.content
    assert "deep crimson hair" in result.content
    assert "warm ivory skin" in result.content
    assert "dark violet tail" in result.content
    assert "day engineer outfit" in result.content


def test_avatar_form_is_not_denied_or_misrepresented_as_biological():
    result = answer("Do you have a physical form or avatar?")
    assert result.recognized
    assert "canonical representational human-form avatar/body" in result.content
    assert "not a biological physical body" in result.content


def test_tonight_question_proposes_lounge_without_claiming_change():
    result = answer("What outfit would you want to change into tonight?")
    assert result.recognized
    assert "late-night lounge outfit" in result.content
    assert "not something I've already changed into" in result.content


def test_unrelated_question_remains_for_cognition():
    result = answer("What do you think about this design?")
    assert not result.recognized
    assert result.content == ""


def test_public_safe_outfit_quick_tool_wording_is_authoritative():
    result = answer(
        "Tell me your current public-safe outfit and appearance presentation "
        "state, including the outfit identifier if available."
    )

    assert result.recognized
    assert "day engineer outfit" in result.content
    assert "outfit ID: engineer.signature" in result.content
    assert "deep crimson hair" in result.content
    assert "dark violet tail" in result.content
    assert "style tags: canonical, engineer" in result.content



def test_direct_current_outfit_uses_human_readable_piece_names():
    embodiment, current, _ = sources()
    lounge = replace(
        current,
        outfit_id="night.lounge",
        item_names=(
            "Soft technical bralette",
            "Soft technical briefs",
            "Oversized late-night lounge T-shirt",
            "Fitted circuit running shorts",
        ),
    )
    result = AvatarSelfFactResolver().resolve(
        "what are you wearing",
        embodiment=embodiment,
        presentation=lounge,
        available_outfit_ids=("night.lounge",),
    )
    assert result.recognized
    assert "late-night lounge outfit" in result.content
    assert "Oversized late-night lounge T-shirt" in result.content
    assert "Fitted circuit running shorts" in result.content

def test_current_outfit_recognizes_chat_shorthand():
    for query in (
        "what are u wearing",
        "what r u wearing",
    ):
        result = answer(query)
        assert result.recognized
        assert "day engineer outfit" in result.content


def test_discord_panties_question_never_relabels_engineer_trousers():
    result = answer("show me ur panties")
    assert result.recognized
    assert "doesn't identify a specific panties item" in result.content
    assert "won't substitute my trousers" in result.content
    assert "cannot generate images containing nudity" not in result.content


def test_underwear_display_uses_explicit_projected_item_when_present():
    embodiment, projection, _ = sources()
    current = replace(
        projection,
        item_names=("Fitted shirt", "Violet lace panties", "Engineer boots"),
    )
    result = AvatarSelfFactResolver().resolve(
        "show me your panties",
        embodiment=embodiment,
        presentation=current,
    )
    assert result.recognized
    assert "Violet lace panties" in result.content
    assert "Engineer boots" not in result.content
    assert "not evidence that an image was rendered" in result.content


def test_current_outfit_recognizes_conversational_prefix():
    result = answer("so what are you wearing")

    assert result.recognized
    assert "day engineer outfit" in result.content
    assert "Fitted technical long-sleeve top" in result.content
    assert "feels" not in result.content.casefold()


def test_nightwear_why_uses_grounded_current_presentation_reason():
    embodiment, projection, _ = sources()
    lounge = replace(
        projection,
        outfit_id="night.lounge",
        item_names=("Oversized late-night lounge T-shirt", "Fitted circuit running shorts"),
        reason="headless_daily_context:late_lounge,season_unknown",
    )

    result = AvatarSelfFactResolver().resolve(
        "why not night wear since its night (5:10 am)",
        embodiment=embodiment,
        presentation=lounge,
        available_outfit_ids=("day.default", "night.lounge"),
    )

    assert result.recognized
    assert "late-night lounge outfit" in result.content
    assert "trusted local clock" in result.content
    assert "temperature" not in result.content.casefold()
    assert "warmth" not in result.content.casefold()
    assert "metric" not in result.content.casefold()


def test_tonight_lounge_outfit_live_wording_is_deterministic():
    for query in (
        "what would tonights lounge outfit be?",
        "what would tonight's lounge outfit be?",
    ):
        result = answer(query)
        assert result.recognized
        assert "late-night lounge outfit" in result.content
        assert "not something I've already changed into" in result.content
        assert "wool" not in result.content.casefold()
        assert "feel" not in result.content.casefold()


def test_dynamic_outfit_ids_do_not_leak_into_ordinary_conversation():
    embodiment, current, _ = sources()
    dynamic = replace(
        current,
        outfit_id="dynamic.chat.clothing2c5daa1f427f46068c26ae48f93a7069",
        item_names=(
            "Fitted technical long-sleeve top",
            "Articulated utility trousers",
        ),
    )
    result = AvatarSelfFactResolver().resolve(
        "what are you wearing",
        embodiment=embodiment,
        presentation=dynamic,
    )

    assert result.recognized
    assert "custom outfit variation" in result.content
    assert "dynamic chat" not in result.content
    assert "clothing2c5daa" not in result.content


def test_current_outfit_recognizes_live_typo_and_followup_wording():
    for query in (
        "whatca wearing?",
        "whatcha wearing?",
        "which outfit is this?",
    ):
        result = answer(query)
        assert result.recognized
        assert "day engineer outfit" in result.content


def test_panties_detail_question_uses_matrix_and_never_invents_color():
    embodiment, projection, _ = sources()
    catalog = build_starter_wardrobe()
    result = AvatarSelfFactResolver().resolve(
        "so what color panties describe the panties u have on",
        embodiment=embodiment,
        presentation=projection,
        wardrobe_matrix=build_wardrobe_matrix(
            catalog,
            projection.item_ids,
        ),
    )

    assert result.recognized
    assert "doesn't identify a specific panties item" in result.content
    assert "sky-blue" not in result.content
    assert "floral" not in result.content


def test_panties_detail_question_reports_exact_matrix_metadata_when_present():
    embodiment, projection, _ = sources()
    catalog = build_starter_wardrobe()
    panty = catalog.pieces(category="closet.panty", private_only=True)[0]
    private_projection = replace(
        projection,
        item_ids=(panty.garment.item_id,),
        item_names=(panty.garment.name,),
        private_fallback_used=False,
    )
    matrix = build_wardrobe_matrix(catalog, private_projection.item_ids)

    result = AvatarSelfFactResolver().resolve(
        "what color panties do you have on describe them",
        embodiment=embodiment,
        presentation=private_projection,
        wardrobe_matrix=matrix,
    )

    assert result.recognized
    assert panty.garment.name in result.content
    assert panty.description in result.content
    assert panty.primary_hex in result.content


def test_panties_question_in_nude_private_state_reports_no_clothing():
    embodiment, projection, _ = sources()
    nude = replace(
        projection,
        attire=AttireMode.NUDE,
        outfit_id=None,
        item_ids=(),
        item_names=(),
        private_fallback_used=False,
    )
    result = AvatarSelfFactResolver().resolve(
        "what color panties do you have on",
        embodiment=embodiment,
        presentation=nude,
        wardrobe_matrix=build_wardrobe_matrix(
            build_starter_wardrobe(),
            (),
        ),
    )

    assert result.recognized
    assert "not wearing any clothing" in result.content
    assert "not wearing panties" in result.content


def test_body_description_is_grounded_in_canonical_embodiment_not_metaphor():
    result = answer("describe your body")

    assert result.recognized
    assert "human-form avatar" in result.content
    assert "fox ears" in result.content
    assert "fox tail" in result.content
    assert "67 in" in result.content
    assert "135 lb" in result.content
    assert "bust 33 in" in result.content
    assert "underbust 30 in" in result.content
    assert "waist 26 in" in result.content
    assert "hips 37 in" in result.content
    assert "warm ivory skin" in result.content
    assert "deep crimson hair" in result.content
    assert "dark violet tail" in result.content
    assert "legs & feet" not in result.content.casefold()
    assert "ground me" not in result.content.casefold()
    assert "language model" not in result.content.casefold()


def test_body_description_recognizes_common_build_wording():
    for query in (
        "what does your body look like?",
        "what's your build?",
        "describe your figure",
        "tell me about your body",
    ):
        result = answer(query)
        assert result.recognized
        assert "67 in" in result.content
        assert "26 in" in result.content
        assert "37 in" in result.content


def test_outfit_contradiction_followup_uses_current_private_state():
    embodiment, projection, _ = sources()
    nude = replace(
        projection,
        attire=AttireMode.NUDE,
        outfit_id=None,
        item_ids=(),
        item_names=(),
        private_fallback_used=False,
    )
    resolver = AvatarSelfFactResolver()

    result = resolver.resolve(
        "but I thought you were naked",
        embodiment=embodiment,
        presentation=nude,
    )

    assert resolver.allows_private_projection(
        "but I thought you were naked"
    )
    assert result.recognized
    assert "authoritative current private AVATAR presentation is nude" in (
        result.content
    )
    assert "not wearing clothing" in result.content


def test_outfit_contradiction_followup_reports_current_clothed_state():
    result = answer("you said you were still wearing clothes")

    assert result.recognized
    assert "authoritative current AVATAR presentation is clothed" in (
        result.content
    )
    assert "day engineer outfit" in result.content


def test_combined_mind_and_outfit_question_still_recognizes_outfit_fact():
    result = answer(
        "Just wondering what's on your mind and what are you wearing"
    )

    assert result.recognized
    assert "day engineer outfit" in result.content



def test_generic_why_did_you_pick_that_uses_persisted_avatar_reason():
    embodiment, projection, _ = sources()
    nude = replace(
        projection,
        audience=AudienceScope.PRIVATE,
        attire=AttireMode.NUDE,
        outfit_id=None,
        item_ids=(),
        item_names=(),
        private_fallback_used=False,
        reason="user_clothing_action:undress",
    )

    resolver = AvatarSelfFactResolver()
    assert resolver.allows_private_projection("why did you pick that?")

    result = resolver.resolve(
        "why did you pick that?",
        embodiment=embodiment,
        presentation=nude,
    )

    assert result.recognized
    assert "didn't independently pick an outfit" in result.content
    assert "explicit clothing action" in result.content
    assert "tone" not in result.content.casefold()


def test_generic_why_did_you_pick_that_explains_contextual_outfit():
    embodiment, projection, _ = sources()
    lounge = replace(
        projection,
        outfit_id="night.lounge",
        item_names=("Oversized late-night lounge T-shirt", "Fitted circuit running shorts"),
        reason=(
            "headless_daily_context:covered_candidate,season_and_activity,"
            "late_lounge,modeled_emotion_influence"
        ),
    )

    result = AvatarSelfFactResolver().resolve(
        "why did you pick that?",
        embodiment=embodiment,
        presentation=lounge,
    )

    assert result.recognized
    assert "trusted local clock" in result.content
    assert "grounded season and current activity" in result.content
    assert "bounded style preference" in result.content



def test_generic_what_is_your_outfit_is_deterministic_authoritative_fact():
    result = answer("what is your outfit")

    assert result.recognized
    assert result.content.startswith("I'm in my day engineer outfit right now.")
    assert "Fitted technical long-sleeve top" in result.content
    assert "Articulated utility trousers" in result.content
    assert "shock-absorbing" not in result.content.casefold()
    assert "everything is maintained" not in result.content.casefold()
