"""Staged independent eye/brow art never bypasses the 2D public renderer."""
from __future__ import annotations

from hashlib import sha256
import json

import pytest

Image = pytest.importorskip("PIL.Image")
from sofia.avatar.vtuber_independent_features import (
    BROW_STATES, EYE_STATES, verify_independent_features,
)


@pytest.fixture
def staged(tmp_path):
    base = tmp_path / "Private-Source" / "Reviewed-Candidates"
    foundation = base / "Batch09-ModularFoundation-v3"
    root = base / "Batch10_11_IndependentEyesBrows-v1"
    foundation.mkdir(parents=True)
    root.mkdir(parents=True)
    for filename in ("head_base.png", "face_shading.png"):
        (foundation / filename).write_bytes(filename.encode())
    left = Image.new("RGBA", (2048, 2560))
    right = Image.new("RGBA", (2048, 2560))
    left.putpixel((970, 215), (170, 90, 220, 255))
    right.putpixel((1060, 215), (170, 90, 220, 255))
    left_path = root / "example_left.png"
    right_path = root / "example_right.png"
    left.save(left_path)
    right.save(right_path)
    sprites = []
    for family, states in (("eyes", EYE_STATES), ("brows", BROW_STATES)):
        for side in ("left", "right"):
            for state in states:
                role = f"{'eye' if family == 'eyes' else 'brow'}_{side}"
                rel = f"layers/{family}/{role}/{state}.png"
                file = root / rel
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes((left_path if side == "left" else right_path).read_bytes())
                bbox = [970, 215, 971, 216] if side == "left" else [1060, 215, 1061, 216]
                sprites.append({
                    "file": rel, "role": role, "state": state,
                    "alpha_bbox": bbox,
                })
    left_path.unlink()
    right_path.unlink()
    for filename in (
        "README.txt", "Install-Batch10_11.ps1",
        "Preview_Eyes_Brows_Independent_v1.png",
        "Check-Batch10_11.cmd", "Stage-Batch10_11.cmd",
        "Verify-Batch10_11.cmd", "Rollback-Batch10_11.cmd",
        "Preview-Batch10_11.cmd",
    ):
        (root / filename).write_bytes(filename.encode())
    files = [
        {"file": str(p.relative_to(root)).replace("\\", "/"),
         "bytes": len(p.read_bytes()),
         "sha256": sha256(p.read_bytes()).hexdigest()}
        for p in root.rglob("*") if p.is_file()
    ]
    manifest = {
        "schema": "sofia.avatar2d.independent_eyes_brows.review.v1",
        "private_source_only": True,
        "production_activated": False,
        "master_canvas": [2048, 2560],
        "left_right_split_x": 1024,
        "owner_approved_resting_brow": "soft",
        "head_base_sha256": sha256((foundation / "head_base.png").read_bytes()).hexdigest(),
        "face_shading_sha256": sha256((foundation / "face_shading.png").read_bytes()).hexdigest(),
        "sprites": sprites, "files": files,
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root, foundation


def test_verified_set_has_independent_states_and_stays_inactive(staged):
    root, foundation = staged
    result = verify_independent_features(root, foundation_root=foundation)
    assert result == {
        "validated_sprites": 32, "independent_eyes": 20,
        "independent_brows": 12, "batch09_matched": True,
        "production_activated": False, "renderer_ready": False,
    }


def test_tampered_single_eye_rejected(staged):
    root, foundation = staged
    (root / "layers" / "eyes" / "eye_left" / "closed.png").write_bytes(b"oops")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        verify_independent_features(root, foundation_root=foundation)


def test_changed_foundation_rejected(staged):
    root, foundation = staged
    (foundation / "head_base.png").write_bytes(b"different head")
    with pytest.raises(ValueError, match="Batch09"):
        verify_independent_features(root, foundation_root=foundation)


def test_missing_variant_rejected(staged):
    root, foundation = staged
    path = root / "layers" / "brows" / "brow_right" / "angry.png"
    path.unlink()
    with pytest.raises(ValueError, match="missing"):
        verify_independent_features(root, foundation_root=foundation)


def test_public_dir_cannot_be_verified_as_private(staged, tmp_path):
    _, foundation = staged
    public = tmp_path / "Public-V2"
    public.mkdir()
    with pytest.raises(ValueError, match="Private-Source"):
        verify_independent_features(public, foundation_root=foundation)


def test_manifest_cannot_self_activate(staged):
    root, foundation = staged
    path = root / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["production_activated"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe"):
        verify_independent_features(root, foundation_root=foundation)
