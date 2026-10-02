"""Large individual-piece closet and private-visibility contracts."""
from dataclasses import replace

import pytest

from sofia.avatar.wardrobe import VisibilityDenied, Wardrobe
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_piece_catalog import (
    CLOSET_CATEGORIES,
    NORMAL_STYLES,
    PRIVATE_STYLES,
    generated_piece_specs,
)


def test_each_human_facing_category_has_25_normal_and_25_adult_private_pieces():
    specs = generated_piece_specs()
    assert len(CLOSET_CATEGORIES) == 18
    assert len(NORMAL_STYLES) == 25
    assert len(PRIVATE_STYLES) == 25
    assert len(specs) == 18 * 50 + 50

    for category in CLOSET_CATEGORIES:
        rows = [item for item in specs if item.category == category.category_id]
        normal = [item for item in rows if not item.private_only]
        private = [item for item in rows if item.private_only]
        assert len(normal) == 25
        assert len(private) == 25
        assert len({item.item_id for item in rows}) == 50


def test_generated_closet_is_part_of_real_starter_wardrobe_catalog():
    pack = build_starter_wardrobe()
    summary = pack.closet_summary()

    assert summary["generated_piece_count"] == 962
    assert summary["adult_private_requires_authorization"] is True
    assert summary["assets_verified"] is False
    assert len(summary["categories"]) == 20
    for category, counts in summary["categories"].items():
        if category in {"closet.bra", "closet.panty"}:
            assert counts == {"normal": 0, "adult_private": 25}
        else:
            assert counts == {"normal": 25, "adult_private": 25}


def test_private_pieces_are_first_class_private_metadata_not_name_conventions():
    pack = build_starter_wardrobe()
    private = pack.pieces(
        category="closet.underwear_top",
        private_only=True,
    )
    normal = pack.pieces(
        category="closet.underwear_top",
        private_only=False,
    )

    assert len(private) == 25
    assert len(normal) == 25
    assert all(item.private_only and item.garment.private_only for item in private)
    assert all(not item.private_only and not item.garment.private_only for item in normal)
    assert all("adult-private" in item.style_tags for item in private)


def test_private_piece_cannot_become_public_ready_even_with_fake_asset_metadata():
    pack = build_starter_wardrobe()
    private = pack.pieces(
        category="closet.one_piece",
        private_only=True,
    )[0].garment
    # Simulate a future asset reference. Privacy must still independently deny.
    rendered = replace(private, asset_ref="asset.private.one_piece")
    wardrobe = Wardrobe((rendered,))
    selection = wardrobe.selection((rendered.item_id,))

    assert selection.private_only is True
    with pytest.raises(VisibilityDenied):
        wardrobe.require_public_ready(
            selection,
            assets_verified_by_renderer=True,
        )


def test_normal_piece_categories_map_to_existing_low_level_rig_slots():
    pack = build_starter_wardrobe()
    for category in CLOSET_CATEGORIES:
        piece = pack.pieces(
            category=category.category_id,
            private_only=False,
        )[0].garment
        assert piece.slots == category.slots
        assert piece.tail_clearance is category.tail_clearance
        assert piece.ear_clearance is category.ear_clearance


def test_manifest_exposes_category_style_and_privacy_without_claiming_assets():
    manifest = build_starter_wardrobe().manifest()
    generated = [
        row for row in manifest["garments"]
        if row["category"].startswith("closet.")
    ]
    assert len(generated) == 962
    assert sum(row["private_only"] for row in generated) == 500
    assert all(row["asset_ref"] is None for row in generated)
    assert all(row["style_tags"] for row in generated)
