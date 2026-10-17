"""Opt-in PUBLIC illustrated static portraits, with verified outfit binding.

A separate add-on archive may supply artwork under public_root/portraits.
Portraits are *static illustrated candidates*, not a modular/animated 2D rig.
A missing portrait permits the existing verified procedural renderer to work.
A malformed present portrait raises, so the UI switches to its safe fallback.
No protected private wardrobe can be represented through this public loader.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path, PurePosixPath

from .presentation import AttireMode, AudienceScope, PresentationProjection
from .vtuber_asset_bundle import Avatar2DAssetError, _read_file, _verify_png

_SCHEMA = "sofia-public-illustrated-static-v1"
_MAX_MANIFEST = 32 * 1024
_MAX_PNG = 2 * 1024 * 1024


def load_public_static_portrait(
    public_root: Path, projection: PresentationProjection, *, catalog
) -> bytes | None:
    """Return checked RGBA PNG bytes, or None when no compatible art exists.

    Match both the currently selected canonical public outfit and every
    selected item; never display stale clothing for a different wardrobe.
    This intentionally ignores private sessions and modified outfit mixes.
    """
    if (
        not isinstance(projection, PresentationProjection)
        or projection.audience is not AudienceScope.PUBLIC
        or projection.attire is not AttireMode.CLOTHED
        or not isinstance(projection.outfit_id, str)
        or not projection.outfit_id
    ):
        return None
    outfit_id = projection.outfit_id
    if (
        "/" in outfit_id or "\\" in outfit_id or outfit_id in (".", "..")
        or len(outfit_id) > 128
    ):
        raise Avatar2DAssetError("invalid static portrait outfit ID")

    approved = next(
        (p for p in catalog.presets
         if p.outfit_id == outfit_id and not p.private_only),
        None,
    )
    if approved is None or tuple(approved.item_ids) != tuple(projection.item_ids):
        return None

    directory = public_root / "portraits" / outfit_id
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists() and not manifest_path.is_symlink():
        return None
    manifest_raw = _read_file(
        directory, PurePosixPath("manifest.json"), limit=_MAX_MANIFEST
    )
    try:
        manifest = json.loads(manifest_raw)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise Avatar2DAssetError("invalid illustrated portrait manifest") from exc
    if not isinstance(manifest, dict) or any((
        manifest.get("schema") != _SCHEMA,
        manifest.get("outfit_id") != outfit_id,
        manifest.get("public_only") is not True,
        manifest.get("quality") != "unreviewed_illustrated_candidate",
        manifest.get("animation") != "static",
        manifest.get("image_size") != [320, 400],
        manifest.get("item_ids") != list(approved.item_ids),
    )):
        raise Avatar2DAssetError("static portrait metadata does not match outfit")

    digest = manifest.get("portrait_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise Avatar2DAssetError("static portrait digest missing")
    png = _read_file(directory, PurePosixPath("portrait.png"), limit=_MAX_PNG)
    if sha256(png).hexdigest() != digest:
        raise Avatar2DAssetError("static portrait checksum mismatch")
    _verify_png(png)
    if (
        int.from_bytes(png[16:20], "big") != 320
        or int.from_bytes(png[20:24], "big") != 400
    ):
        raise Avatar2DAssetError("static portrait canvas size mismatch")
    return png
