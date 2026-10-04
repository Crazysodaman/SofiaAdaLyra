"""Offline garment blueprints and covered outfit presets for Sofía.

These are design proposals, not mesh assets or evidence that anything is worn.
Canonical clothing details are transcribed as authoring targets; lounge/fallback
colors and construction remain proposed until visually reviewed. No network,
renderer, file write, preference invention, or LLM action occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import re

from .body_contract import DEFAULT_FIT_ANCHORS
from .wardrobe import Garment, Layer, Wardrobe, WardrobeError
from .wardrobe_planner import Activity, OutfitPlan, Season, Weather

# Closet inventory families, seasonal presets, and swimwear live here so all
# catalog construction shares one set of wardrobe invariants.

@dataclass(frozen=True, slots=True)
class ClosetCategory:
    category_id: str
    label: str
    noun: str
    private_noun: str
    layer: Layer
    slots: tuple[str, ...]
    coverage: tuple[str, ...]
    fit_anchors: tuple[str, ...]
    tail_clearance: bool = False
    ear_clearance: bool = False


@dataclass(frozen=True, slots=True)
class PieceSpec:
    item_id: str
    name: str
    description: str
    category: str
    layer: Layer
    slots: tuple[str, ...]
    coverage: tuple[str, ...]
    primary_hex: str
    accent_hexes: tuple[str, ...]
    material: str
    construction: tuple[str, ...]
    fit_anchors: tuple[str, ...]
    style_tags: tuple[str, ...]
    private_only: bool
    tail_clearance: bool = False
    ear_clearance: bool = False


CLOSET_CATEGORIES: tuple[ClosetCategory, ...] = (
    ClosetCategory("closet.underwear_top", "Undergarment tops", "bralette", "lingerie top", Layer.UNDERWEAR, ("torso",), ("torso",), ("torso.front", "torso.back")),
    ClosetCategory("closet.underwear_bottom", "Undergarment bottoms", "brief", "lingerie bottom", Layer.UNDERWEAR, ("pelvis",), ("pelvis",), ("pelvis.coverage",)),
    ClosetCategory("closet.top", "Tops", "top", "private top", Layer.BASE, ("torso", "left_upper_arm", "right_upper_arm"), ("torso", "left_upper_arm", "right_upper_arm"), ("torso.front", "torso.back", "shoulder.left", "shoulder.right")),
    ClosetCategory("closet.bottom", "Bottoms", "bottom", "private bottom", Layer.BASE, ("pelvis", "left_leg", "right_leg", "tail"), ("pelvis", "left_leg", "right_leg"), ("pelvis.coverage", "tail.opening.clearance"), tail_clearance=True),
    ClosetCategory("closet.one_piece", "One-piece clothing", "one-piece", "private one-piece", Layer.BASE, ("torso", "pelvis", "left_leg", "right_leg", "tail"), ("torso", "pelvis", "left_leg", "right_leg"), ("torso.front", "torso.back", "pelvis.coverage", "tail.opening.clearance"), tail_clearance=True),
    ClosetCategory("closet.outerwear", "Outerwear", "jacket", "private wrap", Layer.OUTER, ("torso", "left_shoulder", "right_shoulder", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm", "tail"), ("torso", "left_shoulder", "right_shoulder", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm"), ("torso.front", "torso.back", "shoulder.left", "shoulder.right", "tail.opening.clearance"), tail_clearance=True),
    ClosetCategory("closet.footwear", "Footwear", "footwear", "private footwear", Layer.BASE, ("left_foot", "right_foot", "left_ankle", "right_ankle", "left_calf", "right_calf"), ("left_foot", "right_foot", "left_ankle", "right_ankle", "left_calf", "right_calf"), ("foot.left", "foot.right")),
    ClosetCategory("closet.legwear", "Legwear", "legwear", "private legwear", Layer.MID, ("left_leg", "right_leg", "left_thigh", "right_thigh", "left_calf", "right_calf"), ("left_leg", "right_leg", "left_thigh", "right_thigh", "left_calf", "right_calf"), ("thigh.left", "thigh.right", "calf.left", "calf.right")),
    ClosetCategory("closet.handwear", "Handwear", "gloves", "private gloves", Layer.ACCESSORY, ("left_hand", "right_hand", "left_fingers", "right_fingers"), ("left_hand", "right_hand", "left_fingers", "right_fingers"), ("wrist.left", "wrist.right")),
    ClosetCategory("closet.forearm_wrist", "Forearm and wrist pieces", "wrist piece", "private wrist piece", Layer.ACCESSORY, ("left_forearm", "right_forearm", "left_wrist", "right_wrist"), ("left_forearm", "right_forearm", "left_wrist", "right_wrist"), ("forearm.left", "forearm.right", "wrist.left", "wrist.right")),
    ClosetCategory("closet.headwear", "Headwear", "headpiece", "private headpiece", Layer.ACCESSORY, ("head", "left_ear", "right_ear"), ("head",), ("head.crown", "ear.left", "ear.right"), ear_clearance=True),
    ClosetCategory("closet.neckwear", "Neckwear", "neck piece", "choker", Layer.ACCESSORY, ("neck",), ("neck",), ("neck.center",)),
    ClosetCategory("closet.waistwear", "Waist pieces", "belt", "private waist piece", Layer.ACCESSORY, ("waist",), ("waist",), ("waist.front",)),
    ClosetCategory("closet.backwear", "Back and harness pieces", "back piece", "fashion harness", Layer.ACCESSORY, ("back", "left_shoulder", "right_shoulder"), (), ("torso.back", "shoulder.left", "shoulder.right")),
    ClosetCategory("closet.ear_accessory", "Ear accessories", "ear accessory", "private ear accessory", Layer.ACCESSORY, ("left_ear", "right_ear"), (), ("ear.left", "ear.right"), ear_clearance=True),
    ClosetCategory("closet.tail_accessory", "Tail accessories", "tail accessory", "private tail accessory", Layer.ACCESSORY, ("tail",), (), ("tail.base", "tail.mid"), tail_clearance=True),
    ClosetCategory("closet.hair_accessory", "Hair accessories", "hair accessory", "private hair accessory", Layer.ACCESSORY, ("hair",), (), ("head.crown",)),
    ClosetCategory("closet.shoulder_accessory", "Shoulder pieces", "shoulder piece", "private shoulder piece", Layer.ACCESSORY, ("left_shoulder", "right_shoulder"), ("left_shoulder", "right_shoulder"), ("shoulder.left", "shoulder.right")),
)

SPECIAL_PRIVATE_CATEGORIES: tuple[ClosetCategory, ...] = (
    ClosetCategory(
        "closet.bra", "Bras", "bra", "bra", Layer.UNDERWEAR,
        ("torso",), (), ("torso.front", "torso.back"),
    ),
    ClosetCategory(
        "closet.panty", "Panties", "panties", "panties", Layer.UNDERWEAR,
        ("pelvis",), (), ("pelvis.coverage",),
    ),
)


def all_closet_categories() -> tuple[ClosetCategory, ...]:
    return CLOSET_CATEGORIES + SPECIAL_PRIVATE_CATEGORIES


NORMAL_STYLES: tuple[str, ...] = (
    "classic", "casual", "utility", "technical", "lounge",
    "athletic", "soft-knit", "ribbed", "layered", "minimalist",
    "oversized", "fitted", "weatherproof", "thermal", "lightweight",
    "streetwear", "cyber", "crimson-trim", "violet-accent", "teal-accent",
    "charcoal", "weekend", "workshop", "travel", "evening",
)

PRIVATE_STYLES: tuple[str, ...] = (
    "lace", "satin", "sheer-mesh", "strappy", "cutout",
    "backless", "plunge", "minimal", "garter", "fishnet",
    "velvet", "glossy", "harness", "ribbon", "corset-inspired",
    "boudoir", "translucent", "high-cut", "side-tie", "open-back",
    "halter", "chokered", "ruched", "silk", "midnight",
)

_PALETTE: tuple[str, ...] = (
    "#0B0D12", "#171A21", "#8B1E3F", "#3A245C", "#19D3C5",
    "#5B2333", "#2C1B47", "#30343F", "#6A1B4D", "#1E4D5C",
)

_NORMAL_STYLE_DETAILS: tuple[str, ...] = (
    "clean straight seams with restrained hardware",
    "soft relaxed shaping with easy everyday proportions",
    "reinforced utility seams with compact functional detailing",
    "precise technical paneling with low-profile fasteners",
    "soft drape and rounded comfort-focused shaping",
    "streamlined athletic contouring with flexible edge binding",
    "fine-gauge knit texture with softly finished edges",
    "vertical rib structure with subtle stretch definition",
    "layer-aware cut lines designed to sit cleanly under outer pieces",
    "minimal seam count with a deliberately uncluttered silhouette",
    "generous volume balanced by controlled cuffs and hems",
    "close tailored shaping with articulated movement allowance",
    "sealed-looking panel lines and storm-ready trim language",
    "insulated-looking quilting or brushed texture cues",
    "reduced bulk with narrow hems and airy construction cues",
    "streetwear proportions with graphic seam placement",
    "angular cyber detailing with small luminous-accent style cues",
    "crimson-edged seam emphasis against a dark main field",
    "violet piping and panel breaks used as the dominant accent",
    "teal micro-accents concentrated at closures and trim points",
    "charcoal tonal blocking with matte-on-matte contrast",
    "comfortable weekend proportions with simple finished edges",
    "workshop-inspired reinforcement zones and practical attachment cues",
    "travel-oriented low-bulk construction with secure pocket language",
    "clean evening lines with slightly sharper tailoring and finish",
)

_PRIVATE_STYLE_DETAILS: tuple[str, ...] = (
    "lace-inspired edgework with floral geometric trim cues",
    "smooth satin-like sheen with softly rounded seam transitions",
    "fine mesh-inspired panel language layered with opaque structural bands",
    "multiple narrow strap lines arranged in a deliberate geometric pattern",
    "strategic cutout-style negative-space panels bounded by finished edges",
    "open-back styling with the front structure carrying most of the visual weight",
    "deep angular neckline styling balanced by stable side structure",
    "very simple linework with minimal trim and hardware",
    "garter-inspired attachment detailing used as a fashion motif",
    "fishnet-inspired open-grid texture cues paired with solid binding",
    "velvet-like matte depth with plush-looking edge finish",
    "high-gloss panel treatment contrasted against matte binding",
    "harness-inspired crossing bands arranged as decorative structure",
    "ribbon-like tie accents with small bow or knot details",
    "corset-inspired vertical seam channels without implying rigid construction",
    "boudoir-inspired soft drape, scalloped trim, and decorative edging",
    "translucent-style panel cues combined with opaque boundary trim",
    "high-cut leg-line styling with clean continuous edge binding",
    "side-tie styling with paired knot or bow details",
    "open-back styling with narrow support bands and a clean front",
    "halter-style neck routing with a defined central front line",
    "choker-linked styling that visually connects neckline and garment trim",
    "ruched gathering concentrated at selected seams for texture",
    "silk-like fluid sheen with narrow polished hems",
    "midnight-themed dark tonal blocking with violet and teal micro-accents",
)

_STYLE_DETAILS = {
    **dict(zip(NORMAL_STYLES, _NORMAL_STYLE_DETAILS, strict=True)),
    **dict(zip(PRIVATE_STYLES, _PRIVATE_STYLE_DETAILS, strict=True)),
}


def _piece(
    category: ClosetCategory,
    *,
    index: int,
    style: str,
    private_only: bool,
) -> PieceSpec:
    visibility = "private" if private_only else "normal"
    noun = category.private_noun if private_only else category.noun
    color = _PALETTE[(index - 1) % len(_PALETTE)]
    accent = _PALETTE[index % len(_PALETTE)]
    coverage = () if private_only else category.coverage
    detail = _STYLE_DETAILS[style]
    material = (
        f"soft stretch fashion textile tuned for {style.replace('-', ' ')} styling"
        if private_only
        else f"opaque wearable textile tuned for {style.replace('-', ' ')} styling"
    )
    description = (
        f"{style.replace('-', ' ').title()} {noun} in {color} with {accent} accents; "
        f"{detail}. Built around the {category.label.casefold()} slot pattern."
    )
    construction = (
        (
            "Adult/private wardrobe design metadata; no renderer asset is implied.",
            f"Distinct design cue: {detail}.",
            "Private-only classification is independent of emotion, attraction or consent.",
            "Fit must preserve fox-ear/tail clearance where the mapped rig slot requires it.",
        )
        if private_only
        else (
            "Mix-and-match wardrobe design metadata; no renderer asset is implied.",
            f"Distinct design cue: {detail}.",
            "Normal/public eligibility still depends on full outfit coverage and verified assets.",
            "Fit must preserve fox-ear/tail clearance where the mapped rig slot requires it.",
        )
    )
    return PieceSpec(
        item_id=f"closet.{visibility}.{category.category_id.split('.', 1)[1]}.{index:02d}",
        name=f"{style.replace('-', ' ').title()} {noun.title()}",
        description=description,
        category=category.category_id,
        layer=category.layer,
        slots=category.slots,
        coverage=coverage,
        primary_hex=color,
        accent_hexes=(accent,),
        material=material,
        construction=construction,
        fit_anchors=category.fit_anchors,
        style_tags=(
            visibility,
            category.category_id.split(".", 1)[1],
            style,
            "adult-private" if private_only else "everyday",
        ),
        private_only=private_only,
        tail_clearance=category.tail_clearance,
        ear_clearance=category.ear_clearance,
    )


def generated_piece_specs() -> tuple[PieceSpec, ...]:
    """Return the generated closet, including explicit bra/panty families."""
    pieces: list[PieceSpec] = []
    for category in CLOSET_CATEGORIES:
        pieces.extend(
            _piece(category, index=index, style=style, private_only=False)
            for index, style in enumerate(NORMAL_STYLES, start=1)
        )
        pieces.extend(
            _piece(category, index=index, style=style, private_only=True)
            for index, style in enumerate(PRIVATE_STYLES, start=1)
        )
    for category in SPECIAL_PRIVATE_CATEGORIES:
        pieces.extend(
            _piece(category, index=index, style=style, private_only=True)
            for index, style in enumerate(PRIVATE_STYLES, start=1)
        )
    return tuple(pieces)


_SEASON_INDEX = {
    Season.SPRING: 0,
    Season.SUMMER: 1,
    Season.AUTUMN: 2,
    Season.WINTER: 3,
}


def _shift(index: int, offset: int) -> int:
    return ((index - 1 + offset) % 25) + 1


def _n(kind: str, index: int) -> str:
    return f"closet.normal.{kind}.{index:02d}"


def _p(kind: str, index: int) -> str:
    return f"closet.private.{kind}.{index:02d}"


def _seasonal_normal(season: Season, index: int) -> OutfitPlan:
    season_index = _SEASON_INDEX[season]
    items = (
        "underlayer.top",
        "underlayer.bottom",
        _n("top", index),
        _n("bottom", _shift(index, 2 + season_index * 3)),
        _n("footwear", _shift(index, 4 + season_index * 5)),
        _n("neckwear", _shift(index, 8 + season_index * 7)),
    )
    if season in {Season.SPRING, Season.AUTUMN, Season.WINTER}:
        items += (
            _n(
                "outerwear",
                _shift(index, 12 + season_index * 11),
            ),
        )
    return OutfitPlan(
        f"seasonal.{season.value}.normal.{index:02d}",
        items,
        frozenset({Activity.CONVERSATION, Activity.FORMAL}),
        frozenset({season}),
        style_tags=("seasonal", "normal", season.value),
        display_name=f"{season.value.title()} Everyday {index:02d}",
    )


def _seasonal_lounge(season: Season, index: int) -> OutfitPlan:
    season_index = _SEASON_INDEX[season]
    items = (
        "underlayer.top",
        "underlayer.bottom",
        _n("top", _shift(index, 4)),
        _n("bottom", _shift(index, 9 + season_index * 3)),
        _n(
            "hair_accessory",
            _shift(index, 13 + season_index * 5),
        ),
    )
    if season is Season.WINTER:
        items += (_n("legwear", _shift(index, 2)),)
    return OutfitPlan(
        f"seasonal.{season.value}.lounge.{index:02d}",
        items,
        frozenset({Activity.CONVERSATION, Activity.RELAXING, Activity.SLEEP}),
        frozenset({season}),
        lounge=True,
        style_tags=("seasonal", "lounge", "cozy", "soft", season.value),
        display_name=f"{season.value.title()} Lounge {index:02d}",
    )


def _seasonal_private(season: Season, index: int) -> OutfitPlan:
    season_index = _SEASON_INDEX[season]
    items = (
        _p("bra", index),
        _p("panty", _shift(index, 5 + season_index * 3)),
        _p("legwear", _shift(index, 10 + season_index * 5)),
        _p("neckwear", _shift(index, 15 + season_index * 7)),
        _p("footwear", _shift(index, 20 + season_index * 9)),
    )
    return OutfitPlan(
        f"seasonal.{season.value}.private.{index:02d}",
        items,
        frozenset({Activity.CONVERSATION, Activity.RELAXING}),
        frozenset({season}),
        private_only=True,
        style_tags=("seasonal", "adult-private", "intimate-style", season.value),
        display_name=f"{season.value.title()} Private {index:02d}",
    )


def generated_seasonal_outfits() -> tuple[OutfitPlan, ...]:
    outfits: list[OutfitPlan] = []
    for season in Season:
        for index in range(1, 26):
            outfits.append(_seasonal_normal(season, index))
            outfits.append(_seasonal_lounge(season, index))
            outfits.append(_seasonal_private(season, index))
    return tuple(outfits)


_BIKINI_DESIGNS: tuple[
    tuple[str, str, str, str, str, str],
    ...,
] = (
    (
        "Cyberwave Triangle",
        "#0B0D12",
        "#19D3C5",
        "triangle-cut top with crisp teal edge piping",
        "mid-rise bottom with matching teal edge piping and a tail-clearance notch",
        "matte chlorine-resistant stretch swim knit",
    ),
    (
        "Violet Halter",
        "#3A245C",
        "#19D3C5",
        "halter-neck top with a softly curved neckline and teal clasp detail",
        "high-waist bottom with violet contour seams and a clean tail opening",
        "smooth violet swim jersey with resilient stretch",
    ),
    (
        "Crimson Sport",
        "#8B1E3F",
        "#171A21",
        "sport-style crossback top with charcoal support bands",
        "secure hipster-cut bottom with charcoal side panels and tail clearance",
        "structured performance swim knit",
    ),
    (
        "Midnight Asymmetric",
        "#171A21",
        "#3A245C",
        "one-shoulder top with a diagonal violet panel break",
        "asymmetric-waist bottom with a single violet side accent and tail clearance",
        "matte black swim fabric with satin-finish contrast panels",
    ),
    (
        "Teal Ring",
        "#19D3C5",
        "#0B0D12",
        "scoop-neck top with small dark ring connectors at the straps",
        "high-cut bottom with matching dark ring side details and tail clearance",
        "smooth teal stretch swim fabric with matte hardware",
    ),
    (
        "Crimson Violet Colorblock",
        "#5B2333",
        "#3A245C",
        "bandeau-style top with violet color blocking and removable-looking strap cues",
        "side-tie-style bottom with violet panels, compact knots, and tail clearance",
        "soft colorblocked swim knit with reinforced edge binding",
    ),
)


def generated_bikini_piece_specs() -> tuple[PieceSpec, ...]:
    """Return twelve garments that form six visually distinct bikini sets."""
    pieces: list[PieceSpec] = []
    for index, (
        label,
        primary,
        accent,
        top_detail,
        bottom_detail,
        material,
    ) in enumerate(_BIKINI_DESIGNS, start=1):
        key = f"{index:02d}"
        pieces.append(
            PieceSpec(
                item_id=f"closet.swim.bikini.{key}.top",
                name=f"{label} Bikini Top",
                description=(
                    f"{label} two-piece swimwear top in {primary} with {accent} "
                    f"accents; {top_detail}."
                ),
                category="closet.swim.bikini_top",
                layer=Layer.BASE,
                slots=("torso",),
                coverage=("torso",),
                primary_hex=primary,
                accent_hexes=(accent,),
                material=material,
                construction=(
                    f"Distinct bikini design {key}: {top_detail}.",
                    "Swimwear metadata only; no renderer asset is implied.",
                ),
                fit_anchors=("torso.front", "torso.back"),
                style_tags=("swimwear", "bikini", f"bikini-{key}", "top"),
                private_only=False,
            )
        )
        pieces.append(
            PieceSpec(
                item_id=f"closet.swim.bikini.{key}.bottom",
                name=f"{label} Bikini Bottom",
                description=(
                    f"{label} two-piece swimwear bottom in {primary} with {accent} "
                    f"accents; {bottom_detail}."
                ),
                category="closet.swim.bikini_bottom",
                layer=Layer.BASE,
                slots=("pelvis", "tail"),
                coverage=("pelvis",),
                primary_hex=primary,
                accent_hexes=(accent,),
                material=material,
                construction=(
                    f"Distinct bikini design {key}: {bottom_detail}.",
                    "Tail opening is part of the reviewed metadata design.",
                    "Swimwear metadata only; no renderer asset is implied.",
                ),
                fit_anchors=("pelvis.coverage", "tail.opening.clearance"),
                style_tags=("swimwear", "bikini", f"bikini-{key}", "bottom"),
                private_only=False,
                tail_clearance=True,
            )
        )
    return tuple(pieces)


def generated_bikini_outfits() -> tuple[OutfitPlan, ...]:
    """Return six complete bikini outfit templates."""
    return tuple(
        OutfitPlan(
            outfit_id=f"swim.bikini.{index:02d}",
            item_ids=(
                f"closet.swim.bikini.{index:02d}.top",
                f"closet.swim.bikini.{index:02d}.bottom",
            ),
            activities=frozenset({
                Activity.RELAXING,
                Activity.CONVERSATION,
            }),
            seasons=frozenset(Season),
            weather=frozenset({Weather.HOT, Weather.MILD}),
            style_tags=(
                "swimwear",
                "bikini",
                f"bikini-{index:02d}",
                "two-piece",
            ),
            display_name=_BIKINI_DESIGNS[index - 1][0] + " Bikini",
        )
        for index in range(1, 7)
    )


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
    category: str = "legacy"
    style_tags: tuple[str, ...] = ()
    private_only: bool = False
    description: str = ""

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
        if not isinstance(self.category, str) or _ID.fullmatch(self.category) is None:
            raise WardrobeError("invalid garment category")
        if (
            not isinstance(self.style_tags, tuple)
            or len(set(self.style_tags)) != len(self.style_tags)
            or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 64
                   for tag in self.style_tags)
        ):
            raise WardrobeError("invalid garment style tags")
        if type(self.private_only) is not bool:
            raise WardrobeError("private_only must be boolean")
        if self.private_only != self.garment.private_only:
            raise WardrobeError("blueprint privacy must match garment privacy")
        if not self.description:
            object.__setattr__(
                self,
                "description",
                (
                    f"{self.garment.name} in {self.primary_hex}; "
                    f"{self.material}. {self.construction[0]}"
                ),
            )
        if (
            not isinstance(self.description, str)
            or not self.description.strip()
            or len(self.description) > 1200
        ):
            raise WardrobeError("garment description must be bounded nonempty text")

    @property
    def design_signature(self) -> str:
        """Stable visual-design fingerprint that intentionally excludes item_id."""
        payload = {
            "name": self.garment.name,
            "description": self.description,
            "layer": self.garment.layer.name,
            "slots": self.garment.slots,
            "coverage": self.garment.coverage,
            "tail_clearance": self.garment.tail_clearance,
            "ear_clearance": self.garment.ear_clearance,
            "primary_hex": self.primary_hex,
            "accent_hexes": self.accent_hexes,
            "material": self.material,
            "construction": self.construction,
            "fit_anchors": self.fit_anchors,
            "category": self.category,
            "style_tags": self.style_tags,
            "private_only": self.private_only,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


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
        signatures = [bp.design_signature for bp in self.blueprints]
        if len(set(signatures)) != len(signatures):
            raise WardrobeError(
                "duplicate garment visual design signature"
            )
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
        known_fit_anchors = {
            anchor.name for anchor in DEFAULT_FIT_ANCHORS
        }
        for blueprint in self.blueprints:
            unknown = set(blueprint.fit_anchors) - known_fit_anchors
            if unknown:
                raise WardrobeError(
                    "garment blueprint references unknown body fit anchor"
                )
        blueprint_ids = {bp.garment.item_id for bp in self.blueprints}
        for plan in self.presets:
            if set(plan.item_ids) - blueprint_ids:
                raise WardrobeError("outfit references unbuilt/unlisted garment")
            selected = self.wardrobe.selection(plan.item_ids)
            if plan.private_only:
                if not selected.private_only:
                    raise WardrobeError(
                        "private outfit must contain private-only garment metadata"
                    )
            else:
                if selected.private_only or not selected.covered_default:
                    raise WardrobeError(
                        "prebuilt normal outfits must remain covered and non-private"
                    )
        if any(x.subject_id not in blueprint_ids and x.subject_id not in {
            p.outfit_id for p in self.presets
        } for x in self.inputs):
            raise WardrobeError("style input references an unknown design")

    def preset(self, outfit_id: str) -> OutfitPlan:
        for plan in self.presets:
            if plan.outfit_id == outfit_id:
                return plan
        raise WardrobeError("unknown prebuilt outfit")

    def pieces(
        self,
        *,
        category: str | None = None,
        private_only: bool | None = None,
    ) -> tuple[GarmentBlueprint, ...]:
        """Query individual closet pieces without claiming they are worn."""
        if category is not None and (
            not isinstance(category, str) or not category.strip()
        ):
            raise WardrobeError("category must be None or nonempty")
        if private_only is not None and type(private_only) is not bool:
            raise WardrobeError("private_only must be None or boolean")
        return tuple(
            blueprint
            for blueprint in self.blueprints
            if (
                (category is None or blueprint.category == category)
                and (
                    private_only is None
                    or blueprint.private_only is private_only
                )
            )
        )

    def closet_summary(self) -> dict[str, object]:
        """Compact text/UI inventory summary, not a renderer asset claim."""
        categories = sorted({
            blueprint.category
            for blueprint in self.blueprints
            if blueprint.category.startswith("closet.")
        })
        rows: dict[str, dict[str, int]] = {}
        for category in categories:
            normal = len(self.pieces(category=category, private_only=False))
            private = len(self.pieces(category=category, private_only=True))
            rows[category] = {
                "normal": normal,
                "adult_private": private,
            }
        signatures = [bp.design_signature for bp in self.blueprints]
        unique_signatures = set(signatures)
        return {
            "generated_piece_count": sum(
                values["normal"] + values["adult_private"]
                for values in rows.values()
            ),
            "total_piece_count": len(self.blueprints),
            "outfit_count": len(self.presets),
            "bikini_outfit_count": sum(
                1 for plan in self.presets
                if plan.outfit_id.startswith("swim.bikini.")
            ),
            "unique_design_signature_count": len(unique_signatures),
            "duplicate_design_signature_count": (
                len(signatures) - len(unique_signatures)
            ),
            "all_designs_unique": len(signatures) == len(unique_signatures),
            "categories": rows,
            "adult_private_requires_authorization": True,
            "assets_verified": False,
        }

    def manifest(self) -> dict[str, object]:
        """Pure JSON-ready authoring handoff, never a renderer-ready asset manifest."""
        return {
            "schema": "sofia.avatar.wardrobe.prebuild.v1",
            "stage": DRAFT_STATUS,
            "garments": [
                {
                    "item_id": bp.garment.item_id,
                    "name": bp.garment.name,
                    "description": bp.description,
                    "design_signature": bp.design_signature,
                    "layer": bp.garment.layer.name.lower(),
                    "slots": list(bp.garment.slots),
                    "coverage": list(bp.garment.coverage),
                    "tail_clearance": bp.garment.tail_clearance,
                    "ear_clearance": bp.garment.ear_clearance,
                    "asset_ref": None,
                    "private_only": bp.private_only,
                    "category": bp.category,
                    "style_tags": list(bp.style_tags),
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
    canonical: bool = False, category: str = "legacy",
    style_tags: tuple[str, ...] = (), private_only: bool = False,
    description: str | None = None,
) -> GarmentBlueprint:
    return GarmentBlueprint(
        Garment(
            item_id, name, layer, slots, coverage,
            tail_clearance=tail,
            ear_clearance=ears,
            asset_ref=None,
            private_only=private_only,
        ),
        primary_hex=color, accent_hexes=accents, material=material,
        construction=construction, fit_anchors=anchors,
        provenance="canonical_clothing_design" if canonical
        else "design_proposal_review_required",
        category=category,
        style_tags=style_tags,
        private_only=private_only,
        description=(
            description
            if description is not None
            else f"{name} in {color}; {material}. {construction[0]}"
        ),
    )


def _generated_blueprint(spec: PieceSpec) -> GarmentBlueprint:
    return _bp(
        spec.item_id,
        spec.name,
        spec.layer,
        spec.slots,
        spec.coverage,
        spec.primary_hex,
        spec.material,
        spec.construction,
        spec.fit_anchors,
        accents=spec.accent_hexes,
        tail=spec.tail_clearance,
        ears=spec.ear_clearance,
        category=spec.category,
        style_tags=spec.style_tags,
        private_only=spec.private_only,
        description=spec.description,
    )


def build_starter_wardrobe() -> WardrobePrebuild:
    """Starter presets plus a large mix-and-match individual-piece closet."""
    dark, charcoal, crimson, teal, violet = (
        "#0B0D12", "#171A21", "#8B1E3F", "#19D3C5", "#3A245C"
    )
    base_blueprints = (
        _bp("underlayer.top", "Breathable underlayer", Layer.UNDERWEAR,
            ("torso",), ("torso",), dark, "soft breathable stretch knit",
            ("Non-rendered draft underlayer; fit beneath base shirt.",),
            ("torso.front", "torso.back")),
        _bp("underlayer.bottom", "Base undergarment", Layer.UNDERWEAR,
            ("pelvis",), ("pelvis",), dark, "soft stretch technical knit",
            ("Fit beneath trousers; do not treat metadata as coverage proof.",),
            ("pelvis.coverage",)),
        _bp("engineer.shirt", "Fitted long-sleeve technical shirt", Layer.BASE,
            ("torso", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm"),
            ("torso", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm"), dark,
            "breathable black technical textile",
            ("Reinforced seams, subtle crimson detailing and teal chest identifier.",
             "Stand collar about 1.25 inches from canonical garment brief."),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
             "forearm.left", "forearm.right"), accents=(crimson, teal), canonical=True),
        _bp("engineer.trousers", "Articulated utility trousers", Layer.BASE,
            ("pelvis", "left_leg", "right_leg", "tail"), ("pelvis", "left_leg", "right_leg"), dark,
            "stretch technical textile with reinforced seat and knees",
            ("Fitted but non-tight; gusseted crotch, articulated knees and pockets.",
             "Dedicated flexible opening at tail root; never compress tail."),
            ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
            accents=(charcoal,), tail=True, canonical=True),
        _bp("engineer.jacket", "Asymmetric engineer jacket", Layer.OUTER,
            ("torso", "left_shoulder", "right_shoulder", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm", "tail"),
            ("torso", "left_shoulder", "right_shoulder", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm"), dark,
            "matte abrasion-resistant water-resistant technical shell",
            ("Offset front zipper, reinforced shoulders/elbows/forearms/back.",
             "Canonical garment guide: shoulder ~16 in; length ~25 in; sleeve ~24.5 in.",
             "Design color ratio ~70% dark, 15% charcoal, 8% crimson, 5% violet, 2% teal.",
             "Rear hem accommodates unrestricted tail motion."),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
             "forearm.left", "forearm.right", "tail.opening.clearance"),
            accents=(charcoal, crimson, violet, teal), tail=True, canonical=True),
        _bp("engineer.socks", "Technical work socks", Layer.UNDERWEAR,
            ("left_foot", "right_foot"), ("left_foot", "right_foot"), dark, "moisture-wicking technical knit",
            ("Reinforced heel and toe; subtle crimson detail.",),
            ("foot.left", "foot.right"), accents=(crimson,), canonical=True),
        _bp("engineer.boots", "Mid-calf engineer boots", Layer.BASE,
            ("left_foot", "right_foot", "left_ankle", "right_ankle", "left_calf", "right_calf"), ("left_foot", "right_foot", "left_ankle", "right_ankle", "left_calf", "right_calf"), dark,
            "waterproof upper, flexible ankle and rubberized tread",
            ("Canonical boot guide: shaft ~10-11 in, heel ~1.25 in.",
             "Reinforced toe, gunmetal hardware and teal indicator."),
            ("foot.left", "foot.right"), accents=(crimson, teal), canonical=True),
        _bp("engineer.gloves", "Technical work gloves", Layer.BASE,
            ("left_hand", "right_hand", "left_fingers", "right_fingers"), ("left_hand", "right_hand", "left_fingers", "right_fingers"), dark,
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
            ("back", "left_shoulder", "right_shoulder"), (), charcoal,
            "reinforced dark webbing with matte metal fittings",
            ("Right shoulder to left hip; minimal crimson identification stripe.",),
            ("shoulder.right", "torso.back", "waist.front"),
            accents=(crimson,), canonical=True),
        _bp("engineer.pouch", "Technical equipment pouch", Layer.ACCESSORY,
            ("left_thigh", "right_thigh"), (), charcoal, "reinforced abrasion-resistant textile",
            ("Secure to approved thigh/waist hardware; avoid knee and stride clipping.",),
            ("pelvis.coverage",), accents=(teal,)),
        _bp("lounge.top", "Oversized lounge T-shirt", Layer.BASE,
            ("torso", "left_upper_arm", "right_upper_arm"), ("torso", "left_upper_arm", "right_upper_arm"), "#393047",
            "soft breathable jersey knit",
            ("Loose shoulder and sleeve drape; comfortable opaque hem.",
             "Proposed color and cut, subject to Sparks' style feedback."),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right"),
            accents=(teal,)),
        _bp("lounge.sweats", "Relaxed lounge sweatpants", Layer.BASE,
            ("pelvis", "left_leg", "right_leg", "tail"), ("pelvis", "left_leg", "right_leg"), "#55515F",
            "soft stretch fleece or jersey",
            ("Relaxed seat and leg; flexible tail opening and comfortable waistband.",
             "Proposed fit/color pending review."),
            ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
            accents=(violet,), tail=True),
        _bp("fallback.top", "Covered fallback long-sleeve top", Layer.BASE,
            ("torso", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm"),
            ("torso", "left_upper_arm", "right_upper_arm", "left_forearm", "right_forearm"), dark,
            "opaque simple technical knit",
            ("Authoring design only; renderer needs a separately verified real asset.",),
            ("torso.front", "torso.back", "shoulder.left", "shoulder.right")),
        _bp("fallback.trousers", "Covered fallback trousers", Layer.BASE,
            ("pelvis", "left_leg", "right_leg", "tail"), ("pelvis", "left_leg", "right_leg"), charcoal,
            "opaque simple technical weave",
            ("Flexible tail opening; renderer must verify real coverage.",),
            ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
            tail=True),
    )
    blueprints = base_blueprints + tuple(
        _generated_blueprint(spec)
        for spec in (
            *generated_piece_specs(),
            *generated_bikini_piece_specs(),
        )
    )
    wardrobe = Wardrobe(tuple(bp.garment for bp in blueprints))
    under = ("underlayer.top", "underlayer.bottom")
    base_presets = (
        OutfitPlan("engineer.signature", under + (
            "engineer.shirt", "engineer.trousers", "engineer.jacket",
            "engineer.socks", "engineer.boots", "engineer.gloves",
            "engineer.gauntlets", "engineer.belt", "engineer.harness",
            "engineer.pouch",
        ), frozenset({Activity.ENGINEERING, Activity.LAB, Activity.CONVERSATION}),
            ALL_SEASONS, style_tags=("technical", "engineer", "canonical_brief")),
        OutfitPlan("engineer.light", under + (
            "engineer.shirt", "engineer.trousers", "engineer.socks",
            "engineer.boots", "engineer.belt", "engineer.pouch",
        ), frozenset({Activity.ENGINEERING, Activity.LAB, Activity.CONVERSATION}),
            frozenset({Season.SPRING, Season.SUMMER, Season.AUTUMN}),
            weather=frozenset({Weather.HOT, Weather.MILD}),
            style_tags=("technical", "engineer", "lightweight")),
        OutfitPlan("lounge.relaxed", under + (
            "lounge.top", "lounge.sweats",
        ), frozenset({Activity.RELAXING, Activity.CONVERSATION, Activity.SLEEP}),
            ALL_SEASONS, lounge=True,
            style_tags=("relaxed", "cozy", "soft", "proposed_colors")),
        OutfitPlan("fallback.covered", under + (
            "fallback.top", "fallback.trousers",
        ), frozenset(Activity), ALL_SEASONS,
            style_tags=("covered", "fallback", "asset_not_yet_verified")),
    )
    presets = (
        base_presets
        + generated_seasonal_outfits()
        + generated_bikini_outfits()
    )
    inputs = (
        StyleInput("engineer.signature", RequestStatus.USER_REQUESTED,
                   "chat.2026-09-22.request.engineer", "Signature engineer wardrobe requested; not a confirmed like."),
        StyleInput("lounge.relaxed", RequestStatus.USER_REQUESTED,
                   "chat.2026-09-22.request.lounge", "Oversized top and sweatpants requested; not a confirmed like."),
    )
    return WardrobePrebuild(wardrobe, blueprints, presets, inputs)


# Source-backed starter taste evidence and optional lounge variation are
# catalog initialization concerns, not separate subsystems.

SPARKS_LIKED_OUTFIT_SOURCE_IDS = frozenset({
    "chat.2026-09-22.like.both.engineer",
    "chat.2026-09-22.like.both.lounge",
})


def confirmed_sparks_outfit_likes() -> tuple[StyleInput, ...]:
    """Outfit likes only; do not infer individual garment or color preferences."""
    return (
        StyleInput(
            "engineer.signature", RequestStatus.USER_LIKED,
            "chat.2026-09-22.like.both.engineer",
            "Sparks answered 'Both' when asked whether he likes the engineer outfit, lounge outfit, both or neither.",
        ),
        StyleInput(
            "lounge.relaxed", RequestStatus.USER_LIKED,
            "chat.2026-09-22.like.both.lounge",
            "Sparks answered 'Both' when asked whether he likes the engineer outfit, lounge outfit, both or neither.",
        ),
    )


def with_sparks_outfit_likes(catalog: WardrobePrebuild) -> WardrobePrebuild:
    """Enrich an existing wardrobe once without overwriting later user input."""
    if not isinstance(catalog, WardrobePrebuild):
        raise WardrobeError("a valid wardrobe prebuild is required")
    existing = {(entry.subject_id, entry.source_id) for entry in catalog.inputs}
    additions = tuple(
        record for record in confirmed_sparks_outfit_likes()
        if (record.subject_id, record.source_id) not in existing
    )
    return replace(catalog, inputs=catalog.inputs + additions)


def build_sparks_starter_wardrobe() -> WardrobePrebuild:
    """Build the starter wardrobe with the confirmed Sparks likes already present."""
    return with_sparks_outfit_likes(build_starter_wardrobe())


GRAPHIC_TEE_ID = "lounge.graphic_tee"
GRAPHIC_OUTFIT_ID = "lounge.graphic"
GRAPHIC_REQUEST_SOURCE_ID = "chat.2026-09-22.request.occasional_graphic_tee"


@dataclass(frozen=True, slots=True)
class GraphicLoungeVariation:
    """Separates an explicitly selectable outfit from routine auto-rotation."""

    catalog: WardrobePrebuild
    optional_plan: OutfitPlan
    print_concepts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, WardrobePrebuild) or not isinstance(self.optional_plan, OutfitPlan):
            raise WardrobeError("graphic variation requires catalog and outfit plan")
        selected = self.catalog.wardrobe.selection(
            self.optional_plan.item_ids
        )
        if (
            not selected.covered_default
            or selected.private_only
            or self.optional_plan.private_only
        ):
            raise WardrobeError(
                "graphic lounge variation must remain covered and public"
            )
        if not isinstance(self.print_concepts, tuple) or not self.print_concepts or any(
            not isinstance(value, str) or not value.strip() for value in self.print_concepts
        ):
            raise WardrobeError("graphic print concepts must be nonempty draft descriptions")

    def select_lounge(self, *, graphic_requested: bool = False) -> OutfitPlan:
        """Plain default; a trusted caller explicitly opts into the occasional graphic.

        The host owns actual rotation timing and confirmation. This method
        neither changes currently worn state nor selects from untrusted prose.
        """
        if type(graphic_requested) is not bool:
            raise WardrobeError("graphic_requested must be a strict boolean")
        return self.optional_plan if graphic_requested else self.catalog.preset("lounge.relaxed")

    def manifest(self) -> dict[str, object]:
        """JSON-ready authoring handoff; no generated print textures or real meshes."""
        result = self.catalog.manifest()
        result["optional_outfits"] = [{
            "outfit_id": self.optional_plan.outfit_id,
            "item_ids": list(self.optional_plan.item_ids),
            "style_tags": list(self.optional_plan.style_tags),
            "selection": "explicit_optional_not_automatic",
        }]
        result["graphic_print_concepts"] = list(self.print_concepts)
        return result


def build_graphic_lounge_variation() -> GraphicLoungeVariation:
    """Build on both outfit likes without interpreting them as a graphic-tee like."""
    catalog = build_sparks_starter_wardrobe()
    plain = next(
        bp for bp in catalog.blueprints if bp.garment.item_id == "lounge.top"
    )
    graphic = replace(
        plain,
        garment=replace(
            plain.garment,
            item_id=GRAPHIC_TEE_ID,
            name="Oversized lounge graphic T-shirt",
            asset_ref=None,
        ),
        construction=plain.construction + (
            "Optional original graphic printed on the front; keep the same relaxed silhouette.",
            "Graphic placement must allow natural jersey drape and torso deformation.",
            "Print art is an unapproved design target; no texture or mesh exists yet.",
        ),
        provenance="design_proposal_review_required",
    )
    blueprints: tuple[GarmentBlueprint, ...] = catalog.blueprints + (graphic,)
    extended = replace(
        catalog,
        wardrobe=Wardrobe(tuple(bp.garment for bp in blueprints)),
        blueprints=blueprints,
        inputs=catalog.inputs + (
            StyleInput(
                GRAPHIC_TEE_ID,
                RequestStatus.USER_REQUESTED,
                GRAPHIC_REQUEST_SOURCE_ID,
                "Sparks approved the lounge concept and requested a graphic T-shirt from time to time; graphic artwork is not yet approved.",
            ),
        ),
    )
    lounge = extended.preset("lounge.relaxed")
    optional_plan = replace(
        lounge,
        outfit_id=GRAPHIC_OUTFIT_ID,
        item_ids=tuple(
            GRAPHIC_TEE_ID if item_id == "lounge.top" else item_id
            for item_id in lounge.item_ids
        ),
        style_tags=lounge.style_tags + (
            "optional_graphic_tee", "manual_selection", "print_art_not_approved",
        ),
    )
    return GraphicLoungeVariation(
        catalog=extended,
        optional_plan=optional_plan,
        print_concepts=(
            "Original minimal fox-and-circuit emblem",
            "Original schematic-inspired constellation graphic",
            "Original tiny engineering joke or abstract circuitry",
        ),
    )

