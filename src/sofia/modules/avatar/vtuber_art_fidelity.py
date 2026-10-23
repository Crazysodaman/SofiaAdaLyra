"""Source-locked art briefs for Sofía's canonical wardrobe.

A generated picture is never inherently a verified 2D sprite. This module
preserves the FULL reviewed design and its SHA-256 fingerprint so prompts,
candidates and human review all refer to the identical wardrobe item.

All ordinary public designs can be exported for authoring. Protected/private
designs require a separately authorized workspace; the public command
intentionally excludes them and will not reveal them in an index.

This module does not generate images or grant identity/private permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from .wardrobe import normalize_slots
from .wardrobe_catalog import build_starter_wardrobe
from .wardrobe_prebuild import GarmentBlueprint, WardrobePrebuild
from .wardrobe_design import resolve_color
from .vtuber_layer_stack import WAIST_UP_SLOTS


_SCHEMA = "sofia.avatar2d.art_brief.v1"
_REVIEW_SCHEMA = "sofia.avatar2d.art_review.v1"


def _canonical_bytes(value: dict[str, object]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class WardrobeArtBrief:
    item_id: str
    source_sha256: str
    fields: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "item_id": self.item_id,
            "source_sha256": self.source_sha256,
            "source": self.fields.copy(),
            "status": "art_spec_only_not_render_verified",
        }


def brief_from_blueprint(
    blueprint: GarmentBlueprint,
    *,
    allow_private: bool = False,
) -> WardrobeArtBrief:
    """Preserve every design-shaping field rather than a shortened summary."""
    if not isinstance(blueprint, GarmentBlueprint):
        raise TypeError("canonical validated wardrobe blueprint required")
    design = blueprint.design
    if design.private_only and not allow_private:
        raise PermissionError("restricted wardrobe brief requires a protected workflow")
    leaf_slots = normalize_slots(blueprint.garment.slots)
    visible = tuple(slot for slot in leaf_slots if slot in WAIST_UP_SLOTS)
    fields: dict[str, object] = {
        "name": design.name,
        "garment_type": design.garment_type,
        "fit": design.fit,
        "rise": design.rise,
        "length": design.length,
        "sleeve_length": design.sleeve_length,
        "material": design.material,
        "primary_name": design.primary,
        "primary_hex": resolve_color(design.primary),
        "accent_name": design.accent,
        "accent_hex": (
            resolve_color(design.accent) if design.accent is not None else None
        ),
        "pattern": design.pattern,
        "graphic": {
            "enabled": design.graphic.enabled,
            "placement": design.graphic.placement,
            "design": design.graphic.design,
        },
        "features": list(design.features),
        "style_tags": list(design.style_tags),
        "description": design.description,
        "wardrobe_layer": blueprint.garment.layer.name,
        "wardrobe_slots": list(leaf_slots),
        "waist_up_slots": list(visible),
        "waist_up_visible": bool(visible),
        "coverage": list(normalize_slots(blueprint.garment.coverage)),
        "ear_clearance": blueprint.garment.ear_clearance,
        "tail_clearance": blueprint.garment.tail_clearance,
        "private_only": design.private_only,
        "content_rating": design.content_rating.value,
        "exposure": [zone.value for zone in design.exposure],
    }
    fingerprint = sha256(_canonical_bytes({
        "item_id": design.item_id,
        "source": fields,
    })).hexdigest()
    return WardrobeArtBrief(design.item_id, fingerprint, fields)


def public_art_briefs(catalog: WardrobePrebuild) -> tuple[WardrobeArtBrief, ...]:
    """Every public item, including off-screen bottoms/shoes, without guessing art."""
    if not isinstance(catalog, WardrobePrebuild):
        raise TypeError("canonical WardrobePrebuild required")
    result = tuple(
        sorted(
            (
                brief_from_blueprint(item)
                for item in catalog.blueprints if not item.design.private_only
            ),
            key=lambda item: item.item_id,
        )
    )
    if len(result) != len({item.item_id for item in result}):
        raise ValueError("duplicate art brief ID")
    return result


def authoring_instructions(brief: WardrobeArtBrief) -> str:
    """Exact positive details and explicit unknowns, not imagined additions."""
    f = brief.fields
    if f["private_only"]:
        raise PermissionError("private briefs cannot enter public art prompts")
    graphic = f["graphic"]
    graphic_phrase = (
        f"Artwork: {graphic['design']}, placed at {graphic['placement']}."
        if graphic["enabled"]
        else "Do not invent a printed graphic unless the description explicitly requires it."
    )
    viewport = (
        "Author exact aligned transparent front/back waist-up sprite layers."
        if f["waist_up_visible"]
        else "Off-camera in the waist-up view; produce a review concept only "
             "unless full-body artwork is separately commissioned."
    )
    return "\n".join((
        f"Canonical item: {brief.item_id} ({f['name']})",
        f"Exact description: {f['description']}",
        f"Type: {f['garment_type']}; fit: {f['fit']}; length: {f['length']}; "
        f"rise: {f['rise']}; sleeve length: {f['sleeve_length']}",
        f"Material: {f['material']}; pattern: {f['pattern']}",
        f"Base: {f['primary_name']} {f['primary_hex']}; "
        f"accent: {f['accent_name']} {f['accent_hex']}",
        f"Construction/features: {', '.join(f['features']) or 'none specified'}",
        graphic_phrase,
        f"Existing wardrobe layer: {f['wardrobe_layer']}; "
        f"actual visible slots: {', '.join(f['waist_up_slots']) or 'none'}",
        viewport,
        "Do not crop a specified hip-length or thigh-length hem merely to "
        "make a prettier sprite. Do not move a specified back graphic to "
        "the front. Do not invent a logo, extra seam, cleavage, sleeve, or "
        "clothing opening that contradicts the design.",
        "Maintain one common canvas, pose, neck/shoulder anchors, and alpha. "
        "A concept is NOT an accepted renderable sprite.",
        f"Binding: {brief.source_sha256}",
    ))


def verify_art_review(
    brief: WardrobeArtBrief, record: dict[str, object],
    *,
    sprite_sha256: str,
) -> bool:
    """Strict metadata comparison; NEVER a visual/owner-authentication oracle.

    A reviewer still must inspect the image, full-body silhouette and match.
    This function ensures a recorded check relates to the current SOURCE
    design and exact sprite bytes. It does NOT assert reviewer identity.
    """
    if (
        not isinstance(brief, WardrobeArtBrief)
        or not isinstance(record, dict)
        or record.get("schema") != _REVIEW_SCHEMA
        or record.get("item_id") != brief.item_id
        or record.get("source_sha256") != brief.source_sha256
        or record.get("sprite_sha256") != sprite_sha256
        or not isinstance(sprite_sha256, str)
        or len(sprite_sha256) != 64
        or any(ch not in "0123456789abcdef" for ch in sprite_sha256)
        or record.get("visual_review_status") != "accepted"
    ):
        return False
    checks = record.get("manual_checks")
    if not isinstance(checks, dict):
        return False
    mandatory = (
        "fit", "hem_length", "sleeve_length", "material",
        "primary_color", "accent_color", "pattern", "graphic_placement",
        "construction_features", "sprite_alignment", "alpha_background",
    )
    return all(checks.get(name) is True for name in mandatory)


def export_public_art_briefs(
    destination: Path,
    *,
    catalog: WardrobePrebuild | None = None,
) -> dict[str, int]:
    """Export without touching canonical DB, overwriting designs, or private art."""
    if not isinstance(destination, Path):
        raise TypeError("output directory must be Path")
    if destination.is_symlink():
        raise ValueError("symlinked art brief root is disallowed")
    if catalog is None:
        catalog = build_starter_wardrobe()
    specs = public_art_briefs(catalog)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("nonempty art-brief directory cannot be overwritten")
    destination.mkdir(parents=True, exist_ok=True)
    public_index = []
    for brief in specs:
        doc = brief.as_dict()
        target = destination / (brief.item_id + ".json")
        if target.exists() or target.is_symlink():
            raise FileExistsError("art brief already exists")
        target.write_bytes(
            json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
        )
        public_index.append({
            "item_id": brief.item_id,
            "source_sha256": brief.source_sha256,
            "waist_up_visible": bool(brief.fields["waist_up_visible"]),
            "file": target.name,
        })
    (destination / "index.json").write_text(
        json.dumps({
            "schema": "sofia.avatar2d.art_brief_index.v1",
            "public_item_count": len(specs),
            "items": public_index,
        }, indent=2),
        encoding="utf-8",
    )
    return {
        "total": len(specs),
        "waist_up_visible": sum(bool(b.fields["waist_up_visible"]) for b in specs),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Export exact reviewed public wardrobe art briefs")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--item", type=str, default=None)
    args = parser.parse_args(argv)
    catalog = build_starter_wardrobe()
    if args.item:
        bp = next(
            (b for b in catalog.blueprints if b.garment.item_id == args.item),
            None,
        )
        if bp is None:
            raise ValueError("unknown wardrobe item")
        print(authoring_instructions(brief_from_blueprint(bp)))
        return 0
    print(export_public_art_briefs(args.output, catalog=catalog))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
