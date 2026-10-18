"""Focused review-job safety checks. Does not require a GUI display."""
import json
from pathlib import Path
import pytest
from PIL import Image
from sofia.ui.live2d_review import FACE_PARTS, create_review_job

def test_creates_unapproved_review_manifest(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (512, 512), (30, 40, 50)).save(source)
    job = create_review_job(source, tmp_path / "job")
    manifest = json.loads((job / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "awaiting_masks"
    assert manifest["auto_extraction_performed"] is False
    assert manifest["psd_exported"] is False
    assert [part["name"] for part in manifest["parts"]] == list(FACE_PARTS)
    assert all(not part["approved"] for part in manifest["parts"])
    assert (job / "source.png").read_bytes() == source.read_bytes()

def test_does_not_overwrite_existing_job(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (512, 512)).save(source)
    directory = tmp_path / "job"
    create_review_job(source, directory)
    with pytest.raises(FileExistsError):
        create_review_job(source, directory)

def test_refuses_invalid_source(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"not a png")
    with pytest.raises(Exception):
        create_review_job(source, tmp_path / "job")
    assert not (tmp_path / "job").exists()
