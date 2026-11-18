"""Audience-scoped equipment catalog and injected design-registry bridge.

The catalog is shared for discovery by every eligible Core.  Privacy and adult
content scope only the *contents* of a design; it never hides the existence of a
design ID from other Cores and never transfers ownership or consent.  Public and
guest views replace restricted metadata with a safe covered-default projection.
This module is an adapter over existing wardrobe metadata, not a second
inventory, item-state store or fit engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping
from uuid import UUID

from .wardrobe import Garment, Wardrobe
from .wardrobe_equipment import (
    ArmorMetadata,
    EquippedItem,
    EquipmentError,
    GarmentClass,
    WardrobeDesign,
    WardrobePrivacy,
)

SAFE_COVERED_DEFAULT_NAME = "Covered default"


class CatalogAudience(str, Enum):
    """Audience classes used only to scope restricted catalog contents."""

    PUBLIC = "public"
    GUEST = "guest"
    PRIVATE = "private"
    ADULT = "adult"


def design_visible_to(
    design: WardrobeDesign, audience: CatalogAudience
) -> bool:
    """Return whether this audience may see the design's detailed metadata."""
    if not isinstance(design, WardrobeDesign):
        raise TypeError("design must be WardrobeDesign")
    if not isinstance(audience, CatalogAudience):
        raise TypeError("audience must be CatalogAudience")
    if design.privacy is WardrobePrivacy.PUBLIC:
        return True
    if design.privacy is WardrobePrivacy.PRIVATE:
        return audience in {CatalogAudience.PRIVATE, CatalogAudience.ADULT}
    if design.privacy is WardrobePrivacy.ADULT:
        return audience is CatalogAudience.ADULT
    return False


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One catalog row; restricted rows expose only safe default metadata."""

    design_id: str
    version: int
    garment_class: GarmentClass
    garment_type: str
    privacy: WardrobePrivacy
    audience: CatalogAudience
    metadata_visible: bool
    safe_covered_default: bool
    name: str | None
    asset_ref: str | None
    content_rating: str | None
    armor: ArmorMetadata | None
    tail_clearance: bool
    ear_clearance: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "aegis.avatar.wardrobe_catalog.v1",
            "design_id": self.design_id,
            "version": self.version,
            "garment_class": self.garment_class.value,
            "garment_type": self.garment_type,
            "privacy": self.privacy.value,
            "audience": self.audience.value,
            "metadata_visible": self.metadata_visible,
            "safe_covered_default": self.safe_covered_default,
            "name": self.name,
            "asset_ref": self.asset_ref,
            "content_rating": self.content_rating,
            "armor": None if self.armor is None else self.armor.family.value,
            "tail_clearance": self.tail_clearance,
            "ear_clearance": self.ear_clearance,
        }


@dataclass(frozen=True, slots=True)
class CatalogView:
    """All discoverable design IDs plus audience-scoped metadata."""

    audience: CatalogAudience
    entries: tuple[CatalogEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.audience, CatalogAudience):
            raise EquipmentError("catalog view requires a CatalogAudience")
        if not isinstance(self.entries, tuple):
            raise EquipmentError("catalog entries must be a tuple")
        ids = [entry.design_id for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise EquipmentError("catalog view design IDs must be unique")

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    @property
    def design_ids(self) -> tuple[str, ...]:
        return tuple(entry.design_id for entry in self.entries)

    @property
    def visible_entries(self) -> tuple[CatalogEntry, ...]:
        return tuple(entry for entry in self.entries if entry.metadata_visible)

    @property
    def restricted_entries(self) -> tuple[CatalogEntry, ...]:
        return tuple(entry for entry in self.entries if not entry.metadata_visible)

    def entry(self, design_id: str) -> CatalogEntry:
        if not isinstance(design_id, str):
            raise TypeError("design_id must be a string")
        for entry in self.entries:
            if entry.design_id == design_id:
                return entry
        raise KeyError(design_id)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "aegis.avatar.wardrobe_catalog_view.v1",
            "audience": self.audience.value,
            "entries": [entry.to_payload() for entry in self.entries],
        }


def project_catalog(
    designs: Iterable[WardrobeDesign], audience: CatalogAudience
) -> CatalogView:
    """Project every design for one audience without leaking restricted data."""
    if not isinstance(audience, CatalogAudience):
        raise TypeError("audience must be CatalogAudience")
    values = tuple(designs)
    if any(not isinstance(design, WardrobeDesign) for design in values):
        raise TypeError("designs must contain WardrobeDesign values")
    ids = [design.design_id for design in values]
    if len(set(ids)) != len(ids):
        raise EquipmentError("catalog design IDs must be unique")

    entries: list[CatalogEntry] = []
    for design in values:
        visible = design_visible_to(design, audience)
        if visible:
            entries.append(
                CatalogEntry(
                    design_id=design.design_id,
                    version=design.version,
                    garment_class=design.garment_class,
                    garment_type=design.garment_type,
                    privacy=design.privacy,
                    audience=audience,
                    metadata_visible=True,
                    safe_covered_default=False,
                    name=design.name,
                    asset_ref=design.asset_ref,
                    content_rating=design.content_rating,
                    armor=design.armor,
                    tail_clearance=design.tail_clearance,
                    ear_clearance=design.ear_clearance,
                )
            )
        else:
            entries.append(
                CatalogEntry(
                    design_id=design.design_id,
                    version=design.version,
                    garment_class=design.garment_class,
                    garment_type=design.garment_type,
                    privacy=design.privacy,
                    audience=audience,
                    metadata_visible=False,
                    safe_covered_default=True,
                    name=SAFE_COVERED_DEFAULT_NAME,
                    asset_ref=None,
                    content_rating=None,
                    armor=None,
                    tail_clearance=False,
                    ear_clearance=False,
                )
            )
    return CatalogView(audience=audience, entries=tuple(entries))


class EquipmentDesignRegistry:
    """Immutable lookup injected by an inventory/adapter boundary."""

    def __init__(self, designs: Iterable[WardrobeDesign]) -> None:
        values = tuple(designs)
        if not values:
            raise EquipmentError("design registry cannot be empty")
        if any(not isinstance(design, WardrobeDesign) for design in values):
            raise TypeError("designs must contain WardrobeDesign values")
        by_id: dict[str, WardrobeDesign] = {}
        for design in values:
            if design.design_id in by_id:
                raise EquipmentError(f"duplicate design ID: {design.design_id}")
            by_id[design.design_id] = design
        self._designs = values
        self._by_id: Mapping[str, WardrobeDesign] = MappingProxyType(by_id)

    @property
    def designs(self) -> tuple[WardrobeDesign, ...]:
        return self._designs

    def __len__(self) -> int:
        return len(self._designs)

    def __iter__(self):
        return iter(self._designs)

    def __contains__(self, design_id: object) -> bool:
        return design_id in self._by_id

    def get(self, design_id: str) -> WardrobeDesign:
        if not isinstance(design_id, str):
            raise TypeError("design_id must be a string")
        try:
            return self._by_id[design_id]
        except KeyError as exc:
            raise EquipmentError(f"unknown catalog design: {design_id}") from exc

    def require(self, design_id: str) -> WardrobeDesign:
        return self.get(design_id)

    def for_class(
        self, garment_class: GarmentClass
    ) -> tuple[WardrobeDesign, ...]:
        return tuple(
            design
            for design in self._designs
            if design.garment_class is garment_class
        )

    def visible_to(self, audience: CatalogAudience) -> CatalogView:
        return project_catalog(self._designs, audience)


def wardrobe_design_from_garment(
    garment: Garment,
    *,
    garment_class: GarmentClass = GarmentClass.CLOTHING,
    garment_type: str | None = None,
    fit_anchors: tuple[str, ...],
    armor: ArmorMetadata | None = None,
    privacy: WardrobePrivacy | None = None,
    content_rating: str = "standard",
    version: int = 1,
    source: str = "aegis.wardrobe.existing",
    license: str = "project-owned",
) -> WardrobeDesign:
    """Adapt an existing :class:`Garment` without creating duplicate state."""
    if not isinstance(garment, Garment):
        raise TypeError("garment must be Garment")
    resolved_privacy = privacy
    if resolved_privacy is None:
        resolved_privacy = (
            WardrobePrivacy.PRIVATE if garment.private_only else WardrobePrivacy.PUBLIC
        )
    return WardrobeDesign(
        design_id=garment.item_id,
        version=version,
        name=garment.name,
        garment_class=garment_class,
        garment_type=garment_type or garment.item_id,
        layer=garment.layer,
        slots=garment.slots,
        coverage=garment.coverage,
        fit_anchors=fit_anchors,
        privacy=resolved_privacy,
        content_rating=content_rating,
        asset_ref=garment.asset_ref,
        source=source,
        license=license,
        armor=armor,
        tail_clearance=garment.tail_clearance,
        ear_clearance=garment.ear_clearance,
    )


def garment_from_wardrobe_design(design: WardrobeDesign) -> Garment:
    """Project a design back to the existing ordinary Garment vocabulary."""
    if not isinstance(design, WardrobeDesign):
        raise TypeError("design must be WardrobeDesign")
    return Garment(
        item_id=design.design_id,
        name=design.name,
        layer=design.layer,
        slots=design.slots,
        coverage=design.coverage,
        tail_clearance=design.tail_clearance,
        ear_clearance=design.ear_clearance,
        asset_ref=design.asset_ref,
        private_only=design.privacy is not WardrobePrivacy.PUBLIC,
    )


def wardrobe_from_designs(designs: Iterable[WardrobeDesign]) -> Wardrobe:
    """Build one ordinary Wardrobe projection from shared catalog designs."""
    values = tuple(designs)
    if any(not isinstance(design, WardrobeDesign) for design in values):
        raise TypeError("designs must contain WardrobeDesign values")
    return Wardrobe(tuple(garment_from_wardrobe_design(design) for design in values))


def equipped_item_from_design_id(
    item_instance_id: UUID,
    design_id: str,
    registry: EquipmentDesignRegistry,
    *,
    design_version: int | None = None,
    asset_verified: bool = False,
) -> EquippedItem:
    """Build an equip projection from an instance ID and injected registry."""
    if not isinstance(registry, EquipmentDesignRegistry):
        raise TypeError("registry must be EquipmentDesignRegistry")
    if type(asset_verified) is not bool:
        raise TypeError("asset_verified must be boolean")
    design = registry.require(design_id)
    if design_version is not None and design.version != design_version:
        raise EquipmentError(
            f"design {design_id!r} version {design.version} does not match "
            f"instance version {design_version}"
        )
    return EquippedItem.from_design(
        item_instance_id, design, asset_verified=asset_verified,
    )


__all__ = [
    "CatalogAudience",
    "CatalogEntry",
    "CatalogView",
    "EquipmentDesignRegistry",
    "SAFE_COVERED_DEFAULT_NAME",
    "design_visible_to",
    "equipped_item_from_design_id",
    "garment_from_wardrobe_design",
    "project_catalog",
    "wardrobe_design_from_garment",
    "wardrobe_from_designs",
]
