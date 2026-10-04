"""Structured garment design vocabulary for Sofía's wardrobe creator.

This module describes what a garment is. It does not claim that an asset exists,
that a garment is currently worn, or that a renderer has displayed it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .wardrobe import Layer, WardrobeError

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\\Z", re.ASCII)
_STYLE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\\Z", re.ASCII)
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\\Z")

PALETTE: dict[str, str] = {
    "black": "#0B0D12",
    "charcoal": "#171A21",
    "crimson": "#8B1E3F",
    "dark_violet": "#3A245C",
    "cyan": "#19D3C5",
    "soft_violet": "#6A4C93",
    "silver": "#AAB2BD",
}


def resolve_color(value: str) -> str:
    """Resolve a named palette color or accept an explicit RGB hex."""
    if not isinstance(value, str) or not value.strip():
        raise WardrobeError("color must be nonempty")
    key = value.strip()
    if _HEX.fullmatch(key):
        return key.upper()
    try:
        return PALETTE[key.casefold()]
    except KeyError as exc:
        raise WardrobeError(f"unknown wardrobe color: {value}") from exc


class GarmentFamily(str, Enum):
    UNDERWEAR = "underwear"
    TOP = "top"
    BOTTOM = "bottom"
    ONE_PIECE = "one_piece"
    OUTERWEAR = "outerwear"
    FOOTWEAR = "footwear"
    LEGWEAR = "legwear"
    ACCESSORY = "accessory"


@dataclass(frozen=True, slots=True)
class GarmentTypeDefinition:
    type_id: str
    family: GarmentFamily
    layer: Layer
    slots: tuple[str, ...]
    coverage: tuple[str, ...]
    fit_anchors: tuple[str, ...]
    supports_rise: bool = False
    supports_sleeve_length: bool = False
    supports_graphic: bool = True
    tail_clearance: bool = False
    ear_clearance: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.type_id, str) or _TOKEN.fullmatch(self.type_id) is None:
            raise WardrobeError("invalid garment type ID")
        if not isinstance(self.family, GarmentFamily):
            raise WardrobeError("invalid garment family")
        if not isinstance(self.layer, Layer):
            raise WardrobeError("invalid garment type layer")
        if not self.slots or len(set(self.slots)) != len(self.slots):
            raise WardrobeError("garment type slots must be unique and nonempty")
        if len(set(self.coverage)) != len(self.coverage):
            raise WardrobeError("garment type coverage must be unique")
        if not set(self.coverage).issubset(set(self.slots)):
            raise WardrobeError("garment type coverage must be within its slots")
        if not self.fit_anchors or len(set(self.fit_anchors)) != len(self.fit_anchors):
            raise WardrobeError("garment type fit anchors must be unique and nonempty")
        if any(type(flag) is not bool for flag in (
            self.supports_rise,
            self.supports_sleeve_length,
            self.supports_graphic,
            self.tail_clearance,
            self.ear_clearance,
        )):
            raise WardrobeError("garment type flags must be boolean")


@dataclass(frozen=True, slots=True)
class GraphicDesign:
    enabled: bool = False
    placement: str | None = None
    design: str | None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise WardrobeError("graphic enabled flag must be boolean")
        if self.enabled:
            if (
                not isinstance(self.placement, str)
                or not self.placement.strip()
                or not isinstance(self.design, str)
                or not self.design.strip()
            ):
                raise WardrobeError(
                    "enabled graphic requires placement and design"
                )
        elif self.placement is not None or self.design is not None:
            raise WardrobeError(
                "disabled graphic cannot define placement or design"
            )


@dataclass(frozen=True, slots=True)
class GarmentDesign:
    """Creator-facing structured design for one actual wardrobe piece."""

    item_id: str
    name: str
    garment_type: str
    fit: str
    rise: str | None
    length: str
    sleeve_length: str | None
    material: str
    primary: str
    accent: str | None
    pattern: str
    graphic: GraphicDesign
    features: tuple[str, ...]
    style_tags: tuple[str, ...] = ()
    private_only: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        for value, label in (
            (self.item_id, "item ID"),
            (self.garment_type, "garment type"),
            (self.fit, "fit"),
            (self.length, "length"),
        ):
            if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
                raise WardrobeError(f"invalid {label}")
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 160:
            raise WardrobeError("invalid garment name")
        if self.rise is not None and (
            not isinstance(self.rise, str) or _STYLE.fullmatch(self.rise) is None
        ):
            raise WardrobeError("invalid garment rise")
        if self.sleeve_length is not None and (
            not isinstance(self.sleeve_length, str)
            or _STYLE.fullmatch(self.sleeve_length) is None
        ):
            raise WardrobeError("invalid sleeve length")
        if not isinstance(self.material, str) or not self.material.strip():
            raise WardrobeError("material is required")
        resolve_color(self.primary)
        if self.accent is not None:
            resolve_color(self.accent)
        if not isinstance(self.pattern, str) or not self.pattern.strip():
            raise WardrobeError("pattern is required")
        if not isinstance(self.graphic, GraphicDesign):
            raise WardrobeError("graphic must be GraphicDesign")
        for values, label in (
            (self.features, "features"),
            (self.style_tags, "style tags"),
        ):
            if (
                not isinstance(values, tuple)
                or len(set(values)) != len(values)
                or any(
                    not isinstance(value, str)
                    or _STYLE.fullmatch(value) is None
                    for value in values
                )
            ):
                raise WardrobeError(f"invalid {label}")
        if type(self.private_only) is not bool:
            raise WardrobeError("private_only must be boolean")
        if (
            not isinstance(self.description, str)
            or not self.description.strip()
            or len(self.description) > 1600
        ):
            raise WardrobeError("description must be bounded nonempty text")


def _type(
    type_id: str,
    family: GarmentFamily,
    layer: Layer,
    slots: tuple[str, ...],
    coverage: tuple[str, ...],
    anchors: tuple[str, ...],
    *,
    rise: bool = False,
    sleeves: bool = False,
    graphic: bool = True,
    tail: bool = False,
    ears: bool = False,
) -> GarmentTypeDefinition:
    return GarmentTypeDefinition(
        type_id=type_id,
        family=family,
        layer=layer,
        slots=slots,
        coverage=coverage,
        fit_anchors=anchors,
        supports_rise=rise,
        supports_sleeve_length=sleeves,
        supports_graphic=graphic,
        tail_clearance=tail,
        ear_clearance=ears,
    )


GARMENT_TYPES: tuple[GarmentTypeDefinition, ...] = (
    _type("bralette", GarmentFamily.UNDERWEAR, Layer.UNDERWEAR,
          ("torso",), ("torso",), ("torso.front", "torso.back"),
          graphic=False),
    _type("briefs", GarmentFamily.UNDERWEAR, Layer.UNDERWEAR,
          ("pelvis", "tail"), ("pelvis",),
          ("pelvis.coverage", "tail.opening.clearance"),
          rise=True, graphic=False, tail=True),
    _type("ankle_socks", GarmentFamily.UNDERWEAR, Layer.UNDERWEAR,
          ("left_foot", "right_foot", "left_ankle", "right_ankle"),
          ("left_foot", "right_foot", "left_ankle", "right_ankle"),
          ("foot.left", "foot.right"), graphic=False),
    _type("crew_socks", GarmentFamily.UNDERWEAR, Layer.UNDERWEAR,
          ("left_foot", "right_foot", "left_ankle", "right_ankle",
           "left_calf", "right_calf"),
          ("left_foot", "right_foot", "left_ankle", "right_ankle",
           "left_calf", "right_calf"),
          ("foot.left", "foot.right", "calf.left", "calf.right"),
          graphic=False),

    _type("t_shirt", GarmentFamily.TOP, Layer.BASE,
          ("torso", "left_upper_arm", "right_upper_arm"),
          ("torso", "left_upper_arm", "right_upper_arm"),
          ("torso.front", "torso.back", "shoulder.left", "shoulder.right"),
          sleeves=True),
    _type("crop_top", GarmentFamily.TOP, Layer.BASE,
          ("torso", "left_upper_arm", "right_upper_arm"),
          ("torso", "left_upper_arm", "right_upper_arm"),
          ("torso.front", "torso.back", "shoulder.left", "shoulder.right"),
          sleeves=True),
    _type("tank_top", GarmentFamily.TOP, Layer.BASE,
          ("torso",), ("torso",),
          ("torso.front", "torso.back")),
    _type("long_sleeve_tee", GarmentFamily.TOP, Layer.BASE,
          ("torso", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
           "forearm.left", "forearm.right"),
          sleeves=True),
    _type("button_up", GarmentFamily.TOP, Layer.BASE,
          ("torso", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
           "forearm.left", "forearm.right"),
          sleeves=True),
    _type("hoodie", GarmentFamily.TOP, Layer.MID,
          ("torso", "head", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso", "head", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso.front", "torso.back", "head.crown",
           "shoulder.left", "shoulder.right", "forearm.left", "forearm.right"),
          sleeves=True, ears=True),
    _type("sweater", GarmentFamily.TOP, Layer.MID,
          ("torso", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso", "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
           "forearm.left", "forearm.right"),
          sleeves=True),

    _type("running_shorts", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_thigh", "right_thigh", "tail"),
          ("pelvis", "left_thigh", "right_thigh"),
          ("pelvis.coverage", "thigh.left", "thigh.right",
           "tail.opening.clearance"),
          rise=True, tail=True),
    _type("athletic_shorts", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_thigh", "right_thigh", "tail"),
          ("pelvis", "left_thigh", "right_thigh"),
          ("pelvis.coverage", "thigh.left", "thigh.right",
           "tail.opening.clearance"),
          rise=True, tail=True),
    _type("denim_shorts", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_thigh", "right_thigh", "tail"),
          ("pelvis", "left_thigh", "right_thigh"),
          ("pelvis.coverage", "thigh.left", "thigh.right",
           "tail.opening.clearance"),
          rise=True, tail=True),
    _type("cargo_shorts", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_thigh", "right_thigh", "tail"),
          ("pelvis", "left_thigh", "right_thigh"),
          ("pelvis.coverage", "thigh.left", "thigh.right",
           "tail.opening.clearance"),
          rise=True, tail=True),
    _type("lounge_shorts", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_thigh", "right_thigh", "tail"),
          ("pelvis", "left_thigh", "right_thigh"),
          ("pelvis.coverage", "thigh.left", "thigh.right",
           "tail.opening.clearance"),
          rise=True, tail=True),
    _type("bike_shorts", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_thigh", "right_thigh", "tail"),
          ("pelvis", "left_thigh", "right_thigh"),
          ("pelvis.coverage", "thigh.left", "thigh.right",
           "tail.opening.clearance"),
          rise=True, tail=True),
    _type("utility_trousers", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_leg", "right_leg", "tail"),
          ("pelvis", "left_leg", "right_leg"),
          ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
          rise=True, tail=True),
    _type("jeans", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_leg", "right_leg", "tail"),
          ("pelvis", "left_leg", "right_leg"),
          ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
          rise=True, tail=True),
    _type("leggings", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_leg", "right_leg", "tail"),
          ("pelvis", "left_leg", "right_leg"),
          ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
          rise=True, tail=True),
    _type("skirt", GarmentFamily.BOTTOM, Layer.BASE,
          ("pelvis", "left_thigh", "right_thigh", "tail"),
          ("pelvis",),
          ("pelvis.coverage", "waist.front", "tail.opening.clearance"),
          rise=True, tail=True),

    _type("dress", GarmentFamily.ONE_PIECE, Layer.BASE,
          ("torso", "pelvis", "left_thigh", "right_thigh", "tail"),
          ("torso", "pelvis", "left_thigh", "right_thigh"),
          ("torso.front", "torso.back", "pelvis.coverage",
           "thigh.left", "thigh.right", "tail.opening.clearance"),
          sleeves=True, tail=True),
    _type("jumpsuit", GarmentFamily.ONE_PIECE, Layer.BASE,
          ("torso", "pelvis", "left_leg", "right_leg", "tail"),
          ("torso", "pelvis", "left_leg", "right_leg"),
          ("torso.front", "torso.back", "pelvis.coverage",
           "tail.opening.clearance"),
          sleeves=True, tail=True),

    _type("engineer_jacket", GarmentFamily.OUTERWEAR, Layer.OUTER,
          ("torso", "left_shoulder", "right_shoulder",
           "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm", "tail"),
          ("torso", "left_shoulder", "right_shoulder",
           "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
           "forearm.left", "forearm.right", "tail.opening.clearance"),
          sleeves=True, tail=True),
    _type("bomber_jacket", GarmentFamily.OUTERWEAR, Layer.OUTER,
          ("torso", "left_shoulder", "right_shoulder",
           "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso", "left_shoulder", "right_shoulder",
           "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso.front", "torso.back", "shoulder.left", "shoulder.right",
           "forearm.left", "forearm.right"),
          sleeves=True),
    _type("coat", GarmentFamily.OUTERWEAR, Layer.OUTER,
          ("torso", "pelvis", "left_shoulder", "right_shoulder",
           "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm", "tail"),
          ("torso", "pelvis", "left_shoulder", "right_shoulder",
           "left_upper_arm", "right_upper_arm",
           "left_forearm", "right_forearm"),
          ("torso.front", "torso.back", "pelvis.coverage",
           "shoulder.left", "shoulder.right",
           "forearm.left", "forearm.right", "tail.opening.clearance"),
          sleeves=True, tail=True),

    _type("sneakers", GarmentFamily.FOOTWEAR, Layer.BASE,
          ("left_foot", "right_foot", "left_ankle", "right_ankle"),
          ("left_foot", "right_foot", "left_ankle", "right_ankle"),
          ("foot.left", "foot.right"), graphic=False),
    _type("work_boots", GarmentFamily.FOOTWEAR, Layer.BASE,
          ("left_foot", "right_foot", "left_ankle", "right_ankle",
           "left_calf", "right_calf"),
          ("left_foot", "right_foot", "left_ankle", "right_ankle",
           "left_calf", "right_calf"),
          ("foot.left", "foot.right", "calf.left", "calf.right"),
          graphic=False),
    _type("slippers", GarmentFamily.FOOTWEAR, Layer.BASE,
          ("left_foot", "right_foot"),
          ("left_foot", "right_foot"),
          ("foot.left", "foot.right"), graphic=False),
    _type("sandals", GarmentFamily.FOOTWEAR, Layer.BASE,
          ("left_foot", "right_foot"),
          ("left_foot", "right_foot"),
          ("foot.left", "foot.right"), graphic=False),

    _type("fingerless_gloves", GarmentFamily.ACCESSORY, Layer.ACCESSORY,
          ("left_hand", "right_hand", "left_fingers", "right_fingers"),
          ("left_hand", "right_hand"),
          ("wrist.left", "wrist.right"), graphic=False),
    _type("gauntlets", GarmentFamily.ACCESSORY, Layer.ACCESSORY,
          ("left_forearm", "right_forearm", "left_wrist", "right_wrist"),
          ("left_forearm", "right_forearm", "left_wrist", "right_wrist"),
          ("forearm.left", "forearm.right", "wrist.left", "wrist.right"),
          graphic=False),
    _type("belt", GarmentFamily.ACCESSORY, Layer.ACCESSORY,
          ("waist",), ("waist",), ("waist.front",), graphic=False),
    _type("ear_accessory", GarmentFamily.ACCESSORY, Layer.ACCESSORY,
          ("left_ear", "right_ear"), (),
          ("ear.left", "ear.right"), ears=True),
    _type("tail_accessory", GarmentFamily.ACCESSORY, Layer.ACCESSORY,
          ("tail",), (), ("tail.base", "tail.mid"),
          graphic=False, tail=True),
)

_TYPE_BY_ID = {item.type_id: item for item in GARMENT_TYPES}


def garment_type(type_id: str) -> GarmentTypeDefinition:
    if not isinstance(type_id, str):
        raise WardrobeError("garment type ID must be a string")
    try:
        return _TYPE_BY_ID[type_id]
    except KeyError as exc:
        raise WardrobeError(f"unknown garment type: {type_id}") from exc


def all_garment_types() -> tuple[GarmentTypeDefinition, ...]:
    return GARMENT_TYPES


def validate_design(design: GarmentDesign) -> GarmentTypeDefinition:
    """Validate type-specific fields and return the resolved type definition."""
    if not isinstance(design, GarmentDesign):
        raise TypeError("design must be GarmentDesign")
    definition = garment_type(design.garment_type)
    if definition.supports_rise:
        if design.rise is None:
            raise WardrobeError(
                f"{design.garment_type} requires rise"
            )
    elif design.rise is not None:
        raise WardrobeError(
            f"{design.garment_type} does not support rise"
        )
    if definition.supports_sleeve_length:
        if design.sleeve_length is None:
            raise WardrobeError(
                f"{design.garment_type} requires sleeve_length"
            )
    elif design.sleeve_length is not None:
        raise WardrobeError(
            f"{design.garment_type} does not support sleeve_length"
        )
    if design.graphic.enabled and not definition.supports_graphic:
        raise WardrobeError(
            f"{design.garment_type} does not support graphics"
        )
    return definition
