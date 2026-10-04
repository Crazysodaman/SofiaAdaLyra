"""Validated AVATAR wardrobe design/composition studio.

This creates metadata proposals only. It cannot mint renderer assets, current
presentation state, consent, private authorization or durable user preference.
"""
from __future__ import annotations

from dataclasses import dataclass

from .presentation import PresentationAuthority
from .presentation_store import PresentationStore
from .wardrobe import Garment, WardrobeError
from .wardrobe_catalog import GarmentBlueprint, WardrobePrebuild
from .wardrobe_catalog import all_closet_categories
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
