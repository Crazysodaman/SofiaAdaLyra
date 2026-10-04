"""Accessory catalog contracts for Sofía's owned wardrobe."""
from collections import Counter

from sofia.avatar.wardrobe import Layer
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import ContentRating
from sofia.avatar.wardrobe_types import GarmentFamily, garment_type


PREFIXES = {
    "legwear.": GarmentFamily.LEGWEAR,
    "hand.": GarmentFamily.ACCESSORY,
    "waist.": GarmentFamily.ACCESSORY,
    "ear.": GarmentFamily.ACCESSORY,
    "tail.": GarmentFamily.ACCESSORY,
    "neck.": GarmentFamily.ACCESSORY,
}


def _pieces_for_prefix(pack, prefix):
    return tuple(
        blueprint
        for blueprint in pack.blueprints
        if blueprint.garment.item_id.startswith(prefix)
    )


def test_each_accessory_category_has_twenty_standard_two_lewd_two_explicit():
    pack = build_starter_wardrobe()

    for prefix in PREFIXES:
        pieces = _pieces_for_prefix(pack, prefix)
        assert len(pieces) == 24
        counts = Counter(piece.content_rating for piece in pieces)
        assert counts == {
            ContentRating.STANDARD: 20,
            ContentRating.LEWD: 2,
            ContentRating.EXPLICIT: 2,
        }
        assert all(
            piece.private_only
            for piece in pieces
            if piece.content_rating is not ContentRating.STANDARD
        )
        assert all(
            not piece.private_only
            for piece in pieces
            if piece.content_rating is ContentRating.STANDARD
        )


def test_accessory_catalogs_use_expected_families_and_accessory_layer():
    pack = build_starter_wardrobe()

    for prefix, family in PREFIXES.items():
        pieces = _pieces_for_prefix(pack, prefix)
        assert pieces
        for piece in pieces:
            definition = garment_type(piece.design.garment_type)
            assert definition.family is family
            assert definition.layer is Layer.ACCESSORY


def test_one_standard_piece_from_each_category_can_layer_over_safe_fallback():
    pack = build_starter_wardrobe()
    fallback = pack.preset("fallback.covered")

    extras = tuple(
        _pieces_for_prefix(pack, prefix)[0].garment.item_id
        for prefix in PREFIXES
    )
    selection = pack.wardrobe.selection(fallback.item_ids + extras)

    assert selection.covered_default is True
    assert selection.private_only is False


def test_private_accessories_are_not_part_of_automatic_saved_outfits():
    pack = build_starter_wardrobe()
    automatic_ids = {
        item_id
        for plan in pack.presets
        if not plan.private_only and not plan.manual_only
        for item_id in plan.item_ids
    }

    for prefix in PREFIXES:
        for piece in _pieces_for_prefix(pack, prefix):
            if piece.private_only:
                assert piece.garment.item_id not in automatic_ids
