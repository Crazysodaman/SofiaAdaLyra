"""Static cohesive head acceptance is integrity-only, not public activation."""
from __future__ import annotations

from hashlib import sha256
import json

import pytest

from sofia.avatar.vtuber_cohesive_candidate import verify_cohesive_candidate

Image = pytest.importorskip("PIL.Image")


@pytest.fixture
def reviewed(tmp_path):
    root = tmp_path / "Private-Source" / "Reviewed-Candidates" / "CohesiveHead" / "v1"
    root.mkdir(parents=True)
    shapes = {
        "cohesive_head_layer_2048x2560.png": ((2048, 2560), "RGBA"),
        "cohesive_head_source_original.png": ((1315, 1197), "RGBA"),
        "canonical_body_head_suppression_mask.png": ((2048, 2560), "L"),
        "Sofia_Cohesive_Face_Registered_Preview.png": ((668, 495), "RGB"),
    }
    rows = []
    for name, (shape, mode) in shapes.items():
        image = Image.new(mode, shape)
        path = root / name
        image.save(path)
        data = path.read_bytes()
        rows.append({"file": name, "sha256": sha256(data).hexdigest(), "bytes": len(data)})
    manifest = {
        "schema": "sofia.avatar2d.cohesive_head_candidate.v1",
        "private_source_only": True,
        "production_activated": False,
        "canvas": {"width": 2048, "height": 2560},
        "registration": {"x": 734, "y": 0, "width": 580, "height": 528},
        "files": rows,
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


def test_verified_candidate_never_reports_animation_or_runtime_ready(reviewed):
    result = verify_cohesive_candidate(reviewed)
    assert result.verified_pngs == 4
    assert result.production_activated is False
    assert result.independent_animation_ready is False
    assert result.canvas == (2048, 2560)


def test_corrupted_head_rejected_before_any_paint(reviewed):
    (reviewed / "cohesive_head_layer_2048x2560.png").write_bytes(b"broken")
    with pytest.raises(ValueError, match="size mismatch|digest mismatch"):
        verify_cohesive_candidate(reviewed)


def test_missing_source_rejected(reviewed):
    (reviewed / "cohesive_head_source_original.png").unlink()
    with pytest.raises(ValueError, match="missing"):
        verify_cohesive_candidate(reviewed)


def test_unknown_or_repeated_sprite_rejected(reviewed):
    path = reviewed / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"][0]["file"] = "../outside.png"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="untrusted"):
        verify_cohesive_candidate(reviewed)


def test_public_location_rejected(reviewed, tmp_path):
    other = tmp_path / "Public-V2" / "character"
    other.mkdir(parents=True)
    with pytest.raises(ValueError, match="Private-Source"):
        verify_cohesive_candidate(other)


def test_manifest_cannot_grant_activation(reviewed):
    path = reviewed / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["production_activated"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="must not declare"):
        verify_cohesive_candidate(reviewed)
