"""Optional graphic T-shirt design for Sofía's existing relaxed lounge outfit.

The standard plain tee stays the default. This module adds an *unrendered*
blueprint and an explicit outfit variation, not an automatic wardrobe change,
verified art asset, fixed rotation schedule, or a new claim of Sofía's taste.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .starter_user_preferences import build_sparks_starter_wardrobe
from .wardrobe import Wardrobe, WardrobeError
from .wardrobe_catalog import (
    GarmentBlueprint, RequestStatus, StyleInput, WardrobePrebuild,
)
from .wardrobe_routine import OutfitPlan

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
        if not self.catalog.wardrobe.selection(self.optional_plan.item_ids).covered_default:
            raise WardrobeError("graphic lounge variation must remain covered")
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
