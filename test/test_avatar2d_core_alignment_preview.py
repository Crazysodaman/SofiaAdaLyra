"""Owner art alignment preview stays isolated from public production rendering."""
from __future__ import annotations

import json

import pytest

from sofia.modules.avatar.vtuber_core_alignment_preview import (
    HEAD_CROP, REGISTRATION, make_candidate,
)
from test.test_avatar2d_external_core import _make

Image = pytest.importorskip("PIL.Image")


@pytest.fixture
def artwork(tmp_path):
    root = tmp_path / "CoreLayers"
    root.mkdir()
    _make(root)
    canonical = tmp_path / "canonical_body.png"
    im = Image.new("RGBA", (2048, 2560))
    im.putpixel((1000, 160), (196, 131, 104, 255))
    im.save(canonical)
    return root, canonical, tmp_path


def test_alignment_stages_head_only_and_tail_contact(artwork):
    source, canonical, root = artwork
    target = root / "Private-Source" / "Review" / "candidate"
    report = make_candidate(source, canonical, target)
    assert report["source_pngs_audited"] == 57
    assert report["missing"] == report["invalid"] == 0
    assert report["status"] == "review_only_not_production_activated"
    with Image.open(target / "head_alignment_candidate.png") as head:
        assert head.size == (
            HEAD_CROP[2] - HEAD_CROP[0],
            HEAD_CROP[3] - HEAD_CROP[1],
        )
    with Image.open(target / "tail_pose_contact_sheet.png") as tails:
        assert tails.size == (1060, 660)
    loaded = json.loads((target / "alignment_candidate.json").read_text())
    assert loaded["candidate_transforms"].keys() == REGISTRATION.keys()
    assert not (target / "character" / "manifest.json").exists()


def test_candidate_never_writes_into_public_or_source(artwork):
    source, canonical, root = artwork
    with pytest.raises(ValueError, match="Private-Source"):
        make_candidate(source, canonical, root / "Public-V2" / "Review")
    with pytest.raises(ValueError, match="approved source"):
        make_candidate(source, canonical, source / "review")
    candidate = root / "Private-Source" / "Review" / "candidate"
    make_candidate(source, canonical, candidate)
    with pytest.raises(ValueError, match="new absolute"):
        make_candidate(source, canonical, candidate)


def test_brow_alpha_fringe_is_excluded_from_registration():
    """Nearly invisible outlying pixels must not squeeze the brow shape."""
    from PIL import ImageDraw
    from sofia.modules.avatar.vtuber_core_alignment_preview import _fit

    source = Image.new("RGBA", (300, 120))
    source.putpixel((1, 1), (120, 12, 36, 1))
    ImageDraw.Draw(source).rectangle((50, 60, 250, 80), fill=(120, 12, 36, 255))

    fitted = _fit(source, (700, 40, 1000, 100), alpha_threshold=15)
    bbox = fitted.getchannel("A").point(
        lambda alpha: 255 if alpha > 15 else 0
    ).getbbox()
    assert bbox is not None
    assert bbox[2] - bbox[0] >= 290
    assert bbox[1] >= 40
    assert bbox[3] <= 100



def test_review_rejects_full_face_and_avoids_double_head(artwork):
    """A second opaque oval must not cover the canonical body's face."""
    source, canonical, root = artwork
    face_png = source / "layers" / "face" / "face_base.png"
    with Image.open(face_png) as original:
        face = original.copy()
    # An obvious sentinel in the duplicate face base must never appear.
    face.putpixel((1000, 160), (0, 255, 0, 255))
    face.save(face_png)
    target = root / "Private-Source" / "Review" / "head_gate"
    result = make_candidate(source, canonical, target)
    assert result["head_quality"] == "REJECTED_needs_cohesive_head_and_nose_art"
    assert result["head_base"] == "canonical_body_only"
    assert result["owner_approved"]["brow_variant"] == "brows_soft"
    assert result["owner_approved"]["full_face"] is False
    with Image.open(target / "head_alignment_candidate.png") as preview:
        # Crop begins at (750, 0): source (1000,160) maps to (250,160).
        assert preview.convert("RGBA").getpixel((250, 160))[:3] != (0, 255, 0)
