"""Typed garment creator and reviewed outfit-composition APIs.

Fit vocabulary is owned by fit.py; these APIs preserve the structured garment
creator added on main while the obsolete body-authoring contract stays retired.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .presentation import PresentationAuthority
from .wardrobe_generated_store import (
    GarmentAcceptanceResult,
    GeneratedWardrobeStore,
    SofiaGarmentAcceptance,
)
from .presentation_store import PresentationStore
from .wardrobe import Garment, WardrobeError
from .wardrobe_design import (
    ComfortProfile,
    ContentRating,
    ContextProfile,
    EnvironmentProfile,
    ExposureZone,
    GarmentDesign,
    GraphicDesign,
    MaterialProperties,
    validate_design,
)
from .wardrobe_planner import Activity, OutfitPlan, Season


@dataclass(frozen=True, slots=True)
class GarmentDesignRequest:
    """Creator-facing request matching the structured garment schema."""

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
    content_rating: ContentRating = ContentRating.STANDARD
    exposure: tuple[ExposureZone, ...] = ()
    description: str = ""
    material_properties: MaterialProperties = field(
        default_factory=MaterialProperties
    )
    environment: EnvironmentProfile = field(
        default_factory=EnvironmentProfile
    )
    context: ContextProfile = field(default_factory=ContextProfile)
    comfort: ComfortProfile = field(default_factory=ComfortProfile)


class WardrobeStudio:
    """Compose outfits and propose new garment blueprints from typed inputs."""

    def __init__(
        self,
        catalog: WardrobePrebuild,
        *,
        authority: PresentationAuthority | None = None,
        store: PresentationStore | None = None,
        generated_store: GeneratedWardrobeStore | None = None,
    ) -> None:
        from .wardrobe_prebuild import WardrobePrebuild

        if not isinstance(catalog, WardrobePrebuild):
            raise TypeError("catalog must be WardrobePrebuild")
        if authority is not None and not isinstance(authority, PresentationAuthority):
            raise TypeError("authority must be PresentationAuthority or None")
        if store is not None and not isinstance(store, PresentationStore):
            raise TypeError("store must be PresentationStore or None")
        if store is not None and authority is None:
            raise ValueError("store requires live presentation authority")
        if generated_store is not None and not isinstance(
            generated_store, GeneratedWardrobeStore
        ):
            raise TypeError(
                "generated_store must be GeneratedWardrobeStore or None"
            )
        self.catalog = catalog
        self.authority = authority
        self.store = store
        self.generated_store = generated_store

    def decide_generated_piece(
        self,
        blueprint: "GarmentBlueprint",
        acceptance: SofiaGarmentAcceptance,
    ) -> GarmentAcceptanceResult:
        """Only Sofía can accept a generated piece into permanent ownership."""
        from .wardrobe_prebuild import GarmentBlueprint

        if not isinstance(blueprint, GarmentBlueprint):
            raise TypeError("blueprint must be GarmentBlueprint")
        if not isinstance(acceptance, SofiaGarmentAcceptance):
            raise TypeError("acceptance must be SofiaGarmentAcceptance")
        if any(
            item.garment.item_id == blueprint.garment.item_id
            for item in self.catalog.blueprints
        ):
            raise WardrobeError("generated garment ID already exists")
        if self.generated_store is None:
            if acceptance.requires_persistence:
                raise WardrobeError(
                    "accepted generated garment requires generated wardrobe store"
                )
            return GarmentAcceptanceResult.from_acceptance(acceptance)
        return self.generated_store.apply(blueprint, acceptance)

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
                # Callers supplying the canonical store get durable-or-rollback
                # registration. The application wardrobe-generation pipeline
                # is the production caller for this creator API.
                self.store.persist_mutation(
                    self.authority,
                    mutate,
                )
        return plan

    def design_piece(
        self,
        request: GarmentDesignRequest,
    ) -> "GarmentBlueprint":
        from .wardrobe_prebuild import GarmentBlueprint

        if not isinstance(request, GarmentDesignRequest):
            raise TypeError("request must be GarmentDesignRequest")
        design = GarmentDesign(
            item_id=request.item_id,
            name=request.name,
            garment_type=request.garment_type,
            fit=request.fit,
            rise=request.rise,
            length=request.length,
            sleeve_length=request.sleeve_length,
            material=request.material,
            primary=request.primary,
            accent=request.accent,
            pattern=request.pattern,
            graphic=request.graphic,
            features=request.features,
            style_tags=request.style_tags,
            private_only=request.private_only,
            content_rating=request.content_rating,
            exposure=request.exposure,
            description=request.description,
            material_properties=request.material_properties,
            environment=request.environment,
            context=request.context,
            comfort=request.comfort,
        )
        definition = validate_design(design)
        garment = Garment(
            item_id=design.item_id,
            name=design.name,
            layer=definition.layer,
            slots=definition.slots,
            coverage=definition.coverage,
            tail_clearance=(
                definition.tail_clearance
                or "tail_clearance" in design.features
            ),
            ear_clearance=(
                definition.ear_clearance
                or "ear_clearance" in design.features
            ),
            asset_ref=None,
            private_only=design.private_only,
        )
        return GarmentBlueprint(garment=garment, design=design)

