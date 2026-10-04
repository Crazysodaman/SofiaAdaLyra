"""Production wardrobe fit metadata contracts."""
import pytest

from sofia.avatar.fit import (
    BodyContractError, BodyRegion, DEFAULT_FIT_ANCHORS, FitAnchor, REGION_TO_SLOTS,
)
from sofia.avatar.wardrobe import SLOTS
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def test_region_to_existing_slots_complete_and_separate():
    assert set(REGION_TO_SLOTS) == set(BodyRegion)
    assert {slot for value in REGION_TO_SLOTS.values() for slot in value} <= SLOTS
    assert REGION_TO_SLOTS[BodyRegion.TAIL_ROOT] == ("tail",)
    assert REGION_TO_SLOTS[BodyRegion.PERINEUM] == ("pelvis",)
    assert REGION_TO_SLOTS[BodyRegion.BUTTOCKS] == ("pelvis",)


def test_tail_opening_does_not_attach_to_perineum():
    anchor = next(item for item in DEFAULT_FIT_ANCHORS if item.name == "tail.opening.clearance")
    assert anchor.region == BodyRegion.TAIL_ROOT and anchor.slot == "tail"
    assert all(item.region is not BodyRegion.PERINEUM for item in DEFAULT_FIT_ANCHORS)


def test_mismatched_slot_and_anatomical_landmark_anchor_rejected():
    with pytest.raises(BodyContractError):
        FitAnchor("wrong.tail", BodyRegion.TAIL_ROOT, "pelvis")
    with pytest.raises(BodyContractError):
        FitAnchor("vulva", BodyRegion.PELVIS, "pelvis")


def test_every_starter_blueprint_uses_declared_body_fit_anchors():
    known = {anchor.name for anchor in DEFAULT_FIT_ANCHORS}
    catalog = build_starter_wardrobe()
    for blueprint in catalog.blueprints:
        assert set(blueprint.fit_anchors) <= known


def test_fit_anchor_names_are_unique_and_references_have_no_geometry_authority():
    assert len({anchor.name for anchor in DEFAULT_FIT_ANCHORS}) == len(DEFAULT_FIT_ANCHORS)
    for anchor in DEFAULT_FIT_ANCHORS:
        assert anchor.slot in SLOTS
        assert not hasattr(anchor, "position")
        assert not hasattr(anchor, "permission")
