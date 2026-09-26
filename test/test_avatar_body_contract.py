"""A1 metadata tests: never claim actual anatomy, Blender or renderer acceptance."""
import dataclasses
import pytest

from sofia.avatar.body_contract import (
    AuthoringLandmark, BodyAuthoringContract, BodyContractError, BodyRegion,
    DEFAULT_FIT_ANCHORS, FitAnchor, REGION_TO_SLOTS,
)
from sofia.avatar.wardrobe import SLOTS


SHA = "a" * 64


def test_canonical_pinned_and_adult_female_authoring_only():
    contract = BodyAuthoringContract(SHA)
    assert contract.normal_display_clothed and contract.unclothed_authoring_only
    assert contract.adult_female_character
    assert dataclasses.is_dataclass(contract)
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.normal_display_clothed = False


@pytest.mark.parametrize("bad", ["", "a" * 63, "Z" * 64, "a" * 65])
def test_invalid_canonical_revision_rejected(bad):
    with pytest.raises(BodyContractError):
        BodyAuthoringContract(bad)


def test_required_external_landmarks_are_explicit_and_not_clothing_slots():
    contract = BodyAuthoringContract(SHA)
    assert {"left_nipple", "right_nipple", "vulva", "anus", "tail_root"} == {x.value for x in contract.landmarks}
    assert not ({x.value for x in contract.landmarks} & SLOTS)
    with pytest.raises(BodyContractError):
        BodyAuthoringContract(SHA, landmarks=frozenset({AuthoringLandmark.TAIL_ROOT}))


@pytest.mark.parametrize("field", ["adult_female_character", "normal_display_clothed", "unclothed_authoring_only"])
def test_required_design_invariants_cannot_be_downgraded(field):
    with pytest.raises(BodyContractError):
        BodyAuthoringContract(SHA, **{field: False})


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


def test_duplicate_anchor_and_unknown_slot_rejected():
    with pytest.raises(BodyContractError):
        BodyAuthoringContract(SHA, anchors=(DEFAULT_FIT_ANCHORS[0],) * 2)
    with pytest.raises(BodyContractError):
        BodyAuthoringContract(SHA).anchors_for_slot("vulva")


def test_fitting_anchors_are_authoring_references_only():
    result = BodyAuthoringContract(SHA).anchors_for_slot("left_wrist")
    assert len(result) == 1 and result[0].name == "wrist.left"
    assert not hasattr(result[0], "position")
    assert not hasattr(result[0], "permission")


def test_unsupported_revision_rejected():
    with pytest.raises(BodyContractError):
        BodyAuthoringContract(SHA, revision="a2")
