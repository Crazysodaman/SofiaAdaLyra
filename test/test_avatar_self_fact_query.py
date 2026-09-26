from __future__ import annotations

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
    assert "signature engineer outfit" in result.content
    assert result.content == "I'm in my signature engineer outfit right now."


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
