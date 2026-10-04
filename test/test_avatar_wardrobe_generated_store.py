"""Generated wardrobe ownership requires Sofía's own acceptance."""
import json

from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import GraphicDesign
from sofia.avatar.wardrobe_generated_store import (
    GeneratedWardrobeStore,
    SofiaGarmentAcceptance,
    SofiaGarmentDecision,
    generated_wardrobe_path,
)


def _draft(studio):
    return studio.design_piece(
        GarmentDesignRequest(
            item_id="generated.sofia.soft_tee",
            name="Sofía soft generated tee",
            garment_type="t_shirt",
            fit="relaxed",
            rise=None,
            length="hip",
            sleeve_length="short",
            material="soft cotton-modal knit",
            primary="black",
            accent="dark_violet",
            pattern="solid",
            graphic=GraphicDesign(),
            features=("soft_hem",),
            style_tags=("generated", "casual"),
            description="A generated soft black tee with violet trim.",
        )
    )


def test_unsure_asks_sparks_without_saving(tmp_path):
    state_path = tmp_path / "sofia.db"
    studio = WardrobeStudio(
        build_starter_wardrobe(),
        generated_store=GeneratedWardrobeStore(state_path),
    )
    result = studio.decide_generated_piece(
        _draft(studio),
        SofiaGarmentAcceptance(
            SofiaGarmentDecision.ASK_SPARKS,
            "I like the shape but I am not sure about the color.",
        ),
    )
    assert result.ask_sparks is True
    assert result.persisted is False
    assert not generated_wardrobe_path(state_path).exists()


def test_accept_persists_sofia_provenance_and_reloads(tmp_path):
    state_path = tmp_path / "sofia.db"
    studio = WardrobeStudio(
        build_starter_wardrobe(),
        generated_store=GeneratedWardrobeStore(state_path),
    )
    result = studio.decide_generated_piece(
        _draft(studio),
        SofiaGarmentAcceptance(
            SofiaGarmentDecision.ACCEPT,
            "I would actually wear this as a relaxed everyday top.",
        ),
    )
    assert result.persisted is True
    path = generated_wardrobe_path(state_path)
    row = json.loads(path.read_text(encoding="utf-8"))["garments"][0]
    assert row["acceptance"]["actor"] == "sofia"
    assert row["provenance"] == "sofia_accepted_generated_design"

    rebuilt = build_starter_wardrobe(state_path=state_path)
    accepted = next(
        bp for bp in rebuilt.blueprints
        if bp.garment.item_id == "generated.sofia.soft_tee"
    )
    assert accepted.provenance == "sofia_accepted_generated_design"
