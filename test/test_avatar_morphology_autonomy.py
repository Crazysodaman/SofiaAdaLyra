"""Regression contract: canonical body vs. reversible avatar presentation."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from sofia.avatar.presentation import (
    AppearanceState, AudienceScope, PresentationAuthority, PresentationError,
)
from sofia.avatar.presentation_store import PresentationStore
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.core.embodiment.model import Measurement
from sofia.core.embodiment.store import EmbodimentStore


SEED = Path(__file__).resolve().parents[1] / "src/sofia/core/embodiment/avatar.json"


def baseline():
    return EmbodimentStore(SEED).load()


def authority():
    wardrobe = build_starter_wardrobe()
    outfits = {preset.outfit_id: preset.item_ids for preset in wardrobe.presets}
    presentation = PresentationAuthority(
        wardrobe.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="day.default",
        initial_appearance=AppearanceState(
            "long layered", "#8B1E3F", "#3A245C", eye_color="violet",
        ),
    )
    return wardrobe.wardrobe, outfits, presentation


def test_canonical_morphology_is_uninvented_and_original_figures_unchanged():
    physical = baseline().physical_self
    measures = dict(physical.measurements)
    assert {key: measures[key].value for key in (
        "height", "weight", "bust", "underbust", "waist", "hips"
    )} == {
        "height": 67, "weight": 135, "bust": 33,
        "underbust": 30, "waist": 26, "hips": 37,
    }
    assert len(measures) == 22
    assert measures["neck_circumference"].value is None
    assert measures["fox_tail_length"].value is None
    assert measures["shoe_size"].unit == "US_womens"
    assert dict(physical.anatomy)["limbs"] == "2 arms, 2 legs"
    assert dict(physical.appearance)["eye_color"] == "violet"


def test_private_metadata_round_trip_but_not_public_appearance(tmp_path):
    original = baseline()
    colors = dict(original.physical_self.private_anatomy)
    assert colors == {
        "nipple_color": None, "vulva_color": None, "anus_color": None
    }
    copy = EmbodimentStore(tmp_path / "avatar.json")
    copy.save(original)
    loaded = copy.load()
    assert loaded == original
    assert dict(loaded.physical_self.appearance).get("nipple_color") is None
    _, _, presentation = authority()
    public = presentation.projection(AudienceScope.PUBLIC)
    snapshot = presentation.snapshot()
    assert "private_anatomy" not in str(snapshot)
    assert "nipple_color" not in str(public)
    assert "anus_color" not in str(public)


def test_stable_topology_rejects_modifying_number_of_ears_tails_or_limbs():
    original = baseline().physical_self
    for field, value in (
        ("ears", "3 fox ears"),
        ("tail", "2 fox tails"),
        ("limbs", "4 arms, 2 legs"),
    ):
        altered = dict(original.anatomy)
        altered[field] = value
        with pytest.raises(ValueError, match="topology"):
            replace(original, anatomy=tuple(altered.items()))


def test_optional_measurements_reject_boolean_and_nonfinite():
    assert Measurement(None, "in").value is None
    for value in (True, float("nan"), float("inf"), "12"):
        with pytest.raises(TypeError):
            Measurement(value, "in")


def test_reversible_styles_persist_after_restart_and_legacy_restore(tmp_path):
    wardrobe, outfits, state = authority()
    style = AppearanceState(
        hairstyle="short braid", hair_color="#622A87", tail_color="#3A245C",
        hair_length="shoulder", hair_design="braided", eye_color="#AC69EE",
        posture="hip-pop", ear_pose="perked", tail_pose="raised",
        expression="curious", fur_style="fluffy", makeup="soft violet",
        freckles="light", tattoos=("left shoulder star",),
        piercings=("left ear stud",),
    )
    store = PresentationStore(tmp_path / "sofia.db")
    store.save(state)

    def change():
        state.propose_appearance(
            operation_id="op.avatar.autonomy", expected_revision=state.current.revision,
            appearance=style, reason="selected a favorite autumn look",
        )
        return state.commit_text(
            operation_id="op.avatar.autonomy", renderer_unavailable=True,
        )

    store.persist_mutation(state, change)
    restored = store.load(wardrobe, outfits=outfits)
    assert restored.current.appearance == style
    assert restored.projection(AudienceScope.PUBLIC).appearance == style
    assert store.recent_appearance_history()[0]["reason"] == "selected a favorite autumn look"

    old = restored.snapshot()
    for record in ("current", "last_daily"):
        for field in (
            "hair_length", "hair_design", "eye_color", "posture", "ear_pose",
            "tail_pose", "expression", "fur_style", "makeup", "freckles",
            "tattoos", "piercings",
        ):
            old[record]["appearance"].pop(field)
    legacy = PresentationAuthority.restore(wardrobe, outfits=outfits, snapshot=old)
    assert legacy.current.appearance.eye_color is None
    assert legacy.current.appearance.tattoos == ()


def test_favorites_are_reversible_and_do_not_change_active_look(tmp_path):
    _, _, state = authority()
    store = PresentationStore(tmp_path / "sofia.db")
    favorite = replace(
        state.current.appearance,
        hair_color="#722CA0", eye_color="#A976EC",
        tattoos=("temporary wrist mark",), piercings=("silver stud",),
    )
    store.save_style_favorite(name="violet weekend", appearance=favorite)
    assert store.list_style_favorites()["violet weekend"] == favorite
    assert state.current.appearance != favorite
    assert store.delete_style_favorite("violet weekend") is True
    assert store.list_style_favorites() == {}


def test_bad_cosmetic_input_cannot_poison_snapshots():
    with pytest.raises(PresentationError):
        AppearanceState("layered", "crimson", "violet", eye_color="#GGGGGG")
    with pytest.raises(PresentationError):
        AppearanceState("layered", "crimson", "violet", tattoos=("x", "x"))
    with pytest.raises(PresentationError):
        AppearanceState("layered", "crimson", "violet", piercings=("unsafe\ntext",))
    with pytest.raises(PresentationError):
        AppearanceState("layered", "crimson", "violet", posture="sit\nstand")
