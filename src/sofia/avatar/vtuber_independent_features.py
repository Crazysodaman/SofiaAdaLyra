"""Strict verification for staged independent 2D eye and brow review artwork.

The reviewed Batch10/11 set contains 10 LEFT/RIGHT eye state pairs and six
LEFT/RIGHT eyebrow state pairs at the canonical 2048 x 2560 source canvas.
It is not a 320 x 400 public renderer bundle and cannot grant activation.

No user-controlled paths from its manifest are used without exact allowlists.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

EYE_STATES = (
    "open_center", "open_left", "open_right", "open_up", "open_down",
    "half_lidded", "closed", "happy_closed", "wink_left", "wink_right",
)
BROW_STATES = ("neutral", "soft", "happy", "skeptical", "concerned", "angry")
_CANVAS = (2048, 2560)
_SCHEMA = "sofia.avatar2d.independent_eyes_brows.review.v1"
_ASSETS = {
    f"layers/eyes/eye_{side}/{state}.png": (f"eye_{side}", state)
    for side in ("left", "right") for state in EYE_STATES
} | {
    f"layers/brows/brow_{side}/{state}.png": (f"brow_{side}", state)
    for side in ("left", "right") for state in BROW_STATES
}


def _file(root: Path, relative: str) -> Path:
    # Callers must use fixed, known paths, never a dynamic manifest path.
    file = root
    for component in relative.split("/"):
        file = file / component
        if file.is_symlink():
            raise ValueError(f"linked art is forbidden: {relative}")
    if not file.is_file():
        raise ValueError(f"missing reviewed art: {relative}")
    return file


def _check_root(root: Path) -> None:
    if not isinstance(root, Path) or not root.is_absolute() or not root.is_dir():
        raise ValueError("absolute, existing candidate root required")
    if "private-source" not in {part.casefold() for part in root.parts}:
        raise ValueError("candidate must be kept under Private-Source")
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError("candidate cannot use linked directories")


def verify_independent_features(root: Path, *, foundation_root: Path) -> dict:
    """Recheck file bytes, variant matrices, geometry and source-head binding."""
    _check_root(root)
    _check_root(foundation_root)
    manifest_path = _file(root, "manifest.json")
    if manifest_path.stat().st_size > 500_000:
        raise ValueError("oversized review manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid review manifest") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != _SCHEMA
        or manifest.get("private_source_only") is not True
        or manifest.get("production_activated") is not False
        or manifest.get("master_canvas") != list(_CANVAS)
        or manifest.get("left_right_split_x") != 1024
        or manifest.get("owner_approved_resting_brow") != "soft"
    ):
        raise ValueError("unsupported or unsafe features manifest")
    for field, name in (
        ("head_base_sha256", "head_base.png"),
        ("face_shading_sha256", "face_shading.png"),
    ):
        supplied = manifest.get(field)
        if not isinstance(supplied, str) or supplied != sha256(
            _file(foundation_root, name).read_bytes()
        ).hexdigest():
            raise ValueError(f"staged Batch09 {name} does not match")
    assets = manifest.get("sprites")
    if not isinstance(assets, list) or len(assets) != len(_ASSETS):
        raise ValueError("incomplete independent feature matrix")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("invalid file hash inventory")
    files_index = {}
    fixed_misc = {
        "README.txt", "Install-Batch10_11.ps1",
        "Preview_Eyes_Brows_Independent_v1.png",
        "Check-Batch10_11.cmd", "Stage-Batch10_11.cmd",
        "Verify-Batch10_11.cmd", "Rollback-Batch10_11.cmd",
        "Preview-Batch10_11.cmd",
    }
    expected_files = set(_ASSETS) | fixed_misc
    if len(files) != len(expected_files):
        raise ValueError("incomplete hash inventory")
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("invalid hash inventory entry")
        rel, digest, size = entry.get("file"), entry.get("sha256"), entry.get("bytes")
        if (
            rel not in expected_files or rel in files_index
            or not isinstance(digest, str) or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
            or type(size) is not int or size <= 0 or size > 12_000_000
        ):
            raise ValueError("unsafe file hash entry")
        data = _file(root, rel).read_bytes()
        if len(data) != size or sha256(data).hexdigest() != digest:
            raise ValueError(f"reviewed file SHA256 mismatch: {rel}")
        files_index[rel] = digest
    if set(files_index) != expected_files:
        raise ValueError("unexpected file inventory")

    from PIL import Image
    seen = set()
    for item in assets:
        if not isinstance(item, dict):
            raise ValueError("invalid sprite entry")
        rel = item.get("file")
        if rel not in _ASSETS or rel in seen:
            raise ValueError("unknown or duplicate sprite state")
        seen.add(rel)
        role, state = _ASSETS[rel]
        if item.get("role") != role or item.get("state") != state:
            raise ValueError("sprite role/state does not match file name")
        with Image.open(_file(root, rel)) as image:
            if image.format != "PNG" or image.mode != "RGBA" or image.size != _CANVAS:
                raise ValueError(f"invalid independent RGBA canvas: {rel}")
            box = image.getchannel("A").getbbox()
        if box is None or item.get("alpha_bbox") != list(box):
            raise ValueError(f"invalid sprite alpha bounds: {rel}")
        if (role.endswith("_left") and box[2] > 1024) or (
            role.endswith("_right") and box[0] < 1024
        ):
            raise ValueError(f"eye/brow crosses side boundary: {rel}")
    if seen != set(_ASSETS):
        raise ValueError("missing independent sprite states")
    return {
        "validated_sprites": len(seen),
        "independent_eyes": 20,
        "independent_brows": 12,
        "batch09_matched": True,
        "production_activated": False,
        "renderer_ready": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify staged independent source eye and brow sprites"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--foundation-root", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify_independent_features(
        args.root, foundation_root=args.foundation_root,
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
