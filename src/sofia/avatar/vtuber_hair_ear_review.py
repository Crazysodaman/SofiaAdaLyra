"""Registered hair and fox-ear composition for PRIVATE visual review only.

Owner-approved source hair/ear PNGs are much wider than Sofía's head. This
module verifies their exact hashes, places them on the canonical 2048x2560
master and emits a review image. It does NOT convert or publish source art
into the covered public Tk renderer; no rig pose is approved by this image.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .vtuber_mouth_viseme_review import verify_review_mouths, compose_review_frame
from .vtuber_independent_features import verify_independent_features

_MASTER = (2048, 2560)
# Registered cropped content boxes: x, y, max_width, max_height
_CANDIDATE_BOXES = {
    "hair_back_main.png": (800, 0, 440, 610),
    "hair_front_bangs.png": (900, 14, 218, 258),
    "ear_pose_01.png": (827, 0, 123, 170),
    "ear_pose_06.png": (1070, 0, 123, 170),
}
_APPROVED_SHA = {
    "hair_back_main.png": "48ff998d86b9f01d39b04f17da3ed7554a351c18d2843316d0154896a37a766e",
    "hair_front_bangs.png": "4ebc44984537b328be533a8676b94baeecaca5ffe7d974f418a3cb7ae5f0b0fe",
    "ear_pose_01.png": "7a33ccbc3b17058b4673f39fd5c4f415bfe5cfaa90e25867976d520a357b45c2",
    "ear_pose_06.png": "d89753201eeaded21c4368632b5b1ee619067d34575301dacf1d0fef125c883b",
}
_CROP = (710, 0, 1334, 620)


def candidate_boxes() -> dict[str, tuple[int, int, int, int]]:
    return dict(_CANDIDATE_BOXES)


def _private_path(path: Path) -> None:
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("explicit absolute PRIVATE source path required")
    if "private-source" not in {part.casefold() for part in path.parts}:
        raise ValueError("all art must stay under Private-Source")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("linked source path forbidden")


def _load(path: Path, *, name: str | None = None):
    from PIL import Image
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 12_000_000:
        raise ValueError("unavailable or unsafe artwork path")
    if name is not None and sha256(path.read_bytes()).hexdigest() != _APPROVED_SHA[name]:
        raise ValueError(f"original approved art hash mismatch: {name}")
    with Image.open(path) as file:
        if file.format != "PNG" or file.mode != "RGBA":
            raise ValueError("expected RGBA PNG")
        file.load()
        return file.copy()


def _registered(source, bounds: tuple[int, int, int, int]):
    from PIL import Image, ImageOps
    x, y, width, height = bounds
    if not (0 <= x < _MASTER[0] and 0 <= y < _MASTER[1]
            and 0 < width <= _MASTER[0] - x and 0 < height <= _MASTER[1] - y):
        raise ValueError("candidate anchor outside canvas")
    alpha = source.getchannel("A").point(lambda level: 255 if level > 4 else 0)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("empty approved art")
    cropped = source.crop(bbox)
    sized = ImageOps.contain(cropped, (width, height), Image.Resampling.LANCZOS)
    registered = Image.new("RGBA", _MASTER)
    registered.alpha_composite(sized, (
        x + (width - sized.width) // 2,
        y + (height - sized.height) // 2,
    ))
    return registered


def create_hair_ear_review(
    *, source_root: Path, foundation_root: Path, features_root: Path,
    mouths_root: Path, canonical_body: Path, output: Path,
) -> dict:
    from PIL import Image, ImageOps, ImageDraw
    for path in (source_root, foundation_root, features_root, mouths_root, canonical_body, output):
        _private_path(path)
    if output.exists():
        raise ValueError("output directory already exists; refuse overwrite")
    if any(root == output or root in output.parents for root in (
        source_root, foundation_root, features_root, mouths_root,
    )):
        raise ValueError("review output cannot modify installed artwork")
    for directory in (source_root, foundation_root, features_root, mouths_root):
        if not directory.is_dir():
            raise ValueError("staged review directory missing")
    from .vtuber_batch09_foundation import verify_head_foundation
    verify_head_foundation(foundation_root, canonical_body=canonical_body)
    verify_independent_features(features_root, foundation_root=foundation_root)
    verify_review_mouths(
        mouths_root, foundation_root=foundation_root,
        features_root=features_root,
    )

    parts = {
        "hair_back_main.png": source_root / "layers" / "hair" / "hair_back_main.png",
        "hair_front_bangs.png": source_root / "layers" / "hair" / "hair_front_bangs.png",
        "ear_pose_01.png": source_root / "layers" / "ears" / "ear_pose_01.png",
        "ear_pose_06.png": source_root / "layers" / "ears" / "ear_pose_06.png",
    }
    registered = {}
    for name, file in parts.items():
        if file.parent.is_symlink():
            raise ValueError("linked art directory forbidden")
        registered[name] = _registered(
            _load(file, name=name), _CANDIDATE_BOXES[name],
        )
    with Image.open(canonical_body) as original:
        if original.mode != "RGBA" or original.size != _MASTER:
            raise ValueError("canonical body master dimensions mismatch")
        body = original.copy()
    face = compose_review_frame(
        foundation_root=foundation_root,
        features_root=features_root,
        mouths_root=mouths_root,
        expression="neutral",
    )
    panels = []
    names = (
        "Back hair + canonical body",
        "Plus two fox ears (review)",
        "Plus front bangs (review)",
    )
    for i, label in enumerate(names):
        img = Image.new("RGBA", _MASTER)
        img.alpha_composite(registered["hair_back_main.png"])
        img.alpha_composite(body)
        if i >= 1:
            img.alpha_composite(registered["ear_pose_01.png"])
            img.alpha_composite(registered["ear_pose_06.png"])
        img.alpha_composite(face)
        if i == 2:
            img.alpha_composite(registered["hair_front_bangs.png"])
        portrait = ImageOps.contain(
            img.crop(_CROP), (480, 520), Image.Resampling.LANCZOS,
        )
        panel = Image.new("RGBA", (500, 600), (34, 31, 45, 255))
        panel.alpha_composite(portrait, ((500-portrait.width)//2, 5))
        ImageDraw.Draw(panel).text((20, 548), label, fill=(242, 233, 255))
        panels.append(panel)
    sheet = Image.new("RGB", (1500, 600), (34, 31, 45))
    for i, panel in enumerate(panels):
        sheet.paste(panel.convert("RGB"), (i*500, 0))
    output.mkdir(parents=True)
    sheet.save(output / "hair_ear_alignment_candidate.png", optimize=True)
    report = {
        "schema": "sofia.avatar2d.hair_ear_registration_review.v1",
        "production_activated": False,
        "owner_approved_geometry": False,
        "master_canvas": list(_MASTER),
        "candidate_boxes": {key:list(value) for key,value in _CANDIDATE_BOXES.items()},
        "pinned_original_sha256": dict(_APPROVED_SHA),
        "notes": [
            "Approved hair/ear source color and silhouette do not imply approved attachment positions.",
            "Ear left/right labels are provisional; source poses need explicit directional review.",
            "Tail root, hair variants and garment occlusion are not verified here.",
            "No HUMAN ears are drawn in this registration.",
        ],
    }
    (output / "alignment_candidate.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build private head/hair/fox-ear fit comparison")
    for option in ("source_root", "foundation_root", "features_root", "mouths_root", "canonical_body", "output"):
        parser.add_argument("--" + option.replace("_", "-"), required=True, type=Path)
    args = parser.parse_args(argv)
    result = create_hair_ear_review(**vars(args))
    print(json.dumps({
        "status": "review_only",
        "production_activated": result["production_activated"],
        "result": str(args.output / "hair_ear_alignment_candidate.png"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
