"""Explicit public scene-pack installation, ZIP-safe and without DB mutation.

The owner downloads an illustrated scene pack and opts in to install it.
The pack is never read automatically by the live renderer from Downloads.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from zipfile import ZipFile, BadZipFile

from .presentation import AppearanceState, AttireMode, AudienceScope, PresentationProjection
from .scene_compositor import (
    SceneSettings, _identifier, _verify_png, load_public_background,
    load_scene_preset, scene_png_bytes,
)
from .vtuber_static_portraits import load_public_static_portrait
from .vtuber_asset_bundle import Avatar2DAssetError
from .wardrobe_catalog import build_starter_wardrobe
from sofia.modules.ui.avatar2d_installation import discover_public_avatar2d_root


_REQUIRED = (
    "portraits/outfit.autumn_cyber/portrait.png",
    "portraits/outfit.autumn_cyber/manifest.json",
    "scenes/backgrounds/autumn_neon/background.png",
    "scenes/backgrounds/autumn_neon/manifest.json",
    "scenes/presets/outfit.autumn_cyber.json",
)
_ALLOWED = frozenset((*_REQUIRED, "PUBLIC_SCENE_README.txt"))
_MAX_ZIP = 20 * 1024 * 1024
_MAX_UNCOMPRESSED = 25 * 1024 * 1024


def _safe_zip_bytes(archive: Path):
    if not archive.is_file() or archive.is_symlink() or archive.stat().st_size > _MAX_ZIP:
        raise Avatar2DAssetError("invalid or oversized public scene archive")
    try:
        with ZipFile(archive) as reader:
            infos = reader.infolist()
            names = [i.filename for i in infos]
            if (
                not set(_REQUIRED).issubset(names)
                or len(names) != len(set(names))
                or any(name not in _ALLOWED for name in names)
                or any(i.is_dir() or i.file_size > _MAX_UNCOMPRESSED for i in infos)
                or sum(i.file_size for i in infos) > _MAX_UNCOMPRESSED
                or any((i.external_attr >> 16) & 0o170000 == stat.S_IFLNK for i in infos)
            ):
                raise Avatar2DAssetError("scene archive has unexpected files or unsafe entries")
            return {name: reader.read(name) for name in names}
    except (BadZipFile, OSError, ValueError, RuntimeError) as exc:
        raise Avatar2DAssetError("cannot read public scene archive") from exc


def install_public_scene_pack(archive: Path, root: Path, *, verify_only=False):
    """Verify all source-bound public artwork before writing any installation files.

    No private art and no changes to canonical sofia.db. This is a deliberately
    version-specific install; future packs require a separately reviewed spec.
    """
    root = Path(root)
    if root.is_symlink() or not (
        (root / "character" / "manifest.json").is_file()
        and (root / "outfits" / "day.default" / "manifest.json").is_file()
    ):
        raise Avatar2DAssetError("complete public base pack must be installed first")
    files = _safe_zip_bytes(Path(archive))
    preset = SceneSettings.from_dict(json.loads(files[
        "scenes/presets/outfit.autumn_cyber.json"
    ]))
    catalog = build_starter_wardrobe()
    approved = next((p for p in catalog.presets
        if p.outfit_id == preset.outfit_id and not p.private_only), None)
    if approved is None or preset.item_ids != approved.item_ids:
        raise Avatar2DAssetError("unapproved illustrated scene wardrobe")
    portrait_manifest = json.loads(files[
        "portraits/outfit.autumn_cyber/manifest.json"
    ])
    portrait_png = files["portraits/outfit.autumn_cyber/portrait.png"]
    bg_manifest = json.loads(files["scenes/backgrounds/autumn_neon/manifest.json"])
    bg_png = files["scenes/backgrounds/autumn_neon/background.png"]
    if (
        portrait_manifest.get("schema") != "sofia-public-illustrated-static-v1"
        or portrait_manifest.get("outfit_id") != preset.outfit_id
        or portrait_manifest.get("item_ids") != list(preset.item_ids)
        or portrait_manifest.get("public_only") is not True
        or portrait_manifest.get("quality") != "unreviewed_illustrated_candidate"
        or portrait_manifest.get("animation") != "static"
        or portrait_manifest.get("image_size") != [320, 400]
        or sha256(portrait_png).hexdigest() != portrait_manifest.get("portrait_sha256")
        or bg_manifest.get("schema") != "sofia.avatar2d.public_background.v1"
        or bg_manifest.get("id") != preset.background_id
        or bg_manifest.get("public_only") is not True
        or bg_manifest.get("sha256") != preset.background_sha256
        or sha256(bg_png).hexdigest() != preset.background_sha256
    ):
        raise Avatar2DAssetError("public illustrated scene identity/hash mismatch")
    _verify_png(portrait_png)
    _verify_png(bg_png)
    if portrait_png[16:24] != (320).to_bytes(4,"big") + (400).to_bytes(4,"big"):
        raise Avatar2DAssetError("portrait canvas dimensions mismatch")
    if int.from_bytes(bg_png[16:20],"big") * int.from_bytes(bg_png[20:24],"big") > 12_000_000:
        raise Avatar2DAssetError("background dimensions too large")
    targets = [root / path for path in _REQUIRED]
    if not verify_only and any(
        p.exists() or p.is_symlink() or any(parent.is_symlink() for parent in p.parents if parent != root)
        for p in targets
    ):
        raise FileExistsError("public scene assets already installed; no overwrite allowed")
    if verify_only:
        return preset
    stage = Path(tempfile.mkdtemp(prefix=".sofia-scene-stage-", dir=root))
    created = []
    try:
        for path in _REQUIRED:
            out = stage / path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(files[path])
        # Validate the actual staged structure through production loaders.
        proj = PresentationProjection(
            audience=AudienceScope.PUBLIC, source_revision=1,
            attire=AttireMode.CLOTHED, outfit_id=preset.outfit_id,
            item_ids=preset.item_ids,
            appearance=AppearanceState(
                hairstyle="long layered", hair_color="deep crimson",
                tail_color="dark violet", eye_color="violet",
            ),
            private_fallback_used=False, reason="verified public scene install",
        )
        if load_public_static_portrait(stage, proj, catalog=catalog) is None:
            raise Avatar2DAssetError("illustrated portrait staging failed")
        load_public_background(stage, preset.background_id, preset.background_sha256)
        if load_scene_preset(stage, proj, catalog=catalog) != preset:
            raise Avatar2DAssetError("public scene preset staging failed")
        scene_png_bytes(stage, proj, catalog=catalog, scene=preset)
        for path in _REQUIRED:
            dest = root / path
            if dest.is_symlink() or dest.exists():
                raise FileExistsError("scene install destination changed")
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / path, dest)
            created.append(dest)
        return preset
    except BaseException:
        for path in reversed(created):
            if path.exists():
                path.unlink()
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install verified PUBLIC Autumn Cyber 2D scene")
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    root = args.root or discover_public_avatar2d_root(
        os.environ.get("SOFIA_AVATAR2D_PUBLIC_ROOT"),
        local_app_data=os.environ.get("LOCALAPPDATA"),
    )
    if root is None:
        parser.error("public 2D pack not found")
    scene = install_public_scene_pack(args.archive, root, verify_only=args.verify_only)
    print(("Verified" if args.verify_only else "Installed") + " PUBLIC scene for " + scene.outfit_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
