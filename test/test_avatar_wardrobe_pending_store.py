import pytest

"""Pending generated wardrobe state is durable but never owned."""
from pathlib import Path

from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_design import GraphicDesign
from sofia.avatar.wardrobe_generated_store import (
    SofiaGarmentAcceptance,
    SofiaGarmentDecision,
    generated_wardrobe_path,
)
from sofia.avatar.wardrobe_pending_store import (
    PendingGeneratedWardrobeStore,
    pending_generated_wardrobe_path,
)


def _blueprint():
    return WardrobeStudio(build_starter_wardrobe()).design_piece(
        GarmentDesignRequest(
            item_id="generated.sofia.pending_violet_tee",
            name="Pending Violet Tee",
            garment_type="t_shirt",
            fit="relaxed",
            rise=None,
            length="hip",
            sleeve_length="short",
            material="soft cotton-modal knit",
            primary="dark_violet",
            accent="cyan",
            pattern="solid",
            graphic=GraphicDesign(),
            features=("soft_hem",),
            style_tags=("casual", "violet"),
            description="A pending violet tee awaiting preference input.",
        )
    )


def test_pending_ask_survives_reload_without_entering_owned_wardrobe(tmp_path):
    state_path = tmp_path / "sofia.db"
    store = PendingGeneratedWardrobeStore(state_path)
    blueprint = _blueprint()
    acceptance = SofiaGarmentAcceptance(
        SofiaGarmentDecision.ASK_SPARKS,
        "I like it, but I want Sparks' opinion before I decide.",
    )

    store.save(blueprint, acceptance)
    pending = PendingGeneratedWardrobeStore(state_path).load()

    assert pending is not None
    assert pending.blueprint.garment.item_id == blueprint.garment.item_id
    assert pending.reason == acceptance.reason
    assert pending_generated_wardrobe_path(state_path).is_file()
    assert not generated_wardrobe_path(state_path).exists()

    rebuilt = build_starter_wardrobe(state_path=state_path)
    assert blueprint.garment.item_id not in {
        item.garment.item_id for item in rebuilt.blueprints
    }


def test_pending_store_clears_only_matching_piece(tmp_path):
    state_path = tmp_path / "sofia.db"
    store = PendingGeneratedWardrobeStore(state_path)
    blueprint = _blueprint()
    store.save(
        blueprint,
        SofiaGarmentAcceptance(
            SofiaGarmentDecision.ASK_SPARKS,
            "I want another opinion.",
        ),
    )

    assert store.clear(item_id="generated.sofia.other") is False
    assert store.load() is not None
    assert store.clear(item_id=blueprint.garment.item_id) is True
    assert store.load() is None


def test_pending_store_refuses_to_overwrite_different_question(tmp_path):
    state_path = tmp_path / "sofia.db"
    store = PendingGeneratedWardrobeStore(state_path)
    first = _blueprint()
    store.save(
        first,
        SofiaGarmentAcceptance(
            SofiaGarmentDecision.ASK_SPARKS,
            "I want Sparks' opinion on this one.",
        ),
    )
    studio = WardrobeStudio(build_starter_wardrobe())
    second = studio.design_piece(
        GarmentDesignRequest(
            item_id="generated.sofia.pending_second_tee",
            name="Second Pending Tee",
            garment_type="t_shirt",
            fit="relaxed",
            rise=None,
            length="hip",
            sleeve_length="short",
            material="soft cotton knit",
            primary="black",
            accent="cyan",
            pattern="solid",
            graphic=GraphicDesign(),
            features=("soft_hem",),
            style_tags=("casual",),
            description="A second proposal that must not replace the first.",
        )
    )

    with pytest.raises(WardrobeError, match="already awaiting Sparks"):
        store.save(
            second,
            SofiaGarmentAcceptance(
                SofiaGarmentDecision.ASK_SPARKS,
                "I also want Sparks' opinion on this one.",
            ),
        )

    pending = store.load()
    assert pending is not None
    assert pending.blueprint.garment.item_id == first.garment.item_id
