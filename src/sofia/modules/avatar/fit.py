"""Body-region mappings and validated fit anchors for wardrobe blueprints.

These are design references, without geometry, renderer or state authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Mapping

from .wardrobe_equipment import WardrobeDesign

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


class WearerFitStatus(str, Enum):
    """Metadata-only result of a shared body/rig fit gate."""

    FITTED = "fitted"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class WearerProfile:
    """External wearer facts supplied by the host; never the canonical body.

    The profile is intentionally inert.  Evaluating a design against it cannot
    mutate the Core's canonical body, measurements or rig.
    """

    body_profile: str | None
    measurements: Mapping[str, float] = field(default_factory=dict)
    anchors: tuple[str, ...] = ()
    rig_id: str | None = None
    rig_mounts: tuple[str, ...] = ()
    has_tail: bool = False
    has_ears: bool = False

    def __post_init__(self) -> None:
        if self.body_profile is not None and (
            not isinstance(self.body_profile, str)
            or _ID.fullmatch(self.body_profile) is None
        ):
            raise BodyContractError("invalid wearer body profile")
        if not isinstance(self.measurements, Mapping):
            raise BodyContractError("wearer measurements must be a mapping")
        measured: dict[str, float] = {}
        for key, value in self.measurements.items():
            if not isinstance(key, str) or _ID.fullmatch(key) is None:
                raise BodyContractError("invalid wearer measurement name")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0.0
            ):
                raise BodyContractError("wearer measurements must be positive numbers")
            measured[key] = float(value)
        object.__setattr__(self, "measurements", MappingProxyType(measured))
        for values, label in (
            (self.anchors, "wearer anchors"),
            (self.rig_mounts, "wearer rig mounts"),
        ):
            if not isinstance(values, tuple) or len(set(values)) != len(values):
                raise BodyContractError(f"{label} must be a unique tuple")
            for value in values:
                if not isinstance(value, str) or _ID.fullmatch(value) is None:
                    raise BodyContractError(f"invalid {label} entry")
        if self.rig_id is not None and (
            not isinstance(self.rig_id, str) or _ID.fullmatch(self.rig_id) is None
        ):
            raise BodyContractError("invalid wearer rig ID")
        if type(self.has_tail) is not bool or type(self.has_ears) is not bool:
            raise BodyContractError("wearer anatomy flags must be boolean")


@dataclass(frozen=True, slots=True)
class WearerFitResult:
    """Honest fit outcome; never proof of a rendered or canonical body change."""

    status: WearerFitStatus
    design_id: str
    reason: str
    body_profile: str | None = None
    evidence_ref: str | None = None
    missing_anchors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, WearerFitStatus):
            raise BodyContractError("fit status must be WearerFitStatus")
        if not isinstance(self.design_id, str) or _ID.fullmatch(self.design_id) is None:
            raise BodyContractError("invalid fit design ID")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise BodyContractError("fit reason must be nonempty text")
        if self.evidence_ref is not None and (
            not isinstance(self.evidence_ref, str)
            or _ID.fullmatch(self.evidence_ref) is None
        ):
            raise BodyContractError("invalid fit evidence reference")
        if not isinstance(self.missing_anchors, tuple) or len(
            set(self.missing_anchors)
        ) != len(self.missing_anchors):
            raise BodyContractError("missing anchors must be a unique tuple")

    @property
    def mutates_canonical_body(self) -> bool:
        return False

    @property
    def metadata_only(self) -> bool:
        return self.status is not WearerFitStatus.FITTED


def _fit_result(
    design: WardrobeDesign,
    wearer: WearerProfile,
    status: WearerFitStatus,
    reason: str,
    *,
    evidence_ref: str | None = None,
    missing_anchors: tuple[str, ...] = (),
) -> WearerFitResult:
    return WearerFitResult(
        status=status,
        design_id=design.design_id,
        reason=reason,
        body_profile=wearer.body_profile,
        evidence_ref=evidence_ref,
        missing_anchors=missing_anchors,
    )


def evaluate_wearer_fit(
    design: WardrobeDesign,
    wearer: WearerProfile,
    *,
    evidence_ref: str | None = None,
    asset_verified: bool = False,
) -> WearerFitResult:
    """Evaluate one design against an external wearer without mutating the body.

    ``FITTED`` is only returned when a reviewed asset reference, an explicitly
    verified asset, matching body/rig anchors, anatomy clearance and an external
    renderer/fit evidence receipt all agree.  A metadata match without that
    evidence is ``UNAVAILABLE`` rather than a fabricated mesh-fit success.
    """
    if not isinstance(design, WardrobeDesign):
        raise TypeError("design must be WardrobeDesign")
    if not isinstance(wearer, WearerProfile):
        raise TypeError("wearer must be WearerProfile")
    if type(asset_verified) is not bool:
        raise TypeError("asset_verified must be boolean")
    if evidence_ref is not None and (
        not isinstance(evidence_ref, str) or _ID.fullmatch(evidence_ref) is None
    ):
        raise BodyContractError("invalid fit evidence reference")

    if wearer.body_profile is None:
        return _fit_result(
            design, wearer, WearerFitStatus.UNAVAILABLE,
            "wearer body profile is unknown; fit cannot be claimed",
        )

    if design.armor is not None:
        if wearer.body_profile not in design.armor.compatible_body_profiles:
            return _fit_result(
                design, wearer, WearerFitStatus.UNSUPPORTED,
                f"{design.design_id} is not fit-compatible with body profile "
                f"{wearer.body_profile!r}",
            )
        if wearer.rig_id is None:
            return _fit_result(
                design, wearer, WearerFitStatus.UNAVAILABLE,
                "armor fit requires an identified body/rig mount set",
            )
        if wearer.rig_mounts:
            required = design.armor.mount_id
            if required is not None and required not in wearer.rig_mounts:
                return _fit_result(
                    design, wearer, WearerFitStatus.UNSUPPORTED,
                    f"wearer rig does not expose mount {required!r}",
                )

    if wearer.has_tail and not design.tail_clearance:
        return _fit_result(
            design, wearer, WearerFitStatus.UNSUPPORTED,
            f"{design.design_id} has no reviewed tail clearance for this wearer",
        )
    if wearer.has_ears and not design.ear_clearance:
        return _fit_result(
            design, wearer, WearerFitStatus.UNSUPPORTED,
            f"{design.design_id} has no reviewed ear clearance for this wearer",
        )

    missing = tuple(
        anchor for anchor in design.fit_anchors if anchor not in wearer.anchors
    )
    if missing:
        return _fit_result(
            design, wearer, WearerFitStatus.UNSUPPORTED,
            "wearer measurements/anchors do not cover the design fit anchors",
            missing_anchors=missing,
        )

    if design.asset_ref is None:
        return _fit_result(
            design, wearer, WearerFitStatus.UNAVAILABLE,
            "no reviewed renderer asset reference; fit remains metadata-only",
        )
    if not asset_verified:
        return _fit_result(
            design, wearer, WearerFitStatus.UNAVAILABLE,
            "renderer asset is not verified installed; fit cannot be claimed",
        )
    if evidence_ref is None:
        return _fit_result(
            design, wearer, WearerFitStatus.UNAVAILABLE,
            "no external fit/rendition evidence; mesh fit cannot be claimed",
        )
    return _fit_result(
        design, wearer, WearerFitStatus.FITTED,
        "body profile, rig anchors, clearance and fit evidence agree",
        evidence_ref=evidence_ref,
    )


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
