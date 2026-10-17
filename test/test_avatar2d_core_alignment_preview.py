"""Owner art alignment preview stays isolated from public production rendering."""
from __future__ import annotations

import json

import pytest

from sofia.avatar.vtuber_core_alignment_preview import (
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
