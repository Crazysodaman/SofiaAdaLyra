"""Public-only, source-bound illustrated scenes and modular wardrobe compositing.

Phase A: compose a validated outfit portrait over a separately approved backdrop.
Phase B: versioned, editable scene placements saved outside canonical sofia.db.
Phase C: compose *existing verified* modular body/wardrobe/character PNG layers.
Unfitted generated clothing drafts are never accepted as fitted wardrobe assets.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

from .presentation import AttireMode, AudienceScope, PresentationProjection
from .vtuber_asset_bundle import (
    Avatar2DArtSelection, Avatar2DAssetError, _read_bundle, _read_file, _verify_png,
)
from .vtuber_character_bundle import load_selected_character_sprites
from .vtuber_character_selection import select_character_parts
from .vtuber_layer_stack import assemble_avatar2d_layers
from .vtuber_static_portraits import load_public_static_portrait
from .wardrobe_matrix import build_wardrobe_matrix

_SCENE_SCHEMA = "sofia.avatar2d.public_scene.v1"
_BACKGROUND_SCHEMA = "sofia.avatar2d.public_background.v1"
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_BACKGROUND = 16 * 1024 * 1024
_MAX_IMAGE_PIXELS = 12_000_000
_MAX_PRESET = 16 * 1024

# Full alpha compositor is deliberately Pillow-backed. It is not a hallucinated
# rig and can run offline without a model, browser, or owner database writes.


def _pil():
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as exc:
        raise RuntimeError("Scene compositing needs Pillow: python -m pip install Pillow") from exc
    return Image, ImageFilter, ImageOps


def _identifier(value: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise Avatar2DAssetError("invalid public scene identifier")
    return value


def _digest(value: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise Avatar2DAssetError("invalid public scene asset hash")
    return value


@dataclass(frozen=True)
class SceneSettings:
    outfit_id: str
    item_ids: tuple[str, ...]
    background_id: str
    background_sha256: str
    scale: float = 0.85
    x: float = 0.5
    y: float = 1.0  # normalized bottom anchor
    background_fit: str = "cover"
    blur: float = 0.0
    dim: float = 0.0
    shadow: float = 0.2
    width: int = 640
    height: int = 800
    version: int = 1

    def __post_init__(self):
        _identifier(self.outfit_id)
        _identifier(self.background_id)
        _digest(self.background_sha256)
        if (
            not isinstance(self.item_ids, tuple)
            or not self.item_ids
            or any(not isinstance(v, str) or _ID.fullmatch(v) is None for v in self.item_ids)
            or len(set(self.item_ids)) != len(self.item_ids)
        ):
            raise Avatar2DAssetError("invalid public scene garment list")
        if self.background_fit not in ("cover", "contain"):
            raise Avatar2DAssetError("invalid public background fit")
        for label, low, high in (
            ("scale", .15, 3), ("x", -0.25, 1.25), ("y", 0, 1.5),
            ("blur", 0, 16), ("dim", 0, .9), ("shadow", 0, 1),
        ):
            v = getattr(self, label)
            if not isinstance(v, (float, int)) or isinstance(v, bool) or not math.isfinite(v) or not low <= v <= high:
                raise Avatar2DAssetError("invalid public scene " + label)
        if (
            type(self.width) is not int or type(self.height) is not int
            or not 240 <= self.width <= 2048 or not 240 <= self.height <= 2048
            or self.width * self.height > 2_500_000
            or self.version != 1
        ):
            raise Avatar2DAssetError("invalid public scene size/version")

    def as_dict(self):
        return {
            "schema": _SCENE_SCHEMA, "version": self.version,
            "outfit_id": self.outfit_id, "item_ids": list(self.item_ids),
            "background_id": self.background_id, "background_sha256": self.background_sha256,
            "scale": self.scale, "x": self.x, "y": self.y,
            "background_fit": self.background_fit, "blur": self.blur,
            "dim": self.dim, "shadow": self.shadow,
            "width": self.width, "height": self.height,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != set(cls(
            outfit_id="valid", item_ids=("valid",),
            background_id="valid", background_sha256="0" * 64,
        ).as_dict()):
            raise Avatar2DAssetError("invalid public scene preset fields")
        if data["schema"] != _SCENE_SCHEMA or type(data["version"]) is not int:
            raise Avatar2DAssetError("unsupported public scene preset")
        if not isinstance(data["item_ids"], list):
            raise Avatar2DAssetError("public scene garment IDs must be a list")
        return cls(**{
            key: (tuple(value) if key == "item_ids" else value)
            for key, value in data.items() if key != "schema"
        })


def _public_preset(catalog, projection: PresentationProjection):
    if not isinstance(projection, PresentationProjection):
        raise Avatar2DAssetError("trusted public avatar projection required")
    if (
        projection.audience is not AudienceScope.PUBLIC
        or projection.attire is not AttireMode.CLOTHED
        or not projection.outfit_id
    ):
        raise Avatar2DAssetError("scenes require clothed PUBLIC avatar presentation")
    approved = next((p for p in catalog.presets
        if p.outfit_id == projection.outfit_id and not p.private_only
        and tuple(p.item_ids) == projection.item_ids), None)
    if approved is None:
        raise Avatar2DAssetError("scene outfit must match approved PUBLIC preset")
    # Avoid exposing protected overlays through a public screenshot.
    selected = catalog.wardrobe.selection(projection.item_ids)
    if selected.private_only or not selected.covered_default:
        raise Avatar2DAssetError("scene outfit is not public-safe")
    return approved


def preset_path(public_root: Path, outfit_id: str) -> Path:
    return public_root / "scenes" / "presets" / (_identifier(outfit_id) + ".json")


def load_scene_preset(public_root: Path, projection, *, catalog) -> SceneSettings | None:
    approved = _public_preset(catalog, projection)
    directory = public_root / "scenes" / "presets"
    file = directory / (approved.outfit_id + ".json")
    if not file.exists() and not file.is_symlink():
        return None
    raw = _read_file(directory, PurePosixPath(file.name), limit=_MAX_PRESET)
    try:
        scene = SceneSettings.from_dict(json.loads(raw))
    except (ValueError, TypeError, KeyError) as exc:
        raise Avatar2DAssetError("invalid public scene JSON") from exc
    if scene.outfit_id != approved.outfit_id or scene.item_ids != approved.item_ids:
        raise Avatar2DAssetError("scene outfit is stale or mismatched")
    return scene


def save_scene_preset(public_root: Path, scene: SceneSettings, *, catalog, replace_existing=False) -> Path:
    """Owner-initiated save; does not modify sofia.db or overwrite by default."""
    approved = next((p for p in catalog.presets
        if p.outfit_id == scene.outfit_id and not p.private_only
        and p.item_ids == scene.item_ids), None)
    if approved is None or not catalog.wardrobe.selection(scene.item_ids).covered_default:
        raise Avatar2DAssetError("scene cannot save a private or stale outfit")
    load_public_background(public_root, scene.background_id, scene.background_sha256)
    destination = preset_path(public_root, scene.outfit_id)
    directory = destination.parent
    if directory.is_symlink() or destination.is_symlink():
        raise Avatar2DAssetError("linked public scene destination refused")
    directory.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not replace_existing:
        raise FileExistsError("scene preset exists; explicitly request replacement")
    payload = json.dumps(scene.as_dict(), sort_keys=True, indent=2).encode("utf-8") + b"\n"
    fd, tmp = tempfile.mkstemp(prefix=".scene-", suffix=".json.tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        if not replace_existing and destination.exists():
            raise FileExistsError("scene preset already created")
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return destination


def load_public_background(public_root: Path, background_id: str, expected_sha: str):
    """Require owner-imported public PNG plus matching manifest and CRC checks."""
    _identifier(background_id)
    _digest(expected_sha)
    directory = public_root / "scenes" / "backgrounds" / background_id
    manifest_raw = _read_file(directory, PurePosixPath("manifest.json"), limit=2048)
    try:
        manifest = json.loads(manifest_raw)
    except (TypeError, ValueError) as exc:
        raise Avatar2DAssetError("invalid public background manifest") from exc
    if not isinstance(manifest, dict) or (
        manifest.get("schema") != _BACKGROUND_SCHEMA
        or manifest.get("id") != background_id
        or manifest.get("public_only") is not True
        or manifest.get("sha256") != expected_sha
    ):
        raise Avatar2DAssetError("public background manifest mismatch")
    png = _read_file(directory, PurePosixPath("background.png"), limit=_MAX_BACKGROUND)
    if sha256(png).hexdigest() != expected_sha:
        raise Avatar2DAssetError("public background bytes changed")
    _verify_png(png)
    pixels = int.from_bytes(png[16:20], "big") * int.from_bytes(png[20:24], "big")
    if pixels > _MAX_IMAGE_PIXELS:
        raise Avatar2DAssetError("public background exceeds pixel limit")
    return png


def import_public_background(public_root: Path, background_id: str, png_bytes: bytes):
    """Explicit owner import of transparent/opaque RGBA PNG, with immutable ID."""
    _identifier(background_id)
    if not isinstance(png_bytes, bytes) or not 0 < len(png_bytes) <= _MAX_BACKGROUND:
        raise Avatar2DAssetError("background PNG exceeds byte limit")
    _verify_png(png_bytes)
    if int.from_bytes(png_bytes[16:20], "big") * int.from_bytes(png_bytes[20:24], "big") > _MAX_IMAGE_PIXELS:
        raise Avatar2DAssetError("public background exceeds pixel limit")
    root = public_root / "scenes" / "backgrounds"
    if root.is_symlink():
        raise Avatar2DAssetError("background root symlink denied")
    root.mkdir(parents=True, exist_ok=True)
    target = root / background_id
    if target.exists() or target.is_symlink():
        raise FileExistsError("public background ID already installed")
    target.mkdir()
    digest = sha256(png_bytes).hexdigest()
    try:
        (target / "background.png").write_bytes(png_bytes)
        (target / "manifest.json").write_text(json.dumps({
            "schema": _BACKGROUND_SCHEMA, "id": background_id,
            "sha256": digest, "public_only": True,
        }, sort_keys=True), encoding="utf-8")
    except BaseException:
        # Never leave a partially trusted background manifest.
        for p in (target / "manifest.json", target / "background.png"):
            if p.exists():
                p.unlink()
        target.rmdir()
        raise
    return digest


def _decode_rgba(png):
    Image, _, _ = _pil()
    with Image.open(BytesIO(png)) as source:
        source.load()
        if source.width * source.height > _MAX_IMAGE_PIXELS:
            raise Avatar2DAssetError("public sprite dimensions too large")
        return source.convert("RGBA")


def compose_modular_public_outfit(public_root, projection, *, catalog):
    """Use the existing verified wardrobe stack, not generated unfitted drafts."""
    _public_preset(catalog, projection)
    directory = public_root / "outfits" / projection.outfit_id
    with _read_bundle(
        directory, audience=AudienceScope.PUBLIC,
        attire=AttireMode.CLOTHED, outfit_id=projection.outfit_id,
    ) as bundle:
        matrix = build_wardrobe_matrix(catalog, projection.item_ids)
        plan = assemble_avatar2d_layers(
            Avatar2DArtSelection("public", projection, bundle, "verified scene composition"),
            matrix=matrix,
        )
        modular = (public_root / "character" / "manifest.json").is_file()
        layers = []
        if modular:
            for sprite in plan.draw_layers:
                if sprite.role not in ("base_back", "base_face", "base_front"):
                    layers.append((sprite.stack_order, sprite.sprite_id, bytes(bundle.images[sprite.sprite_id])))
            selection = select_character_parts(
                projection, expression="neutral", optional_freckles=bool(
                    projection.appearance.freckles and
                    projection.appearance.freckles.casefold() not in ("none", "off", "false")
                ),
            )
            if selection.source_revision != projection.source_revision or selection.warnings:
                raise Avatar2DAssetError("unavailable matching modular appearance")
            order = {
                "tail": 50, "hair_back": 80, "ear_left": 100, "ear_right": 100,
                "face": 8000, "eye_left": 8100, "eye_right": 8100,
                "brow_left": 8200, "brow_right": 8200, "mouth": 8300,
                "freckles": 8400, "hair_front": 9000,
            }
            for sprite in load_selected_character_sprites(public_root / "character", selection):
                layers.append((order[sprite.group], sprite.group + "." + sprite.variant, sprite.png))
        else:
            layers.extend((sprite.stack_order, sprite.sprite_id, bytes(bundle.images[sprite.sprite_id])) for sprite in plan.draw_layers)
    Image, _, _ = _pil()
    canvas = Image.new("RGBA", (320, 400))
    for _, _, png in sorted(layers, key=lambda row: (row[0], row[1])):
        image = _decode_rgba(png)
        if image.size != (320, 400):
            raise Avatar2DAssetError("modular sprite canvas mismatch")
        canvas.alpha_composite(image)
    return canvas


def outfit_image(public_root, projection, *, catalog, allow_modular=True):
    _public_preset(catalog, projection)
    static = load_public_static_portrait(public_root, projection, catalog=catalog)
    if static is not None:
        return _decode_rgba(static), "illustrated static portrait"
    if not allow_modular:
        raise Avatar2DAssetError("no illustrated portrait for this PUBLIC outfit")
    return compose_modular_public_outfit(public_root, projection, catalog=catalog), "verified modular wardrobe sprites"


def compose_public_scene(public_root: Path, projection: PresentationProjection, *, catalog, scene: SceneSettings):
    """Return (Pillow RGBA Image, source detail) without mutating state."""
    approved = _public_preset(catalog, projection)
    if scene.outfit_id != approved.outfit_id or scene.item_ids != approved.item_ids:
        raise Avatar2DAssetError("scene does not match current public clothing")
    Image, ImageFilter, ImageOps = _pil()
    bg = _decode_rgba(load_public_background(public_root, scene.background_id, scene.background_sha256))
    target = (scene.width, scene.height)
    if scene.background_fit == "cover":
        bg = ImageOps.fit(bg, target, method=Image.Resampling.LANCZOS)
    else:
        bg.thumbnail(target, Image.Resampling.LANCZOS)
        surface = Image.new("RGBA", target, (8, 10, 17, 255))
        surface.alpha_composite(bg, ((target[0]-bg.width)//2, (target[1]-bg.height)//2))
        bg = surface
    if scene.blur:
        bg = bg.filter(ImageFilter.GaussianBlur(scene.blur))
    if scene.dim:
        veil = Image.new("RGBA", target, (0, 0, 0, round(scene.dim * 255)))
        bg = Image.alpha_composite(bg, veil)
    body, art_source = outfit_image(public_root, projection, catalog=catalog)
    # Scale as a factor of the canvas height, preserve body aspect ratio.
    new_height = max(1, round(scene.height * scene.scale))
    new_width = max(1, round(body.width * new_height / body.height))
    body = body.resize((new_width, new_height), Image.Resampling.LANCZOS)
    x = round(scene.width * scene.x - body.width / 2)
    y = round(scene.height * scene.y - body.height)
    if scene.shadow:
        mask = body.getchannel("A")
        blur = max(2, round(scene.width / 100))
        shadow_image = Image.new("RGBA", body.size, (0, 0, 0, round(145 * scene.shadow)))
        shadow_layer = Image.new("RGBA", target)
        shadow_layer.paste(shadow_image, (x + blur, y + blur), mask)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
        bg = Image.alpha_composite(bg, shadow_layer)
    layer = Image.new("RGBA", target)
    layer.alpha_composite(body, dest=(x, y))
    return Image.alpha_composite(bg, layer), art_source


def scene_png_bytes(public_root, projection, *, catalog, scene: SceneSettings):
    canvas, source = compose_public_scene(public_root, projection, catalog=catalog, scene=scene)
    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue(), source


def export_scene_png(public_root, projection, *, catalog, scene, destination: Path, replace_existing=False):
    """Explicit output path, no auto-export and no overwrite by default."""
    if destination.is_symlink() or destination.suffix.lower() != ".png":
        raise Avatar2DAssetError("scene export must be a nonlinked PNG path")
    data, _ = scene_png_bytes(public_root, projection, catalog=catalog, scene=scene)
    if destination.exists() and not replace_existing:
        raise FileExistsError("scene image exists; request replacement explicitly")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".sofia-scene-", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if destination.exists() and not replace_existing:
            raise FileExistsError("scene image created concurrently")
        os.replace(temp, destination)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return destination
