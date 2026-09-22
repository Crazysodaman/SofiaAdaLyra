"""Isolated authoring checks: not a Blender, anatomy or renderer acceptance suite."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import sys

import numpy as np
import pytest
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "avatar"))
from measure_calibrated_body import (  # noqa: E402
    GIRTH_Z, MeasurementError, build_scene, ellipse_vertices, export,
    measure_girth, read_canonical, torso_mesh,
)

INCH = .0254
VALUES = {"height": 67 * INCH, "bust": 33 * INCH,
          "underbust": 30 * INCH, "waist": 26 * INCH, "hips": 37 * INCH}


def write_fixture(tmp_path, *, bust=33, form="human", height_unit="in"):
    data = {"subject": "Sofía Ada Lyra", "physical_self": {
        "form": form, "additional_features": ["fox ears", "fox tail"],
        "measurements": {name: {"value": value, "unit": height_unit if name == "height" else "in"}
                         for name, value in {"height": 67, "bust": bust, "underbust": 30, "waist": 26, "hips": 37}.items()},
        "appearance": {"skin_hex": "#F1E9D8", "hair_hex": "#8B1E3F"},
    }}
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")
    return path


def test_sources_are_canonical_measurements_and_sha(tmp_path):
    file = write_fixture(tmp_path)
    values, source_hash, colors = read_canonical(file)
    assert values == VALUES
    assert source_hash == sha256(file.read_bytes()).hexdigest()
    assert colors["skin_hex"] == "#F1E9D8"


@pytest.mark.parametrize("kwargs", [{"bust": 20}, {"form": "robot"}, {"height_unit": "cm"}])
def test_bad_canonical_rejected(tmp_path, kwargs):
    with pytest.raises(MeasurementError):
        read_canonical(write_fixture(tmp_path, **kwargs))


def test_circumference_not_bounding_box():
    poly = ellipse_vertices(circumference=VALUES["hips"], x_over_y=1.25)
    perimeter = np.linalg.norm(np.roll(poly, -1, axis=0)-poly, axis=1).sum()
    assert abs(perimeter - VALUES["hips"]) < 1e-10
    assert not np.isclose(2 * (poly[:, 0].max()-poly[:, 0].min()), perimeter)


def test_torso_closed_and_all_four_surface_girths():
    mesh = torso_mesh(VALUES)
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    for name, z in GIRTH_Z.items():
        assert abs(measure_girth(mesh, z) - VALUES[name]) < .0005


def test_measurement_fails_when_section_missing():
    with pytest.raises(MeasurementError):
        measure_girth(torso_mesh(VALUES), 3.0)


def test_names_and_human_crown_separate_from_fox_ears():
    scene, nodes = build_scene(VALUES, {"skin_hex": "#F1E9D8", "hair_hex": "#8B1E3F"})
    assert "BODY_TORSO_MEASUREMENT_PROXY" in nodes
    assert "FOX_TAIL_ROOT_PROXY" in nodes
    assert "FOX_EAR_LEFT_PROXY" in nodes
    head = scene.geometry["BODY_HEAD_CROWN_REFERENCE"]
    assert abs(head.bounds[1][2] - VALUES["height"]) < 1e-6
    assert scene.geometry["FOX_EAR_LEFT_PROXY"].bounds[1][2] > VALUES["height"]
    assert not any("NIPPLE" in name or "VULVA" in name or "ANUS" in name for name in nodes)


def test_export_real_glb_roundtrip_manifest_and_authored_section(tmp_path):
    source = write_fixture(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    glb, manifest = export(canonical_path=source, output_dir=out)
    assert glb.read_bytes()[:4] == b"glTF"
    data = json.loads(manifest.read_text())
    assert data["glb_sha256"] == sha256(glb.read_bytes()).hexdigest()
    assert data["canonical_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert data["asset_class"].startswith("controlled_authoring_only")
    assert "detailed_anatomy" in data["unimplemented"]
    loaded = trimesh.load(glb, force="scene", process=False)
    assert "BODY_TORSO_MEASUREMENT_PROXY" in loaded.geometry
    for name, z in GIRTH_Z.items():
        measured = measure_girth(loaded.geometry["BODY_TORSO_MEASUREMENT_PROXY"], z)
        assert abs(measured - VALUES[name]) < .0005, name
        assert abs(data["measurements"][name]["measured_m"] - measured) < .0005


def test_export_refuses_overwrite_without_modifying_files(tmp_path):
    src = write_fixture(tmp_path)
    with pytest.raises(MeasurementError):
        export(canonical_path=src, output_dir=tmp_path / "not-exists")
    glb, manifest = export(canonical_path=src, output_dir=tmp_path)
    original = glb.read_bytes(), manifest.read_bytes()
    with pytest.raises(MeasurementError):
        export(canonical_path=src, output_dir=tmp_path)
    assert (glb.read_bytes(), manifest.read_bytes()) == original


def test_output_symlink_refused(tmp_path):
    src = write_fixture(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("symlinks not available")
    with pytest.raises(MeasurementError):
        export(canonical_path=src, output_dir=link)
