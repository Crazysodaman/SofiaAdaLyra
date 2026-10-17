"""Validate staged Batch12/13 mouth art and construct honest review-only frames.

Never discovers private source packages automatically. Never writes Public-V2
or changes wardrobe, database, or the live Tk renderer. Mouth viseme states
are not voice receipts: all rendered frames here are offline artwork proofs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import json

from .vtuber_independent_features import _ASSETS as _FEATURE_ASSETS

MOUTH_STATES = ("neutral", "small_smile", "smile", "smirk", "frown", "open_small")
VISEME_STATES = ("open_medium", "open_wide", "A", "E", "O", "M")
_SCHEMA = "sofia.avatar2d.mouth_viseme_source_review.v1"
_ART_FILES = {
    f"layers/{group}/{state}.png"
    for group, states in (("mouths", MOUTH_STATES), ("visemes", VISEME_STATES))
}
_EXTRAS = {
    "README.txt", "Install-Batch12_13.ps1",
    "Check-Batch12_13.cmd", "Stage-Batch12_13.cmd",
    "Verify-Batch12_13.cmd", "Preview-Batch12_13.cmd",
    "Rollback-Batch12_13.cmd",
    "Preview_Mouths_Visemes_And_Expressions.png",
    "Preview_Frame_Swaps_Review_Only.gif",
    "Preview_320x400_Source_Scale.png",
}
_EXPECTED = _ART_FILES | _EXTRAS
_MASTER = (2048, 2560)
_EXAMPLE_STATES = (
    ("neutral", "mouths", "neutral", "open_center", "open_center", "soft"),
    ("smile", "mouths", "smile", "open_center", "open_center", "soft"),
    ("smirk", "mouths", "smirk", "open_center", "open_center", "skeptical"),
    ("frown", "mouths", "frown", "open_center", "open_center", "concerned"),
    ("open", "mouths", "open_small", "open_center", "open_center", "soft"),
    ("A", "visemes", "A", "open_center", "open_center", "soft"),
    ("E", "visemes", "E", "open_center", "open_center", "soft"),
    ("O", "visemes", "O", "open_center", "open_center", "soft"),
    ("M", "visemes", "M", "open_center", "open_center", "soft"),
    ("blink", "mouths", "neutral", "closed", "closed", "soft"),
    ("left_wink", "mouths", "smile", "closed", "open_center", "soft"),
    ("right_wink", "mouths", "smile", "open_center", "closed", "soft"),
)


def _root(path: Path) -> None:
    if not isinstance(path, Path) or not path.is_absolute() or not path.is_dir():
        raise ValueError("explicit existing absolute review directory required")
    if "private-source" not in {item.casefold() for item in path.parts}:
        raise ValueError("staged review must remain under Private-Source")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("linked review directory forbidden")


def _file(root: Path, relative: str) -> Path:
    if (
        relative not in _EXPECTED
        and relative not in ("manifest.json", "head_base.png", "face_shading.png")
        and relative not in _FEATURE_ASSETS
    ):
        raise ValueError("unrecognized candidate file")
    file = root
    for part in relative.split("/"):
        file = file / part
        if file.is_symlink():
            raise ValueError(f"linked file forbidden: {relative}")
    if not file.is_file():
        raise ValueError(f"missing candidate file: {relative}")
    return file


def verify_review_mouths(
    root: Path, *, foundation_root: Path, features_root: Path,
) -> dict:
    """Check exact assets, RGBA coordinates and pinned previous batches."""
    from PIL import Image

    for candidate in (root, foundation_root, features_root):
        _root(candidate)
    manifest_file = _file(root, "manifest.json")
    if manifest_file.stat().st_size > 65536:
        raise ValueError("oversized mouth manifest")
    try:
        doc = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid mouth manifest") from exc
    if (
        not isinstance(doc, dict) or doc.get("schema") != _SCHEMA
        or doc.get("private_source_only") is not True
        or doc.get("production_activated") is not False
        or doc.get("master_canvas") != list(_MASTER)
        or doc.get("mouth_anchor") != [1008, 317]
        or doc.get("review_status") != "visual_corrections_await_owner"
    ):
        raise ValueError("unsafe mouth review manifest")
    pins = (
        ("head_base_sha256", _file(foundation_root, "head_base.png")),
        ("face_shading_sha256", _file(foundation_root, "face_shading.png")),
        ("features_manifest_sha256", _file(features_root, "manifest.json")),
    )
    for name, path in pins:
        if doc.get(name) != sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"stage dependency changed: {name}")

    files = doc.get("files")
    if not isinstance(files, list) or len(files) != len(_EXPECTED):
        raise ValueError("incorrect file inventory")
    seen_files: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("malformed file entry")
        name = entry.get("file")
        digest = entry.get("sha256")
        length = entry.get("bytes")
        if (
            name not in _EXPECTED or name in seen_files
            or type(length) is not int or length < 1 or length > 12_000_000
            or not isinstance(digest, str) or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError("unsafe file inventory entry")
        file = _file(root, name)
        if file.stat().st_size != length or sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError(f"file hash mismatch: {name}")
        seen_files.add(name)
    if seen_files != _EXPECTED:
        raise ValueError("incomplete file inventory")

    sprites = doc.get("sprites")
    if not isinstance(sprites, list) or len(sprites) != 12:
        raise ValueError("expected 12 explicit mouth/viseme states")
    seen_sprites: set[str] = set()
    for entry in sprites:
        if not isinstance(entry, dict) or entry.get("file") not in _ART_FILES:
            raise ValueError("unexpected sprite entry")
        relative = entry["file"]
        if relative in seen_sprites:
            raise ValueError("duplicate mouth or viseme state")
        seen_sprites.add(relative)
        expected_role = "mouth" if relative.startswith("layers/mouths/") else "viseme"
        if entry.get("role") != expected_role or entry.get("state") != Path(relative).stem:
            raise ValueError("sprite role/state mismatch")
        with Image.open(_file(root, relative)) as image:
            if image.format != "PNG" or image.mode != "RGBA" or image.size != _MASTER:
                raise ValueError(f"sprite wrong canvas: {relative}")
            image.load()
            bbox = image.getchannel("A").getbbox()
        if bbox is None or tuple(entry.get("alpha_bbox") or ()) != bbox:
            raise ValueError(f"incorrect visible sprite bounds: {relative}")
        if not (945 <= bbox[0] and bbox[2] <= 1075 and 280 <= bbox[1] and bbox[3] <= 355):
            raise ValueError(f"mouth art outside face slot: {relative}")
    if seen_sprites != _ART_FILES:
        raise ValueError("missing mouth sprite state")
    if doc.get("source_flaws") != {
        "viseme_A": "original PNG depicts hair",
        "viseme_O": "original PNG depicts hair",
        "viseme_M": "original PNG depicts incorrectly open mouth",
    }:
        raise ValueError("original source repair provenance missing")
    return {
        "verified_files": len(files),
        "mouth_states": len(MOUTH_STATES),
        "viseme_states": len(VISEME_STATES),
        "dependencies_match": True,
        "production_activated": False,
        "voice_lip_sync_implemented": False,
    }


def compose_review_frame(
    *, foundation_root: Path, features_root: Path, mouths_root: Path,
    expression: str,
):
    """Return one full-canvas PIL frame from EXACT approved state identifiers.

    This only reads known staged file paths. Cannot be used to authorize
    private art in a public renderer, or to claim audio-driven lip sync.
    """
    from PIL import Image

    selected = [item for item in _EXAMPLE_STATES if item[0] == expression]
    if len(selected) != 1:
        raise ValueError("unsupported expression")
    _, family, mouth, left_eye, right_eye, brow = selected[0]
    frame = Image.new("RGBA", _MASTER)
    files = (
        (foundation_root, "head_base.png"),
        (foundation_root, "face_shading.png"),
        (features_root, f"layers/eyes/eye_left/{left_eye}.png"),
        (features_root, f"layers/eyes/eye_right/{right_eye}.png"),
        (features_root, f"layers/brows/brow_left/{brow}.png"),
        (features_root, f"layers/brows/brow_right/{brow}.png"),
        (mouths_root, f"layers/{family}/{mouth}.png"),
    )
    for folder, relative in files:
        with Image.open(_file(folder, relative)) as image:
            if image.mode != "RGBA" or image.size != _MASTER:
                raise ValueError(f"incorrect animation layer dimensions: {relative}")
            frame.alpha_composite(image)
    return frame


def create_review_frames(
    *, foundation_root: Path, features_root: Path,
    mouths_root: Path, output: Path,
) -> tuple[str, ...]:
    """Offline, reproducible PNG proof of independent frame changes."""
    verify_review_mouths(
        mouths_root, foundation_root=foundation_root,
        features_root=features_root,
    )
    from .vtuber_independent_features import verify_independent_features
    verify_independent_features(
        features_root, foundation_root=foundation_root,
    )
    if not isinstance(output, Path) or not output.is_absolute() or output.exists():
        raise ValueError("review output must be a new absolute path")
    if any(part.casefold().startswith("public") for part in output.parts):
        raise ValueError("cannot write source-review frames into public folders")
    if "private-source" not in {part.casefold() for part in output.parts}:
        raise ValueError("review output must stay under Private-Source")
    if any(part.is_symlink() for part in (output, *output.parents)):
        raise ValueError("linked output directory forbidden")
    if any(folder == output or folder in output.parents for folder in (
        foundation_root, features_root, mouths_root,
    )):
        raise ValueError("must not write review frames inside staged source art")
    output.mkdir(parents=True)
    produced = []
    for expression, *_ in _EXAMPLE_STATES:
        image = compose_review_frame(
            foundation_root=foundation_root,
            features_root=features_root,
            mouths_root=mouths_root, expression=expression,
        )
        filename = f"{len(produced):02d}_{expression}.png"
        image.save(output / filename, optimize=True)
        produced.append(filename)
    (output / "README.txt").write_text(
        "Offline preview only. No renderer activation or real speech receipt.\n",
        encoding="utf-8",
    )
    return tuple(produced)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit or generate private review-only 2D mouth/eye animation frames"
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--foundation-root", required=True, type=Path)
    parser.add_argument("--features-root", required=True, type=Path)
    parser.add_argument("--frames-output", type=Path)
    args = parser.parse_args(argv)
    result = verify_review_mouths(
        args.root,
        foundation_root=args.foundation_root,
        features_root=args.features_root,
    )
    if args.frames_output:
        files = create_review_frames(
            foundation_root=args.foundation_root,
            features_root=args.features_root,
            mouths_root=args.root,
            output=args.frames_output,
        )
        result["review_frames_created"] = len(files)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
