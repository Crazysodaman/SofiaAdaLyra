"""Offline art-export tests. Trimesh verifies GLB structure, not Blender or aesthetics."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("trimesh")
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "avatar"))
from export_stylized_blockouts import BlockoutError, build_scene, export_blockouts, load_canon


@pytest.fixture
def canon(tmp_path):
    path = tmp_path / "avatar.json"
    path.write_text(json.dumps({
        "subject": "Sofía Ada Lyra",
        "physical_self": {
            "form": "human", "additional_features": ["fox ears", "fox tail"],
            "appearance": {"hair_hex": "#8B1E3F", "skin_hex": "#F1E9D8", "accent_hex": "#19D3C5"},
        },
    }), encoding="utf-8")
    return path


@pytest.mark.parametrize("variant", ["engineer", "lounge"])
def test_build_variant_contains_covered_parts_and_fox_features(canon, variant):
    colors, _ = load_canon(canon)
    scene, nodes, anchors = build_scene(variant, colors)
    assert scene.geometry and len(scene.geometry) >= 20
    assert "GARMENT_SHIRT_TORSO" in nodes
    assert "GARMENT_PANTS_HIPS" in nodes
    assert "FOX_EAR_LEFT_VIOLET" in nodes
    assert "FOX_EAR_RIGHT_VIOLET" in nodes
    assert "TAIL_TIP_LIGHT" in nodes
    assert {"torso", "pelvis", "ears", "tail", "left_wrist", "right_wrist"} <= anchors.keys()
    assert all(len(meta["color"]) == 7 for meta in nodes.values())
    assert len(scene.graph.nodes_geometry) == len(nodes)
    if variant == "engineer":
        assert "GARMENT_ENGINEER_JACKET" in nodes
        assert "GARMENT_LEATHER_GAUNTLET_LEFT" in nodes
    else:
        assert "GARMENT_ENGINEER_JACKET" not in nodes
        assert "GARMENT_SWEATPANTS_CUFF_RIGHT" in nodes


def test_exports_real_readable_glbs_and_sha_bound_manifests(canon, tmp_path):
    output = tmp_path / "assets"
    output.mkdir()
    paths = export_blockouts(canon_path=canon, output_dir=output)
    assert len(paths) == 4
    assert {p.name for p in paths} == {
        "sofia_a0_engineer.glb", "sofia_a0_engineer.json",
        "sofia_a0_lounge.glb", "sofia_a0_lounge.json",
    }
    for variant in ("engineer", "lounge"):
        glb = output / f"sofia_a0_{variant}.glb"
        manifest = json.loads((output / f"sofia_a0_{variant}.json").read_text())
        assert glb.read_bytes().startswith(b"glTF")
        assert manifest["glb_sha256"] == sha256(glb.read_bytes()).hexdigest()
        assert manifest["canonical_sha256"] == sha256(canon.read_bytes()).hexdigest()
        assert manifest["covered_default"] is True
        assert manifest["restricted_asset"] is False
        imported = trimesh.load(glb, force="scene")
        assert len(imported.geometry) >= 20
        assert set(manifest["nodes"]).issubset(set(imported.graph.nodes_geometry))
        assert all(mesh.vertices.shape[0] > 0 for mesh in imported.geometry.values())
    assert (output / "sofia_a0_engineer.glb").read_bytes() != (output / "sofia_a0_lounge.glb").read_bytes()


def test_refuses_existing_files_without_changing_them(canon, tmp_path):
    output = tmp_path / "assets"
    output.mkdir()
    occupied = output / "sofia_a0_engineer.glb"
    occupied.write_bytes(b"leave-me-alone")
    with pytest.raises(BlockoutError, match="output exists"):
        export_blockouts(canon_path=canon, output_dir=output)
    assert occupied.read_bytes() == b"leave-me-alone"
    assert len(list(output.iterdir())) == 1


def test_refuses_nonexistent_directory_and_symlink(canon, tmp_path):
    with pytest.raises(BlockoutError):
        export_blockouts(canon_path=canon, output_dir=tmp_path / "missing")
    output = tmp_path / "real"
    output.mkdir()
    symlink = tmp_path / "alias"
    try:
        symlink.symlink_to(output, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on host")
    with pytest.raises(BlockoutError):
        export_blockouts(canon_path=canon, output_dir=symlink)


@pytest.mark.parametrize("mutation", [
    lambda data: data.update(subject="Imposter"),
    lambda data: data["physical_self"].update(additional_features=[]),
    lambda data: data["physical_self"]["appearance"].update(hair_hex="#000000"),
    lambda data: data["physical_self"]["appearance"].update(accent_hex="not a color"),
])
def test_canonical_mismatch_fails_closed(canon, mutation):
    data = json.loads(canon.read_text())
    mutation(data)
    canon.write_text(json.dumps(data))
    with pytest.raises(BlockoutError):
        load_canon(canon)


def test_unknown_variant_denied(canon):
    colors, _ = load_canon(canon)
    with pytest.raises(BlockoutError):
        build_scene("unclothed", colors)
