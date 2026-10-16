"""Exact, auditable production coverage for ALL canonical JSON wardrobe items.

This is a source/asset work queue, not a claim that final PNG assets exist.
Public export never exposes private item names, designs, or private artwork.
Protected work orders require a trusted, existing private presentation grant,
which this module does not mint.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from typing import Iterable

from .presentation import PrivatePresentationGrant
from .wardrobe_catalog import build_starter_wardrobe
from .vtuber_art_fidelity import brief_from_blueprint


GARMENT_FILES = (
    "accessories_ear.json",
    "accessories_hand_wrist.json",
    "accessories_legwear.json",
    "accessories_neck.json",
    "accessories_tail.json",
    "accessories_waist.json",
    "bottoms.json",
    "footwear.json",
    "intimate_underlayers.json",
    "one_pieces.json",
    "outerwear.json",
    "tops.json",
    "underlayers_lower.json",
    "underlayers_upper.json",
)

QUEUE_SCHEMA = "sofia.avatar2d.production_queue.v1"


@dataclass(frozen=True, slots=True)
class ArtProductionItem:
    item_id: str
    source_file: str
    source_sha256: str
    private_only: bool
    waist_up_visible: bool
    required_views: tuple[str, ...]
    # This is a statement about the state of production, not image content.
    status: str = "source_brief_ready_art_unverified"

    def public_entry(self) -> dict[str, object]:
        if self.private_only:
            raise PermissionError("private wardrobe work order is not public")
        return {
            "item_id": self.item_id,
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
            "waist_up_visible": self.waist_up_visible,
            "required_views": list(self.required_views),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ArtProductionCoverage:
    total: int
    public: int
    private: int
    waist_up_public: int
    waist_up_private: int
    by_source: tuple[tuple[str, int], ...]


def canonical_json_wardrobe_records() -> tuple[tuple[str, dict[str, object]], ...]:
    """Read all JSON garment records, fail on missing/duplicate/reclassified IDs."""
    source = files("sofia.avatar").joinpath("wardrobe_data")
    results: list[tuple[str, dict[str, object]]] = []
    seen: set[str] = set()
    for name in GARMENT_FILES:
        document = json.loads(source.joinpath(name).read_text(encoding="utf-8"))
        if document.get("schema") != "sofia.avatar.wardrobe.garments.v1":
            raise ValueError("unsupported canonical wardrobe record schema")
        items = document.get("garments")
        if not isinstance(items, list):
            raise ValueError("invalid garment source")
        for row in items:
            if not isinstance(row, dict):
                raise ValueError("invalid garment row")
            item_id = row.get("item_id")
            if not isinstance(item_id, str) or not item_id or item_id in seen:
                raise ValueError("missing or duplicate canonical garment ID")
            if type(row.get("private_only")) is not bool:
                raise ValueError("missing private classification")
            seen.add(item_id)
            results.append((name, row))
    return tuple(results)


def _views(record: dict[str, object]) -> tuple[str, ...]:
    """Required illustrated sides. Face/head rig is produced separately."""
    description = str(record.get("description", "")).casefold()
    graphic = record.get("graphic") or {}
    place = str(graphic.get("placement", "")).casefold() if isinstance(graphic, dict) else ""
    features = tuple(str(x) for x in record.get("features", ()))
    if (
        "back" in place
        or "rear" in description
        or "back" in description
        or any("tail_clearance" == x for x in features)
    ):
        return ("front", "back")
    return ("front",)


def wardrobe_production_queue(
    *,
    catalog=None,
) -> tuple[ArtProductionItem, ...]:
    """Every JSON-defined item exactly once, including protected entries."""
    if catalog is None:
        catalog = build_starter_wardrobe()
    blueprints = {bp.garment.item_id: bp for bp in catalog.blueprints}
    records = canonical_json_wardrobe_records()
    output = []
    for source_file, row in records:
        item_id = row["item_id"]
        bp = blueprints.get(item_id)
        if bp is None:
            raise ValueError("source item absent from authoritative catalog")
        if bool(row["private_only"]) != bp.garment.private_only:
            raise ValueError("source privacy and canonical wardrobe differ")
        # Full source fingerprint, including all private design fields, is
        # calculated in memory; public export hides private entry metadata.
        brief = brief_from_blueprint(bp, allow_private=True)
        output.append(ArtProductionItem(
            item_id=item_id,
            source_file=source_file,
            source_sha256=brief.source_sha256,
            private_only=bp.garment.private_only,
            waist_up_visible=bool(brief.fields["waist_up_visible"]),
            required_views=_views(row),
        ))
    return tuple(output)


def wardrobe_production_coverage(
    queue: Iterable[ArtProductionItem],
) -> ArtProductionCoverage:
    records = tuple(queue)
    source_count: dict[str, int] = {key: 0 for key in GARMENT_FILES}
    for item in records:
        source_count[item.source_file] += 1
    return ArtProductionCoverage(
        total=len(records),
        public=sum(not item.private_only for item in records),
        private=sum(item.private_only for item in records),
        waist_up_public=sum(
            item.waist_up_visible and not item.private_only for item in records
        ),
        waist_up_private=sum(
            item.waist_up_visible and item.private_only for item in records
        ),
        by_source=tuple((file, count) for file, count in source_count.items()),
    )


def export_public_production_queue(path: Path) -> ArtProductionCoverage:
    """Export public work orders and only aggregate counts for protected work."""
    if not isinstance(path, Path) or path.is_symlink() or path.exists():
        raise ValueError("public production queue output must be a new file")
    queue = wardrobe_production_queue()
    coverage = wardrobe_production_coverage(queue)
    payload = {
        "schema": QUEUE_SCHEMA,
        "source": "canonical sofia.avatar.wardrobe_data JSON",
        "coverage": {
            "total": coverage.total,
            "public": coverage.public,
            "private": coverage.private,
            "waist_up_public": coverage.waist_up_public,
            "waist_up_private": coverage.waist_up_private,
        },
        "public_items": [item.public_entry() for item in queue if not item.private_only],
        "private_work_orders": {
            "count": coverage.private,
            "status": "restricted_separate_authorization_required",
        },
        "completion_state": "source_coverage_only_no_final_sprite_claims",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return coverage


def protected_work_orders(
    *,
    grant: PrivatePresentationGrant | None,
    catalog=None,
) -> tuple[ArtProductionItem, ...]:
    """Return private metadata only after host-provided grant is validated.

    Caller MUST separately enforce exact authenticated owner session/STOP,
    private workspace ACL, no public logs/notifications, and grant expiry.
    """
    if not isinstance(grant, PrivatePresentationGrant):
        raise PermissionError("trusted private owner grant required")
    grant.require()
    return tuple(
        item for item in wardrobe_production_queue(catalog=catalog)
        if item.private_only
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Audit exact 2D wardrobe source coverage")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    coverage = export_public_production_queue(args.output)
    print(
        "Wardrobe work orders: "
        f"{coverage.total} total, {coverage.public} public, "
        f"{coverage.private} protected. No final sprites were asserted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
