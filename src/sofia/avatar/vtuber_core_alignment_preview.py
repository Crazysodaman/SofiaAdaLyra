"""Review-only geometry registration for owner-approved high-resolution 2D art.

This is deliberately NOT a public runtime loader. It composes only a cropped
head preview and a tail contact sheet from the validated Private-Source art.
No files or state under Public-V2, wardrobe, or the canonical database change.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .vtuber_external_core import audit_installed_core, _safe_file, _pil

MASTER_SIZE = (2048, 2560)
HEAD_CROP = (750, 0, 1310, 510)
# Preliminary 2048x2560 registration boxes, not approved animation anchors.
REGISTRATION = {
    "hair_back": ("hair", "hair_back_main.png", (786, 0, 1223, 548)),
    "ear_left": ("ears", "ear_pose_01.png", (837, 0, 952, 170)),
    "ear_right": ("ears", "ear_pose_06.png", (1072, 0, 1187, 170)),
    # Approved soft variant makes a more neutral preview than the
    # dramatically inward-slanted "brows_neutral" source illustration.
    # This is not a production expression-state mapping.
    "brows": ("brows", "brows_soft.png", (943, 183, 1104, 205)),
    "hair_front": ("hair", "hair_front_bangs.png", (898, 12, 1119, 252)),
}


def _load(source_root: Path, group: str, filename: str):
    Image, _, _ = _pil()
    file = _safe_file(source_root, group, filename)
    with Image.open(file) as source:
        return source.convert("RGBA")


def _fit(source, box, *, alpha_threshold: int = 0):
    Image, _, ImageOps = _pil()
    if type(alpha_threshold) is not int or not 0 <= alpha_threshold < 256:
        raise ValueError("invalid alpha crop threshold")
    mask = source.getchannel("A")
    # Generated brow images contain very faint far-field alpha specks.
    # Their unfiltered bounding box made the previous brows tiny and steep.
    if alpha_threshold:
        mask = mask.point(lambda v: 255 if v > alpha_threshold else 0)
    content = mask.getbbox()
    if content is None:
        raise ValueError("cannot register an empty layer")
    cropped = source.crop(content)
    x1, y1, x2, y2 = box
    if not (0 <= x1 < x2 <= MASTER_SIZE[0] and
            0 <= y1 < y2 <= MASTER_SIZE[1]):
        raise ValueError("layer registration outside master canvas")
    fitted = ImageOps.contain(
        cropped, (x2 - x1, y2 - y1), Image.Resampling.LANCZOS
    )
    result = Image.new("RGBA", MASTER_SIZE)
    result.alpha_composite(fitted, (
        x1 + ((x2 - x1) - fitted.width) // 2,
        y1 + ((y2 - y1) - fitted.height) // 2,
    ))
    return result


def _private_review_target(target: Path, source_root: Path) -> None:
    if not target.is_absolute() or target.exists():
        raise ValueError("review output must be a new absolute directory")
    if source_root in target.parents or target == source_root:
        raise ValueError("review output cannot modify approved source art")
    if "private-source" not in {p.casefold() for p in target.parts}:
        raise ValueError("review output must stay under Private-Source")
    if any("public" in p.casefold() for p in target.parts):
        raise ValueError("review output cannot be public")
    if any(path.is_symlink() for path in (target, *target.parents)):
        raise ValueError("review path cannot contain symlinks")


def make_candidate(
    source_root: Path, canonical_body: Path, output_dir: Path,
) -> dict:
    """Generate registration proof, without activating or exporting a rig."""
    audit = audit_installed_core(source_root)
    if audit.missing or audit.invalid:
        raise ValueError("source-art audit must have no missing or invalid PNGs")
    _private_review_target(output_dir, source_root)
    if canonical_body.is_symlink() or not canonical_body.is_file():
        raise ValueError("explicit canonical body PNG missing or linked")
    Image, ImageDraw, ImageOps = _pil()
    with Image.open(canonical_body) as original:
        if original.format != "PNG" or original.mode != "RGBA" or original.size != MASTER_SIZE:
            raise ValueError("canonical body must be 2048x2560 RGBA PNG")
        body = original.copy()

    canvas = Image.new("RGBA", MASTER_SIZE)
    transforms = {}
    for group_name in ("hair_back", "ear_left", "ear_right"):
        group, filename, box = REGISTRATION[group_name]
        canvas.alpha_composite(_fit(_load(source_root, group, filename), box))
        transforms[group_name] = {"source": f"{group}/{filename}", "box": list(box)}
    canvas.alpha_composite(body)
    for group, filename in (
        ("face", "face_base.png"),
        ("face", "face_shading.png"),
        ("eyes", "eyes_open_center.png"),
    ):
        canvas.alpha_composite(_load(source_root, group, filename))
    for group_name in ("brows",):
        group, filename, box = REGISTRATION[group_name]
        canvas.alpha_composite(_fit(
            _load(source_root, group, filename), box,
            alpha_threshold=15,
        ))
        transforms[group_name] = {
            "source": f"{group}/{filename}", "box": list(box),
            "alpha_crop_threshold": 15,
            "selection": "soft review expression, not runtime neutral",
        }
    canvas.alpha_composite(_load(source_root, "mouth", "mouth_neutral.png"))
    group, filename, box = REGISTRATION["hair_front"]
    canvas.alpha_composite(_fit(_load(source_root, group, filename), box))
    transforms["hair_front"] = {"source": f"{group}/{filename}", "box": list(box)}

    head = canvas.crop(HEAD_CROP)
    # Tail previews contain no body art. Root placement remains unapproved.
    cols, cell_w, cell_h = 4, 265, 330
    tails = Image.new("RGB", (cols * cell_w, 2 * cell_h), (31, 29, 41))
    draw = ImageDraw.Draw(tails)
    for index in range(7):
        name = f"tail_pose_{index+1:02d}.png"
        artwork = _load(source_root, "tail", name)
        alpha_box = artwork.getchannel("A").getbbox()
        if alpha_box is None:
            raise ValueError("empty tail sprite")
        thumb = ImageOps.contain(
            artwork.crop(alpha_box), (cell_w - 24, cell_h - 54),
            Image.Resampling.LANCZOS,
        )
        x, y = (index % cols) * cell_w, (index // cols) * cell_h
        # RGBA -> RGB with alpha masking, without hiding geometry.
        tails.paste(thumb, (x + (cell_w-thumb.width)//2, y+14), thumb)
        draw.text((x+10, y+cell_h-28), name, fill=(242, 233, 251))

    report = {
        "schema": "sofia.avatar2d.core_alignment_candidate.v1",
        "status": "review_only_not_production_activated",
        "source_pngs_audited": len(audit.sprites),
        "missing": audit.missing,
        "invalid": audit.invalid,
        "unresolved_source_alignment_warnings": audit.needs_alignment,
        "body_sha256": sha256(canonical_body.read_bytes()).hexdigest(),
        "canvas": list(MASTER_SIZE),
        "head_crop": list(HEAD_CROP),
        "candidate_transforms": transforms,
        "notes": [
            "Ear L/R mapping is provisional, not independent artwork authorization.",
            "Brows are resized and repositioned for visual review only.",
            "Tail root, hair styles, visemes, and garment occlusion require calibration.",
            "Preview uses approved brows_soft art, not a runtime neutral-expression mapping.",
            "Brows crop excludes near-invisible alpha fringe before fitting; original PNG is unchanged.",
            "Do not use review PNGs as verified public sprites or enable private content.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    head.save(output_dir / "head_alignment_candidate.png")
    tails.save(output_dir / "tail_pose_contact_sheet.png")
    (output_dir / "alignment_candidate.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8",
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a head-only PRIVATE 2D alignment candidate"
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--canonical-body", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = make_candidate(args.source_root, args.canonical_body, args.output)
    print(json.dumps({
        "status": report["status"],
        "missing": report["missing"],
        "invalid": report["invalid"],
        "output": str(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
