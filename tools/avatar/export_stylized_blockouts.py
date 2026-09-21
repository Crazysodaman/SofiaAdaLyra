"""Export two *dressed* A0 Sofía character blockouts as GLB + evidence manifests.

Optional art-authoring dependency: ``pip install trimesh numpy``. This tool does
not import Sofía's runtime, execute Blender, access the network, or change any
canonical files. A0 meshes have no rig, skin weights, fitted clothing or final
approved proportions. Import GLBs into Blender to inspect/edit individual parts.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

_CANON_COLORS = {"hair_hex": "#8B1E3F", "skin_hex": "#F1E9D8", "accent_hex": "#19D3C5"}
_HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
_VARIANTS = ("engineer", "lounge")


class BlockoutError(ValueError):
    """Invalid canonical input or unsafe destination; no files intentionally replaced."""


def load_canon(path: Path) -> tuple[dict[str, str], str]:
    """Read only known appearance fields; do not infer unspecified geometry."""
    data = path.read_bytes()
    source = json.loads(data.decode("utf-8-sig"))
    if source.get("subject") != "Sofía Ada Lyra":
        raise BlockoutError("unexpected canonical subject")
    physical = source["physical_self"]
    features = physical["additional_features"]
    if physical["form"] != "human" or not {"fox ears", "fox tail"}.issubset(features):
        raise BlockoutError("canonical fox embodiment not verified")
    appearance = physical["appearance"]
    colors = {}
    for name, expected in _CANON_COLORS.items():
        value = appearance.get(name)
        if not isinstance(value, str) or not _HEX.fullmatch(value):
            raise BlockoutError(f"missing or invalid canonical {name}")
        if value.upper() != expected.upper():
            raise BlockoutError(f"canonical {name} changed; review design before export")
        colors[name] = value.upper()
    return colors, sha256(data).hexdigest()


def build_scene(variant: str, colors: dict[str, str]):
    """Create modular preview geometry; names are stable *authoring* identifiers."""
    if variant not in _VARIANTS:
        raise BlockoutError("unknown outfit variant")
    import numpy as np
    import trimesh

    palette = {
        "skin": colors["skin_hex"], "hair": colors["hair_hex"],
        "teal": colors["accent_hex"], "violet": "#3A245C",
        "violet_light": "#79578F", "dark": "#0B0D12", "charcoal": "#171A21",
        "gunmetal": "#353742", "lounge": "#393047", "sweats": "#55515F",
        "eye": "#9A64C5", "leather": "#241A1B", "rose": "#B55A72",
    }
    scene = trimesh.Scene()
    nodes: dict[str, dict[str, object]] = {}

    def add(name: str, mesh, color: str, slot: str) -> None:
        if name in nodes or not _HEX.fullmatch(color):
            raise BlockoutError("duplicate node or invalid color")
        rgba = list(bytes.fromhex(color[1:])) + [255]
        mesh.visual.vertex_colors = np.tile(np.array(rgba, dtype=np.uint8), (len(mesh.vertices), 1))
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        nodes[name] = {"slot": slot, "color": color, "geometry_stage": "placeholder"}

    def ellipsoid(name, center, radii, color, slot, *, detail=1, tip=None):
        mesh = trimesh.creation.icosphere(subdivisions=detail, radius=1.0)
        mesh.apply_scale(radii)
        if tip is not None:
            vector = np.asarray(tip, dtype=float) - np.asarray(center, dtype=float)
            if np.linalg.norm(vector) < 1e-8:
                raise BlockoutError("invalid segment vector")
            mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], vector))
        mesh.apply_translation(center)
        add(name, mesh, color, slot)

    def box(name, center, size, color, slot):
        mesh = trimesh.creation.box(extents=size)
        mesh.apply_translation(center)
        add(name, mesh, color, slot)

    def segment(name, start, end, radius_a, radius_b, color, slot, *, sections=12):
        start = np.asarray(start, dtype=float)
        end = np.asarray(end, dtype=float)
        displacement = end - start
        length = float(np.linalg.norm(displacement))
        if length < 1e-8:
            raise BlockoutError("zero-length part")
        mesh = trimesh.creation.conical_frustum(
            height=length, radius_top=radius_b, radius_base=radius_a, sections=sections
        ) if hasattr(trimesh.creation, 'conical_frustum') else None
        if mesh is None:
            angles = np.arange(sections) * (2 * np.pi / sections)
            bottom = np.stack((radius_a * np.cos(angles), radius_a * np.sin(angles), np.zeros(sections)), axis=1)
            top = np.stack((radius_b * np.cos(angles), radius_b * np.sin(angles), np.full(sections, length)), axis=1)
            vertices = np.vstack((bottom, top, [[0, 0, 0], [0, 0, length]]))
            faces = []
            for i in range(sections):
                j = (i + 1) % sections
                faces.extend(((i, j, sections + j), (i, sections + j, sections + i),
                              (2 * sections, j, i), (2 * sections + 1, sections + i, sections + j)))
            mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        mesh.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], displacement))
        mesh.apply_translation(start)
        add(name, mesh, color, slot)

    # Upright Z in meters; y negative faces viewer. ALL proportions are A0 guesses.
    ellipsoid("BODY_FACE_GUIDE", (0, -0.012, 1.50), (0.117, 0.105, 0.151), palette["skin"], "head", detail=2)
    ellipsoid("HAIR_CRIMSON_CROWN", (0, 0.020, 1.605), (0.130, 0.114, 0.066), palette["hair"], "hair", detail=2)
    ellipsoid("HAIR_LONG_BACK", (0, 0.079, 1.31), (0.135, 0.065, 0.31), palette["hair"], "hair", detail=2)
    for side, sign in (("left", -1), ("right", 1)):
        x = sign * 0.082
        segment(f"FOX_EAR_{side.upper()}_VIOLET", (x, 0.022, 1.68), (x + sign * 0.021, 0.02, 1.88),
                0.068, 0.008, palette["violet"], "ears")
        segment(f"FOX_EAR_{side.upper()}_INNER", (x, -0.029, 1.70), (x + sign * 0.014, -0.028, 1.84),
                0.035, 0.004, palette["violet_light"], "ears")
        ellipsoid(f"EYE_{side.upper()}_VIOLET", (sign * 0.052, -0.105, 1.515),
                  (0.019, 0.009, 0.018), palette["eye"], "face", detail=2)
        ellipsoid(f"HAIR_SIDE_{side.upper()}", (sign * 0.12, 0.005, 1.38),
                  (0.040, 0.045, 0.23), palette["hair"], "hair")
    ellipsoid("NOSE_GUIDE", (0, -0.121, 1.468), (0.017, 0.018, 0.013), palette["skin"], "face")
    ellipsoid("TAIL_ROOT_VIOLET", (0, 0.15, 0.83), (0.092, 0.110, 0.090), palette["violet"], "tail")
    ellipsoid("TAIL_CURVE_VIOLET", (0.035, 0.292, 0.69), (0.105, 0.18, 0.10), palette["violet"], "tail", detail=2,
              tip=(0.06, 0.42, 0.75))
    ellipsoid("TAIL_TIP_LIGHT", (0.065, 0.441, 0.76), (0.074, 0.132, 0.077),
              palette["violet_light"], "tail", tip=(0.11, 0.55, 0.82))

    shirt_color = palette["charcoal"] if variant == "engineer" else palette["lounge"]
    pants_color = palette["dark"] if variant == "engineer" else palette["sweats"]
    ellipsoid("GARMENT_SHIRT_TORSO", (0, 0, 1.105), (0.22, 0.135, 0.315), shirt_color, "torso", detail=2)
    ellipsoid("GARMENT_PANTS_HIPS", (0, 0, 0.84), (0.21, 0.13, 0.155), pants_color, "pelvis", detail=2)
    for side, sign in (("left", -1), ("right", 1)):
        segment(f"GARMENT_SLEEVE_{side.upper()}", (sign * 0.20, 0, 1.30), (sign * 0.33, 0, 1.02),
                0.085 if variant == "lounge" else 0.068, 0.055, shirt_color, f"{side}_forearm")
        ellipsoid(f"BODY_HAND_{side.upper()}_GUIDE", (sign * 0.347, -0.009, 0.91),
                  (0.043, 0.047, 0.075), palette["skin"], f"{side}_hand")
        segment(f"GARMENT_PANTS_{side.upper()}_LEG", (sign * 0.115, 0, 0.82),
                (sign * 0.129, 0, 0.155), 0.112, 0.071, pants_color, f"{side}_leg")
        box(f"GARMENT_BOOT_{side.upper()}", (sign * 0.132, -0.041, 0.079),
            (0.155, 0.23, 0.14), palette["dark"], f"{side}_foot")
        if variant == "engineer":
            segment(f"GARMENT_LEATHER_GAUNTLET_{side.upper()}", (sign * 0.32, 0, 1.052),
                    (sign * 0.342, 0, 0.963), 0.064, 0.056, palette["leather"], f"{side}_wrist")
            box(f"GARMENT_BOOT_TEAL_DETAIL_{side.upper()}", (sign * 0.132, -0.158, 0.091),
                (0.07, 0.008, 0.017), palette["teal"], f"{side}_foot")
        else:
            box(f"GARMENT_SWEATPANTS_CUFF_{side.upper()}", (sign * 0.129, 0, 0.20),
                (0.125, 0.15, 0.055), palette["charcoal"], f"{side}_ankle")

    if variant == "engineer":
        ellipsoid("GARMENT_ENGINEER_JACKET", (0, 0.017, 1.105), (0.236, 0.152, 0.288),
                  palette["dark"], "torso", detail=2)
        box("GARMENT_JACKET_CRIMSON_TRIM", (-0.10, -0.142, 1.13), (0.016, 0.012, 0.33),
            palette["hair"], "torso")
        box("GARMENT_JACKET_TEAL_ID", (0.072, -0.144, 1.20), (0.056, 0.012, 0.019),
            palette["teal"], "torso")
        box("GARMENT_UTILITY_BELT", (0, -0.008, 0.86), (0.425, 0.28, 0.046),
            palette["gunmetal"], "waist")
        box("GARMENT_TOOL_POUCH", (0.204, -0.022, 0.77), (0.071, 0.16, 0.13),
            palette["charcoal"], "waist")
    else:
        box("GARMENT_LOUNGE_TEE_CYAN_DETAIL", (0, -0.138, 1.125), (0.077, 0.013, 0.018),
            palette["teal"], "torso")

    anchors = {"torso": [0, -0.19, 1.12], "pelvis": [0, -0.16, 0.84],
               "ears": [0, 0.02, 1.74], "tail": [0, 0.18, 0.83],
               "left_wrist": [-0.342, 0, 0.963], "right_wrist": [0.342, 0, 0.963],
               "left_hand": [-0.347, 0, 0.91], "right_hand": [0.347, 0, 0.91]}
    return scene, nodes, anchors


def export_blockouts(*, canon_path: Path, output_dir: Path) -> tuple[Path, ...]:
    """Explicit output directory; refuses overwrites and invalid canonical data."""
    colors, source_sha = load_canon(canon_path)
    if not output_dir.is_dir() or output_dir.is_symlink():
        raise BlockoutError("destination must be an existing ordinary directory")
    outputs = [output_dir / f"sofia_a0_{variant}.{ext}" for variant in _VARIANTS for ext in ("glb", "json")]
    if any(path.exists() or path.is_symlink() for path in outputs):
        raise BlockoutError("output exists: no overwriting or partial replacement")
    payloads = []
    for variant in _VARIANTS:
        scene, nodes, anchors = build_scene(variant, colors)
        blob = scene.export(file_type="glb")
        if not isinstance(blob, bytes) or not blob.startswith(b"glTF"):
            raise BlockoutError("invalid GLB export")
        manifest = {
            "schema": "sofia.avatar.a0.blockout.v1", "variant": variant,
            "stage": "preview_only_not_rigged_not_renderer_verified",
            "canonical_sha256": source_sha, "glb_sha256": sha256(blob).hexdigest(),
            "covered_default": True, "restricted_asset": False,
            "units": "meters_placeholder_proportions",
            "art_provenance": "original_procedural_preview; verify licensing before publication",
            "nodes": nodes, "anchors": anchors,
            "not_verified": ["body_proportions", "mesh_fit", "skin_weights", "animation", "canonical_slot_mapping", "public_renderer"],
        }
        payloads.extend((blob, (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()))
    created = []
    try:
        for path, payload in zip(outputs, payloads):
            with path.open("xb") as handle:
                created.append(path)
                handle.write(payload)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return tuple(outputs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canon", type=Path, required=True, help="Existing protected avatar.json, READ ONLY")
    parser.add_argument("--output-dir", type=Path, required=True, help="Existing empty/nonconflicting directory")
    args = parser.parse_args(argv)
    for path in export_blockouts(canon_path=args.canon, output_dir=args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
