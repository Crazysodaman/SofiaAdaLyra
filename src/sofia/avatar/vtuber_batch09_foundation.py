"""Verify the owner-staged Batch09 v3 modular head foundation, never render it.

The 2048x2560 RGBA art and editable OpenRaster master remain under
Private-Source. This gate does not copy them to Public-V2, modify sofia.db,
approve an animation rig, or grant private presentation.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from zipfile import ZipFile

_SCHEMA = "sofia.avatar2d.head_foundation.canonical_matched.v3"
_EXPECTED = frozenset({
    "head_base.png", "face_shading.png", "Preview_Batch09_HeadFit.png",
    "Sofia_Batch09_Editable_Layers.ora", "Install-Batch09.ps1",
    "README.txt", "Check-Batch09.cmd", "Stage-Batch09.cmd",
    "Verify-Batch09.cmd", "Rollback-Batch09.cmd", "Preview-Batch09.cmd",
})
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _checked_file(root: Path, name: str) -> bytes:
    if name not in _EXPECTED and name != "manifest.json":
        raise ValueError("unrecognized candidate file")
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or symlinked candidate file: {name}")
    if path.stat().st_size > 12 * 1024 * 1024:
        raise ValueError(f"oversized candidate file: {name}")
    return path.read_bytes()


def verify_head_foundation(root: Path, *, canonical_body: Path) -> dict:
    if not isinstance(root, Path) or not root.is_absolute() or not root.is_dir():
        raise ValueError("absolute existing candidate directory required")
    if "private-source" not in {part.casefold() for part in root.parts}:
        raise ValueError("candidate must remain under Private-Source")
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError("candidate path cannot include symlinks")
    if not isinstance(canonical_body, Path) or not canonical_body.is_file():
        raise ValueError("explicit canonical body source required")
    if canonical_body.is_symlink():
        raise ValueError("linked canonical body forbidden")

    try:
        document = json.loads(_checked_file(root, "manifest.json"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("unreadable Batch09 manifest") from exc
    if (
        not isinstance(document, dict)
        or document.get("schema") != _SCHEMA
        or document.get("private_source_only") is not True
        or document.get("production_activated") is not False
        or document.get("layer_dimensions") != [2048, 2560]
    ):
        raise ValueError("unsafe or incompatible Batch09 manifest")
    if sha256(canonical_body.read_bytes()).hexdigest() != document.get("canonical_body_sha256"):
        raise ValueError("canonical body SHA256 mismatch")
    rows = document.get("files")
    if not isinstance(rows, list) or len(rows) != len(_EXPECTED):
        raise ValueError("incomplete candidate file inventory")
    seen: set[str] = set()
    for entry in rows:
        if not isinstance(entry, dict):
            raise ValueError("invalid candidate entry")
        name, expected_hash, length = entry.get("file"), entry.get("sha256"), entry.get("bytes")
        if (
            name not in _EXPECTED or name in seen or not isinstance(expected_hash, str)
            or not _HEX.fullmatch(expected_hash) or type(length) is not int
        ):
            raise ValueError("unsafe candidate entry")
        seen.add(name)
        data = _checked_file(root, name)
        if len(data) != length or sha256(data).hexdigest() != expected_hash:
            raise ValueError(f"candidate file mismatch: {name}")
    if seen != _EXPECTED:
        raise ValueError("wrong candidate inventory")

    try:
        from PIL import Image
        for name in ("head_base.png", "face_shading.png"):
            with Image.open(root / name) as image:
                if image.format != "PNG" or image.mode != "RGBA" or image.size != (2048, 2560):
                    raise ValueError(f"incorrect RGBA canvas: {name}")
                image.load()
                alpha = image.getchannel("A")
                bbox = alpha.getbbox()
                if bbox is None or bbox[0] < 750 or bbox[1] > 185 or bbox[2] > 1300 or bbox[3] > 500:
                    raise ValueError(f"head layer escapes approved registration: {name}")
                if name == "face_shading.png" and alpha.getextrema()[1] >= 100:
                    raise ValueError("shading includes overly opaque face pixels")
        with ZipFile(root / "Sofia_Batch09_Editable_Layers.ora") as master:
            if (
                master.testzip() is not None
                or master.read("mimetype") != b"image/openraster"
                or not {"stack.xml", "data/layer0.png", "data/layer1.png",
                        "data/layer2.png", "mergedimage.png"} <= set(master.namelist())
            ):
                raise ValueError("corrupt or incomplete editable layer master")
    except (OSError, KeyError) as exc:
        raise ValueError("damaged candidate PNG or editable master") from exc
    return {
        "verified_files": len(seen),
        "source_kind": "private_review_only",
        "production_activated": False,
        "independent_expression_rig_ready": False,
        "canonical_body_matched": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify non-production Batch09 head layers")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--canonical-body", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify_head_foundation(args.root, canonical_body=args.canonical_body), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
