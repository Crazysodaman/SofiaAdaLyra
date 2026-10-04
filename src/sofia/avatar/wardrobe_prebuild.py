"""Validated wardrobe prebuild metadata and creator handoff."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from .fit import DEFAULT_FIT_ANCHORS
from .wardrobe import Garment, Wardrobe, WardrobeError
from .wardrobe_design import ContentRating, ExposureZone, GarmentDesign, resolve_color, validate_design
from sofia.avatar.wardrobe_types import garment_type
from .wardrobe_planner import OutfitPlan, Preference, PreferenceActor, PreferenceTarget, Sentiment

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


DRAFT_STATUS = "proposed_no_mesh_no_verified_asset"


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
        bra_types = {
            "bralette", "wireless_bra", "sports_bra", "longline_bralette",
            "triangle_bralette", "plunge_bra", "bandeau", "open_cup_bra",
        }
        panty_types = {
            "briefs", "hipster", "boyshort", "bikini_brief",
            "cheeky_brief", "thong", "athletic_brief",
            "open_crotch_briefs",
        }
        if self.design.garment_type in bra_types:
            return "closet.bra"
        if self.design.garment_type in panty_types:
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
    def content_rating(self) -> ContentRating:
        return self.design.content_rating

    @property
    def exposure(self) -> tuple[ExposureZone, ...]:
        return self.design.exposure

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
            "content_rating": self.design.content_rating.value,
            "exposure": tuple(zone.value for zone in self.design.exposure),
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
                    "content_rating": bp.content_rating.value,
                    "exposure": [zone.value for zone in bp.exposure],
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
