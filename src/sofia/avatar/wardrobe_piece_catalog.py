"""Generated individual wardrobe-piece specifications.

The closet uses human-facing categories mapped onto the existing AVATAR rig
slots. These are metadata/design proposals only. Adult/private pieces are
explicitly private-only and never become public/default presentation merely
because their slot/coverage metadata happens to fit.
"""
from __future__ import annotations

from dataclasses import dataclass

from .wardrobe import Layer


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
    ClosetCategory("closet.top", "Tops", "top", "private top", Layer.BASE, ("torso", "upper_arms"), ("torso", "upper_arms"), ("torso.front", "torso.back", "shoulder.left", "shoulder.right")),
    ClosetCategory("closet.bottom", "Bottoms", "bottom", "private bottom", Layer.BASE, ("pelvis", "legs", "tail"), ("pelvis", "legs"), ("pelvis.coverage", "tail.opening.clearance"), tail_clearance=True),
    ClosetCategory("closet.one_piece", "One-piece clothing", "one-piece", "private one-piece", Layer.BASE, ("torso", "pelvis", "legs", "tail"), ("torso", "pelvis", "legs"), ("torso.front", "torso.back", "pelvis.coverage", "tail.opening.clearance"), tail_clearance=True),
    ClosetCategory("closet.outerwear", "Outerwear", "jacket", "private wrap", Layer.OUTER, ("torso", "shoulders", "upper_arms", "forearms", "tail"), ("torso", "shoulders", "upper_arms", "forearms"), ("torso.front", "torso.back", "shoulder.left", "shoulder.right", "tail.opening.clearance"), tail_clearance=True),
    ClosetCategory("closet.footwear", "Footwear", "footwear", "private footwear", Layer.BASE, ("feet", "ankles", "calves"), ("feet", "ankles", "calves"), ("foot.left", "foot.right")),
    ClosetCategory("closet.legwear", "Legwear", "legwear", "private legwear", Layer.MID, ("legs", "thighs", "calves"), ("legs", "thighs", "calves"), ("thigh.left", "thigh.right", "calf.left", "calf.right")),
    ClosetCategory("closet.handwear", "Handwear", "gloves", "private gloves", Layer.ACCESSORY, ("hands", "fingers"), ("hands", "fingers"), ("wrist.left", "wrist.right")),
    ClosetCategory("closet.forearm_wrist", "Forearm and wrist pieces", "wrist piece", "private wrist piece", Layer.ACCESSORY, ("forearms", "wrists"), ("forearms", "wrists"), ("forearm.left", "forearm.right", "wrist.left", "wrist.right")),
    ClosetCategory("closet.headwear", "Headwear", "headpiece", "private headpiece", Layer.ACCESSORY, ("head", "ears"), ("head",), ("head.crown", "ear.left", "ear.right"), ear_clearance=True),
    ClosetCategory("closet.neckwear", "Neckwear", "neck piece", "choker", Layer.ACCESSORY, ("neck",), ("neck",), ("neck.center",)),
    ClosetCategory("closet.waistwear", "Waist pieces", "belt", "private waist piece", Layer.ACCESSORY, ("waist",), ("waist",), ("waist.front",)),
    ClosetCategory("closet.backwear", "Back and harness pieces", "back piece", "fashion harness", Layer.ACCESSORY, ("back", "shoulders"), (), ("torso.back", "shoulder.left", "shoulder.right")),
    ClosetCategory("closet.ear_accessory", "Ear accessories", "ear accessory", "private ear accessory", Layer.ACCESSORY, ("ears",), (), ("ear.left", "ear.right"), ear_clearance=True),
    ClosetCategory("closet.tail_accessory", "Tail accessories", "tail accessory", "private tail accessory", Layer.ACCESSORY, ("tail",), (), ("tail.base", "tail.mid"), tail_clearance=True),
    ClosetCategory("closet.hair_accessory", "Hair accessories", "hair accessory", "private hair accessory", Layer.ACCESSORY, ("hair",), (), ("head.crown",)),
    ClosetCategory("closet.shoulder_accessory", "Shoulder pieces", "shoulder piece", "private shoulder piece", Layer.ACCESSORY, ("shoulders",), ("shoulders",), ("shoulder.left", "shoulder.right")),
)

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
    material = (
        "soft stretch lace, satin, mesh or fashion textile"
        if private_only
        else "reviewed opaque textile appropriate to the garment category"
    )
    construction = (
        (
            "Adult/private wardrobe design metadata; no renderer asset is implied.",
            "Private-only classification is independent of emotion, attraction or consent.",
            "Fit must preserve fox-ear/tail clearance where the mapped rig slot requires it.",
        )
        if private_only
        else (
            "Mix-and-match wardrobe design metadata; no renderer asset is implied.",
            "Normal/public eligibility still depends on full outfit coverage and verified assets.",
            "Fit must preserve fox-ear/tail clearance where the mapped rig slot requires it.",
        )
    )
    return PieceSpec(
        item_id=f"closet.{visibility}.{category.category_id.split('.', 1)[1]}.{index:02d}",
        name=f"{style.replace('-', ' ').title()} {noun.title()}",
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
    """Return 25 normal + 25 adult/private pieces for every closet category."""
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
    return tuple(pieces)
