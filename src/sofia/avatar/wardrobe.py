"""Offline wardrobe metadata, layering and covered-default policy.

This module has no mesh, texture, renderer, age proof, physical sensor or
external permission authority. A host must supply independently authenticated
and verified facts. Unknowns deny restricted visibility. Displaying a garment
metadata record does not claim that its art asset has been created.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import re

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
SLOTS = frozenset({
    "torso", "pelvis", "legs", "feet", "hands", "head", "ears", "tail", "neck",
    "shoulders", "upper_arms", "forearms", "wrists", "fingers", "waist", "back",
    "thighs", "calves", "ankles", "hair",
    "left_hand", "right_hand", "left_forearm", "right_forearm",
    "left_wrist", "right_wrist", "left_foot", "right_foot",
})
COVERED_DEFAULT = frozenset({"torso", "pelvis"})


class WardrobeError(ValueError):
    pass


class WardrobeConflict(RuntimeError):
    pass


class VisibilityDenied(PermissionError):
    pass


class Layer(IntEnum):
    UNDERWEAR = 10
    BASE = 20
    MID = 30
    OUTER = 40
    ACCESSORY = 50


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise WardrobeError(f"invalid {name}")
    return value


@dataclass(frozen=True)
class Garment:
    """Reviewed metadata; source/license and real assets are separate gates."""

    item_id: str
    name: str
    layer: Layer
    slots: tuple[str, ...]
    coverage: tuple[str, ...]
    tail_clearance: bool = False
    ear_clearance: bool = False
    asset_ref: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.item_id, "garment ID")
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 160:
            raise WardrobeError("invalid garment name")
        if not isinstance(self.layer, Layer):
            raise WardrobeError("unknown garment layer")
        if (not isinstance(self.slots, tuple) or not self.slots
                or set(self.slots) - SLOTS or len(set(self.slots)) != len(self.slots)):
            raise WardrobeError("invalid garment slots")
        if (not isinstance(self.coverage, tuple) or set(self.coverage) - SLOTS
                or len(set(self.coverage)) != len(self.coverage)
                or not set(self.coverage).issubset(self.slots)):
            raise WardrobeError("coverage must be unique valid garment slots")
        if type(self.tail_clearance) is not bool or type(self.ear_clearance) is not bool:
            raise WardrobeError("clearance flags must be boolean")
        if self.asset_ref is not None:
            _identifier(self.asset_ref, "asset reference")


@dataclass(frozen=True)
class Outfit:
    """Validated metadata selection; not confirmation of a visual change."""
    item_ids: tuple[str, ...]
    coverage: frozenset[str]
    covered_default: bool
    asset_refs_present: bool


@dataclass(frozen=True)
class PreviewRequest:
    """Trusted adapter-supplied facts, not user text or LLM claims."""
    adult_verified: bool = False
    owner_verified: bool = False
    private_local_session: bool = False
    explicit_current_opt_in: bool = False
    external_stop_active: bool = False

    def __post_init__(self) -> None:
        if any(type(value) is not bool for value in (
            self.adult_verified, self.owner_verified, self.private_local_session,
            self.explicit_current_opt_in, self.external_stop_active
        )):
            raise WardrobeError("preview facts must be strict booleans")

    def allow_restricted_preview(self) -> None:
        if (not self.adult_verified or not self.owner_verified
                or not self.private_local_session or not self.explicit_current_opt_in
                or self.external_stop_active):
            raise VisibilityDenied("restricted preview is not authorized")


class Wardrobe:
    """Immutable catalogue and checked layer selection with no side effects."""

    def __init__(self, garments: tuple[Garment, ...]) -> None:
        if not isinstance(garments, tuple) or any(not isinstance(g, Garment) for g in garments):
            raise WardrobeError("garments must be a tuple of Garment")
        ids = [g.item_id for g in garments]
        if len(set(ids)) != len(ids):
            raise WardrobeError("duplicate garment ID")
        self._garments = {g.item_id: g for g in garments}

    def selection(self, item_ids: tuple[str, ...]) -> Outfit:
        if not isinstance(item_ids, tuple):
            raise WardrobeError("item_ids must be a tuple")
        if len(set(item_ids)) != len(item_ids):
            raise WardrobeConflict("duplicate selected item")
        selected: list[Garment] = []
        for item_id in item_ids:
            _identifier(item_id, "garment ID")
            try:
                selected.append(self._garments[item_id])
            except KeyError as error:
                raise WardrobeError("unknown garment ID") from error
        occupied: set[tuple[Layer, str]] = set()
        for garment in selected:
            for slot in garment.slots:
                key = (garment.layer, slot)
                if key in occupied:
                    raise WardrobeConflict("two garments occupy one layer and slot")
                occupied.add(key)
        covers = frozenset(slot for g in selected for slot in g.coverage)
        # A garment occupying ears/tail must actually accommodate them.
        if any("tail" in g.slots and not g.tail_clearance for g in selected):
            raise WardrobeConflict("tail region requires explicit clearance")
        if any("ears" in g.slots and not g.ear_clearance for g in selected):
            raise WardrobeConflict("ear region requires explicit clearance")
        return Outfit(item_ids, covers, COVERED_DEFAULT.issubset(covers),
                      bool(selected) and all(g.asset_ref is not None for g in selected))

    def require_public_ready(
        self, outfit: Outfit, *, assets_verified_by_renderer: bool = False
    ) -> None:
        """Conservative display gate; only a trusted renderer verifies actual assets."""
        if (not isinstance(outfit, Outfit) or not outfit.covered_default
                or not outfit.asset_refs_present
                or type(assets_verified_by_renderer) is not bool
                or not assets_verified_by_renderer):
            raise VisibilityDenied("public/default outfit requires coverage and verified assets")

    def restricted_preview(self, *, request: PreviewRequest) -> None:
        if not isinstance(request, PreviewRequest):
            raise VisibilityDenied("restricted preview requires verified session facts")
        request.allow_restricted_preview()
