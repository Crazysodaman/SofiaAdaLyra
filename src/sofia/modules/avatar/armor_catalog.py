"""Parallel garment/equipment type catalog for modular armor.

The ordinary garment vocabulary in :mod:`wardrobe_types` is deliberately not
modified.  This catalog adds the reviewed equipment classes introduced by
:mod:`wardrobe_equipment` as additive type definitions so creators and catalog
consumers can discover canonical slots/coverage without a second inventory or
state engine.  A type definition is metadata only: it never claims a mesh,
renderer asset, fitted variant or physical protection.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .wardrobe import Layer, SLOTS, WardrobeError
from .wardrobe_equipment import ARMOR_CLASSES, EquipmentError, GarmentClass

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


@dataclass(frozen=True, slots=True)
class EquipmentTypeDefinition:
    """Canonical authoring defaults for one modular-equipment class."""

    type_id: str
    garment_class: GarmentClass
    layer: Layer
    slots: tuple[str, ...]
    coverage: tuple[str, ...]
    fit_anchors: tuple[str, ...]
    tail_clearance: bool = False
    ear_clearance: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.type_id, str) or _TOKEN.fullmatch(self.type_id) is None:
            raise EquipmentError("invalid equipment type ID")
        if not isinstance(self.garment_class, GarmentClass):
            raise EquipmentError("equipment type requires a GarmentClass")
        if self.garment_class not in ARMOR_CLASSES:
            raise EquipmentError("equipment types must describe armor components")
        if self.type_id != self.garment_class.value:
            raise EquipmentError("equipment type ID must match its garment class")
        if not isinstance(self.layer, Layer):
            raise EquipmentError("invalid equipment type layer")
        if not self.slots or len(set(self.slots)) != len(self.slots):
            raise EquipmentError("equipment type slots must be unique and nonempty")
        if not set(self.slots).issubset(SLOTS):
            raise EquipmentError("equipment type slots must use canonical wardrobe slots")
        if len(set(self.coverage)) != len(self.coverage):
            raise EquipmentError("equipment type coverage must be unique")
        if not set(self.coverage).issubset(set(self.slots)):
            raise EquipmentError("equipment type coverage must be within its slots")
        if not self.fit_anchors or len(set(self.fit_anchors)) != len(self.fit_anchors):
            raise EquipmentError("equipment type fit anchors must be unique and nonempty")
        for anchor in self.fit_anchors:
            if _TOKEN.fullmatch(anchor) is None:
                raise EquipmentError("invalid equipment type fit anchor")
        if type(self.tail_clearance) is not bool or type(self.ear_clearance) is not bool:
            raise EquipmentError("equipment type clearance flags must be boolean")


def _type(
    garment_class: GarmentClass,
    layer: Layer,
    slots: tuple[str, ...],
    coverage: tuple[str, ...],
    anchors: tuple[str, ...],
    *,
    tail: bool = False,
    ears: bool = False,
) -> EquipmentTypeDefinition:
    return EquipmentTypeDefinition(
        type_id=garment_class.value,
        garment_class=garment_class,
        layer=layer,
        slots=slots,
        coverage=coverage,
        fit_anchors=anchors,
        tail_clearance=tail,
        ear_clearance=ears,
    )


_UNDERSUIT_SLOTS = (
    "torso", "pelvis", "left_leg", "right_leg", "left_upper_arm",
    "right_upper_arm", "left_forearm", "right_forearm", "left_foot",
    "right_foot", "neck",
)
_UNDERSUIT_ANCHORS = (
    "torso.front", "torso.back", "pelvis.coverage", "shoulder.left",
    "shoulder.right", "forearm.left", "forearm.right", "foot.left",
    "foot.right", "neck.center",
)


def _sided(
    left: GarmentClass,
    right: GarmentClass,
    layer: Layer,
    slots_left: tuple[str, ...],
    coverage_left: tuple[str, ...],
    anchors_left: tuple[str, ...],
    *,
    tail: bool = False,
    ears: bool = False,
) -> tuple[EquipmentTypeDefinition, EquipmentTypeDefinition]:
    mirrored_slots = tuple(
        slot.replace("left_", "right_", 1) for slot in slots_left
    )
    mirrored_coverage = tuple(
        slot.replace("left_", "right_", 1) for slot in coverage_left
    )
    mirrored_anchors = tuple(
        anchor.replace("left", "right", 1) for anchor in anchors_left
    )
    return (
        _type(
            left, layer, slots_left, coverage_left, anchors_left,
            tail=tail, ears=ears,
        ),
        _type(
            right, layer, mirrored_slots, mirrored_coverage, mirrored_anchors,
            tail=tail, ears=ears,
        ),
    )


EQUIPMENT_TYPES: tuple[EquipmentTypeDefinition, ...] = (
    _type(
        GarmentClass.ARMOR_UNDERSUIT, Layer.UNDERWEAR,
        _UNDERSUIT_SLOTS, _UNDERSUIT_SLOTS, _UNDERSUIT_ANCHORS,
    ),
    _type(
        GarmentClass.ARMOR_BASE, Layer.OUTER,
        ("torso", "back"), ("torso", "back"),
        ("torso.front", "torso.back"),
    ),
    _type(
        GarmentClass.ARMOR_CHEST, Layer.OUTER,
        ("torso",), ("torso",), ("torso.front",),
    ),
    _type(
        GarmentClass.ARMOR_BACK, Layer.OUTER,
        ("back", "torso"), ("back",), ("torso.back",),
    ),
    _type(
        GarmentClass.ARMOR_HELMET, Layer.OUTER,
        ("head",), ("head",), ("head.crown",), ears=True,
    ),
    _type(
        GarmentClass.ARMOR_VISOR, Layer.OUTER,
        ("head",), (), ("head.crown",),
    ),
    *_sided(
        GarmentClass.ARMOR_SHOULDER_LEFT, GarmentClass.ARMOR_SHOULDER_RIGHT,
        Layer.OUTER,
        ("left_shoulder", "left_upper_arm"),
        ("left_shoulder",),
        ("shoulder.left",),
    ),
    *_sided(
        GarmentClass.ARMOR_FOREARM_LEFT, GarmentClass.ARMOR_FOREARM_RIGHT,
        Layer.OUTER,
        ("left_forearm", "left_wrist"),
        ("left_forearm",),
        ("forearm.left",),
    ),
    *_sided(
        GarmentClass.ARMOR_GAUNTLET_LEFT, GarmentClass.ARMOR_GAUNTLET_RIGHT,
        Layer.OUTER,
        ("left_hand", "left_fingers", "left_wrist"),
        ("left_hand", "left_fingers"),
        ("wrist.left",),
    ),
    *_sided(
        GarmentClass.ARMOR_THIGH_LEFT, GarmentClass.ARMOR_THIGH_RIGHT,
        Layer.OUTER,
        ("left_thigh",), ("left_thigh",), ("thigh.left",),
    ),
    *_sided(
        GarmentClass.ARMOR_SHIN_LEFT, GarmentClass.ARMOR_SHIN_RIGHT,
        Layer.OUTER,
        ("left_calf",), ("left_calf",), ("calf.left",),
    ),
    *_sided(
        GarmentClass.ARMOR_BOOT_LEFT, GarmentClass.ARMOR_BOOT_RIGHT,
        Layer.OUTER,
        ("left_foot", "left_ankle"),
        ("left_foot",), ("foot.left",),
    ),
    _type(
        GarmentClass.ARMOR_ATTACHMENT, Layer.ACCESSORY,
        ("torso", "back"), (),
        ("torso.front", "torso.back"),
    ),
)

_BY_ID = {item.type_id: item for item in EQUIPMENT_TYPES}
_BY_CLASS = {item.garment_class: item for item in EQUIPMENT_TYPES}

if len(_BY_ID) != len(EQUIPMENT_TYPES) or len(_BY_CLASS) != len(EQUIPMENT_TYPES):
    raise EquipmentError("duplicate equipment type definition")
if set(_BY_CLASS) != set(ARMOR_CLASSES):
    raise EquipmentError("equipment type catalog must cover every armor class")


def equipment_type(type_id: str) -> EquipmentTypeDefinition:
    if not isinstance(type_id, str):
        raise WardrobeError("equipment type ID must be a string")
    try:
        return _BY_ID[type_id]
    except KeyError as exc:
        raise WardrobeError(f"unknown equipment type: {type_id}") from exc


def equipment_type_for_class(
    garment_class: GarmentClass,
) -> EquipmentTypeDefinition:
    if not isinstance(garment_class, GarmentClass):
        raise WardrobeError("equipment class must be GarmentClass")
    try:
        return _BY_CLASS[garment_class]
    except KeyError as exc:
        raise WardrobeError(
            f"no equipment type for garment class: {garment_class.value}"
        ) from exc


def all_equipment_types() -> tuple[EquipmentTypeDefinition, ...]:
    return EQUIPMENT_TYPES


__all__ = [
    "EQUIPMENT_TYPES",
    "EquipmentTypeDefinition",
    "all_equipment_types",
    "equipment_type",
    "equipment_type_for_class",
]
