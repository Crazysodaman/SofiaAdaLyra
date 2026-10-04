"""Durable ownership gate for generated wardrobe pieces."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path

from .wardrobe import WardrobeError
from .wardrobe_prebuild import GarmentBlueprint


GENERATED_WARDROBE_FILENAME = "wardrobe-owned.generated.json"


def generated_wardrobe_path(state_path: str | Path) -> Path:
    return Path(state_path).parent / GENERATED_WARDROBE_FILENAME


class SofiaGarmentDecision(str, Enum):
    ACCEPT = "accept"
    ASK_SPARKS = "ask_sparks"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class SofiaGarmentAcceptance:
    decision: SofiaGarmentDecision
    reason: str
    decided_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not isinstance(self.decision, SofiaGarmentDecision):
            raise WardrobeError("garment decision must be typed")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise WardrobeError("garment decision requires Sofía's reason")
        if (
            not isinstance(self.decided_at, datetime)
            or self.decided_at.tzinfo is None
            or self.decided_at.utcoffset() is None
        ):
            raise WardrobeError("garment decision time must be timezone-aware")

    @property
    def requires_persistence(self) -> bool:
        return self.decision is SofiaGarmentDecision.ACCEPT


@dataclass(frozen=True, slots=True)
class GarmentAcceptanceResult:
    decision: SofiaGarmentDecision
    persisted: bool
    ask_sparks: bool
    reason: str
    path: Path | None = None

    @classmethod
    def from_acceptance(
        cls,
        acceptance: SofiaGarmentAcceptance,
        *,
        persisted: bool = False,
        path: Path | None = None,
    ) -> "GarmentAcceptanceResult":
        return cls(
            acceptance.decision,
            persisted,
            acceptance.decision is SofiaGarmentDecision.ASK_SPARKS,
            acceptance.reason,
            path,
        )


class GeneratedWardrobeStore:
    """ACCEPT persists; ASK_SPARKS and REJECT never mutate the closet."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = generated_wardrobe_path(state_path)

    @staticmethod
    def _profile_id(blueprint: GarmentBlueprint) -> str:
        return "generated." + blueprint.design.item_id

    @staticmethod
    def _profile(blueprint: GarmentBlueprint) -> dict[str, object]:
        design = blueprint.design
        return {
            "material_properties": design.material_properties.as_dict(),
            "environment": design.environment.as_dict(),
            "context": design.context.as_dict(),
            "comfort": design.comfort.as_dict(),
        }

    @staticmethod
    def _row(
        blueprint: GarmentBlueprint,
        acceptance: SofiaGarmentAcceptance,
        profile_id: str,
    ) -> dict[str, object]:
        design = blueprint.design
        return {
            "item_id": design.item_id,
            "name": design.name,
            "garment_type": design.garment_type,
            "fit": design.fit,
            "rise": design.rise,
            "length": design.length,
            "sleeve_length": design.sleeve_length,
            "material": design.material,
            "primary": design.primary,
            "accent": design.accent,
            "pattern": design.pattern,
            "graphic": {
                "enabled": design.graphic.enabled,
                "placement": design.graphic.placement,
                "design": design.graphic.design,
            },
            "features": list(design.features),
            "style_tags": list(design.style_tags),
            "private_only": design.private_only,
            "content_rating": design.content_rating.value,
            "exposure": [zone.value for zone in design.exposure],
            "profile": profile_id,
            "canonical": False,
            "provenance": "sofia_accepted_generated_design",
            "acceptance": {
                "actor": "sofia",
                "decision": acceptance.decision.value,
                "reason": acceptance.reason,
                "decided_at": acceptance.decided_at.astimezone(
                    timezone.utc
                ).isoformat(),
            },
            "description": design.description,
        }

    def _read(self) -> dict[str, object]:
        if not self.path.is_file():
            return {
                "schema": "sofia.avatar.wardrobe.garments.v1",
                "category": "generated_owned",
                "profiles": {},
                "garments": [],
            }
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WardrobeError("generated wardrobe store is unreadable") from exc
        if (
            not isinstance(raw, dict)
            or raw.get("schema") != "sofia.avatar.wardrobe.garments.v1"
            or not isinstance(raw.get("profiles"), dict)
            or not isinstance(raw.get("garments"), list)
        ):
            raise WardrobeError("generated wardrobe store has invalid schema")
        return raw

    def _write(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    payload, indent=2, sort_keys=True, ensure_ascii=False
                ) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise WardrobeError(
                "generated wardrobe store could not be persisted"
            ) from exc

    def apply(
        self,
        blueprint: GarmentBlueprint,
        acceptance: SofiaGarmentAcceptance,
    ) -> GarmentAcceptanceResult:
        if not isinstance(blueprint, GarmentBlueprint):
            raise TypeError("blueprint must be GarmentBlueprint")
        if not isinstance(acceptance, SofiaGarmentAcceptance):
            raise TypeError("acceptance must be SofiaGarmentAcceptance")
        if acceptance.decision is not SofiaGarmentDecision.ACCEPT:
            return GarmentAcceptanceResult.from_acceptance(acceptance)

        payload = self._read()
        garments = payload["garments"]
        profiles = payload["profiles"]
        assert isinstance(garments, list)
        assert isinstance(profiles, dict)
        if any(
            isinstance(row, dict)
            and row.get("item_id") == blueprint.garment.item_id
            for row in garments
        ):
            raise WardrobeError("generated garment ID is already owned")

        profile_id = self._profile_id(blueprint)
        if profile_id in profiles:
            raise WardrobeError("generated garment profile already exists")
        profiles[profile_id] = self._profile(blueprint)
        garments.append(self._row(blueprint, acceptance, profile_id))
        self._write(payload)
        return GarmentAcceptanceResult.from_acceptance(
            acceptance, persisted=True, path=self.path
        )
