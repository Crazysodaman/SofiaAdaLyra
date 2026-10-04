"""Durable pending state for generated garments awaiting Sparks input."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .wardrobe import WardrobeError
from .wardrobe_generated_store import (
    GeneratedWardrobeStore,
    SofiaGarmentAcceptance,
    SofiaGarmentDecision,
)
from .wardrobe_prebuild import GarmentBlueprint


PENDING_GENERATED_WARDROBE_FILENAME = "wardrobe-pending.generated.json"


def pending_generated_wardrobe_path(state_path: str | Path) -> Path:
    return Path(state_path).parent / PENDING_GENERATED_WARDROBE_FILENAME


@dataclass(frozen=True, slots=True)
class PendingGeneratedGarment:
    blueprint: GarmentBlueprint
    reason: str
    decided_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.blueprint, GarmentBlueprint):
            raise TypeError("blueprint must be GarmentBlueprint")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise WardrobeError("pending generated garment requires a reason")
        if (
            not isinstance(self.decided_at, datetime)
            or self.decided_at.tzinfo is None
            or self.decided_at.utcoffset() is None
        ):
            raise WardrobeError(
                "pending generated garment time must be timezone-aware"
            )


class PendingGeneratedWardrobeStore:
    """Persist ASK_SPARKS proposals without adding them to owned wardrobe."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = pending_generated_wardrobe_path(state_path)

    def save(
        self,
        blueprint: GarmentBlueprint,
        acceptance: SofiaGarmentAcceptance,
    ) -> PendingGeneratedGarment:
        if not isinstance(blueprint, GarmentBlueprint):
            raise TypeError("blueprint must be GarmentBlueprint")
        if not isinstance(acceptance, SofiaGarmentAcceptance):
            raise TypeError("acceptance must be SofiaGarmentAcceptance")
        if acceptance.decision is not SofiaGarmentDecision.ASK_SPARKS:
            raise WardrobeError(
                "only ASK_SPARKS decisions belong in pending wardrobe state"
            )

        existing = self.load()
        if (
            existing is not None
            and existing.blueprint.garment.item_id
            != blueprint.garment.item_id
        ):
            raise WardrobeError(
                "another generated garment is already awaiting Sparks input"
            )

        profile_id = GeneratedWardrobeStore._profile_id(blueprint)
        row = GeneratedWardrobeStore._row(
            blueprint,
            acceptance,
            profile_id,
        )
        row["provenance"] = "design_proposal_review_required"
        payload = {
            "schema": "sofia.avatar.wardrobe.garments.v1",
            "category": "generated_pending",
            "profiles": {
                profile_id: GeneratedWardrobeStore._profile(blueprint),
            },
            "garments": [row],
            "pending": {
                "reason": acceptance.reason,
                "decided_at": acceptance.decided_at.astimezone(
                    timezone.utc
                ).isoformat(),
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise WardrobeError(
                "pending generated wardrobe could not be persisted"
            ) from exc
        return PendingGeneratedGarment(
            blueprint,
            acceptance.reason,
            acceptance.decided_at,
        )

    def load(self) -> PendingGeneratedGarment | None:
        if not self.path.is_file():
            return None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WardrobeError(
                "pending generated wardrobe is unreadable"
            ) from exc
        if (
            not isinstance(raw, dict)
            or raw.get("category") != "generated_pending"
            or not isinstance(raw.get("pending"), dict)
        ):
            raise WardrobeError(
                "pending generated wardrobe has invalid schema"
            )
        pending = raw["pending"]
        reason = pending.get("reason")
        decided_at_raw = pending.get("decided_at")
        if (
            not isinstance(reason, str)
            or not reason.strip()
            or not isinstance(decided_at_raw, str)
        ):
            raise WardrobeError(
                "pending generated wardrobe metadata is invalid"
            )
        try:
            decided_at = datetime.fromisoformat(decided_at_raw)
        except ValueError as exc:
            raise WardrobeError(
                "pending generated wardrobe timestamp is invalid"
            ) from exc
        if decided_at.tzinfo is None or decided_at.utcoffset() is None:
            raise WardrobeError(
                "pending generated wardrobe timestamp must be timezone-aware"
            )

        from .wardrobe_catalog import _blueprint
        from .wardrobe_loader import _load_wardrobe_data_file

        blueprints = _load_wardrobe_data_file(
            self.path,
            _blueprint,
        )
        if len(blueprints) != 1:
            raise WardrobeError(
                "pending generated wardrobe must contain exactly one garment"
            )
        return PendingGeneratedGarment(
            blueprints[0],
            reason.strip(),
            decided_at,
        )

    def clear(self, *, item_id: str | None = None) -> bool:
        pending = self.load()
        if pending is None:
            return False
        if (
            item_id is not None
            and pending.blueprint.garment.item_id != item_id
        ):
            return False
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise WardrobeError(
                "pending generated wardrobe could not be cleared"
            ) from exc
        return True
