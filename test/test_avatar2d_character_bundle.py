"""Only checked public per-part sprites enter the modular Tk compositor."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from sofia.modules.avatar.vtuber_asset_bundle import Avatar2DAssetError
from sofia.modules.avatar.vtuber_character_bundle import load_selected_character_sprites
from sofia.modules.avatar.vtuber_character_parts import generate_public_character_parts
from sofia.modules.avatar.vtuber_character_selection import select_character_parts
from test.test_ui_avatar2d_renderer import env


def pack(tmp_path):
    root, projection, state = env(tmp_path)
    parts = root / "character"
    generate_public_character_parts(parts)
    chosen = select_character_parts(projection)
    return parts, chosen


def test_complete_pack_loads_exactly_one_approved_part_per_group(tmp_path):
    root, selection = pack(tmp_path)
    sprites = load_selected_character_sprites(root, selection)
    assert len(sprites) == 12
    assert len({sprite.group for sprite in sprites}) == 12
    assert all(sprite.png.startswith(b"\x89PNG\r\n\x1a\n") for sprite in sprites)
    assert {s.group for s in sprites} == {
        "face", "freckles", "eye_left", "eye_right",
        "brow_left", "brow_right", "mouth", "hair_back",
        "hair_front", "ear_left", "ear_right", "tail",
    }


@pytest.mark.parametrize("modification", [
    "unsafe_path", "private_audience", "wrong_digest",
    "duplicate_variant", "different_topology", "wrong_canvas",
])
def test_bad_manifest_is_never_accepted(tmp_path, modification):
    root, selection = pack(tmp_path)
    file = root / "manifest.json"
    manifest = json.loads(file.read_text(encoding="utf-8"))
    if modification == "unsafe_path":
        manifest["parts"][0]["path"] = "../secret.png"
    elif modification == "private_audience":
        manifest["parts"][0]["audience"] = "private"
    elif modification == "wrong_digest":
        manifest["parts"][0]["sha256"] = "0" * 64
    elif modification == "duplicate_variant":
        manifest["parts"][1]["id"] = manifest["parts"][0]["id"]
        manifest["parts"][1]["variant"] = manifest["parts"][0]["variant"]
        manifest["parts"][1]["group"] = manifest["parts"][0]["group"]
    elif modification == "different_topology":
        manifest["fixed_topology"]["tails"] = 2
    elif modification == "wrong_canvas":
        manifest["canvas"]["width"] = 512
    file.write_text(json.dumps(manifest), encoding="utf-8")
    if modification == "wrong_digest":
        # Descriptor sha is only checked against selected sprite bytes.
        # The first manifest entry (face.neutral) is selected, so it fails.
        assert selection.as_dict()["face"] == "neutral"
    with pytest.raises(Avatar2DAssetError):
        load_selected_character_sprites(root, selection)


def test_corrupted_selected_png_fails_without_loading_any_untrusted_pixels(tmp_path):
    root, selection = pack(tmp_path)
    (root / "eye_right" / "open.png").write_bytes(b"bad")
    with pytest.raises(Avatar2DAssetError):
        load_selected_character_sprites(root, selection)


def test_symlink_is_refused_even_when_it_points_to_valid_public_png(tmp_path):
    root, selection = pack(tmp_path)
    path = root / "eye_left" / "open.png"
    original = path.read_bytes()
    outside = tmp_path / "outside.png"
    outside.write_bytes(original)
    path.unlink()
    try:
        path.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("local filesystem disallows creating symlinks")
    with pytest.raises(Avatar2DAssetError):
        load_selected_character_sprites(root, selection)


def test_unavailable_character_variant_cannot_be_invented(tmp_path):
    root, selection = pack(tmp_path)
    forged = replace(
        selection, groups=tuple(
            (group, "flying" if group == "tail" else variant)
            for group, variant in selection.groups
        ),
    )
    with pytest.raises(Avatar2DAssetError):
        load_selected_character_sprites(root, forged)
