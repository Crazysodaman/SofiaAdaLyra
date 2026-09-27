"""Validated AVATAR wardrobe design/composition studio.

This creates metadata proposals only. It cannot mint renderer assets, current
presentation state, consent, private authorization or durable user preference.
"""
from __future__ import annotations

from dataclasses import dataclass

from .wardrobe import Garment, Wardrobe, WardrobeError
from .wardrobe_catalog import GarmentBlueprint, WardrobePrebuild
from .wardrobe_piece_catalog import all_closet_categories
from .wardrobe_routine import Activity, OutfitPlan, Season


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

    def __init__(self, catalog: WardrobePrebuild) -> None:
        if not isinstance(catalog, WardrobePrebuild):
            raise TypeError("catalog must be WardrobePrebuild")
        self.catalog = catalog
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
    ) -> OutfitPlan:
        selected = self.catalog.wardrobe.selection(item_ids)
        if private_only:
            if not selected.private_only:
                raise WardrobeError(
                    "private composition requires at least one private-only piece"
                )
        else:
            if selected.private_only:
                raise WardrobeError(
                    "public composition cannot contain private-only pieces"
                )
            if not selected.covered_default:
                raise WardrobeError(
                    "public composition must cover torso and pelvis"
                )
        return OutfitPlan(
            outfit_id,
            item_ids,
            activities,
            seasons,
            lounge=lounge,
            private_only=private_only,
            style_tags=style_tags,
            display_name=display_name,
        )

    def design_piece(
        self,
        request: GarmentDesignRequest,
    ) -> GarmentBlueprint:
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
