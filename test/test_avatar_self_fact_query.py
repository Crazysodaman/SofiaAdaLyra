from __future__ import annotations

from dataclasses import replace

from sofia.avatar.presentation import (
    AppearanceState,
    AudienceScope,
    PresentationAuthority,
)
from sofia.avatar.self_fact_query import AvatarSelfFactResolver
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
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
        canonical_daily_outfit_id="engineer.signature",
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
    assert result.content.startswith("I'm in my signature engineer outfit right now.")
    assert "Fitted long-sleeve technical shirt" in result.content
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
    assert "signature engineer outfit" in result.content


def test_avatar_form_is_not_denied_or_misrepresented_as_biological():
    result = answer("Do you have a physical form or avatar?")
    assert result.recognized
    assert "canonical representational human-form avatar/body" in result.content
    assert "not a biological physical body" in result.content


def test_tonight_question_proposes_lounge_without_claiming_change():
    result = answer("What outfit would you want to change into tonight?")
    assert result.recognized
    assert "relaxed lounge outfit" in result.content
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
    assert "signature engineer outfit" in result.content
    assert "outfit ID: engineer.signature" in result.content
    assert "deep crimson hair" in result.content
    assert "dark violet tail" in result.content
    assert "style tags: canonical, engineer" in result.content


def test_direct_current_outfit_uses_human_readable_piece_names():
    embodiment, current, _ = sources()
    seasonal = replace(
        current,
        outfit_id="seasonal.spring.normal.01",
        item_names=(
            "Breathable underlayer",
            "Base undergarment",
            "Classic Top",
            "Utility Bottom",
        ),
    )
    result = AvatarSelfFactResolver().resolve(
        "what are you wearing",
        embodiment=embodiment,
        presentation=seasonal,
        available_outfit_ids=("seasonal.spring.normal.01",),
    )
    assert result.recognized
    assert "Spring Everyday 01" in result.content
    assert "Classic Top" in result.content
    assert "Utility Bottom" in result.content



def test_current_outfit_recognizes_chat_shorthand():
    for query in (
        "what are u wearing",
        "what r u wearing",
    ):
        result = answer(query)
        assert result.recognized
        assert "signature engineer outfit" in result.content


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
    assert "signature engineer outfit" in result.content
    assert "Fitted long-sleeve technical shirt" in result.content
    assert "feels" not in result.content.casefold()


def test_tonight_lounge_outfit_live_wording_is_deterministic():
    for query in (
        "what would tonights lounge outfit be?",
        "what would tonight's lounge outfit be?",
    ):
        result = answer(query)
        assert result.recognized
        assert "relaxed lounge outfit" in result.content
        assert "not something I've already changed into" in result.content
        assert "wool" not in result.content.casefold()
        assert "feel" not in result.content.casefold()
