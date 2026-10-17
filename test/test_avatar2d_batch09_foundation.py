"""Regression tests for staged Batch09 foundation integrity and privacy boundary."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

Image = pytest.importorskip("PIL.Image")
from sofia.avatar.vtuber_batch09_foundation import verify_head_foundation


@pytest.fixture
def package(tmp_path: Path):
    root = tmp_path / "Private-Source" / "Reviewed-Candidates" / "Batch09-ModularFoundation-v3"
    root.mkdir(parents=True)
    body = tmp_path / "canonical.png"
    Image.new("RGBA", (2048, 2560), (210, 157, 136, 255)).save(body)
    alpha = Image.new("RGBA", (2048, 2560))
    from PIL import ImageDraw
    ImageDraw.Draw(alpha).ellipse((900, 75, 1120, 435), fill=(210, 157, 136, 255))
    alpha.save(root / "head_base.png")
    shade = Image.new("RGBA", (2048, 2560))
    ImageDraw.Draw(shade).ellipse((995, 200, 1018, 270), fill=(155, 87, 75, 36))
    shade.save(root / "face_shading.png")
    Image.new("RGB", (470, 395), (36, 36, 42)).save(root / "Preview_Batch09_HeadFit.png")
    with ZipFile(root / "Sofia_Batch09_Editable_Layers.ora", "w") as archive:
        archive.writestr("mimetype", "image/openraster")
        archive.writestr("stack.xml", "<image/>")
        archive.writestr("data/layer0.png", b"base")
        archive.writestr("data/layer1.png", b"head")
        archive.writestr("data/layer2.png", b"shading")
        archive.writestr("mergedimage.png", b"merged")
    for name in (
        "Install-Batch09.ps1", "README.txt", "Check-Batch09.cmd",
        "Stage-Batch09.cmd", "Verify-Batch09.cmd",
        "Rollback-Batch09.cmd", "Preview-Batch09.cmd",
    ):
        (root / name).write_text(name)
    names = sorted(
        path.name for path in root.iterdir()
        if path.is_file()
    )
    rows = [
        {"file": name, "bytes": (root / name).stat().st_size,
         "sha256": sha256((root / name).read_bytes()).hexdigest()}
        for name in names
    ]
    manifest = {
        "schema": "sofia.avatar2d.head_foundation.canonical_matched.v3",
        "private_source_only": True,
        "production_activated": False,
        "canonical_body_sha256": sha256(body.read_bytes()).hexdigest(),
        "layer_dimensions": [2048, 2560],
        "files": rows,
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root, body


def test_review_staging_matches_canonical_without_runtime_activation(package):
    root, body = package
    result = verify_head_foundation(root, canonical_body=body)
    assert result == {
        "verified_files": 11,
        "source_kind": "private_review_only",
        "production_activated": False,
        "independent_expression_rig_ready": False,
        "canonical_body_matched": True,
    }


def test_tampered_shading_does_not_verify(package):
    root, body = package
    (root / "face_shading.png").write_bytes(b"damaged")
    with pytest.raises(ValueError, match="mismatch"):
        verify_head_foundation(root, canonical_body=body)


def test_unexpected_body_does_not_verify(package, tmp_path):
    root, _ = package
    mismatch = tmp_path / "different_body.png"
    mismatch.write_bytes(b"not the owner's body")
    with pytest.raises(ValueError, match="body SHA256 mismatch"):
        verify_head_foundation(root, canonical_body=mismatch)


def test_public_path_never_becomes_private_authority(package, tmp_path):
    root, body = package
    public_dir = tmp_path / "Public-V2" / "character"
    public_dir.mkdir(parents=True)
    with pytest.raises(ValueError, match="Private-Source"):
        verify_head_foundation(public_dir, canonical_body=body)


def test_art_cannot_grant_production_activation(package):
    root, body = package
    manifest_file = root / "manifest.json"
    manifest = json.loads(manifest_file.read_text())
    manifest["production_activated"] = True
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe"):
        verify_head_foundation(root, canonical_body=body)
