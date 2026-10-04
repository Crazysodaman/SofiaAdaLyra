"""Small reviewed starter wardrobe built from structured garment designs.

The type vocabulary lives in wardrobe_design.py. This catalog contains only
pieces Sofía currently owns as design metadata. No blueprint claims a mesh,
texture, renderer asset, or proof that an item is visibly worn.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import re

from .authoring import DEFAULT_FIT_ANCHORS
from .wardrobe import Garment, Wardrobe, WardrobeError
from .wardrobe_design import (
    ComfortProfile,
    ContextProfile,
    EnvironmentProfile,
    FabricWeight,
    GarmentDesign,
    GraphicDesign,
    HumidityProfile,
    MaterialProperties,
    MoistureProfile,
    MovementProfile,
    PrecipitationProfile,
    RatedContext,
    Suitability,
    SunlightProfile,
    TemperatureProfile,
    TraitLevel,
    WindProfile,
    garment_type,
    resolve_color,
    validate_design,
)
from .wardrobe_planner import (
    Activity,
    OutfitPlan,
    Preference,
    PreferenceActor,
    PreferenceTarget,
    Season,
    Sentiment,
)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)

DRAFT_STATUS = "proposed_no_mesh_no_verified_asset"
ALL_SEASONS = frozenset(Season)

DAY_DEFAULT_OUTFIT_ID = "day.default"
NIGHT_LOUNGE_OUTFIT_ID = "night.lounge"
FALLBACK_OUTFIT_ID = "fallback.covered"


class RequestStatus(str, Enum):
    USER_REQUESTED = "user_requested"
    USER_LIKED = "user_liked"
    USER_DISLIKED = "user_disliked"


@dataclass(frozen=True, slots=True)
class StyleInput:
    """Source-backed request or taste. Request does not imply LIKE."""

    subject_id: str
    status: RequestStatus
    source_id: str
    detail: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and _ID.fullmatch(value)
            for value in (self.subject_id, self.source_id)
        ):
            raise WardrobeError("style input requires sourced typed identity")
        if not isinstance(self.status, RequestStatus):
            raise WardrobeError("style input status must be typed")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise WardrobeError("style input requires a concrete detail")


@dataclass(frozen=True, slots=True)
class GarmentBlueprint:
    """One structured garment design plus its low-level wardrobe projection."""

    garment: Garment
    design: GarmentDesign
    provenance: str = "design_proposal_review_required"

    def __post_init__(self) -> None:
        if not isinstance(self.garment, Garment):
            raise WardrobeError("blueprint requires Garment")
        if self.garment.asset_ref is not None:
            raise WardrobeError("blueprints must refer to unbuilt garment assets")
        if not isinstance(self.design, GarmentDesign):
            raise WardrobeError("blueprint requires GarmentDesign")
        definition = validate_design(self.design)
        if self.garment.item_id != self.design.item_id:
            raise WardrobeError("garment and design IDs must match")
        if self.garment.name != self.design.name:
            raise WardrobeError("garment and design names must match")
        if self.garment.layer is not definition.layer:
            raise WardrobeError("garment layer must match garment type")
        if self.garment.slots != definition.slots:
            raise WardrobeError("garment slots must match garment type")
        if self.garment.coverage != definition.coverage:
            raise WardrobeError("garment coverage must match garment type")
        if self.garment.private_only != self.design.private_only:
            raise WardrobeError("garment and design privacy must match")
        if self.provenance not in {
            "canonical_clothing_design",
            "design_proposal_review_required",
        }:
            raise WardrobeError("unknown design provenance")

    @property
    def primary_hex(self) -> str:
        return resolve_color(self.design.primary)

    @property
    def accent_hexes(self) -> tuple[str, ...]:
        return (
            ()
            if self.design.accent is None
            else (resolve_color(self.design.accent),)
        )

    @property
    def material(self) -> str:
        return self.design.material

    @property
    def construction(self) -> tuple[str, ...]:
        details = [
            "Structured wardrobe design metadata; no renderer asset is implied.",
        ]
        if self.design.features:
            details.append(
                "Features: " + ", ".join(
                    feature.replace("_", " ")
                    for feature in self.design.features
                ) + "."
            )
        if self.design.graphic.enabled:
            details.append(
                "Graphic: "
                + str(self.design.graphic.design).replace("_", " ")
                + " at "
                + str(self.design.graphic.placement).replace("_", " ")
                + "."
            )
        return tuple(details)

    @property
    def fit_anchors(self) -> tuple[str, ...]:
        return garment_type(self.design.garment_type).fit_anchors

    @property
    def category(self) -> str:
        # Preserve precise undergarment semantics for conversational queries
        # while the creator itself remains type/family driven.
        if self.design.garment_type == "bralette":
            return "closet.bra"
        if self.design.garment_type == "briefs":
            return "closet.panty"
        family = garment_type(self.design.garment_type).family.value
        return f"closet.{family}"

    @property
    def style_tags(self) -> tuple[str, ...]:
        return self.design.style_tags

    @property
    def private_only(self) -> bool:
        return self.design.private_only

    @property
    def description(self) -> str:
        return self.design.description

    @property
    def design_signature(self) -> str:
        payload = {
            "name": self.design.name,
            "garment_type": self.design.garment_type,
            "fit": self.design.fit,
            "rise": self.design.rise,
            "length": self.design.length,
            "sleeve_length": self.design.sleeve_length,
            "material": self.design.material,
            "primary": self.design.primary,
            "accent": self.design.accent,
            "pattern": self.design.pattern,
            "graphic": {
                "enabled": self.design.graphic.enabled,
                "placement": self.design.graphic.placement,
                "design": self.design.graphic.design,
            },
            "features": self.design.features,
            "style_tags": self.design.style_tags,
            "private_only": self.design.private_only,
            "material_properties": self.design.material_properties.as_dict(),
            "environment": self.design.environment.as_dict(),
            "context": self.design.context.as_dict(),
            "comfort": self.design.comfort.as_dict(),
            "description": self.design.description,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class WardrobePrebuild:
    wardrobe: Wardrobe
    blueprints: tuple[GarmentBlueprint, ...]
    presets: tuple[OutfitPlan, ...]
    inputs: tuple[StyleInput, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.wardrobe, Wardrobe):
            raise WardrobeError("missing wardrobe")
        if (
            not isinstance(self.blueprints, tuple)
            or any(not isinstance(bp, GarmentBlueprint) for bp in self.blueprints)
        ):
            raise WardrobeError("invalid garment blueprints")
        blueprint_ids = tuple(bp.garment.item_id for bp in self.blueprints)
        if len(set(blueprint_ids)) != len(blueprint_ids):
            raise WardrobeError("duplicate garment blueprint")
        signatures = tuple(bp.design_signature for bp in self.blueprints)
        if len(set(signatures)) != len(signatures):
            raise WardrobeError("duplicate garment visual design signature")
        if (
            not isinstance(self.presets, tuple)
            or not self.presets
            or any(not isinstance(plan, OutfitPlan) for plan in self.presets)
        ):
            raise WardrobeError("missing outfit presets")
        if len({plan.outfit_id for plan in self.presets}) != len(self.presets):
            raise WardrobeError("duplicate outfit preset")
        if (
            not isinstance(self.inputs, tuple)
            or any(not isinstance(item, StyleInput) for item in self.inputs)
        ):
            raise WardrobeError("invalid style inputs")

        known_fit_anchors = {anchor.name for anchor in DEFAULT_FIT_ANCHORS}
        for blueprint in self.blueprints:
            unknown = set(blueprint.fit_anchors) - known_fit_anchors
            if unknown:
                raise WardrobeError(
                    "garment blueprint references unknown body fit anchor"
                )

        ids = set(blueprint_ids)
        for plan in self.presets:
            if set(plan.item_ids) - ids:
                raise WardrobeError("outfit references unbuilt/unlisted garment")
            selected = self.wardrobe.selection(plan.item_ids)
            if plan.private_only:
                if not selected.private_only:
                    raise WardrobeError(
                        "private outfit must contain private-only garment metadata"
                    )
            elif selected.private_only or not selected.covered_default:
                raise WardrobeError(
                    "prebuilt public outfits must remain covered and non-private"
                )

        known_subjects = ids | {plan.outfit_id for plan in self.presets}
        if any(item.subject_id not in known_subjects for item in self.inputs):
            raise WardrobeError("style input references an unknown design")

    def reviewed_preferences(self) -> tuple[Preference, ...]:
        plan_ids = {plan.outfit_id for plan in self.presets}
        blueprint_ids = {bp.garment.item_id for bp in self.blueprints}
        result: list[Preference] = []
        for item in self.inputs:
            if item.status is RequestStatus.USER_LIKED:
                sentiment = Sentiment.LIKE
            elif item.status is RequestStatus.USER_DISLIKED:
                sentiment = Sentiment.DISLIKE
            else:
                continue
            target = (
                PreferenceTarget.OUTFIT
                if item.subject_id in plan_ids
                else PreferenceTarget.ITEM
                if item.subject_id in blueprint_ids
                else None
            )
            if target is None:
                raise WardrobeError(
                    "reviewed style input references unknown preference target"
                )
            result.append(
                Preference(
                    actor=PreferenceActor.SPARKS,
                    target=target,
                    ids=(item.subject_id,),
                    sentiment=sentiment,
                    source_id=item.source_id,
                    reviewed=True,
                )
            )
        return tuple(result)

    def preset(self, outfit_id: str) -> OutfitPlan:
        for plan in self.presets:
            if plan.outfit_id == outfit_id:
                return plan
        raise WardrobeError("unknown prebuilt outfit")

    def pieces(
        self,
        *,
        category: str | None = None,
        private_only: bool | None = None,
    ) -> tuple[GarmentBlueprint, ...]:
        if category is not None and (
            not isinstance(category, str) or not category.strip()
        ):
            raise WardrobeError("category must be None or nonempty")
        if private_only is not None and type(private_only) is not bool:
            raise WardrobeError("private_only must be None or boolean")
        return tuple(
            blueprint
            for blueprint in self.blueprints
            if (
                (category is None or blueprint.category == category)
                and (
                    private_only is None
                    or blueprint.private_only is private_only
                )
            )
        )

    def closet_summary(self) -> dict[str, object]:
        categories: dict[str, int] = {}
        for blueprint in self.blueprints:
            categories[blueprint.category] = categories.get(blueprint.category, 0) + 1
        signatures = [bp.design_signature for bp in self.blueprints]
        return {
            "starter_piece_count": len(self.blueprints),
            "outfit_count": len(self.presets),
            "type_count": len({bp.design.garment_type for bp in self.blueprints}),
            "unique_design_signature_count": len(set(signatures)),
            "all_designs_unique": len(signatures) == len(set(signatures)),
            "categories": dict(sorted(categories.items())),
            "assets_verified": False,
        }

    def manifest(self) -> dict[str, object]:
        """JSON-ready handoff for creator/modeler tooling."""
        return {
            "schema": "sofia.avatar.wardrobe.prebuild.v2",
            "stage": DRAFT_STATUS,
            "garments": [
                {
                    "item_id": bp.design.item_id,
                    "name": bp.design.name,
                    "type": bp.design.garment_type,
                    "family": garment_type(bp.design.garment_type).family.value,
                    "fit": bp.design.fit,
                    "rise": bp.design.rise,
                    "length": bp.design.length,
                    "sleeve_length": bp.design.sleeve_length,
                    "material": bp.design.material,
                    "primary": bp.design.primary,
                    "primary_hex": bp.primary_hex,
                    "accent": bp.design.accent,
                    "accent_hexes": list(bp.accent_hexes),
                    "pattern": bp.design.pattern,
                    "graphic": {
                        "enabled": bp.design.graphic.enabled,
                        "placement": bp.design.graphic.placement,
                        "design": bp.design.graphic.design,
                    },
                    "features": list(bp.design.features),
                    "style_tags": list(bp.design.style_tags),
                    "material_properties": bp.design.material_properties.as_dict(),
                    "environment": bp.design.environment.as_dict(),
                    "context": bp.design.context.as_dict(),
                    "comfort": bp.design.comfort.as_dict(),
                    "slots": list(bp.garment.slots),
                    "coverage": list(bp.garment.coverage),
                    "fit_anchors": list(bp.fit_anchors),
                    "layer": bp.garment.layer.name.lower(),
                    "tail_clearance": bp.garment.tail_clearance,
                    "ear_clearance": bp.garment.ear_clearance,
                    "asset_ref": None,
                    "private_only": bp.private_only,
                    "provenance": bp.provenance,
                    "design_signature": bp.design_signature,
                    "description": bp.design.description,
                }
                for bp in self.blueprints
            ],
            "outfits": [
                {
                    "outfit_id": plan.outfit_id,
                    "display_name": plan.display_name,
                    "item_ids": list(plan.item_ids),
                    "activities": sorted(x.value for x in plan.activities),
                    "seasons": sorted(x.value for x in plan.seasons),
                    "lounge": plan.lounge,
                    "private_only": plan.private_only,
                    "manual_only": plan.manual_only,
                    "style_tags": list(plan.style_tags),
                }
                for plan in self.presets
            ],
            "style_inputs": [
                {
                    "subject_id": item.subject_id,
                    "status": item.status.value,
                    "source_id": item.source_id,
                    "detail": item.detail,
                }
                for item in self.inputs
            ],
        }


def _starter_profiles(
    item_id: str,
) -> tuple[
    MaterialProperties,
    EnvironmentProfile,
    ContextProfile,
    ComfortProfile,
]:
    """Return reviewed creator/environment metadata for one starter garment."""

    generic_context = ContextProfile(
        dayparts=RatedContext(
            good=("morning", "afternoon", "evening", "night", "late_night"),
        ),
        seasons=RatedContext(
            good=("spring", "summer", "autumn", "winter"),
        ),
        activities=RatedContext(
            good=("conversation", "relaxing"),
            acceptable=("engineering", "lab", "sleep", "formal"),
        ),
        settings=RatedContext(
            good=("home", "private", "casual_public"),
            acceptable=("workshop", "lab", "office", "outdoor"),
        ),
        formality=RatedContext(
            good=("lounge", "casual"),
            acceptable=("work", "smart_casual"),
            poor=("formal",),
        ),
        movement=MovementProfile(
            mobility=Suitability.GOOD,
            seated_comfort=Suitability.GOOD,
            active_comfort=Suitability.GOOD,
        ),
    )
    generic_environment = EnvironmentProfile(
        temperature=TemperatureProfile(
            5.0, 15.0, 28.0, 38.0, FabricWeight.LIGHT
        ),
        precipitation=PrecipitationProfile(
            dry=Suitability.EXCELLENT,
            mist=Suitability.GOOD,
            drizzle=Suitability.ACCEPTABLE,
            rain=Suitability.POOR,
            heavy_rain=Suitability.UNSUITABLE,
            snow=Suitability.POOR,
        ),
        moisture=MoistureProfile(
            quick_dry=True,
            water_resistance=TraitLevel.LOW,
            absorbency=TraitLevel.LOW,
            wet_comfort=Suitability.ACCEPTABLE,
        ),
        humidity=HumidityProfile(
            low=Suitability.GOOD,
            moderate=Suitability.EXCELLENT,
            high=Suitability.GOOD,
        ),
        wind=WindProfile(
            resistance=TraitLevel.LOW,
            strong_wind=Suitability.POOR,
        ),
        sunlight=SunlightProfile(
            direct_sun=Suitability.GOOD,
            uv_protection=TraitLevel.LOW,
        ),
        indoor=Suitability.EXCELLENT,
        outdoor=Suitability.GOOD,
    )
    generic_material = MaterialProperties(
        stretch=TraitLevel.MODERATE,
        fabric_weight=FabricWeight.LIGHT,
        texture="smooth",
        breathability=TraitLevel.HIGH,
        insulation=TraitLevel.LOW,
    )
    generic_comfort = ComfortProfile(
        softness=TraitLevel.HIGH,
        flexibility=TraitLevel.HIGH,
        compression=TraitLevel.LOW,
        heat_retention=TraitLevel.LOW,
        ventilation=TraitLevel.HIGH,
        skin_contact=Suitability.EXCELLENT,
    )

    if item_id in {"base.bralette", "base.briefs"}:
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.LIGHT,
                texture="soft_smooth",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    5.0, 16.0, 30.0, 40.0, FabricWeight.LIGHT
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.GOOD,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.ACCEPTABLE,
            ),
            generic_context,
            generic_comfort,
        )

    if item_id == "day.technical_top":
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.LIGHT,
                texture="smooth_technical",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    6.0, 13.0, 25.0, 31.0, FabricWeight.LIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.GOOD,
                    drizzle=Suitability.GOOD,
                    rain=Suitability.ACCEPTABLE,
                    heavy_rain=Suitability.POOR,
                    snow=Suitability.POOR,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.LOW,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.GOOD,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.LOW,
                    strong_wind=Suitability.POOR,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.GOOD,
                    uv_protection=TraitLevel.LOW,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.GOOD,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    acceptable=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("spring", "autumn"),
                    good=("summer", "winter"),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab"),
                    good=("conversation", "workshop"),
                    acceptable=("relaxing",),
                    poor=("sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab"),
                    good=("office", "casual_public", "home"),
                    acceptable=("outdoor",),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual", "smart_casual"),
                    poor=("formal", "lounge"),
                ),
                emotion_styles=RatedContext(
                    good=("focused", "energetic", "confident"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.GOOD,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.MODERATE,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.LOW,
                ventilation=TraitLevel.HIGH,
                skin_contact=Suitability.GOOD,
            ),
        )

    if item_id == "day.utility_trousers":
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.MIDWEIGHT,
                texture="smooth_woven",
                breathability=TraitLevel.MODERATE,
                insulation=TraitLevel.MODERATE,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    0.0, 10.0, 24.0, 32.0, FabricWeight.MIDWEIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.GOOD,
                    drizzle=Suitability.GOOD,
                    rain=Suitability.ACCEPTABLE,
                    heavy_rain=Suitability.POOR,
                    snow=Suitability.ACCEPTABLE,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.MODERATE,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.ACCEPTABLE,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.MODERATE,
                    strong_wind=Suitability.GOOD,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.GOOD,
                    uv_protection=TraitLevel.MODERATE,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.EXCELLENT,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    acceptable=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("spring", "autumn", "winter"),
                    good=("summer",),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop"),
                    good=("conversation", "casual"),
                    acceptable=("relaxing",),
                    poor=("sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab", "outdoor"),
                    good=("office", "casual_public", "home"),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual",),
                    acceptable=("smart_casual",),
                    poor=("formal", "lounge"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.GOOD,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.MODERATE,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.MODERATE,
                ventilation=TraitLevel.MODERATE,
                skin_contact=Suitability.GOOD,
            ),
        )

    if item_id == "day.engineer_jacket":
        return (
            MaterialProperties(
                stretch=TraitLevel.MODERATE,
                fabric_weight=FabricWeight.MIDWEIGHT,
                texture="matte_shell",
                breathability=TraitLevel.LOW,
                insulation=TraitLevel.MODERATE,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    -8.0, 4.0, 18.0, 25.0, FabricWeight.MIDWEIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.EXCELLENT,
                    drizzle=Suitability.EXCELLENT,
                    rain=Suitability.GOOD,
                    heavy_rain=Suitability.ACCEPTABLE,
                    snow=Suitability.GOOD,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.HIGH,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.EXCELLENT,
                    moderate=Suitability.GOOD,
                    high=Suitability.POOR,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.HIGH,
                    strong_wind=Suitability.EXCELLENT,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.POOR,
                    uv_protection=TraitLevel.HIGH,
                ),
                indoor=Suitability.ACCEPTABLE,
                outdoor=Suitability.EXCELLENT,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    poor=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("autumn", "winter"),
                    good=("spring",),
                    poor=("summer",),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop"),
                    good=("conversation", "outdoor"),
                    poor=("relaxing", "sleep"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab", "outdoor"),
                    good=("office", "casual_public"),
                    acceptable=("home",),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("smart_casual",),
                    acceptable=("casual",),
                    poor=("lounge",),
                ),
                movement=MovementProfile(
                    mobility=Suitability.GOOD,
                    seated_comfort=Suitability.ACCEPTABLE,
                    active_comfort=Suitability.GOOD,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.LOW,
                flexibility=TraitLevel.MODERATE,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.MODERATE,
                ventilation=TraitLevel.LOW,
                skin_contact=Suitability.ACCEPTABLE,
            ),
        )

    if item_id in {"day.work_socks", "day.fingerless_gloves", "day.utility_belt"}:
        return (
            generic_material,
            generic_environment,
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    acceptable=("late_night",),
                ),
                seasons=RatedContext(
                    good=("spring", "summer", "autumn", "winter"),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop"),
                    good=("conversation",),
                    acceptable=("relaxing",),
                    poor=("sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab"),
                    good=("office", "casual_public", "home"),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual",),
                    acceptable=("smart_casual",),
                    poor=("formal", "lounge"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.GOOD,
                    seated_comfort=Suitability.GOOD,
                    active_comfort=Suitability.GOOD,
                ),
            ),
            generic_comfort,
        )

    if item_id == "day.work_boots":
        return (
            MaterialProperties(
                stretch=TraitLevel.LOW,
                fabric_weight=FabricWeight.HEAVY,
                texture="matte_structured",
                breathability=TraitLevel.LOW,
                insulation=TraitLevel.MODERATE,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    -10.0, 3.0, 22.0, 31.0, FabricWeight.HEAVY
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.EXCELLENT,
                    drizzle=Suitability.EXCELLENT,
                    rain=Suitability.EXCELLENT,
                    heavy_rain=Suitability.GOOD,
                    snow=Suitability.GOOD,
                ),
                moisture=MoistureProfile(
                    quick_dry=False,
                    water_resistance=TraitLevel.HIGH,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.GOOD,
                    high=Suitability.POOR,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.HIGH,
                    strong_wind=Suitability.EXCELLENT,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.ACCEPTABLE,
                    uv_protection=TraitLevel.HIGH,
                ),
                indoor=Suitability.GOOD,
                outdoor=Suitability.EXCELLENT,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("morning", "afternoon", "evening"),
                    good=("night",),
                    poor=("late_night",),
                ),
                seasons=RatedContext(
                    excellent=("autumn", "winter"),
                    good=("spring",),
                    acceptable=("summer",),
                ),
                activities=RatedContext(
                    excellent=("engineering", "lab", "workshop", "outdoor"),
                    good=("conversation",),
                    poor=("relaxing", "sleep", "formal"),
                ),
                settings=RatedContext(
                    excellent=("workshop", "lab", "outdoor"),
                    good=("casual_public",),
                    acceptable=("home", "office"),
                ),
                formality=RatedContext(
                    excellent=("work",),
                    good=("casual",),
                    poor=("lounge", "formal"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.GOOD,
                    seated_comfort=Suitability.ACCEPTABLE,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.LOW,
                flexibility=TraitLevel.MODERATE,
                compression=TraitLevel.LOW,
                heat_retention=TraitLevel.MODERATE,
                ventilation=TraitLevel.LOW,
                skin_contact=Suitability.ACCEPTABLE,
            ),
        )

    if item_id == "night.lounge_tee":
        return (
            MaterialProperties(
                stretch=TraitLevel.MODERATE,
                fabric_weight=FabricWeight.LIGHT,
                texture="soft_brushed",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    10.0, 18.0, 28.0, 34.0, FabricWeight.LIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.GOOD,
                    drizzle=Suitability.ACCEPTABLE,
                    rain=Suitability.POOR,
                    heavy_rain=Suitability.UNSUITABLE,
                    snow=Suitability.UNSUITABLE,
                ),
                moisture=MoistureProfile(
                    quick_dry=False,
                    water_resistance=TraitLevel.LOW,
                    absorbency=TraitLevel.MODERATE,
                    wet_comfort=Suitability.POOR,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.GOOD,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.LOW,
                    strong_wind=Suitability.POOR,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.ACCEPTABLE,
                    uv_protection=TraitLevel.LOW,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.ACCEPTABLE,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("evening", "night", "late_night"),
                    acceptable=("morning", "afternoon"),
                ),
                seasons=RatedContext(
                    excellent=("spring", "summer"),
                    good=("autumn",),
                    acceptable=("winter",),
                ),
                activities=RatedContext(
                    excellent=("relaxing", "sleep", "gaming", "casual_home"),
                    good=("conversation",),
                    poor=("engineering", "lab", "workshop"),
                    unsuitable=("formal",),
                ),
                settings=RatedContext(
                    excellent=("home", "private"),
                    acceptable=("casual_public",),
                    poor=("office", "workshop", "lab", "outdoor"),
                    unsuitable=("formal_event",),
                ),
                formality=RatedContext(
                    excellent=("lounge", "casual"),
                    poor=("work", "smart_casual"),
                    unsuitable=("formal",),
                ),
                emotion_styles=RatedContext(
                    excellent=("relaxed", "cozy", "playful"),
                    good=("fond", "settled"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.EXCELLENT,
                    active_comfort=Suitability.GOOD,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.HIGH,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.NONE,
                heat_retention=TraitLevel.LOW,
                ventilation=TraitLevel.HIGH,
                skin_contact=Suitability.EXCELLENT,
            ),
        )

    if item_id == "night.running_shorts":
        return (
            MaterialProperties(
                stretch=TraitLevel.HIGH,
                fabric_weight=FabricWeight.LIGHT,
                texture="smooth_performance",
                breathability=TraitLevel.HIGH,
                insulation=TraitLevel.LOW,
            ),
            EnvironmentProfile(
                temperature=TemperatureProfile(
                    14.5, 20.0, 32.0, 38.0, FabricWeight.LIGHT
                ),
                precipitation=PrecipitationProfile(
                    dry=Suitability.EXCELLENT,
                    mist=Suitability.EXCELLENT,
                    drizzle=Suitability.GOOD,
                    rain=Suitability.ACCEPTABLE,
                    heavy_rain=Suitability.POOR,
                    snow=Suitability.UNSUITABLE,
                ),
                moisture=MoistureProfile(
                    quick_dry=True,
                    water_resistance=TraitLevel.LOW,
                    absorbency=TraitLevel.LOW,
                    wet_comfort=Suitability.GOOD,
                ),
                humidity=HumidityProfile(
                    low=Suitability.GOOD,
                    moderate=Suitability.EXCELLENT,
                    high=Suitability.EXCELLENT,
                ),
                wind=WindProfile(
                    resistance=TraitLevel.LOW,
                    strong_wind=Suitability.POOR,
                ),
                sunlight=SunlightProfile(
                    direct_sun=Suitability.GOOD,
                    uv_protection=TraitLevel.LOW,
                ),
                indoor=Suitability.EXCELLENT,
                outdoor=Suitability.GOOD,
            ),
            ContextProfile(
                dayparts=RatedContext(
                    excellent=("evening", "night", "late_night"),
                    acceptable=("morning", "afternoon"),
                ),
                seasons=RatedContext(
                    excellent=("spring", "summer"),
                    good=("autumn",),
                    poor=("winter",),
                ),
                activities=RatedContext(
                    excellent=("relaxing", "exercise", "gaming", "casual_home"),
                    good=("conversation", "sleep", "casual_outing"),
                    poor=("engineering", "lab", "workshop"),
                    unsuitable=("formal",),
                ),
                settings=RatedContext(
                    excellent=("home", "private"),
                    good=("casual_public", "outdoor"),
                    poor=("workshop", "lab", "office"),
                    unsuitable=("formal_event",),
                ),
                formality=RatedContext(
                    excellent=("lounge", "casual"),
                    poor=("work", "smart_casual"),
                    unsuitable=("formal",),
                ),
                emotion_styles=RatedContext(
                    excellent=("relaxed", "playful", "energetic", "cozy"),
                    good=("fond", "settled"),
                ),
                movement=MovementProfile(
                    mobility=Suitability.EXCELLENT,
                    seated_comfort=Suitability.EXCELLENT,
                    active_comfort=Suitability.EXCELLENT,
                ),
            ),
            ComfortProfile(
                softness=TraitLevel.HIGH,
                flexibility=TraitLevel.HIGH,
                compression=TraitLevel.MODERATE,
                heat_retention=TraitLevel.LOW,
                ventilation=TraitLevel.HIGH,
                skin_contact=Suitability.EXCELLENT,
            ),
        )

    return generic_material, generic_environment, generic_context, generic_comfort


def _blueprint(design: GarmentDesign, *, canonical: bool = False) -> GarmentBlueprint:
    material_properties, environment, context, comfort = _starter_profiles(
        design.item_id
    )
    design = replace(
        design,
        material_properties=material_properties,
        environment=environment,
        context=context,
        comfort=comfort,
    )
    definition = validate_design(design)
    garment = Garment(
        item_id=design.item_id,
        name=design.name,
        layer=definition.layer,
        slots=definition.slots,
        coverage=definition.coverage,
        tail_clearance=(
            definition.tail_clearance or "tail_clearance" in design.features
        ),
        ear_clearance=(
            definition.ear_clearance or "ear_clearance" in design.features
        ),
        asset_ref=None,
        private_only=design.private_only,
    )
    return GarmentBlueprint(
        garment=garment,
        design=design,
        provenance=(
            "canonical_clothing_design"
            if canonical
            else "design_proposal_review_required"
        ),
    )


def _no_graphic() -> GraphicDesign:
    return GraphicDesign()


def build_starter_wardrobe() -> WardrobePrebuild:
    """Build the intentionally small day/night starter closet."""
    blueprints = (
        _blueprint(
            GarmentDesign(
                "base.bralette", "Soft technical bralette", "bralette",
                "fitted", None, "cropped", None,
                "soft breathable stretch knit", "black", "dark_violet",
                "solid", _no_graphic(), ("soft_band",),
                ("base", "technical", "soft"), False,
                "A simple black technical bralette in soft breathable stretch "
                "knit with a dark-violet band. Clean seams and low-profile "
                "edges keep it comfortable beneath other layers."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "base.briefs", "Soft technical briefs", "briefs",
                "fitted", "mid", "brief", None,
                "soft breathable stretch knit", "black", "dark_violet",
                "solid", _no_graphic(), ("soft_band", "tail_clearance"),
                ("base", "technical", "soft"), False,
                "Fitted black technical briefs with a mid rise, soft "
                "dark-violet waistband, and a comfortable tailored opening "
                "that preserves unrestricted tail movement."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.technical_top", "Fitted technical long-sleeve top",
                "long_sleeve_tee", "fitted", None, "hip", "long",
                "breathable performance-knit", "black", "crimson",
                "panelled",
                GraphicDesign(True, "left_chest", "small_cyan_circuit_mark"),
                ("reinforced_seams", "stretch_panels"),
                ("day", "engineer", "technical", "fitted"), False,
                "A fitted black long-sleeve technical top cut to the hip in "
                "breathable performance knit. Crimson seam accents follow the "
                "shoulders and sides, while a small cyan circuit mark sits on "
                "the left chest. The silhouette is clean and mobile, with "
                "reinforced seams and subtle stretch panels."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.utility_trousers", "Articulated utility trousers",
                "utility_trousers", "fitted", "mid", "full", None,
                "stretch technical weave", "charcoal", "dark_violet",
                "panelled",
                _no_graphic(),
                ("articulated_knees", "utility_pockets", "tail_clearance"),
                ("day", "engineer", "technical", "utility"), False,
                "Fitted charcoal utility trousers with a mid rise and full "
                "length, built from a flexible technical weave. Dark-violet "
                "panel accents, articulated knees, practical low-profile "
                "pockets, and a dedicated tail opening keep the look "
                "functional without becoming bulky."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.engineer_jacket", "Asymmetric engineer jacket",
                "engineer_jacket", "tailored", None, "hip", "long",
                "matte abrasion-resistant technical shell", "black", "crimson",
                "asymmetric_panelled", _no_graphic(),
                ("asymmetric_zip", "reinforced_panels", "cyan_micro_accents", "tail_clearance"),
                ("day", "engineer", "technical", "outerwear"), False,
                "A tailored hip-length black engineer jacket with long sleeves "
                "and an asymmetric front zip. Crimson edge lines, small cyan "
                "hardware accents, and reinforced shoulder and forearm panels "
                "give it a practical cyber-engineering look. The rear hem is "
                "shaped around the tail opening."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.work_socks", "Technical crew socks", "crew_socks",
                "fitted", None, "crew", None,
                "moisture-wicking technical knit", "black", "crimson",
                "solid", _no_graphic(),
                ("reinforced_heel", "reinforced_toe"),
                ("day", "engineer", "technical"), False,
                "Black technical crew socks in moisture-wicking knit with "
                "subtle crimson trim and reinforced heel and toe zones."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.work_boots", "Mid-calf engineer boots", "work_boots",
                "fitted", None, "mid_calf", None,
                "matte technical leather and textile", "black", "dark_violet",
                "solid", _no_graphic(),
                ("grip_sole", "reinforced_toe", "side_zip"),
                ("day", "engineer", "technical", "footwear"), False,
                "Matte black mid-calf engineer boots with dark-violet paneling, "
                "a compact side zip, reinforced toe, and practical grip sole. "
                "The shape stays sleek rather than heavy."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.fingerless_gloves", "Technical fingerless gloves",
                "fingerless_gloves", "fitted", None, "wrist", None,
                "stretch technical textile", "black", "cyan",
                "panelled", _no_graphic(), ("grip_palms",),
                ("day", "engineer", "technical", "accessory"), False,
                "Close-fitting black fingerless technical gloves with small "
                "cyan panel accents and textured grip palms."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "day.utility_belt", "Low-profile utility belt", "belt",
                "fitted", None, "waist", None,
                "matte technical webbing", "black", "crimson",
                "solid", _no_graphic(),
                ("low_profile_buckle", "small_utility_pouch"),
                ("day", "engineer", "technical", "accessory"), False,
                "A slim black technical utility belt with a compact buckle, "
                "small practical pouch, and restrained crimson hardware detail."
            ),
            canonical=True,
        ),
        _blueprint(
            GarmentDesign(
                "night.lounge_tee", "Oversized late-night lounge T-shirt",
                "t_shirt", "oversized", None, "upper_thigh", "short",
                "soft brushed cotton-modal knit", "black", "dark_violet",
                "solid",
                GraphicDesign(True, "back_center", "violet_cyan_circuit_fox"),
                ("dropped_shoulders", "soft_hem"),
                ("night", "lounge", "soft", "cozy", "graphic"), False,
                "An oversized black late-night T-shirt in soft brushed "
                "cotton-modal knit, falling to the upper thigh with short "
                "sleeves and relaxed dropped shoulders. A dark-violet and cyan "
                "circuit-fox graphic sits across the upper back, while the "
                "front stays mostly clean."
            ),
        ),
        _blueprint(
            GarmentDesign(
                "night.running_shorts", "Fitted circuit running shorts",
                "running_shorts", "fitted", "mid", "short", None,
                "performance-knit", "dark_violet", "cyan", "none",
                GraphicDesign(True, "left_leg", "small_circuit_mark"),
                ("drawstring", "side_slits", "tail_clearance"),
                ("night", "lounge", "athletic", "soft"), False,
                "Fitted dark-violet running shorts with a mid rise and short "
                "athletic cut in soft performance knit. Cyan trim picks out the "
                "side seams, a small circuit mark sits on the left leg, and the "
                "design includes a drawstring, shallow side slits, and a "
                "comfortable tail opening."
            ),
        ),
    )

    wardrobe = Wardrobe(tuple(bp.garment for bp in blueprints))
    day_items = (
        "base.bralette", "base.briefs", "day.technical_top",
        "day.utility_trousers", "day.engineer_jacket", "day.work_socks",
        "day.work_boots", "day.fingerless_gloves", "day.utility_belt",
    )
    night_items = (
        "base.bralette", "base.briefs", "night.lounge_tee",
        "night.running_shorts",
    )
    fallback_items = (
        "base.bralette", "base.briefs", "day.technical_top",
        "day.utility_trousers",
    )
    presets = (
        OutfitPlan(
            DAY_DEFAULT_OUTFIT_ID,
            day_items,
            frozenset({Activity.CONVERSATION, Activity.ENGINEERING, Activity.LAB}),
            ALL_SEASONS,
            style_tags=("day", "engineer", "technical", "canonical"),
            display_name="Day Engineer Outfit",
        ),
        OutfitPlan(
            NIGHT_LOUNGE_OUTFIT_ID,
            night_items,
            frozenset({Activity.CONVERSATION, Activity.RELAXING, Activity.SLEEP}),
            ALL_SEASONS,
            lounge=True,
            style_tags=("night", "lounge", "soft", "cozy"),
            display_name="Late-Night Lounge Outfit",
        ),
        OutfitPlan(
            FALLBACK_OUTFIT_ID,
            fallback_items,
            frozenset(Activity),
            ALL_SEASONS,
            style_tags=("covered", "fallback", "technical"),
            display_name="Covered Fallback Outfit",
            manual_only=True,
        ),
    )
    inputs = (
        StyleInput(
            DAY_DEFAULT_OUTFIT_ID,
            RequestStatus.USER_REQUESTED,
            "chat.2026-10-04.request.day_default",
            "Sparks requested a rebuilt default daytime outfit using the new structured wardrobe layout.",
        ),
        StyleInput(
            NIGHT_LOUNGE_OUTFIT_ID,
            RequestStatus.USER_REQUESTED,
            "chat.2026-10-04.request.night_lounge",
            "Sparks requested a rebuilt late-night lounge outfit using the new structured wardrobe layout.",
        ),
    )
    return WardrobePrebuild(wardrobe, blueprints, presets, inputs)
