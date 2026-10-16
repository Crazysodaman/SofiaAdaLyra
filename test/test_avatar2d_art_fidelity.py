"""Source exactness: no procedural sprite may self-certify real design fidelity."""
from dataclasses import replace
import json

import pytest

from sofia.avatar.vtuber_art_fidelity import (
    authoring_instructions, brief_from_blueprint, export_public_art_briefs,
    public_art_briefs, verify_art_review,
)
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def _blueprint(item_id):
    return next(
        b for b in build_starter_wardrobe().blueprints
        if b.garment.item_id == item_id
    )


def test_exact_source_details_are_preserved_for_engineer_jacket():
    bp=_blueprint("day.engineer_jacket")
    brief=brief_from_blueprint(bp)
    f=brief.fields
    assert f["name"]=="Asymmetric engineer jacket"
    assert f["garment_type"]=="engineer_jacket"
    assert f["primary_hex"]=="#0B0D12"
    assert f["accent_hex"]=="#8B1E3F"
    assert "asymmetric front zip" in f["description"]
    assert "hip-length" in f["description"]
    assert "cyan" in f["description"]
    assert "tail opening" in f["description"]
    assert "asymmetric_zip" in f["features"]
    assert "reinforced_panels" in f["features"]
    assert f["waist_up_visible"] is True
    assert len(brief.source_sha256) == 64
    assert "hip-length" in authoring_instructions(brief)
    assert "source_sha256" in brief.as_dict()


def test_lounge_graphic_stays_on_back_and_front_stays_plain():
    brief=brief_from_blueprint(_blueprint("night.lounge_tee"))
    f=brief.fields
    assert f["sleeve_length"] is not None
    assert f["primary_name"]=="black"
    assert f["accent_name"]=="dark_violet"
    assert "upper thigh" in f["description"]
    assert "dropped shoulders" in f["description"]
    assert "upper back" in f["description"]
    assert "front stays mostly clean" in f["description"]
    instructions=authoring_instructions(brief)
    assert "back" in instructions
    assert "Do not move a specified back graphic to the front" in instructions


def test_technical_top_keeps_crimson_seams_and_left_chest_circuit():
    brief=brief_from_blueprint(_blueprint("day.technical_top"))
    assert "small cyan circuit mark" in brief.fields["description"]
    assert "left chest" in brief.fields["description"]
    assert "hip" in brief.fields["description"]
    assert brief.fields["garment_type"]=="long_sleeve_tee"
    assert brief.fields["primary_name"]=="black"
    assert brief.fields["accent_name"]=="crimson"


def test_public_export_has_every_public_catalog_item_including_lower_body(tmp_path):
    catalog=build_starter_wardrobe()
    expected=sum(1 for bp in catalog.blueprints if not bp.design.private_only)
    briefs=public_art_briefs(catalog)
    assert len(briefs)==expected>=200
    result=export_public_art_briefs(tmp_path/"specs",catalog=catalog)
    assert result["total"]==expected
    assert result["waist_up_visible"]<result["total"]
    index=json.loads((tmp_path/"specs"/"index.json").read_text("utf-8"))
    assert len(index["items"])==expected
    assert (tmp_path/"specs"/"day.engineer_jacket.json").is_file()
    assert (tmp_path/"specs"/"day.technical_top.json").is_file()
    assert not (tmp_path/"specs"/"under.private.rope_full_harness.json").exists()
    assert not (tmp_path/"sofia.db").exists()
    with pytest.raises(FileExistsError):
        export_public_art_briefs(tmp_path/"specs",catalog=catalog)


def test_private_wardrobe_omitted_from_public_art_prompts():
    private=next(bp for bp in build_starter_wardrobe().blueprints
                 if bp.design.private_only)
    with pytest.raises(PermissionError, match="restricted"):
        brief_from_blueprint(private)
    # A separately protected owner workspace may make an internal brief,
    # but it is never eligible for the PUBLIC image prompt API.
    restricted=brief_from_blueprint(private,allow_private=True)
    with pytest.raises(PermissionError, match="private"):
        authoring_instructions(restricted)


def test_different_source_design_revision_has_different_fingerprint():
    original=_blueprint("day.technical_top")
    changed=replace(original,
                    design=replace(original.design,description=
                        original.design.description+" More detail."))
    before=brief_from_blueprint(original)
    after=brief_from_blueprint(changed)
    assert before.item_id==after.item_id
    assert before.source_sha256!=after.source_sha256


def test_exactness_is_never_approved_by_image_hash_alone():
    brief=brief_from_blueprint(_blueprint("day.engineer_jacket"))
    digest="f"*64
    valid={"schema":"sofia.avatar2d.art_review.v1",
           "item_id":brief.item_id,"source_sha256":brief.source_sha256,
           "sprite_sha256":digest,
           "visual_review_status":"accepted",
           "manual_checks":dict.fromkeys((
              "fit","hem_length","sleeve_length","material","primary_color",
              "accent_color","pattern","graphic_placement",
              "construction_features","sprite_alignment","alpha_background",
           ),True)}
    assert verify_art_review(brief,valid,sprite_sha256=digest)
    assert not verify_art_review(
        brief,{**valid,"source_sha256":"b"*64},sprite_sha256=digest)
    assert not verify_art_review(
        brief,{**valid,"visual_review_status":"candidate"},sprite_sha256=digest)
    assert not verify_art_review(
        brief,{**valid,"manual_checks":{**valid["manual_checks"],
                                      "hem_length":False}},
        sprite_sha256=digest)
    # Marker only verifies exact source/asset binding, not that an arbitrary
    # caller actually saw the image or was a cryptographically proved owner.
