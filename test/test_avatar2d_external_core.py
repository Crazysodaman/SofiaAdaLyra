"""Regression tests for review-only import of eight approved character-art batches."""
from __future__ import annotations

from io import BytesIO
import json

import pytest

from sofia.avatar.vtuber_external_core import (
    _FILES, audit_installed_core, stage_review,
)

PIL = pytest.importorskip("PIL.Image")


def _make(root, *, ear_size=(1254, 1254), tail_size=(1122, 1402)):
    blobs = {}
    for size in ((2048, 2560), ear_size, tail_size):
        image = PIL.new("RGBA", size)
        image.putpixel((15, 15), (150, 25, 65, 255))
        dest = BytesIO()
        image.save(dest, format="PNG")
        blobs[size] = dest.getvalue()
    for group, names in _FILES.items():
        directory = root / "layers" / group
        directory.mkdir(parents=True, exist_ok=True)
        size = (ear_size if group == "ears" else
                tail_size if group == "tail" else (2048, 2560))
        for name in names:
            (directory / name).write_bytes(blobs[size])


def test_all_57_approved_source_names_are_audited(tmp_path):
    source = tmp_path / "CoreLayers"
    source.mkdir()
    _make(source)
    audit = audit_installed_core(source)
    assert len(audit.sprites) == 57
    assert audit.missing == audit.invalid == 0
    assert audit.needs_alignment >= 17
    assert not audit.ready_for_public_renderer


def test_missing_and_mutated_layers_detected(tmp_path):
    source = tmp_path / "CoreLayers"
    source.mkdir()
    _make(source)
    (source / "layers" / "face" / "face_base.png").unlink()
    (source / "layers" / "hair" / "hair_back_main.png").write_bytes(
        b"not a png"
    )
    audit = audit_installed_core(source)
    assert audit.missing == 1
    assert audit.invalid == 1


def test_staging_is_private_review_only(tmp_path):
    source = tmp_path / "CoreLayers"
    source.mkdir()
    _make(source)
    target = tmp_path / "Private-Source" / "Review" / "v1"
    stage_review(source, target)
    data = json.loads((target / "core_inventory.json").read_text())
    assert data["production_activated"] is False
    assert len(data["sprites"]) == 57
    assert (target / "review_contact_sheet.png").is_file()
    with pytest.raises(ValueError):
        stage_review(source, target)
    with pytest.raises(ValueError):
        stage_review(source, tmp_path / "Public-V2" / "character")


def test_symlink_file_rejected(tmp_path):
    source = tmp_path / "CoreLayers"
    source.mkdir()
    _make(source)
    bad = source / "layers" / "face" / "face_base.png"
    bad.unlink()
    try:
        bad.symlink_to(source / "layers" / "face" / "face_shading.png")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink"):
        audit_installed_core(source)
