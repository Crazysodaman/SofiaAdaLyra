"""Offline garment blueprints and covered outfit presets for Sofía.

These are design proposals, not mesh assets or evidence that anything is worn.
Canonical clothing details are transcribed as authoring targets; lounge/fallback
colors and construction remain proposed until visually reviewed. No network,
renderer, file write, preference invention, or LLM action occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .wardrobe import Garment, Layer, Wardrobe, WardrobeError
from .wardrobe_routine import Activity, OutfitPlan, Season

_HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
DRAFT_STATUS = "proposed_no_mesh_no_verified_asset"
ALL_SEASONS = frozenset(Season)


class RequestStatus(str, Enum):
    USER_REQUESTED = "user_requested"
    USER_LIKED = "user_liked"
    USER_DISLIKED = "user_disliked"


@dataclass(frozen=True, slots=True)
class GarmentBlueprint:
    garment: Garment
    primary_hex: str
    accent_hexes: tuple[str, ...]
    material: str
    construction: tuple[str, ...]
    fit_anchors: tuple[str, ...]
    provenance: str = "design_proposal_review_required"

    def __post_init__(self) -> None:
        if not isinstance(self.garment, Garment) or self.garment.asset_ref is not None:
            raise WardrobeError("blueprints must refer to unbuilt garment assets")
        if not isinstance(self.primary_hex, str) or not _HEX.fullmatch(self.primary_hex):
            raise WardrobeError("invalid garment primary color")
        if not isinstance(self.accent_hexes, tuple) or any(
            not isinstance(x, str) or not _HEX.fullmatch(x) for x in self.accent_hexes
        ):
            raise WardrobeError("invalid garment accent color")
        if not isinstance(self.material, str) or not self.material.strip():
            raise WardrobeError("material specification is required")
        if not isinstance(self.construction, tuple) or not self.construction or any(
            not isinstance(x, str) or not x.strip() for x in self.construction
        ):
            raise WardrobeError("construction notes are required")
        if not isinstance(self.fit_anchors, tuple) or not self.fit_anchors or any(
            not isinstance(x, str) or not _ID.fullmatch(x) for x in self.fit_anchors
        ) or len(set(self.fit_anchors)) != len(self.fit_anchors):
            raise WardrobeError("fit anchors must be unique stable identifiers")
        if self.provenance not in {"canonical_clothing_design", "design_proposal_review_required"}:
            raise WardrobeError("unknown design provenance")


@dataclass(frozen=True, slots=True)
class StyleInput:
    """Source-backed request or taste. Request does not imply LIKE."""
    subject_id: str
    status: RequestStatus
    source_id: str
    detail: str

    def __post_init__(self) -> None:
        if not all(isinstance(x, str) and _ID.fullmatch(x) for x in (
            self.subject_id, self.source_id
        )) or not isinstance(self.status, RequestStatus):
            raise WardrobeError("style input requires sourced typed identity")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise WardrobeError("style input requires a concrete detail")


@dataclass(frozen=True, slots=True)
class WardrobePrebuild:
    wardrobe: Wardrobe
    blueprints: tuple[GarmentBlueprint, ...]
    presets: tuple[OutfitPlan, ...]
    inputs: tuple[StyleInput, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.wardrobe, Wardrobe):
            raise WardrobeError("missing wardrobe")
        if not isinstance(self.blueprints, tuple) or any(
            not isinstance(bp, GarmentBlueprint) for bp in self.blueprints
        ):
            raise WardrobeError("invalid garment blueprints")
        if len({bp.garment.item_id for bp in self.blueprints}) != len(self.blueprints):
            raise WardrobeError("duplicate garment blueprint")
        if not isinstance(self.presets, tuple) or not self.presets or any(
            not isinstance(plan, OutfitPlan) for plan in self.presets
        ):
            raise WardrobeError("missing outfit presets")
        if len({p.outfit_id for p in self.presets}) != len(self.presets):
            raise WardrobeError("duplicate outfit preset")
        if not isinstance(self.inputs, tuple) or any(not isinstance(x, StyleInput) for x in self.inputs):
            raise WardrobeError("invalid style inputs")
        if len({(x.subject_id, x.source_id) for x in self.inputs}) != len(self.inputs):
            raise WardrobeError("duplicate source-backed style input")
        blueprint_ids = {bp.garment.item_id for bp in self.blueprints}
        for plan in self.presets:
            if set(plan.item_ids) - blueprint_ids:
                raise WardrobeError("outfit references unbuilt/unlisted garment")
            if not self.wardrobe.selection(plan.item_ids).covered_default:
                raise WardrobeError("prebuilt normal outfits must remain covered")
        if any(x.subject_id not in blueprint_ids and x.subject_id not in {
            p.outfit_id for p in self.presets
        } for x in self.inputs):
            raise WardrobeError("style input references an unknown design")

    def preset(self, outfit_id: str) -> OutfitPlan:
        for plan in self.presets:
            if plan.outfit_id == outfit_id:
                return plan
        raise WardrobeError("unknown prebuilt outfit")

    def manifest(self) -> dict[str, object]:
        """Pure JSON-ready authoring handoff, never a renderer-ready asset manifest."""
        return {
            "schema": "sofia.avatar.wardrobe.prebuild.v1",
            "stage": DRAFT_STATUS,
            "garments": [
                {
                    "item_id": bp.garment.item_id,
                    "name": bp.garment.name,
                    "layer": bp.garment.layer.name.lower(),
                    "slots": list(bp.garment.slots),
                    "coverage": list(bp.garment.coverage),
                    "tail_clearance": bp.garment.tail_clearance,
                    "ear_clearance": bp.garment.ear_clearance,
                    "asset_ref": None,
                    "primary_hex": bp.primary_hex,
                    "accent_hexes": list(bp.accent_hexes),
                    "material": bp.material,
                    "construction": list(bp.construction),
                    "fit_anchors": list(bp.fit_anchors),
                    "provenance": bp.provenance,
                } for bp in self.blueprints
            ],
            "outfits": [
                {
                    "outfit_id": plan.outfit_id,
                    "item_ids": list(plan.item_ids),
                    "activities": sorted(x.value for x in plan.activities),
                    "seasons": sorted(x.value for x in plan.seasons),
                    "lounge": plan.lounge,
                    "private_only": plan.private_only,
                    "style_tags": list(plan.style_tags),
                } for plan in self.presets
            ],
            "style_inputs": [
                {
                    "subject_id": x.subject_id,
                    "status": x.status.value,
                    "source_id": x.source_id,
                    "detail": x.detail,
                } for x in self.inputs
            ],
        }


def _bp(
    item_id: str, name: str, layer: Layer, slots: tuple[str, ...],
    coverage: tuple[str, ...], color: str, material: str,
    construction: tuple[str, ...], anchors: tuple[str, ...], *,
    accents: tuple[str, ...] = (), tail: bool = False, ears: bool = False,
    canonical: bool = False,
) -> GarmentBlueprint:
    return GarmentBlueprint(
        Garment(item_id, name, layer, slots, coverage, tail_clearance=tail,
                ear_clearance=ears, asset_ref=None),
        primary_hex=color, accent_hexes=accents, material=material,
        construction=construction, fit_anchors=anchors,
        provenance="canonical_clothing_design" if canonical
        else "design_proposal_review_required",
    )


def build_starter_wardrobe() -> WardrobePrebuild:
    """Three fully covered metadata presets, with no fabricated owned assets/taste."""
    dark, charcoal, crimson, teal, violet = (
        "#0B0D12", "#171A21", "#8B1E3F", "#19D3C5", "#3A245C"
    )
    blueprints = (
        _bp("underlayer.top", "Breathable underlayer", Layer.UNDERWEAR,
            ("torso",), ("torso",), dark, "soft breathable stretch knit",
            ("Non-rendered draft underlayer; fit beneath base shirt.",),
            ("torso.front", "torso.back")),
        _bp("underlayer.bottom", "Base undergarment", Layer.UNDERWEAR,
            ("pelvis",), ("pelvis",), dark, "soft stretch technical knit",
            ("Fit beneath trousers; do not treat metadata as coverage proof.",),
            ("pelvis.coverage",)),
        _bp("engineer.shirt", "Fitted long-sleeve technical shirt", Layer.BASE,
            ("torso", "upper_arms", "forearms"),
            ("torso", "upper_arms", "forearms"), dark,
            "breathable black technical textile",
            ("Reinforced seams, subtle crimson detailing and teal chest identifier.",
             "Stand collar about 1.25 inches from canonical garment brief."),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
             "forearm.left", "forearm.right"), accents=(crimson, teal), canonical=True),
        _bp("engineer.trousers", "Articulated utility trousers", Layer.BASE,
            ("pelvis", "legs", "tail"), ("pelvis", "legs"), dark,
            "stretch technical textile with reinforced seat and knees",
            ("Fitted but non-tight; gusseted crotch, articulated knees and pockets.",
             "Dedicated flexible opening at tail root; never compress tail."),
            ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
            accents=(charcoal,), tail=True, canonical=True),
        _bp("engineer.jacket", "Asymmetric engineer jacket", Layer.OUTER,
            ("torso", "shoulders", "upper_arms", "forearms", "tail"),
            ("torso", "shoulders", "upper_arms", "forearms"), dark,
            "matte abrasion-resistant water-resistant technical shell",
            ("Offset front zipper, reinforced shoulders/elbows/forearms/back.",
             "Canonical garment guide: shoulder ~16 in; length ~25 in; sleeve ~24.5 in.",
             "Design color ratio ~70% dark, 15% charcoal, 8% crimson, 5% violet, 2% teal.",
             "Rear hem accommodates unrestricted tail motion."),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
             "forearm.left", "forearm.right", "tail.opening.clearance"),
            accents=(charcoal, crimson, violet, teal), tail=True, canonical=True),
        _bp("engineer.socks", "Technical work socks", Layer.UNDERWEAR,
            ("feet",), ("feet",), dark, "moisture-wicking technical knit",
            ("Reinforced heel and toe; subtle crimson detail.",),
            ("foot.left", "foot.right"), accents=(crimson,), canonical=True),
        _bp("engineer.boots", "Mid-calf engineer boots", Layer.BASE,
            ("feet", "ankles", "calves"), ("feet", "ankles", "calves"), dark,
            "waterproof upper, flexible ankle and rubberized tread",
            ("Canonical boot guide: shaft ~10-11 in, heel ~1.25 in.",
             "Reinforced toe, gunmetal hardware and teal indicator."),
            ("foot.left", "foot.right"), accents=(crimson, teal), canonical=True),
        _bp("engineer.gloves", "Technical work gloves", Layer.BASE,
            ("hands", "fingers"), ("hands", "fingers"), dark,
            "flexible technical fabric with reinforced palms",
            ("Conductive fingertips, flexible knuckles and wrist adjustment.",),
            ("wrist.left", "wrist.right"), accents=(charcoal,), canonical=True),
        _bp("engineer.gauntlets", "Modular forearm gauntlets", Layer.ACCESSORY,
            ("left_forearm", "right_forearm", "left_wrist", "right_wrist"),
            ("left_forearm", "right_forearm", "left_wrist", "right_wrist"),
            charcoal, "synthetic leather and reinforced polymer",
            ("Left/right modular shells fit over the jacket sleeves.",
             "Check wrist mobility and glove clearance in rigged poses."),
            ("forearm.left", "forearm.right", "wrist.left", "wrist.right"),
            accents=(violet, teal)),
        _bp("engineer.belt", "Utility belt", Layer.ACCESSORY,
            ("waist",), ("waist",), dark, "polymer-nylon webbing and matte gunmetal",
            ("Canonical width ~1.5 in; low-profile buckle and tool mounts.",),
            ("waist.front",), accents=(crimson,), canonical=True),
        _bp("engineer.harness", "Diagonal tool harness", Layer.ACCESSORY,
            ("back", "shoulders"), (), charcoal,
            "reinforced dark webbing with matte metal fittings",
            ("Right shoulder to left hip; minimal crimson identification stripe.",),
            ("shoulder.right", "torso.back", "waist.front"),
            accents=(crimson,), canonical=True),
        _bp("engineer.pouch", "Technical equipment pouch", Layer.ACCESSORY,
            ("thighs",), (), charcoal, "reinforced abrasion-resistant textile",
            ("Secure to approved thigh/waist hardware; avoid knee and stride clipping.",),
            ("pelvis.coverage",), accents=(teal,)),
        _bp("lounge.top", "Oversized lounge T-shirt", Layer.BASE,
            ("torso", "upper_arms"), ("torso", "upper_arms"), "#393047",
            "soft breathable jersey knit",
            ("Loose shoulder and sleeve drape; comfortable opaque hem.",
             "Proposed color and cut, subject to Sparks' style feedback."),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right"),
            accents=(teal,)),
        _bp("lounge.sweats", "Relaxed lounge sweatpants", Layer.BASE,
            ("pelvis", "legs", "tail"), ("pelvis", "legs"), "#55515F",
            "soft stretch fleece or jersey",
            ("Relaxed seat and leg; flexible tail opening and comfortable waistband.",
             "Proposed fit/color pending review."),
            ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
            accents=(violet,), tail=True),
        _bp("fallback.top", "Covered fallback long-sleeve top", Layer.BASE,
            ("torso", "upper_arms", "forearms"),
            ("torso", "upper_arms", "forearms"), dark,
            "opaque simple technical knit",
            ("Authoring design only; renderer needs a separately verified real asset.",),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right")),
        _bp("fallback.trousers", "Covered fallback trousers", Layer.BASE,
            ("pelvis", "legs", "tail"), ("pelvis", "legs"), charcoal,
            "opaque simple technical weave",
            ("Flexible tail opening; renderer must verify real coverage.",),
            ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
            tail=True),
    )
    wardrobe = Wardrobe(tuple(bp.garment for bp in blueprints))
    under = ("underlayer.top", "underlayer.bottom")
    presets = (
        OutfitPlan("engineer.signature", under + (
            "engineer.shirt", "engineer.trousers", "engineer.jacket",
            "engineer.socks", "engineer.boots", "engineer.gloves",
            "engineer.gauntlets", "engineer.belt", "engineer.harness",
            "engineer.pouch",
        ), frozenset({Activity.ENGINEERING, Activity.LAB, Activity.CONVERSATION}),
            ALL_SEASONS, style_tags=("technical", "engineer", "canonical_brief")),
        OutfitPlan("lounge.relaxed", under + (
            "lounge.top", "lounge.sweats",
        ), frozenset({Activity.RELAXING, Activity.CONVERSATION, Activity.SLEEP}),
            ALL_SEASONS, lounge=True, style_tags=("relaxed", "proposed_colors")),
        OutfitPlan("fallback.covered", under + (
            "fallback.top", "fallback.trousers",
        ), frozenset(Activity), ALL_SEASONS,
            style_tags=("covered", "fallback", "asset_not_yet_verified")),
    )
    inputs = (
        StyleInput("engineer.signature", RequestStatus.USER_REQUESTED,
                   "chat.2026-09-22.request.engineer", "Signature engineer wardrobe requested; not a confirmed like."),
        StyleInput("lounge.relaxed", RequestStatus.USER_REQUESTED,
                   "chat.2026-09-22.request.lounge", "Oversized top and sweatpants requested; not a confirmed like."),
    )
    return WardrobePrebuild(wardrobe, blueprints, presets, inputs)
