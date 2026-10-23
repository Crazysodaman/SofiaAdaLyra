"""Public draft wardrobe atlas smoke and privacy coverage."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import tomllib

import pytest
from PIL import Image

from sofia.modules.avatar.wardrobe_public_sprite_batch import (
    CATEGORIES, _render_vector_candidate, make_batch, public_garment_data,
)


@pytest.mark.pkg_avatar
@pytest.mark.pkg_verify
def test_illustrated_reference_archive_is_declared_as_wheel_package_data():
    root=Path(__file__).resolve().parents[1]
    manifest=tomllib.loads((root/"pyproject.toml").read_text(encoding="utf-8"))
    avatar_data=set(
        manifest["tool"]["setuptools"]["package-data"]["sofia.modules.avatar"]
    )
    assert "assets/sofia2d_public_illustrated_candidates_v1.zip" in avatar_data


@pytest.mark.pkg_avatar
def test_full_public_wardrobe_has_all_expected_canonical_items():
    public=public_garment_data()
    ids=[row["item_id"] for category,row in public]
    assert len(ids)==244
    assert len(set(ids))==244
    assert "day.engineer_jacket" in ids
    assert "night.lounge_tee" in ids
    assert "outer.black_leather_jacket" in ids
    assert all(not row["private_only"] for _,row in public)
    assert len({category for category,row in public})==len(CATEGORIES)


@pytest.mark.pkg_avatar
def test_generate_complete_public_draft_archive_without_private_items(tmp_path):
    root=tmp_path/"atlas"
    manifest=make_batch(root)
    assert manifest["count"]==244
    assert manifest["art_status"]=="DRAFT_VECTOR_NOT_PRODUCTION"
    assert len(list((root/"items").glob("*.png")))==244
    assert len(manifest["items"])==244
    assert manifest["illustrated_unfitted_reference_count"]==9
    assert len(list((root/"illustrated_references").glob("*.png")))==9
    assert len(list((root/"preview").glob("*.png")))==len(CATEGORIES)
    for entry in manifest["items"]:
        assert entry["private_only"] is False
        assert entry["rig_status"]=="NOT_FITTED_FOR_LIVE_REUSE"
        if "illustrated_reference" in entry:
            reference=entry["illustrated_reference"]
            assert reference["status"]=="UNFITTED_ILLUSTRATED_REFERENCE_NOT_LIVE"
            assert sha256((root/reference["path"]).read_bytes()).hexdigest()==reference["sha256"]
        p=root/entry["sprite_file"]
        raw=p.read_bytes()
        assert sha256(raw).hexdigest()==entry["sprite_sha256"]
        im=Image.open(BytesIO(raw)).convert("RGBA")
        assert im.size==(640,800)
        assert im.getchannel("A").getbbox() is not None
    with pytest.raises(FileExistsError):
        make_batch(root)


@pytest.mark.pkg_avatar
def test_unknown_privacy_label_is_fail_closed(tmp_path):
    source=tmp_path/"fake"
    source.mkdir()
    for category in CATEGORIES:
        row={
            "item_id":"only."+category,"name":"Safe garment",
            "garment_type":"belt","primary":"black","accent":"cyan",
            "pattern":"solid","features":[],"private_only":False,
        }
        if category==CATEGORIES[-1]:
            row["private_only"]="false"
        (source/(category+".json")).write_text(json.dumps({"garments":[row]}))
    with pytest.raises(ValueError,match="privacy"):
        public_garment_data(source)


@pytest.mark.pkg_avatar
def test_candidate_visuals_distinguish_jackets_boots_ears_and_belts():
    rows=public_garment_data()
    different=[next((category, row) for category,row in rows if category==name)
               for name in ("outerwear","footwear","accessories_ear","accessories_waist")]
    bboxes=[]
    for category, row in different:
        im=_render_vector_candidate(category,row)
        bboxes.append(im.getchannel("A").getbbox())
    assert len(set(bboxes))==4
