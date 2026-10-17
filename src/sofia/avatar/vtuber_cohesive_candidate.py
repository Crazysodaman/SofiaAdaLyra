"""Integrity-only review of a separately staged cohesive 2D head candidate.

A cohesive portrait is a STATIC image: it has baked facial features, hair and
ears, and must not be mixed with independently animated legacy sprite layers.
This module does not activate or supply any art to the public Tk renderer.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re

_SCHEMA = "sofia.avatar2d.cohesive_head_candidate.v1"
_FILES = {
    "cohesive_head_layer_2048x2560.png": (2048, 2560, "RGBA"),
    "cohesive_head_source_original.png": (1315, 1197, "RGBA"),
    "canonical_body_head_suppression_mask.png": (2048, 2560, "L"),
    "Sofia_Cohesive_Face_Registered_Preview.png": (668, 495, "RGB"),
}
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_MAX_FILE_BYTES = 12 * 1024 * 1024
_MAX_MANIFEST_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class CandidateReview:
    verified_pngs: int
    production_activated: bool
    independent_animation_ready: bool
    source_sha256: str
    canvas: tuple[int, int]


def verify_cohesive_candidate(root: Path) -> CandidateReview:
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("explicit absolute staged candidate directory required")
    if "private-source" not in {part.casefold() for part in root.parts}:
        raise ValueError("candidate must be staged under Private-Source")
    if any(part.casefold().startswith("public") for part in root.parts):
        raise ValueError("private candidate cannot be read from public folders")
    if not root.is_dir() or any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("candidate root missing or symlinked")
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("candidate manifest missing or linked")
    if manifest_path.stat().st_size > _MAX_MANIFEST_BYTES:
        raise ValueError("candidate manifest too large")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid candidate manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != _SCHEMA:
        raise ValueError("unknown cohesive head candidate schema")
    if manifest.get("private_source_only") is not True or manifest.get("production_activated") is not False:
        raise ValueError("candidate must not declare production activation")
    if manifest.get("canvas") != {"width": 2048, "height": 2560}:
        raise ValueError("candidate canvas mismatch")
    if manifest.get("registration") != {"x": 734, "y": 0, "width": 580, "height": 528}:
        raise ValueError("unreviewed candidate registration")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != len(_FILES):
        raise ValueError("incomplete candidate file list")
    from PIL import Image
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid candidate file entry")
        name, digest = row.get("file"), row.get("sha256")
        if name not in _FILES or name in seen or not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError("untrusted candidate file descriptor")
        seen.add(name)
        candidate = root / name
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError(f"candidate artwork missing or linked: {name}")
        size = candidate.stat().st_size
        if size == 0 or size > _MAX_FILE_BYTES or row.get("bytes") != size:
            raise ValueError(f"candidate artwork size mismatch: {name}")
        data = candidate.read_bytes()
        if sha256(data).hexdigest() != digest:
            raise ValueError(f"candidate artwork digest mismatch: {name}")
        try:
            from io import BytesIO
            with Image.open(BytesIO(data)) as image:
                if image.format != "PNG" or (image.width, image.height, image.mode) != _FILES[name]:
                    raise ValueError("wrong PNG geometry")
                image.verify()
        except (OSError, ValueError) as exc:
            raise ValueError(f"unusable candidate PNG: {name}") from exc
    if seen != set(_FILES):
        raise ValueError("candidate file set is incomplete")
    source = next(row["sha256"] for row in rows if row["file"] == "cohesive_head_source_original.png")
    return CandidateReview(len(seen), False, False, source, (2048, 2560))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify staged private static face candidate")
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args(argv)
    review = verify_cohesive_candidate(args.root)
    print(json.dumps({
        "verified_pngs": review.verified_pngs,
        "production_activated": review.production_activated,
        "independent_animation_ready": review.independent_animation_ready,
        "source_sha256": review.source_sha256,
        "canvas": list(review.canvas),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
