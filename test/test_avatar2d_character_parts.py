"""Each face/fox component has independent alpha PNGs on a shared canvas."""
import json
from hashlib import sha256
from pathlib import Path
import struct

import pytest

from sofia.avatar.vtuber_character_parts import (
    character_part_options, generate_public_character_parts,
)
from sofia.avatar.vtuber_starter_art import WIDTH, HEIGHT, PNG_HEADER


def test_all_character_groups_include_independent_variants(tmp_path):
    out = tmp_path / "character"
    report = generate_public_character_parts(out)
    manifest = json.loads((out / "manifest.json").read_text("utf-8"))
    options = character_part_options()
    assert report.groups == len(options) == 12
    assert report.parts == sum(map(len, options.values()))
    assert report.parts >= 20
    assert manifest["fixed_topology"] == {"ears": 2, "tails": 1}
    assert manifest["quality"] == "procedural_starter_unreviewed"
    assert set(manifest["groups"]) == set(options)
    assert len(manifest["parts"]) == report.parts
    assert set(options["eye_left"]) >= {"open", "closed", "looking_left"}
    assert {"long_layered", "tied_back"} <= set(options["hair_front"])
    assert {"perked", "relaxed"} <= set(options["ear_left"])
    assert {"calm", "raised", "flick"} <= set(options["tail"])


def test_all_parts_are_real_separate_consistently_aligned_transparent_pngs(tmp_path):
    output=tmp_path/"parts"
    generate_public_character_parts(output)
    manifest=json.loads((output/"manifest.json").read_text("utf-8"))
    seen=set()
    for item in manifest["parts"]:
        assert item["id"] not in seen
        seen.add(item["id"])
        relative=Path(item["path"])
        assert ".." not in relative.parts
        data=(output / relative).read_bytes()
        assert data.startswith(PNG_HEADER)
        assert struct.unpack(">II", data[16:24]) == (WIDTH,HEIGHT)
        assert sha256(data).hexdigest()==item["sha256"]
        assert item["audience"] == "public"
        assert item["anchor"] in (
            "head","left_fox_ear","right_fox_ear","tail_root",
        )
        assert item["group"] in character_part_options()
    assert (output/"face"/"neutral.png").exists()
    assert (output/"eye_left"/"closed.png").exists()
    assert (output/"eye_right"/"open.png").exists()
    assert (output/"hair_front"/"long_layered.png").exists()
    assert (output/"ear_left"/"perked.png").exists()
    assert (output/"ear_right"/"relaxed.png").exists()
    assert (output/"tail"/"raised.png").exists()
    with pytest.raises(FileExistsError):
        generate_public_character_parts(output)


def test_character_parts_do_not_mint_private_body_or_new_anatomy(tmp_path):
    output=tmp_path/"parts"
    generate_public_character_parts(output)
    manifest=json.loads((output/"manifest.json").read_text("utf-8"))
    assert all(item["audience"] == "public" for item in manifest["parts"])
    assert "private_anatomy" not in json.dumps(manifest)
    assert manifest["face_geometry"]=="illustrative_not_a_canonical_measurement"
    assert set(manifest["groups"]) == {
        "face","eye_left","eye_right","brow_left","brow_right",
        "mouth","freckles","hair_back",
        "hair_front","ear_left","ear_right","tail",
    }
