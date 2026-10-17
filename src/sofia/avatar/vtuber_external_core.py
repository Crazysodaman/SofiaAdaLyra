"""Audit owner-installed 2D character artwork before renderer import.

The eight approved source-art ZIPs are NOT the public 320x400 character
manifest. This module is a deliberate staging boundary. It reads only known
art paths, checks actual image properties, and can write a PRIVATE review
sheet. It does not mount raw Private-Source art in Tk, change canonical
state, or activate an unreviewed public pack.

Usage on Venus:
  python -m sofia.avatar.vtuber_external_core --source-root PATH --check
  python -m sofia.avatar.vtuber_external_core --source-root PATH --stage PATH
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

_CANVAS = (2048, 2560)
_RENDER_CANVAS = (320, 400)
_MAX_BYTES = 12 * 1024 * 1024

_FILES: dict[str, tuple[str, ...]] = {
    "face": ("face_base.png", "face_shading.png"),
    "eyes": (
        "eyes_open_center.png", "eyes_open_left.png", "eyes_open_right.png",
        "eyes_open_up.png", "eyes_open_down.png", "eyes_half_lidded.png",
        "eyes_closed.png", "eyes_happy_closed.png", "eyes_wink_left.png",
        "eyes_wink_right.png",
    ),
    "brows": tuple(f"brows_{name}.png" for name in (
        "neutral", "soft", "happy", "skeptical", "concerned", "angry",
    )),
    "mouth": tuple(f"mouth_{name}.png" for name in (
        "neutral", "small_smile", "smile", "smirk", "frown", "open_small",
    )),
    "mouth_visemes": tuple(f"mouth_{name}.png" for name in (
        "open_medium", "open_wide", "viseme_A", "viseme_E", "viseme_O",
        "viseme_M",
    )),
    "hair": (
        "hair_back_main.png", "hair_front_bangs.png",
        "hair_front_left_strand.png", "hair_front_right_strand.png",
        "hair_high_ponytail.png", "hair_low_ponytail.png",
        "hair_side_braid.png", "hair_single_long_braid.png",
        "hair_twin_braids.png", "hair_messy_bun.png",
    ),
    "ears": tuple(f"ear_pose_{i:02d}.png" for i in range(1, 11)),
    "tail": tuple(f"tail_pose_{i:02d}.png" for i in range(1, 8)),
}
assert sum(map(len, _FILES.values())) == 57


@dataclass(frozen=True)
class InstalledSprite:
    group: str
    filename: str
    width: int | None
    height: int | None
    alpha_bbox: tuple[int, int, int, int] | None
    sha256: str | None
    problems: tuple[str, ...]


@dataclass(frozen=True)
class CoreAudit:
    sprites: tuple[InstalledSprite, ...]
    missing: int
    invalid: int
    needs_alignment: int
    ready_for_public_renderer: bool
    notes: tuple[str, ...]


def _safe_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("source root must be an absolute path")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("source root missing or is a symlink")
    if root.name.casefold() == "public-v2":
        raise ValueError("expected source-art root, not public runtime artwork")
    return root


def _safe_file(root: Path, group: str, filename: str) -> Path:
    layers = root / "layers"
    directory = layers / group
    target = directory / filename
    if any(part.is_symlink() for part in (layers, directory, target)):
        raise ValueError("symlink in source artwork path")
    return target


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required for installed-art inspection") from exc
    return Image, ImageDraw, ImageOps


def audit_installed_core(source_root: Path) -> CoreAudit:
    """Read only 57 predictable files; no paths or code from image manifests."""
    root = _safe_root(source_root)
    Image, _, _ = _pil()
    rows: list[InstalledSprite] = []
    missing = invalid = needs_alignment = 0
    bounding: dict[str, tuple[int, int, int, int]] = {}
    for group, filenames in _FILES.items():
        for filename in filenames:
            path = _safe_file(root, group, filename)
            problems: list[str] = []
            dimensions = bbox = digest = None
            if not path.is_file():
                problems.append("missing")
                missing += 1
            else:
                try:
                    size = path.stat().st_size
                    if size == 0 or size > _MAX_BYTES:
                        raise ValueError("empty or oversized image")
                    data = path.read_bytes()
                    digest = sha256(data).hexdigest()
                    from io import BytesIO
                    with Image.open(BytesIO(data)) as image:
                        if image.format != "PNG" or image.mode != "RGBA":
                            raise ValueError("expected RGBA PNG")
                        image.load()
                        dimensions = image.size
                        bbox = image.getchannel("A").getbbox()
                        if bbox is None:
                            raise ValueError("completely transparent sprite")
                        if image.getchannel("A").getextrema()[0] == 255:
                            raise ValueError("sprite has opaque background")
                    if dimensions != _CANVAS:
                        problems.append("requires explicit canvas/anchor registration")
                        needs_alignment += 1
                    else:
                        bounding[f"{group}/{filename}"] = bbox
                except (OSError, ValueError, SyntaxError) as exc:
                    problems.append(f"invalid PNG: {exc}")
                    invalid += 1
            rows.append(InstalledSprite(
                group, filename,
                dimensions[0] if dimensions else None,
                dimensions[1] if dimensions else None,
                bbox, digest, tuple(problems),
            ))
    face = bounding.get("face/face_base.png")
    eyebrow = bounding.get("brows/brows_neutral.png")
    notes = [
        "Private-Source is not a verified public character manifest.",
        "No private body, underwear or garment is exported by this check.",
        "An artist must approve visual overlap, separate L/R masks and tail roots before activation.",
    ]
    if face and eyebrow and eyebrow[1] > face[3]:
        notes.append("Eyebrow sprite is below the face bounding box; requires re-registration.")
        needs_alignment += 1
    return CoreAudit(
        sprites=tuple(rows), missing=missing, invalid=invalid,
        needs_alignment=needs_alignment,
        ready_for_public_renderer=False, notes=tuple(notes),
    )


def stage_review(source_root: Path, output_root: Path) -> CoreAudit:
    """Write non-production contact sheet, never guess pose/attachment anchors."""
    audit = audit_installed_core(source_root)
    if not isinstance(output_root, Path) or not output_root.is_absolute():
        raise ValueError("review output must be an absolute path")
    if output_root.exists() or any(part.is_symlink() for part in output_root.parents):
        raise ValueError("review output already exists or has symlink ancestors")
    if any(part.casefold().startswith("public") for part in output_root.parts):
        raise ValueError("cannot stage unreviewed Private-Source art in public folders")
    if "private-source" not in {part.casefold() for part in output_root.parts}:
        raise ValueError("review files must be kept under Private-Source")
    if output_root == source_root or source_root in output_root.parents:
        raise ValueError("review output must be separate from approved source")
    Image, ImageDraw, ImageOps = _pil()
    tile_w, tile_h, cols = 270, 345, 4
    rows = (len(audit.sprites) + cols - 1) // cols
    board = Image.new("RGB", (cols * tile_w, rows * tile_h), (28, 27, 35))
    draw = ImageDraw.Draw(board)
    for index, entry in enumerate(audit.sprites):
        x, y = (index % cols) * tile_w, (index // cols) * tile_h
        draw.rectangle((x+5, y+5, x+tile_w-5, y+tile_h-5), fill=(50,49,60))
        draw.text((x+12, y+12), f"{entry.group}/{entry.filename}", fill=(250,245,255))
        if entry.sha256 is not None and not any(p.startswith("invalid") for p in entry.problems):
            path = _safe_file(source_root, entry.group, entry.filename)
            with Image.open(path) as image:
                # Thumbnail crop for review ONLY. It is not a rig transform.
                crop = image.crop(entry.alpha_bbox)
                thumb = ImageOps.contain(crop, (tile_w-30, tile_h-85))
                board.paste(thumb, (x+(tile_w-thumb.width)//2, y+40), thumb)
        if entry.problems:
            draw.text((x+12, y+tile_h-27), "; ".join(entry.problems)[:37], fill=(255,180,165))
    output_root.mkdir(parents=True, exist_ok=False)
    board.save(output_root / "review_contact_sheet.png", format="PNG")
    (output_root / "core_inventory.json").write_text(
        json.dumps({
            "schema": "sofia.avatar2d.external_core_review.v1",
            "source_kind": "private_source_review_only",
            "production_activated": False,
            "canvas_expected": list(_CANVAS),
            "runtime_canvas": list(_RENDER_CANVAS),
            "audit": {
                "missing": audit.missing,
                "invalid": audit.invalid,
                "needs_alignment": audit.needs_alignment,
                "ready_for_public_renderer": False,
                "notes": list(audit.notes),
            },
            "sprites": [asdict(row) for row in audit.sprites],
        }, indent=2), encoding="utf-8",
    )
    return audit


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit installed Sofía 2D art without enabling private sprites"
    )
    parser.add_argument("--source-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--stage", type=Path, metavar="NEW_PRIVATE_REVIEW_DIR")
    args = parser.parse_args(argv)
    audit = (
        audit_installed_core(args.source_root) if args.check
        else stage_review(args.source_root, args.stage)
    )
    missing_files = [
        f"{sprite.group}/{sprite.filename}"
        for sprite in audit.sprites if "missing" in sprite.problems
    ]
    invalid_files = [
        f"{sprite.group}/{sprite.filename}"
        for sprite in audit.sprites
        if any(problem.startswith("invalid PNG") for problem in sprite.problems)
    ]
    print(json.dumps({
        "expected": len(audit.sprites), "missing": audit.missing,
        "invalid": audit.invalid, "needs_alignment": audit.needs_alignment,
        "production_activated": False,
        "missing_files": missing_files,
        "invalid_files": invalid_files,
        "group_status": {
            group: {
                "expected": len(names),
                "missing": sum(
                    1 for sprite in audit.sprites
                    if sprite.group == group and "missing" in sprite.problems
                ),
            } for group, names in _FILES.items()
        },
        "notes": list(audit.notes),
    }, indent=2))
    return 1 if audit.missing or audit.invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
