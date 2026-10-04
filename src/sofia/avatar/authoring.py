"""AVATAR authoring contracts and wardrobe composition tools.

This module owns design-time mesh/fit contracts plus validated wardrobe
composition and garment blueprint authoring. It does not render, infer user
preferences, grant private access, or claim that authored pieces are worn.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .wardrobe import SLOTS

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
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


@dataclass(frozen=True, slots=True)
class BodyAuthoringContract:
    """Reviewed *requirements* for one adult female base, not a finished model."""
    canonical_avatar_sha256: str
    revision: str = "a1.body-contract.v1"
    adult_female_character: bool = True
    landmarks: frozenset[AuthoringLandmark] = REQUIRED_AUTHORING_LANDMARKS
    anchors: tuple[FitAnchor, ...] = DEFAULT_FIT_ANCHORS
    normal_display_clothed: bool = True
    unclothed_authoring_only: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_avatar_sha256, str) or not _SHA256.fullmatch(self.canonical_avatar_sha256):
            raise BodyContractError("canonical avatar must be pinned to a SHA-256")
        if self.revision != "a1.body-contract.v1":
            raise BodyContractError("unsupported body contract revision")
        if self.adult_female_character is not True or self.normal_display_clothed is not True or self.unclothed_authoring_only is not True:
            raise BodyContractError("adult female authoring and clothed display requirements cannot be disabled")
        if not isinstance(self.landmarks, frozenset) or not REQUIRED_AUTHORING_LANDMARKS.issubset(self.landmarks) or any(not isinstance(item, AuthoringLandmark) for item in self.landmarks):
            raise BodyContractError("required external authoring landmarks are missing")
        if not isinstance(self.anchors, tuple) or any(not isinstance(anchor, FitAnchor) for anchor in self.anchors):
            raise BodyContractError("anchors must be typed")
        if len({anchor.name for anchor in self.anchors}) != len(self.anchors):
            raise BodyContractError("duplicate garment anchor ID")
        if any(slot not in SLOTS for slots in REGION_TO_SLOTS.values() for slot in slots):
            raise BodyContractError("body mapping contains an unsupported wardrobe slot")
        if set(REGION_TO_SLOTS) != set(BodyRegion):
            raise BodyContractError("unmapped body region")

    def anchors_for_slot(self, slot: str) -> tuple[FitAnchor, ...]:
        if not isinstance(slot, str) or slot not in SLOTS:
            raise BodyContractError("unknown clothing slot")
        return tuple(anchor for anchor in self.anchors if anchor.slot == slot)


from dataclasses import dataclass

from .presentation import PresentationAuthority
from .presentation_store import PresentationStore
from .wardrobe import Garment, WardrobeError
from .wardrobe_planner import Activity, OutfitPlan, Season


@dataclass(frozen=True, slots=True)
class GarmentDesignRequest:
    item_id: str
    name: str
    category_id: str
    primary_hex: str
    material: str
    style_tags: tuple[str, ...]
    private_only: bool = False


class WardrobeStudio:
    """Compose outfits and propose new garment blueprints from typed inputs."""

    def __init__(
        self,
        catalog: WardrobePrebuild,
        *,
        authority: PresentationAuthority | None = None,
        store: PresentationStore | None = None,
    ) -> None:
        from .wardrobe_catalog import WardrobePrebuild, all_closet_categories

        if not isinstance(catalog, WardrobePrebuild):
            raise TypeError("catalog must be WardrobePrebuild")
        if authority is not None and not isinstance(authority, PresentationAuthority):
            raise TypeError("authority must be PresentationAuthority or None")
        if store is not None and not isinstance(store, PresentationStore):
            raise TypeError("store must be PresentationStore or None")
        if store is not None and authority is None:
            raise ValueError("store requires live presentation authority")
        self.catalog = catalog
        self.authority = authority
        self.store = store
        self._categories = {
            category.category_id: category
            for category in all_closet_categories()
        }

    def compose(
        self,
        *,
        outfit_id: str,
        item_ids: tuple[str, ...],
        activities: frozenset[Activity],
        seasons: frozenset[Season],
        lounge: bool = False,
        private_only: bool = False,
        style_tags: tuple[str, ...] = (),
        display_name: str | None = None,
        manual_only: bool = False,
        register: bool = False,
    ) -> OutfitPlan:
        if type(register) is not bool:
            raise WardrobeError("register must be boolean")
        selected = self.catalog.wardrobe.selection(item_ids)
        if not private_only:
            if selected.private_only:
                raise WardrobeError(
                    "public composition cannot contain private-only pieces"
                )
            if not selected.covered_default:
                raise WardrobeError(
                    "public composition must cover torso and pelvis"
                )
        plan = OutfitPlan(
            outfit_id,
            item_ids,
            activities,
            seasons,
            lounge=lounge,
            private_only=private_only,
            style_tags=style_tags,
            display_name=display_name,
            manual_only=manual_only,
        )
        if register:
            if self.authority is None:
                raise WardrobeError(
                    "registered composition requires live presentation authority"
                )

            def mutate() -> None:
                self.authority.register_outfit(
                    outfit_id=plan.outfit_id,
                    item_ids=plan.item_ids,
                    private_only=plan.private_only,
                )

            if self.store is None:
                # Standalone authoring callers may intentionally work only in
                # memory and serialize the authority snapshot themselves.
                mutate()
            else:
                # Production application wiring supplies the canonical store,
                # so live registration is durable-or-rollback.
                self.store.persist_mutation(
                    self.authority,
                    mutate,
                )
        return plan

    def design_piece(
        self,
        request: GarmentDesignRequest,
    ) -> "GarmentBlueprint":
        from .wardrobe_catalog import GarmentBlueprint

        if not isinstance(request, GarmentDesignRequest):
            raise TypeError("request must be GarmentDesignRequest")
        try:
            category = self._categories[request.category_id]
        except KeyError as exc:
            raise WardrobeError("unknown closet category") from exc
        if category.category_id in {"closet.bra", "closet.panty"} and not request.private_only:
            raise WardrobeError("bra/panty design proposals are private-only in this catalog")
        coverage = () if request.private_only else category.coverage
        garment = Garment(
            request.item_id,
            request.name,
            category.layer,
            category.slots,
            coverage,
            tail_clearance=category.tail_clearance,
            ear_clearance=category.ear_clearance,
            asset_ref=None,
            private_only=request.private_only,
        )
        return GarmentBlueprint(
            garment=garment,
            primary_hex=request.primary_hex,
            accent_hexes=(),
            material=request.material,
            construction=(
                "Sofía-generated wardrobe design proposal; no renderer asset exists yet.",
                "A separate asset-build/verification path is required before visual claims.",
            ),
            fit_anchors=category.fit_anchors,
            category=category.category_id,
            style_tags=request.style_tags,
            private_only=request.private_only,
        )
