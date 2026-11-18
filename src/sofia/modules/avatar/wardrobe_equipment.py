"""Universal wardrobe equipment metadata and modular armor dependency rules.

An undersuit, an armor base and every plate/boot/visor/attachment are ordinary
wardrobe designs.  They are *not* a second inventory: an item instance is owned
and traded exactly like a jacket.  This module only validates the additive
equipment metadata and the mandatory dependency graph:

    compatible equipped undersuit -> fixed armor base -> compatible part/mount

No function here claims a mesh exists, proves body fit, grants physical
protection, or creates a separate armor permission store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Iterable, Mapping
from uuid import UUID

from .wardrobe import Layer, SLOTS, WardrobeError, normalize_slots

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\Z")


class EquipmentError(WardrobeError):
    """A wardrobe equipment definition or dependency rule is invalid."""


class GarmentClass(str, Enum):
    """Ordinary clothing plus the reviewed modular-armor component classes."""

    CLOTHING = "clothing"
    ARMOR_UNDERSUIT = "armor_undersuit"
    ARMOR_BASE = "armor_base"
    ARMOR_CHEST = "armor_chest"
    ARMOR_BACK = "armor_back"
    ARMOR_HELMET = "armor_helmet"
    ARMOR_VISOR = "armor_visor"
    ARMOR_SHOULDER_LEFT = "armor_shoulder_left"
    ARMOR_SHOULDER_RIGHT = "armor_shoulder_right"
    ARMOR_FOREARM_LEFT = "armor_forearm_left"
    ARMOR_FOREARM_RIGHT = "armor_forearm_right"
    ARMOR_GAUNTLET_LEFT = "armor_gauntlet_left"
    ARMOR_GAUNTLET_RIGHT = "armor_gauntlet_right"
    ARMOR_THIGH_LEFT = "armor_thigh_left"
    ARMOR_THIGH_RIGHT = "armor_thigh_right"
    ARMOR_SHIN_LEFT = "armor_shin_left"
    ARMOR_SHIN_RIGHT = "armor_shin_right"
    ARMOR_BOOT_LEFT = "armor_boot_left"
    ARMOR_BOOT_RIGHT = "armor_boot_right"
    ARMOR_ATTACHMENT = "armor_attachment"


ARMOR_CLASSES: frozenset[GarmentClass] = frozenset(
    item for item in GarmentClass if item is not GarmentClass.CLOTHING
)
SIDED_CLASSES: frozenset[GarmentClass] = frozenset({
    GarmentClass.ARMOR_SHOULDER_LEFT,
    GarmentClass.ARMOR_SHOULDER_RIGHT,
    GarmentClass.ARMOR_FOREARM_LEFT,
    GarmentClass.ARMOR_FOREARM_RIGHT,
    GarmentClass.ARMOR_GAUNTLET_LEFT,
    GarmentClass.ARMOR_GAUNTLET_RIGHT,
    GarmentClass.ARMOR_THIGH_LEFT,
    GarmentClass.ARMOR_THIGH_RIGHT,
    GarmentClass.ARMOR_SHIN_LEFT,
    GarmentClass.ARMOR_SHIN_RIGHT,
    GarmentClass.ARMOR_BOOT_LEFT,
    GarmentClass.ARMOR_BOOT_RIGHT,
})


class ArmorFamily(str, Enum):
    MARK_IV = "mark_iv"
    MARK_V = "mark_v"


class ArmorSeries(str, Enum):
    MARK_IV_CQB = "mark_iv_cqb"
    MARK_IV = "mark_iv"
    MARK_V = "mark_v"


class WardrobePrivacy(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ADULT = "adult"


CONTENT_RATINGS = frozenset({"standard", "lewd", "explicit"})
MAX_ROUGHNESS = 1.0
DEFAULT_ARMOR_ROUGHNESS = 0.55


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise EquipmentError(f"{label} must be a bounded identifier")
    return value


def _text(value: object, label: str, *, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(character) < 0x20 for character in value)
    ):
        raise EquipmentError(f"{label} must be bounded visible text")
    return value


def _hex(value: object, label: str) -> str:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        raise EquipmentError(f"{label} must be a six-digit hex color")
    return value


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise EquipmentError(f"{label} must be a nonzero UUID")
    return value


def _unique_tuple(values: object, label: str) -> tuple:
    if not isinstance(values, tuple):
        raise EquipmentError(f"{label} must be a tuple")
    if len(set(values)) != len(values):
        raise EquipmentError(f"{label} must be unique")
    return values


@dataclass(frozen=True, slots=True)
class ArmorMetadata:
    """Additive compatibility metadata attached to one wardrobe design."""

    family: ArmorFamily
    undersuit_interface: str
    requires_undersuit: bool = True
    requires_base: bool = False
    base_series: ArmorSeries | None = None
    mount_id: str | None = None
    socket: str | None = None
    provided_mounts: tuple[str, ...] = ()
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    visor_color: str | None = None
    unresolved_color_channels: tuple[str, ...] = ()
    roughness: float = DEFAULT_ARMOR_ROUGHNESS
    weathered: bool = True
    reflective: bool = True
    compatible_body_profiles: tuple[str, ...] = ("human",)

    def __post_init__(self) -> None:
        if not isinstance(self.family, ArmorFamily):
            raise EquipmentError("armor family must be ArmorFamily")
        _identifier(self.undersuit_interface, "undersuit_interface")
        for flag in (
            "requires_undersuit", "requires_base", "weathered", "reflective",
        ):
            if type(getattr(self, flag)) is not bool:
                raise EquipmentError(f"{flag} must be boolean")
        if self.base_series is not None and not isinstance(self.base_series, ArmorSeries):
            raise EquipmentError("base_series must be ArmorSeries")
        if self.requires_base and self.base_series is None:
            raise EquipmentError("components that require a base must name its series")
        if self.mount_id is not None:
            _identifier(self.mount_id, "mount_id")
        if self.socket is not None:
            _identifier(self.socket, "socket")
        _unique_tuple(self.provided_mounts, "provided_mounts")
        for mount in self.provided_mounts:
            _identifier(mount, "provided mount")
        for name in ("primary_color", "secondary_color", "accent_color", "visor_color"):
            value = getattr(self, name)
            if value is not None:
                _hex(value, name)
        _unique_tuple(self.unresolved_color_channels, "unresolved_color_channels")
        allowed_channels = {"primary", "secondary", "accent", "visor"}
        if not set(self.unresolved_color_channels).issubset(allowed_channels):
            raise EquipmentError("unresolved color channel is unknown")
        if (
            isinstance(self.roughness, bool)
            or not isinstance(self.roughness, (int, float))
            or not 0.0 <= float(self.roughness) <= MAX_ROUGHNESS
        ):
            raise EquipmentError("armor roughness must be in [0, 1]")
        _unique_tuple(self.compatible_body_profiles, "compatible_body_profiles")
        for profile in self.compatible_body_profiles:
            _identifier(profile, "body profile")
        if not self.compatible_body_profiles:
            raise EquipmentError("at least one compatible body profile is required")


@dataclass(frozen=True, slots=True)
class WardrobeDesign:
    """Immutable catalog design, shared for discovery by every Core.

    A design is not an owned instance, a fitted variant, a selected outfit or a
    renderer receipt.  Catalog visibility never transfers ownership or consent.
    """

    design_id: str
    version: int
    name: str
    garment_class: GarmentClass
    garment_type: str
    layer: Layer
    slots: tuple[str, ...]
    coverage: tuple[str, ...]
    fit_anchors: tuple[str, ...]
    privacy: WardrobePrivacy = WardrobePrivacy.PUBLIC
    content_rating: str = "standard"
    asset_ref: str | None = None
    source: str = "aegis.wardrobe.reviewed"
    license: str = "project-owned"
    armor: ArmorMetadata | None = None
    tail_clearance: bool = False
    ear_clearance: bool = False

    def __post_init__(self) -> None:
        _identifier(self.design_id, "design_id")
        if type(self.version) is not int or not 1 <= self.version <= 2**31 - 1:
            raise EquipmentError("design version must be a positive integer")
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 160:
            raise EquipmentError("design name must be bounded nonempty text")
        if not isinstance(self.garment_class, GarmentClass):
            raise EquipmentError("garment_class must be GarmentClass")
        _identifier(self.garment_type, "garment_type")
        if not isinstance(self.layer, Layer):
            raise EquipmentError("layer must be a wardrobe Layer")
        if not self.slots or len(set(self.slots)) != len(self.slots):
            raise EquipmentError("design slots must be unique and nonempty")
        if not set(self.slots).issubset(SLOTS):
            raise EquipmentError("design slots must use the canonical wardrobe vocabulary")
        if (
            len(set(self.coverage)) != len(self.coverage)
            or not set(self.coverage).issubset(set(self.slots))
        ):
            raise EquipmentError("coverage must be unique slots within the design")
        if not self.fit_anchors or len(set(self.fit_anchors)) != len(self.fit_anchors):
            raise EquipmentError("fit anchors must be unique and nonempty")
        for anchor in self.fit_anchors:
            _identifier(anchor, "fit anchor")
        if not isinstance(self.privacy, WardrobePrivacy):
            raise EquipmentError("privacy must be WardrobePrivacy")
        if self.content_rating not in CONTENT_RATINGS:
            raise EquipmentError("content_rating is unknown")
        if self.content_rating != "standard" and self.privacy is not WardrobePrivacy.PRIVATE:
            raise EquipmentError("lewd/explicit designs must be private")
        if self.asset_ref is not None:
            _identifier(self.asset_ref, "asset_ref")
        _text(self.source, "source")
        _text(self.license, "license")
        for flag in ("tail_clearance", "ear_clearance"):
            if type(getattr(self, flag)) is not bool:
                raise EquipmentError(f"{flag} must be boolean")
        if self.is_armor:
            if not isinstance(self.armor, ArmorMetadata):
                raise EquipmentError("armor designs require ArmorMetadata")
        elif self.armor is not None:
            raise EquipmentError("ordinary clothing cannot carry armor metadata")
        if self.garment_class is GarmentClass.ARMOR_UNDERSUIT:
            assert self.armor is not None
            if self.armor.requires_undersuit:
                raise EquipmentError("an undersuit is the undersuit, not its own dependent")
        if self.garment_class is GarmentClass.ARMOR_BASE:
            assert self.armor is not None
            if not self.armor.requires_undersuit:
                raise EquipmentError("every approved armor base requires an undersuit")
            if self.armor.requires_base or self.armor.base_series is None:
                raise EquipmentError("an armor base defines its series and has no base dependency")
        if self.is_armor_part:
            assert self.armor is not None
            if not self.armor.requires_undersuit or not self.armor.requires_base:
                raise EquipmentError("armor components require both undersuit and base")

    @property
    def is_armor(self) -> bool:
        return self.garment_class in ARMOR_CLASSES

    @property
    def is_armor_part(self) -> bool:
        return self.is_armor and self.garment_class not in {
            GarmentClass.ARMOR_UNDERSUIT, GarmentClass.ARMOR_BASE,
        }

    @property
    def normalized_slots(self) -> tuple[str, ...]:
        return normalize_slots(self.slots)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "aegis.avatar.wardrobe_design.v1",
            "design_id": self.design_id,
            "version": self.version,
            "name": self.name,
            "garment_class": self.garment_class.value,
            "garment_type": self.garment_type,
            "layer": self.layer.name.lower(),
            "slots": list(self.slots),
            "coverage": list(self.coverage),
            "fit_anchors": list(self.fit_anchors),
            "privacy": self.privacy.value,
            "content_rating": self.content_rating,
            "asset_ref": self.asset_ref,
            "source": self.source,
            "license": self.license,
            "armor": None if self.armor is None else _armor_payload(self.armor),
            "tail_clearance": self.tail_clearance,
            "ear_clearance": self.ear_clearance,
        }


def _armor_payload(armor: ArmorMetadata) -> dict[str, object]:
    return {
        "family": armor.family.value,
        "undersuit_interface": armor.undersuit_interface,
        "requires_undersuit": armor.requires_undersuit,
        "requires_base": armor.requires_base,
        "base_series": None if armor.base_series is None else armor.base_series.value,
        "mount_id": armor.mount_id,
        "socket": armor.socket,
        "provided_mounts": list(armor.provided_mounts),
        "primary_color": armor.primary_color,
        "secondary_color": armor.secondary_color,
        "accent_color": armor.accent_color,
        "visor_color": armor.visor_color,
        "unresolved_color_channels": list(armor.unresolved_color_channels),
        "roughness": armor.roughness,
        "weathered": armor.weathered,
        "reflective": armor.reflective,
        "compatible_body_profiles": list(armor.compatible_body_profiles),
    }


@dataclass(frozen=True, slots=True)
class EquippedItem:
    """A minimal equipped-design projection used for dependency validation."""

    item_instance_id: UUID
    design_id: str
    garment_class: GarmentClass
    armor: ArmorMetadata | None = None
    asset_ref: str | None = None
    asset_verified: bool = False
    tail_clearance: bool = False
    ear_clearance: bool = False

    def __post_init__(self) -> None:
        _uuid(self.item_instance_id, "item_instance_id")
        _identifier(self.design_id, "design_id")
        if not isinstance(self.garment_class, GarmentClass):
            raise EquipmentError("garment_class must be GarmentClass")
        if self.garment_class in ARMOR_CLASSES:
            if not isinstance(self.armor, ArmorMetadata):
                raise EquipmentError("equipped armor requires metadata")
        elif self.armor is not None:
            raise EquipmentError("equipped clothing cannot carry armor metadata")
        for flag in ("asset_verified", "tail_clearance", "ear_clearance"):
            if type(getattr(self, flag)) is not bool:
                raise EquipmentError(f"{flag} must be boolean")

    @classmethod
    def from_design(
        cls,
        item_instance_id: UUID,
        design: WardrobeDesign,
        *,
        asset_verified: bool = False,
    ) -> "EquippedItem":
        if not isinstance(design, WardrobeDesign):
            raise TypeError("design must be WardrobeDesign")
        return cls(
            item_instance_id=item_instance_id,
            design_id=design.design_id,
            garment_class=design.garment_class,
            armor=design.armor,
            asset_ref=design.asset_ref,
            asset_verified=asset_verified,
            tail_clearance=design.tail_clearance,
            ear_clearance=design.ear_clearance,
        )


class ArmorDecisionStatus(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    ATOMIC_DISASSEMBLY_REQUIRED = "atomic_disassembly_required"


@dataclass(frozen=True, slots=True)
class ArmorDecision:
    """Metadata-only decision; never proof of geometry, fit or protection."""

    status: ArmorDecisionStatus
    reason: str
    dependent_item_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ArmorDecisionStatus):
            raise EquipmentError("status must be ArmorDecisionStatus")
        _text(self.reason, "reason", maximum=1024)
        if not isinstance(self.dependent_item_ids, tuple):
            raise EquipmentError("dependent_item_ids must be a tuple")
        for item_id in self.dependent_item_ids:
            _uuid(item_id, "dependent item id")
        if self.status is ArmorDecisionStatus.ATOMIC_DISASSEMBLY_REQUIRED and not self.dependent_item_ids:
            raise EquipmentError("atomic disassembly must name the dependent items")

    @property
    def allowed(self) -> bool:
        return self.status is ArmorDecisionStatus.ALLOWED

    @property
    def metadata_only(self) -> bool:
        return True


def _deny(reason: str) -> ArmorDecision:
    return ArmorDecision(ArmorDecisionStatus.DENIED, reason)


def _unavailable(reason: str) -> ArmorDecision:
    return ArmorDecision(ArmorDecisionStatus.UNAVAILABLE, reason)


def _for_item(item: EquippedItem, label: str) -> str:
    return f"{label} {item.design_id!r}"


def _equipped_by_class(
    equipped: tuple[EquippedItem, ...], garment_class: GarmentClass
) -> tuple[EquippedItem, ...]:
    return tuple(item for item in equipped if item.garment_class is garment_class)


def _undersuit_for(
    equipped: tuple[EquippedItem, ...], family: ArmorFamily, interface: str
) -> EquippedItem | None:
    for item in _equipped_by_class(equipped, GarmentClass.ARMOR_UNDERSUIT):
        assert item.armor is not None
        if item.armor.family is family and item.armor.undersuit_interface == interface:
            return item
    return None


def _base_for(
    equipped: tuple[EquippedItem, ...],
    family: ArmorFamily,
    series: ArmorSeries | None,
) -> EquippedItem | None:
    for item in _equipped_by_class(equipped, GarmentClass.ARMOR_BASE):
        assert item.armor is not None
        if item.armor.family is family and item.armor.base_series is series:
            return item
    return None


def _validate_body(
    candidate: EquippedItem,
    *,
    body_profile: str | None,
    body_has_tail: bool,
    body_has_ears: bool,
    require_fit: bool,
) -> ArmorDecision | None:
    armor = candidate.armor
    assert armor is not None
    if require_fit and body_profile is None:
        return _unavailable("wearer body profile is unknown; fit cannot be claimed")
    if body_profile is not None and body_profile not in armor.compatible_body_profiles:
        return _deny(
            f"{candidate.design_id} is not fit-compatible with body profile {body_profile!r}"
        )
    if body_has_tail and not candidate.tail_clearance:
        return _deny(f"{candidate.design_id} has no reviewed tail clearance")
    if body_has_ears and not candidate.ear_clearance:
        return _deny(f"{candidate.design_id} has no reviewed ear clearance")
    return None


def validate_armor_equip(
    equipped: Iterable[EquippedItem],
    candidate: EquippedItem,
    *,
    body_profile: str | None = None,
    body_has_tail: bool = False,
    body_has_ears: bool = False,
    require_fit: bool = False,
    require_assets: bool = False,
) -> ArmorDecision:
    """Validate the mandatory undersuit/base/mount chain for one equip attempt.

    A part is never represented as equipped without an actually equipped
    compatible undersuit (and, for plates, a compatible base).  A Mark IV part
    cannot be silently normalized onto a Mark V base.
    """
    if not isinstance(candidate, EquippedItem):
        raise TypeError("candidate must be EquippedItem")
    items = tuple(equipped)
    if any(not isinstance(item, EquippedItem) for item in items):
        raise TypeError("equipped must contain EquippedItem values")
    if len({item.item_instance_id for item in items}) != len(items):
        raise EquipmentError("equipped item instances must be unique")
    if not candidate.garment_class in ARMOR_CLASSES:
        return _deny("candidate is not an armor component")
    assert candidate.armor is not None
    armor = candidate.armor

    if any(item.item_instance_id == candidate.item_instance_id for item in items):
        return _deny("item instance is already equipped")

    body = _validate_body(
        candidate,
        body_profile=body_profile,
        body_has_tail=body_has_tail,
        body_has_ears=body_has_ears,
        require_fit=require_fit,
    )
    if body is not None:
        return body

    if require_assets and (
        candidate.asset_ref is None or not candidate.asset_verified
    ):
        return _unavailable(
            "reviewed renderer asset is not installed/verified; metadata-only status"
        )

    same_class = _equipped_by_class(items, candidate.garment_class)
    if same_class and candidate.garment_class is not GarmentClass.ARMOR_ATTACHMENT:
        return _deny(f"another {candidate.garment_class.value} is already equipped")
    if candidate.garment_class is GarmentClass.ARMOR_ATTACHMENT and candidate.armor.socket is not None:
        for item in same_class:
            if item.armor is not None and item.armor.socket == candidate.armor.socket:
                return _deny("another attachment already occupies this socket")

    if candidate.garment_class is GarmentClass.ARMOR_UNDERSUIT:
        if _equipped_by_class(items, GarmentClass.ARMOR_UNDERSUIT):
            return _deny("another undersuit is already equipped")
        return ArmorDecision(
            ArmorDecisionStatus.ALLOWED,
            "compatible undersuit selected; body/rig fit remains a separate gate",
        )

    if not armor.requires_undersuit:
        return _deny("approved armor components require an equipped undersuit")
    undersuit = _undersuit_for(items, armor.family, armor.undersuit_interface)
    if undersuit is None:
        return _deny(
            "a compatible equipped armor undersuit is required "
            f"(family={armor.family.value}, interface={armor.undersuit_interface})"
        )

    if candidate.garment_class is GarmentClass.ARMOR_BASE:
        assert armor.base_series is not None
        if _base_for(items, armor.family, armor.base_series) is not None:
            return _deny("another base for this armor family/series is already equipped")
        return ArmorDecision(
            ArmorDecisionStatus.ALLOWED,
            "undersuit and base family/interface are compatible",
        )

    if not armor.requires_base:
        return _deny("approved armor plates require a compatible equipped base")
    base = _base_for(items, armor.family, armor.base_series)
    if base is None:
        return _deny(
            "a compatible equipped armor base is required "
            f"(family={armor.family.value}, series={armor.base_series.value})"
        )
    assert base.armor is not None
    if armor.mount_id is not None and armor.mount_id not in base.armor.provided_mounts:
        return _deny(
            f"mount {armor.mount_id!r} is not provided by base {base.design_id!r}"
        )
    if armor.socket is not None and not armor.mount_id:
        return _deny("an attachment socket requires an explicit reviewed mount")
    return ArmorDecision(
        ArmorDecisionStatus.ALLOWED,
        "undersuit, base, family, series and mount/socket are compatible",
    )


def dependent_armor_items(
    equipped: Iterable[EquippedItem], target_item_id: UUID
) -> tuple[EquippedItem, ...]:
    """Return equipped armor that depends on the target undersuit or base."""
    _uuid(target_item_id, "target_item_id")
    items = tuple(equipped)
    target = next(
        (item for item in items if item.item_instance_id == target_item_id), None
    )
    if target is None or target.armor is None:
        return ()
    if target.garment_class is GarmentClass.ARMOR_UNDERSUIT:
        return tuple(
            item for item in items
            if item.garment_class is GarmentClass.ARMOR_BASE
            or (
                item.armor is not None
                and item.armor.family is target.armor.family
                and item.armor.undersuit_interface == target.armor.undersuit_interface
            )
        )
    if target.garment_class is GarmentClass.ARMOR_BASE:
        return tuple(
            item for item in items
            if item.armor is not None
            and item.armor.family is target.armor.family
            and item.armor.base_series is target.armor.base_series
            and item.garment_class not in {
                GarmentClass.ARMOR_UNDERSUIT, GarmentClass.ARMOR_BASE,
            }
        )
    return ()


def validate_armor_unequip(
    equipped: Iterable[EquippedItem], item_instance_id: UUID
) -> ArmorDecision:
    """Refuse to orphan plates; return an explicit atomic-strip requirement."""
    items = tuple(equipped)
    _uuid(item_instance_id, "item_instance_id")
    target = next(
        (item for item in items if item.item_instance_id == item_instance_id), None
    )
    if target is None:
        return _deny("item instance is not equipped")
    dependents = dependent_armor_items(items, item_instance_id)
    if dependents:
        return ArmorDecision(
            ArmorDecisionStatus.ATOMIC_DISASSEMBLY_REQUIRED,
            "supporting armor item has dependent equipped components; "
            "reviewed atomic disassembly is required",
            tuple(item.item_instance_id for item in dependents),
        )
    return ArmorDecision(
        ArmorDecisionStatus.ALLOWED,
        "no equipped armor component depends on this item",
    )


def atomic_disassembly_plan(
    equipped: Iterable[EquippedItem], item_instance_id: UUID
) -> tuple[UUID, ...]:
    """Return a safe removal order: dependent parts, then base, then undersuit."""
    items = tuple(equipped)
    dependents = dependent_armor_items(items, item_instance_id)
    order = [item.item_instance_id for item in dependents]
    order.append(item_instance_id)
    return tuple(dict.fromkeys(order))


# ---------------------------------------------------------------------------
# Vera S-039 approved armor configurations.  These are cosmetic wardrobe
# designs, not physical protection, game-model imports or license claims.
# ---------------------------------------------------------------------------

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
_TORSO_SLOTS = ("torso", "back")
_TORSO_ANCHORS = ("torso.front", "torso.back")


def _undersuit(design_id: str, family: ArmorFamily, interface: str) -> WardrobeDesign:
    return WardrobeDesign(
        design_id=design_id,
        version=1,
        name="Vera modular armor undersuit",
        garment_class=GarmentClass.ARMOR_UNDERSUIT,
        garment_type="armor_undersuit",
        layer=Layer.UNDERWEAR,
        slots=_UNDERSUIT_SLOTS,
        coverage=_UNDERSUIT_SLOTS,
        fit_anchors=_UNDERSUIT_ANCHORS,
        armor=ArmorMetadata(
            family=family,
            undersuit_interface=interface,
            requires_undersuit=False,
            primary_color="#242424",
            roughness=DEFAULT_ARMOR_ROUGHNESS,
        ),
    )


def _base(
    design_id: str,
    *,
    family: ArmorFamily,
    series: ArmorSeries,
    interface: str,
    primary: str,
    mounts: tuple[str, ...],
) -> WardrobeDesign:
    return WardrobeDesign(
        design_id=design_id,
        version=1,
        name=f"Vera {series.value} armor base",
        garment_class=GarmentClass.ARMOR_BASE,
        garment_type="armor_base",
        layer=Layer.OUTER,
        slots=_TORSO_SLOTS,
        coverage=_TORSO_SLOTS,
        fit_anchors=_TORSO_ANCHORS,
        armor=ArmorMetadata(
            family=family,
            undersuit_interface=interface,
            requires_base=False,
            base_series=series,
            provided_mounts=mounts,
            primary_color=primary,
            roughness=DEFAULT_ARMOR_ROUGHNESS,
        ),
    )


def _part(
    design_id: str,
    name: str,
    garment_class: GarmentClass,
    *,
    family: ArmorFamily,
    series: ArmorSeries,
    interface: str,
    mount_id: str,
    socket: str,
    slots: tuple[str, ...],
    coverage: tuple[str, ...],
    anchors: tuple[str, ...],
    primary: str,
    visor: str | None = None,
    unresolved: tuple[str, ...] = (),
    tail_clearance: bool = False,
    ear_clearance: bool = False,
) -> WardrobeDesign:
    return WardrobeDesign(
        design_id=design_id,
        version=1,
        name=name,
        garment_class=garment_class,
        garment_type=garment_class.value,
        layer=Layer.OUTER,
        slots=slots,
        coverage=coverage,
        fit_anchors=anchors,
        armor=ArmorMetadata(
            family=family,
            undersuit_interface=interface,
            requires_base=True,
            base_series=series,
            mount_id=mount_id,
            socket=socket,
            primary_color=primary,
            visor_color=visor,
            unresolved_color_channels=unresolved,
            roughness=DEFAULT_ARMOR_ROUGHNESS,
        ),
        tail_clearance=tail_clearance,
        ear_clearance=ear_clearance,
    )


_IV_INTERFACE = "aegis.armor.undersuit.mark_iv.v1"
_V_INTERFACE = "aegis.armor.undersuit.mark_v.v1"


def _mark_iv_series_parts(series: ArmorSeries, base_prefix: str) -> tuple[WardrobeDesign, ...]:
    """Shared Mark IV-compatible component family (CQB and standard)."""
    family = ArmorFamily.MARK_IV
    if series is ArmorSeries.MARK_IV_CQB:
        primary, visor = "#626262", "#D4AF37"
    else:
        primary, visor = "#507D2A", "#EFB82A"
    helmet = _part(
        f"{base_prefix}_helmet", "Vera CQB helmet" if series is ArmorSeries.MARK_IV_CQB
        else "Vera Mark IV helmet",
        GarmentClass.ARMOR_HELMET, family=family, series=series,
        interface=_IV_INTERFACE, mount_id=f"{series.value}.head",
        socket=f"{series.value}.helmet",
        slots=("head",), coverage=("head",), anchors=("head.crown",),
        primary=primary, ear_clearance=True,
    )
    visor_design = _part(
        f"{base_prefix}_visor", "Vera visor",
        GarmentClass.ARMOR_VISOR, family=family, series=series,
        interface=_IV_INTERFACE, mount_id=f"{series.value}.head",
        socket=f"{series.value}.visor",
        slots=("head",), coverage=(), anchors=("head.crown",),
        primary=primary, visor=visor,
    )
    chest = _part(
        f"{base_prefix}_chest", "Vera chest plate",
        GarmentClass.ARMOR_CHEST, family=family, series=series,
        interface=_IV_INTERFACE, mount_id=f"{series.value}.chest",
        socket=f"{series.value}.chest",
        slots=("torso",), coverage=("torso",), anchors=("torso.front",),
        primary=primary,
    )
    back = _part(
        f"{base_prefix}_back", "Vera back plate",
        GarmentClass.ARMOR_BACK, family=family, series=series,
        interface=_IV_INTERFACE, mount_id=f"{series.value}.back",
        socket=f"{series.value}.back",
        slots=("back", "torso"), coverage=("back",), anchors=("torso.back",),
        primary=primary,
    )
    shoulders = tuple(
        _part(
            f"{base_prefix}_shoulder_{side}", f"Vera {side} shoulder",
            GarmentClass.ARMOR_SHOULDER_LEFT if side == "left"
            else GarmentClass.ARMOR_SHOULDER_RIGHT,
            family=family, series=series, interface=_IV_INTERFACE,
            mount_id=f"{series.value}.shoulder.{side}",
            socket=f"{series.value}.shoulder.{side}",
            slots=(f"left_shoulder" if side == "left" else "right_shoulder",
                   f"left_upper_arm" if side == "left" else "right_upper_arm"),
            coverage=(f"left_shoulder" if side == "left" else "right_shoulder",),
            anchors=(f"shoulder.{side}",), primary=primary,
        )
        for side in ("left", "right")
    )
    forearms = tuple(
        _part(
            f"{base_prefix}_forearm_{side}", f"Vera {side} forearm",
            GarmentClass.ARMOR_FOREARM_LEFT if side == "left"
            else GarmentClass.ARMOR_FOREARM_RIGHT,
            family=family, series=series, interface=_IV_INTERFACE,
            mount_id=f"{series.value}.forearm.{side}",
            socket=f"{series.value}.forearm.{side}",
            slots=(f"left_forearm" if side == "left" else "right_forearm",
                   f"left_wrist" if side == "left" else "right_wrist"),
            coverage=(f"left_forearm" if side == "left" else "right_forearm",),
            anchors=(f"forearm.{side}",), primary=primary,
        )
        for side in ("left", "right")
    )
    thighs = tuple(
        _part(
            f"{base_prefix}_thigh_{side}", f"Vera {side} thigh plate",
            GarmentClass.ARMOR_THIGH_LEFT if side == "left" else GarmentClass.ARMOR_THIGH_RIGHT,
            family=family, series=series, interface=_IV_INTERFACE,
            mount_id=f"{series.value}.thigh.{side}",
            socket=f"{series.value}.thigh.{side}",
            slots=(f"left_thigh" if side == "left" else "right_thigh",),
            coverage=(f"left_thigh" if side == "left" else "right_thigh",),
            anchors=(f"thigh.{side}",), primary=primary,
        )
        for side in ("left", "right")
    )
    shins = tuple(
        _part(
            f"{base_prefix}_shin_{side}", f"Vera {side} shin guard",
            GarmentClass.ARMOR_SHIN_LEFT if side == "left" else GarmentClass.ARMOR_SHIN_RIGHT,
            family=family, series=series, interface=_IV_INTERFACE,
            mount_id=f"{series.value}.shin.{side}",
            socket=f"{series.value}.shin.{side}",
            slots=(f"left_calf" if side == "left" else "right_calf",),
            coverage=(f"left_calf" if side == "left" else "right_calf",),
            anchors=(f"calf.{side}",), primary=primary,
        )
        for side in ("left", "right")
    )
    boots = tuple(
        _part(
            f"{base_prefix}_boot_{side}", f"Vera {side} boot",
            GarmentClass.ARMOR_BOOT_LEFT if side == "left" else GarmentClass.ARMOR_BOOT_RIGHT,
            family=family, series=series, interface=_IV_INTERFACE,
            mount_id=f"{series.value}.boot.{side}",
            socket=f"{series.value}.boot.{side}",
            slots=(f"left_foot" if side == "left" else "right_foot",
                   f"left_ankle" if side == "left" else "right_ankle"),
            coverage=(f"left_foot" if side == "left" else "right_foot",),
            anchors=(f"foot.{side}",), primary=primary,
        )
        for side in ("left", "right")
    )
    return (helmet, visor_design, chest, back, *shoulders, *forearms, *thighs, *shins, *boots)


def _mark_v_odst_parts() -> tuple[WardrobeDesign, ...]:
    family, series, interface = ArmorFamily.MARK_V, ArmorSeries.MARK_V, _V_INTERFACE
    primary = "#626262"

    def part(
        design_id: str, name: str, cls: GarmentClass, mount: str, socket: str,
        slots: tuple[str, ...], coverage: tuple[str, ...], anchors: tuple[str, ...],
        *, visor: str | None = None, unresolved: tuple[str, ...] = (),
        tail: bool = False, ear: bool = False,
    ) -> WardrobeDesign:
        return _part(
            design_id, name, cls, family=family, series=series, interface=interface,
            mount_id=mount, socket=socket, slots=slots, coverage=coverage,
            anchors=anchors, primary=primary, visor=visor, unresolved=unresolved,
            tail_clearance=tail, ear_clearance=ear,
        )

    helmet = part(
        "vera_odst_helmet", "Vera ODST helmet", GarmentClass.ARMOR_HELMET,
        "mark_v.head", "mark_v.helmet", ("head",), ("head",), ("head.crown",),
        ear=True,
    )
    visor = part(
        "vera_odst_visor", "Vera ODST visor", GarmentClass.ARMOR_VISOR,
        "mark_v.head", "mark_v.visor", ("head",), (), ("head.crown",),
        unresolved=("visor",),
    )
    chest = part(
        "vera_odst_chest", "Vera ODST chest plate", GarmentClass.ARMOR_CHEST,
        "mark_v.chest", "mark_v.chest", ("torso",), ("torso",), ("torso.front",),
    )
    back = part(
        "vera_odst_back", "Vera ODST back plate", GarmentClass.ARMOR_BACK,
        "mark_v.back", "mark_v.back", ("back", "torso"), ("back",), ("torso.back",),
    )
    shoulders = tuple(
        part(
            f"vera_odst_shoulder_{side}", f"Vera ODST {side} shoulder",
            GarmentClass.ARMOR_SHOULDER_LEFT if side == "left"
            else GarmentClass.ARMOR_SHOULDER_RIGHT,
            f"mark_v.shoulder.{side}", f"mark_v.shoulder.{side}",
            (f"left_shoulder" if side == "left" else "right_shoulder",
             f"left_upper_arm" if side == "left" else "right_upper_arm"),
            (f"left_shoulder" if side == "left" else "right_shoulder",),
            (f"shoulder.{side}",),
        )
        for side in ("left", "right")
    )
    forearms = tuple(
        part(
            f"vera_odst_forearm_{side}", f"Vera ODST {side} forearm",
            GarmentClass.ARMOR_FOREARM_LEFT if side == "left"
            else GarmentClass.ARMOR_FOREARM_RIGHT,
            f"mark_v.forearm.{side}", f"mark_v.forearm.{side}",
            (f"left_forearm" if side == "left" else "right_forearm",
             f"left_wrist" if side == "left" else "right_wrist"),
            (f"left_forearm" if side == "left" else "right_forearm",),
            (f"forearm.{side}",),
        )
        for side in ("left", "right")
    )
    thighs = tuple(
        part(
            f"vera_odst_thigh_{side}", f"Vera ODST {side} thigh plate",
            GarmentClass.ARMOR_THIGH_LEFT if side == "left" else GarmentClass.ARMOR_THIGH_RIGHT,
            f"mark_v.thigh.{side}", f"mark_v.thigh.{side}",
            (f"left_thigh" if side == "left" else "right_thigh",),
            (f"left_thigh" if side == "left" else "right_thigh",),
            (f"thigh.{side}",),
        )
        for side in ("left", "right")
    )
    shins = tuple(
        part(
            f"vera_odst_shin_{side}", f"Vera ODST {side} shin guard",
            GarmentClass.ARMOR_SHIN_LEFT if side == "left" else GarmentClass.ARMOR_SHIN_RIGHT,
            f"mark_v.shin.{side}", f"mark_v.shin.{side}",
            (f"left_calf" if side == "left" else "right_calf",),
            (f"left_calf" if side == "left" else "right_calf",),
            (f"calf.{side}",),
        )
        for side in ("left", "right")
    )
    boots = tuple(
        part(
            f"vera_odst_boot_{side}", f"Vera ODST {side} boot",
            GarmentClass.ARMOR_BOOT_LEFT if side == "left" else GarmentClass.ARMOR_BOOT_RIGHT,
            f"mark_v.boot.{side}", f"mark_v.boot.{side}",
            (f"left_foot" if side == "left" else "right_foot",
             f"left_ankle" if side == "left" else "right_ankle"),
            (f"left_foot" if side == "left" else "right_foot",),
            (f"foot.{side}",),
        )
        for side in ("left", "right")
    )
    return (helmet, visor, chest, back, *shoulders, *forearms, *thighs, *shins, *boots)


_VERA_MARK_IV_UNDERSUIT = _undersuit(
    "vera_undersuit_mark_iv", ArmorFamily.MARK_IV, _IV_INTERFACE,
)
_VERA_MARK_V_UNDERSUIT = _undersuit(
    "vera_undersuit_mark_v", ArmorFamily.MARK_V, _V_INTERFACE,
)
_VERA_CQB_BASE = _base(
    "vera_base_mark_iv_cqb", family=ArmorFamily.MARK_IV,
    series=ArmorSeries.MARK_IV_CQB, interface=_IV_INTERFACE, primary="#626262",
    mounts=(
        "mark_iv_cqb.head", "mark_iv_cqb.chest", "mark_iv_cqb.back",
        "mark_iv_cqb.shoulder.left", "mark_iv_cqb.shoulder.right",
        "mark_iv_cqb.forearm.left", "mark_iv_cqb.forearm.right",
        "mark_iv_cqb.thigh.left", "mark_iv_cqb.thigh.right",
        "mark_iv_cqb.shin.left", "mark_iv_cqb.shin.right",
        "mark_iv_cqb.boot.left", "mark_iv_cqb.boot.right",
    ),
)
_VERA_MARK_IV_BASE = _base(
    "vera_base_mark_iv", family=ArmorFamily.MARK_IV,
    series=ArmorSeries.MARK_IV, interface=_IV_INTERFACE, primary="#507D2A",
    mounts=(
        "mark_iv.head", "mark_iv.chest", "mark_iv.back",
        "mark_iv.shoulder.left", "mark_iv.shoulder.right",
        "mark_iv.forearm.left", "mark_iv.forearm.right",
        "mark_iv.thigh.left", "mark_iv.thigh.right",
        "mark_iv.shin.left", "mark_iv.shin.right",
        "mark_iv.boot.left", "mark_iv.boot.right",
    ),
)
_VERA_MARK_V_BASE = _base(
    "vera_base_mark_v", family=ArmorFamily.MARK_V,
    series=ArmorSeries.MARK_V, interface=_V_INTERFACE, primary="#626262",
    mounts=(
        "mark_v.head", "mark_v.chest", "mark_v.back",
        "mark_v.shoulder.left", "mark_v.shoulder.right",
        "mark_v.forearm.left", "mark_v.forearm.right",
        "mark_v.thigh.left", "mark_v.thigh.right",
        "mark_v.shin.left", "mark_v.shin.right",
        "mark_v.boot.left", "mark_v.boot.right",
    ),
)
_VERA_CQB_PARTS = _mark_iv_series_parts(ArmorSeries.MARK_IV_CQB, "vera_cqb")
_VERA_MARK_IV_PARTS = _mark_iv_series_parts(ArmorSeries.MARK_IV, "vera_mark_iv")
_VERA_ODST_PARTS = _mark_v_odst_parts()

VERA_ARMOR_DESIGNS: tuple[WardrobeDesign, ...] = (
    _VERA_MARK_IV_UNDERSUIT,
    _VERA_MARK_V_UNDERSUIT,
    _VERA_CQB_BASE,
    _VERA_MARK_IV_BASE,
    _VERA_MARK_V_BASE,
    *_VERA_CQB_PARTS,
    *_VERA_MARK_IV_PARTS,
    *_VERA_ODST_PARTS,
)
VERA_ARMOR_BY_DESIGN_ID: Mapping[str, WardrobeDesign] = {
    design.design_id: design for design in VERA_ARMOR_DESIGNS
}
if len(VERA_ARMOR_BY_DESIGN_ID) != len(VERA_ARMOR_DESIGNS):
    raise EquipmentError("duplicate Vera armor design ID")


@dataclass(frozen=True, slots=True)
class VeraArmorConfiguration:
    configuration_id: str
    name: str
    family: ArmorFamily
    series: ArmorSeries
    undersuit_design_id: str
    base_design_id: str
    primary_color: str
    visor_color: str | None
    component_design_ids: tuple[str, ...]
    unresolved_color_channels: tuple[str, ...] = ()
    roughness: float = DEFAULT_ARMOR_ROUGHNESS

    def __post_init__(self) -> None:
        _identifier(self.configuration_id, "configuration_id")
        _text(self.name, "name", maximum=160)
        if not isinstance(self.family, ArmorFamily) or not isinstance(self.series, ArmorSeries):
            raise EquipmentError("configuration family/series must be typed")
        for design_id in (self.undersuit_design_id, self.base_design_id):
            _identifier(design_id, "design_id")
            if design_id not in VERA_ARMOR_BY_DESIGN_ID:
                raise EquipmentError(f"unknown Vera armor design: {design_id}")
        _hex(self.primary_color, "primary_color")
        if self.visor_color is not None:
            _hex(self.visor_color, "visor_color")
        _unique_tuple(self.component_design_ids, "component_design_ids")
        for design_id in self.component_design_ids:
            _identifier(design_id, "component design_id")
            if design_id not in VERA_ARMOR_BY_DESIGN_ID:
                raise EquipmentError(f"unknown Vera armor design: {design_id}")
        _unique_tuple(self.unresolved_color_channels, "unresolved_color_channels")
        if self.series is ArmorSeries.MARK_V and self.visor_color is not None:
            raise EquipmentError("the ODST/Mark V visor color remains undecided")
        if "visor" in self.unresolved_color_channels and self.visor_color is not None:
            raise EquipmentError("an unresolved visor cannot claim a color")

    def equip_order(self) -> tuple[str, ...]:
        """Undersuit, then base, then every component in catalog order."""
        return (self.undersuit_design_id, self.base_design_id, *self.component_design_ids)


_VERA_CQB_COMPONENTS = tuple(item.design_id for item in _VERA_CQB_PARTS)
_VERA_MARK_IV_COMPONENTS = tuple(item.design_id for item in _VERA_MARK_IV_PARTS)
_VERA_ODST_COMPONENTS = tuple(item.design_id for item in _VERA_ODST_PARTS)

VERA_ARMOR_CONFIGURATIONS: tuple[VeraArmorConfiguration, ...] = (
    VeraArmorConfiguration(
        configuration_id="cqb",
        name="CQB",
        family=ArmorFamily.MARK_IV,
        series=ArmorSeries.MARK_IV_CQB,
        undersuit_design_id=_VERA_MARK_IV_UNDERSUIT.design_id,
        base_design_id=_VERA_CQB_BASE.design_id,
        primary_color="#626262",
        visor_color="#D4AF37",
        component_design_ids=_VERA_CQB_COMPONENTS,
    ),
    VeraArmorConfiguration(
        configuration_id="mark_iv",
        name="Mark IV",
        family=ArmorFamily.MARK_IV,
        series=ArmorSeries.MARK_IV,
        undersuit_design_id=_VERA_MARK_IV_UNDERSUIT.design_id,
        base_design_id=_VERA_MARK_IV_BASE.design_id,
        primary_color="#507D2A",
        visor_color="#EFB82A",
        component_design_ids=_VERA_MARK_IV_COMPONENTS,
    ),
    VeraArmorConfiguration(
        configuration_id="odst",
        name="ODST/Mark V",
        family=ArmorFamily.MARK_V,
        series=ArmorSeries.MARK_V,
        undersuit_design_id=_VERA_MARK_V_UNDERSUIT.design_id,
        base_design_id=_VERA_MARK_V_BASE.design_id,
        primary_color="#626262",
        visor_color=None,
        component_design_ids=_VERA_ODST_COMPONENTS,
        unresolved_color_channels=("visor",),
    ),
)
VERA_ARMOR_CONFIGURATION_BY_ID: Mapping[str, VeraArmorConfiguration] = {
    config.configuration_id: config for config in VERA_ARMOR_CONFIGURATIONS
}


def vera_armor_design(design_id: str) -> WardrobeDesign:
    try:
        return VERA_ARMOR_BY_DESIGN_ID[design_id]
    except KeyError as exc:
        raise EquipmentError(f"unknown Vera armor design: {design_id}") from exc


def vera_armor_configuration(configuration_id: str) -> VeraArmorConfiguration:
    try:
        return VERA_ARMOR_CONFIGURATION_BY_ID[configuration_id]
    except KeyError as exc:
        raise EquipmentError(f"unknown Vera armor configuration: {configuration_id}") from exc


def verify_vera_configurations() -> None:
    """Validate each approved kit against the mandatory dependency chain."""
    for config in VERA_ARMOR_CONFIGURATIONS:
        equipped: list[EquippedItem] = []
        for index, design_id in enumerate(config.equip_order()):
            design = vera_armor_design(design_id)
            candidate = EquippedItem.from_design(
                UUID(int=index + 1), design, asset_verified=True
            )
            decision = validate_armor_equip(
                equipped, candidate, body_profile="human", require_fit=True,
            )
            if not decision.allowed:
                raise EquipmentError(
                    f"approved Vera configuration {config.configuration_id!r} is invalid: "
                    f"{decision.reason}"
                )
            equipped.append(candidate)
        base = vera_armor_design(config.base_design_id)
        assert base.armor is not None
        if base.armor.primary_color != config.primary_color:
            raise EquipmentError("configuration primary color differs from its base design")
        for design_id in config.component_design_ids:
            design = vera_armor_design(design_id)
            if design.armor is None or design.armor.family is not config.family:
                raise EquipmentError("configuration component family mismatch")


verify_vera_configurations()


__all__ = [
    "ARMOR_CLASSES",
    "ArmorDecision",
    "ArmorDecisionStatus",
    "ArmorFamily",
    "ArmorMetadata",
    "ArmorSeries",
    "CONTENT_RATINGS",
    "DEFAULT_ARMOR_ROUGHNESS",
    "EquipmentError",
    "EquippedItem",
    "GarmentClass",
    "SIDED_CLASSES",
    "VERA_ARMOR_BY_DESIGN_ID",
    "VERA_ARMOR_CONFIGURATIONS",
    "VERA_ARMOR_CONFIGURATION_BY_ID",
    "VERA_ARMOR_DESIGNS",
    "VeraArmorConfiguration",
    "WardrobeDesign",
    "WardrobePrivacy",
    "atomic_disassembly_plan",
    "dependent_armor_items",
    "validate_armor_equip",
    "validate_armor_unequip",
    "vera_armor_configuration",
    "vera_armor_design",
    "verify_vera_configurations",
]
