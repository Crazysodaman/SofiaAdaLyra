"""Offline A1b *measurement-calibrated authoring blockout*, not final anatomy.

Requires numpy and trimesh, independently from Sofía runtime. The torso rings
are constructed from the canonical circumference targets; the verification
re-measures the exported mesh's actual horizontal cross-sections. All vertical
landmarks, ellipse aspect ratios, limb/head/tail proportions are clearly marked
ARTIST_ESTIMATE and need visual review. This does not author nipples, vulva,
anus, a fitted wardrobe, a rig, or any user-visible runtime asset.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

CANONICAL_TARGETS = ("height", "bust", "underbust", "waist", "hips")
GIRTH_Z = {"hips": 0.89, "waist": 1.035, "underbust": 1.145, "bust": 1.245}
RING_COUNT = 192
# These are ARTIST_ESTIMATE, not additional canonical proportions.
TORSO_PROFILE = (
    (0.77, "pelvis_lower", 0.97, 1.23),
    (GIRTH_Z["hips"], "hips", 1.00, 1.25),
    (0.95, "hip_transition", 0.95, 1.27),
    (GIRTH_Z["waist"], "waist", 1.00, 1.29),
    (GIRTH_Z["underbust"], "underbust", 1.00, 1.26),
    (GIRTH_Z["bust"], "bust", 1.00, 1.28),
    (1.335, "upper_chest", 0.97, 1.34),
    (1.375, "shoulder_base", 0.91, 1.33),
)


class MeasurementError(ValueError):
    """Invalid source, geometry, or output path."""


def read_canonical(path: Path) -> tuple[dict[str, float], str, dict[str, str]]:
    """Read actual canonical bytes (UTF-8 with optional BOM); never change them."""
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    if data.get("subject") != "Sofía Ada Lyra":
        raise MeasurementError("unexpected canonical subject")
    physical = data["physical_self"]
    if physical.get("form") != "human" or not {"fox ears", "fox tail"}.issubset(
        physical.get("additional_features", ())
    ):
        raise MeasurementError("canonical embodiment missing")
    values: dict[str, float] = {}
    for name in CANONICAL_TARGETS:
        item = physical["measurements"][name]
        expected_unit = "lb" if name == "weight" else "in"
        # Weight is intentionally NOT part of CANONICAL_TARGETS or geometry.
        if item.get("unit") != "in" or type(item.get("value")) not in (int, float):
            raise MeasurementError(f"invalid {name} unit/value")
        value = float(item["value"])
        if not 0.0 < value < 300.0:
            raise MeasurementError(f"invalid {name} value")
        values[name] = value * 0.0254
    if not 1.0 < values["height"] < 2.5:
        raise MeasurementError("height is outside the authoring range")
    if not values["hips"] > values["waist"] or not values["bust"] > values["underbust"]:
        raise MeasurementError("unexpected girth relationships; review source")
    colors = {}
    for name in ("skin_hex", "hair_hex"):
        value = physical["appearance"].get(name)
        if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
            raise MeasurementError(f"missing {name}")
        try:
            bytes.fromhex(value[1:])
        except ValueError as error:
            raise MeasurementError(f"invalid {name}") from error
        colors[name] = value.upper()
    return values, sha256(raw).hexdigest(), colors


def ellipse_vertices(*, circumference: float, x_over_y: float, count: int = RING_COUNT):
    """Scale a polygonal ellipse to its exact discrete perimeter in meters."""
    import numpy as np
    theta = 2 * np.pi * np.arange(count) / count
    outline = np.stack((x_over_y * np.cos(theta), np.sin(theta)), axis=1)
    perimeter = float(np.linalg.norm(np.roll(outline, -1, axis=0) - outline, axis=1).sum())
    return outline * (circumference / perimeter)


def torso_mesh(values: dict[str, float]):
    """Closed ring-loft; measured girths follow actual mesh cross-sections."""
    import numpy as np
    import trimesh
    target = {name: values[name] for name in GIRTH_Z}
    vertices = []
    for z, name, factor, ratio in TORSO_PROFILE:
        # Noncanonical transition rings are interpolated/artist-proposed.
        if name in target:
            girth = target[name]
        elif name == "pelvis_lower":
            girth = values["hips"] * 0.94
        elif name == "hip_transition":
            girth = (values["hips"] + values["waist"]) / 2
        elif name == "upper_chest":
            girth = values["bust"] * 0.96
        else:
            girth = values["underbust"] * 0.94
        ring = ellipse_vertices(circumference=girth * factor, x_over_y=ratio)
        vertices.extend((float(x), float(y), z) for x, y in ring)
    low_center = len(vertices)
    vertices.append((0.0, 0.0, TORSO_PROFILE[0][0]))
    high_center = len(vertices)
    vertices.append((0.0, 0.0, TORSO_PROFILE[-1][0]))
    faces = []
    for r in range(len(TORSO_PROFILE) - 1):
        for i in range(RING_COUNT):
            j = (i + 1) % RING_COUNT
            a, b, c, d = r * RING_COUNT + i, r * RING_COUNT + j, (r + 1) * RING_COUNT + i, (r + 1) * RING_COUNT + j
            faces.extend(((a, b, d), (a, d, c)))
    last = (len(TORSO_PROFILE) - 1) * RING_COUNT
    for i in range(RING_COUNT):
        j = (i + 1) % RING_COUNT
        faces.extend(((low_center, j, i), (high_center, last + i, last + j)))
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    if not mesh.is_watertight:
        raise MeasurementError("torso loft is not watertight")
    return mesh


def measure_girth(mesh: Any, z: float) -> float:
    """Measure the actual torso surface at a z-plane, not its bounding box."""
    import numpy as np
    section = mesh.section(plane_origin=(0, 0, z), plane_normal=(0, 0, 1))
    if section is None or len(section.discrete) != 1:
        raise MeasurementError("cross-section must contain one closed loop")
    points = np.asarray(section.discrete[0], dtype=float)
    if len(points) < 4 or not np.allclose(points[0], points[-1], atol=1e-7):
        raise MeasurementError("cross-section is open")
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def build_scene(values: dict[str, float], colors: dict[str, str]):
    """Proportional skeletal-form blockout with a calibrated torso; no fine anatomy."""
    import numpy as np
    import trimesh
    scene = trimesh.Scene()
    nodes: dict[str, dict[str, str]] = {}
    def add(name: str, mesh: Any, color: str, region: str) -> None:
        mesh.visual.vertex_colors = np.tile(
            np.array([*bytes.fromhex(color[1:]), 255], dtype=np.uint8), (len(mesh.vertices), 1)
        )
        scene.add_geometry(mesh, geom_name=name, node_name=name)
        nodes[name] = {"region": region, "detail": "ARTIST_ESTIMATE_blockout"}
    def orb(name: str, center: tuple[float, float, float], radii: tuple[float, float, float], color: str, region: str):
        mesh = trimesh.creation.uv_sphere(radius=1, count=(32, 32))
        mesh.apply_scale(radii)
        mesh.apply_translation(center)
        add(name, mesh, color, region)
    def segment(name: str, start: tuple[float, float, float], end: tuple[float, float, float], r1: float, r2: float, color: str, region: str):
        a, b = np.array(start, float), np.array(end, float)
        vector = b - a
        length = float(np.linalg.norm(vector))
        if length < 1e-6:
            raise MeasurementError("zero-length segment")
        theta = 2 * np.pi * np.arange(32) / 32
        v = np.vstack((np.stack((r1 * np.cos(theta), r1 * np.sin(theta), np.zeros(32)), axis=1),
                       np.stack((r2 * np.cos(theta), r2 * np.sin(theta), np.full(32, length)), axis=1)))
        faces = []
        for i in range(32):
            j = (i + 1) % 32
            faces.extend(((i, j, 32+j), (i, 32+j, 32+i)))
        mesh = trimesh.Trimesh(vertices=v, faces=faces, process=False)
        mesh.apply_transform(trimesh.geometry.align_vectors((0, 0, 1), vector))
        mesh.apply_translation(a)
        add(name, mesh, color, region)
    skin = colors["skin_hex"]
    hair = colors["hair_hex"]
    add("BODY_TORSO_MEASUREMENT_PROXY", torso_mesh(values), skin, "torso")
    height = values["height"]
    # Center/head radius scaled from actual crown height; ears and hair excluded.
    head_radius_z = 0.153
    crown = height
    orb("BODY_HEAD_CROWN_REFERENCE", (0, 0, crown - head_radius_z), (0.105, 0.102, head_radius_z), skin, "head")
    segment("BODY_NECK_PROXY", (0, 0, 1.355), (0, 0, height - 0.265), 0.050, 0.049, skin, "neck")
    for side, sign in (("LEFT", -1), ("RIGHT", 1)):
        x = sign * 0.195
        segment(f"BODY_{side}_UPPER_ARM_PROXY", (x, 0, 1.325), (sign * 0.292, 0, 1.05), 0.071, 0.052, skin, "upper_arm")
        segment(f"BODY_{side}_FOREARM_PROXY", (sign * 0.292, 0, 1.05), (sign * 0.335, -0.02, 0.83), 0.050, 0.033, skin, "forearm")
        orb(f"BODY_{side}_HAND_PROXY", (sign * 0.346, -0.02, 0.765), (0.040, 0.036, 0.085), skin, "hand")
        segment(f"BODY_{side}_THIGH_PROXY", (sign * 0.105, 0, 0.84), (sign * 0.122, 0, 0.46), 0.107, 0.075, skin, "thigh")
        segment(f"BODY_{side}_CALF_PROXY", (sign * 0.122, 0, 0.46), (sign * 0.125, 0, 0.103), 0.073, 0.043, skin, "calf")
        orb(f"BODY_{side}_FOOT_FLOOR_REFERENCE", (sign * 0.126, -0.072, 0.046), (0.067, 0.138, 0.046), skin, "foot")
        segment(f"FOX_EAR_{side}_PROXY", (sign * 0.071, 0.01, crown - 0.025), (sign * 0.101, 0.015, crown + 0.15), 0.048, 0.006, "#3A245C", "fox_ear")
    # +Y denotes posterior. Tail root is separate from anatomical landmarks.
    orb("FOX_TAIL_ROOT_PROXY", (0, 0.155, 0.895), (0.075, 0.104, 0.085), "#3A245C", "tail")
    orb("FOX_TAIL_VOLUME_PROXY", (0.025, 0.295, 0.755), (0.085, 0.165, 0.095), "#3A245C", "tail")
    orb("FOX_TAIL_TIP_PROXY", (0.045, 0.432, 0.80), (0.063, 0.103, 0.075), "#79578F", "tail")
    # Named landmarks are metadata only, NOT detailed sculpted anatomy.
    return scene, nodes


def export(*, canonical_path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Fail closed, no overwrites; outputs are controlled authoring assets."""
    values, source_hash, colors = read_canonical(canonical_path)
    if not output_dir.is_dir() or output_dir.is_symlink():
        raise MeasurementError("output must be a pre-existing non-symlink directory")
    glb = output_dir / "sofia_a1_measured_body_proxy.glb"
    manifest = output_dir / "sofia_a1_measured_body_proxy.json"
    if any(path.exists() or path.is_symlink() for path in (glb, manifest)):
        raise MeasurementError("refusing to overwrite existing authoring outputs")
    torso = torso_mesh(values)
    result = {}
    for name, z in GIRTH_Z.items():
        actual = measure_girth(torso, z)
        target = values[name]
        result[name] = {"target_m": target, "measured_m": actual, "error_mm": (actual-target)*1000, "z_m": z}
        if abs(actual - target) > 0.0005:
            raise MeasurementError(f"{name} circumference out of 0.5mm tolerance")
    scene, nodes = build_scene(values, colors)
    blob = scene.export(file_type="glb")
    if not isinstance(blob, bytes) or not blob.startswith(b"glTF"):
        raise MeasurementError("GLB generation failed")
    record = {
        "schema": "sofia.avatar.a1.measured-proxy.v1",
        "asset_class": "controlled_authoring_only_never_runtime_or_public",
        "stage": "measured_blockout_NOT_anatomically_complete_NOT_rigged_NOT_blender_reviewed",
        "canonical_sha256": source_hash, "glb_sha256": sha256(blob).hexdigest(),
        "units": "meters", "axis_up": "+Z", "forward": "-Y", "human_height_m": values["height"],
        "height_definition": "barefoot floor-to-human-head-crown; fox ears/hair/tail excluded",
        "measurements": result, "nodes": nodes,
        "artist_estimates": {
            "girth_planes_z_m": GIRTH_Z, "torso_profile": [list(row) for row in TORSO_PROFILE],
            "head_limbs_ears_tail": "unapproved proportions; see script source",
        },
        "unimplemented": ["detailed_anatomy", "anatomical_sculpt", "unified_body_topology", "skin_weights", "rig", "fitted_clothing", "blender_visual_approval", "renderer", "restricted_preview"],
        "normal_display": "separately verified clothed asset or non-body placeholder",
    }
    created = []
    try:
        for path, payload in ((glb, blob), (manifest, (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode("utf-8"))):
            with path.open("xb") as out:
                created.append(path)
                out.write(payload)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return glb, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=Path("src/sofia/data/avatar.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    files = export(canonical_path=args.canonical, output_dir=args.output_dir)
    for path in files:
        print(path)


if __name__ == "__main__":
    main()
