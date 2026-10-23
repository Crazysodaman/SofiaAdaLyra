"""Body-region mappings and validated fit anchors for wardrobe blueprints.

These are design references, without geometry, renderer or state authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


class BodyContractError(ValueError):
    """Reject malformed or incompatible authoring metadata."""


class BodyRegion(str, Enum):
    HEAD = "head"
    FACE = "face"
    NECK = "neck"
    CHEST = "chest"
    ABDOMEN = "abdomen"
    BACK = "back"
    PELVIS = "pelvis"
    BUTTOCKS = "buttocks"
    PERINEUM = "perineum"
    LEFT_SHOULDER = "left_shoulder"
    RIGHT_SHOULDER = "right_shoulder"
    LEFT_UPPER_ARM = "left_upper_arm"
    RIGHT_UPPER_ARM = "right_upper_arm"
    LEFT_FOREARM = "left_forearm"
    RIGHT_FOREARM = "right_forearm"
    LEFT_WRIST = "left_wrist"
    RIGHT_WRIST = "right_wrist"
    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"
    LEFT_THIGH = "left_thigh"
    RIGHT_THIGH = "right_thigh"
    LEFT_CALF = "left_calf"
    RIGHT_CALF = "right_calf"
    LEFT_ANKLE = "left_ankle"
    RIGHT_ANKLE = "right_ankle"
    LEFT_FOOT = "left_foot"
    RIGHT_FOOT = "right_foot"
    LEFT_FOX_EAR = "left_fox_ear"
    RIGHT_FOX_EAR = "right_fox_ear"
    TAIL_ROOT = "tail_root"
    TAIL_SHAFT = "tail_shaft"
    TAIL_TIP = "tail_tip"


class AuthoringLandmark(str, Enum):
    """Required external authoring details; no geometry or interactive API."""
    LEFT_NIPPLE = "left_nipple"
    RIGHT_NIPPLE = "right_nipple"
    VULVA = "vulva"
    ANUS = "anus"
    TAIL_ROOT = "tail_root"


REQUIRED_AUTHORING_LANDMARKS = frozenset(AuthoringLandmark)

# Mapping expresses garment FIT only, not geometric coverage, interaction, or
# physical equivalence. The existing wardrobe slots retain their exact names.
REGION_TO_SLOTS: dict[BodyRegion, tuple[str, ...]] = {
    BodyRegion.HEAD: ("head",), BodyRegion.FACE: ("head",),
    BodyRegion.NECK: ("neck",), BodyRegion.CHEST: ("torso",),
    BodyRegion.ABDOMEN: ("torso",), BodyRegion.BACK: ("back", "torso"),
    BodyRegion.PELVIS: ("pelvis", "waist"),
    BodyRegion.BUTTOCKS: ("pelvis",), BodyRegion.PERINEUM: ("pelvis",),
    BodyRegion.LEFT_SHOULDER: ("shoulders",),
    BodyRegion.RIGHT_SHOULDER: ("shoulders",),
    BodyRegion.LEFT_UPPER_ARM: ("upper_arms",),
    BodyRegion.RIGHT_UPPER_ARM: ("upper_arms",),
    BodyRegion.LEFT_FOREARM: ("left_forearm", "forearms"),
    BodyRegion.RIGHT_FOREARM: ("right_forearm", "forearms"),
    BodyRegion.LEFT_WRIST: ("left_wrist", "wrists"),
    BodyRegion.RIGHT_WRIST: ("right_wrist", "wrists"),
    BodyRegion.LEFT_HAND: ("left_hand", "hands"),
    BodyRegion.RIGHT_HAND: ("right_hand", "hands"),
    BodyRegion.LEFT_THIGH: ("left_thigh", "thighs", "legs"),
    BodyRegion.RIGHT_THIGH: ("right_thigh", "thighs", "legs"),
    BodyRegion.LEFT_CALF: ("left_calf", "calves", "legs"),
    BodyRegion.RIGHT_CALF: ("right_calf", "calves", "legs"),
    BodyRegion.LEFT_ANKLE: ("ankles", "feet"),
    BodyRegion.RIGHT_ANKLE: ("ankles", "feet"),
    BodyRegion.LEFT_FOOT: ("left_foot", "feet"),
    BodyRegion.RIGHT_FOOT: ("right_foot", "feet"),
    BodyRegion.LEFT_FOX_EAR: ("left_ear", "ears"),
    BodyRegion.RIGHT_FOX_EAR: ("right_ear", "ears"),
    BodyRegion.TAIL_ROOT: ("tail",), BodyRegion.TAIL_SHAFT: ("tail",),
    BodyRegion.TAIL_TIP: ("tail",),
}


@dataclass(frozen=True, slots=True)
class FitAnchor:
    """Named authoring reference. Position, rig binding and geometry are TBD."""
    name: str
    region: BodyRegion
    slot: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _ID.fullmatch(self.name):
            raise BodyContractError("invalid anchor ID")
        if not isinstance(self.region, BodyRegion):
            raise BodyContractError("unknown anchor region")
        if self.slot not in REGION_TO_SLOTS[self.region]:
            raise BodyContractError("anchor slot must fit its body region")
        if self.name in {landmark.value for landmark in AuthoringLandmark}:
            raise BodyContractError("anatomical landmarks cannot be garment anchors")


DEFAULT_FIT_ANCHORS = (
    FitAnchor("shoulder.left", BodyRegion.LEFT_SHOULDER, "shoulders"),
    FitAnchor("shoulder.right", BodyRegion.RIGHT_SHOULDER, "shoulders"),
    FitAnchor("torso.front", BodyRegion.CHEST, "torso"),
    FitAnchor("torso.back", BodyRegion.BACK, "back"),
    FitAnchor("waist.front", BodyRegion.PELVIS, "waist"),
    FitAnchor("pelvis.coverage", BodyRegion.PELVIS, "pelvis"),
    FitAnchor("forearm.left", BodyRegion.LEFT_FOREARM, "left_forearm"),
    FitAnchor("forearm.right", BodyRegion.RIGHT_FOREARM, "right_forearm"),
    FitAnchor("wrist.left", BodyRegion.LEFT_WRIST, "left_wrist"),
    FitAnchor("wrist.right", BodyRegion.RIGHT_WRIST, "right_wrist"),
    FitAnchor("foot.left", BodyRegion.LEFT_FOOT, "left_foot"),
    FitAnchor("foot.right", BodyRegion.RIGHT_FOOT, "right_foot"),
    FitAnchor("thigh.left", BodyRegion.LEFT_THIGH, "left_thigh"),
    FitAnchor("thigh.right", BodyRegion.RIGHT_THIGH, "right_thigh"),
    FitAnchor("calf.left", BodyRegion.LEFT_CALF, "left_calf"),
    FitAnchor("calf.right", BodyRegion.RIGHT_CALF, "right_calf"),
    FitAnchor("head.crown", BodyRegion.HEAD, "head"),
    FitAnchor("neck.center", BodyRegion.NECK, "neck"),
    FitAnchor("ear.left", BodyRegion.LEFT_FOX_EAR, "left_ear"),
    FitAnchor("ear.right", BodyRegion.RIGHT_FOX_EAR, "right_ear"),
    FitAnchor("ear.left.clearance", BodyRegion.LEFT_FOX_EAR, "ears"),
    FitAnchor("ear.right.clearance", BodyRegion.RIGHT_FOX_EAR, "ears"),
    FitAnchor("tail.opening.clearance", BodyRegion.TAIL_ROOT, "tail"),
    FitAnchor("tail.base", BodyRegion.TAIL_ROOT, "tail"),
    FitAnchor("tail.mid", BodyRegion.TAIL_SHAFT, "tail"),
)
