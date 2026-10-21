"""Read-only diagnostics for the illustrated PUBLIC Avatar2D startup path.

Never creates a state database, changes wardrobe state, or accesses private
art. A private current presentation is not disclosed; report the canonical
public last-daily fallback exactly as the public renderer should receive it.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3

from sofia.config import production_state_path
from sofia.state.sqlite_uri import sqlite_file_uri
from sofia.ui.avatar2d_installation import discover_public_avatar2d_root
from .presentation import (
    AppearanceState, AttireMode, AudienceScope, PresentationProjection,
)
from .vtuber_asset_bundle import Avatar2DAssetError
from .vtuber_static_portraits import load_public_static_portrait
from .scene_compositor import load_scene_preset, scene_png_bytes
from .wardrobe_catalog import build_starter_wardrobe


def _public_snapshot(state_path: Path) -> tuple[dict | None, str]:
    if not state_path.is_file():
        return None, "canonical database is absent at this location"
    try:
        uri = sqlite_file_uri(state_path.resolve(), read_only=True)
        with sqlite3.connect(uri, uri=True, timeout=2) as db:
            row = db.execute(
                "SELECT snapshot_json FROM avatar_presentation_state "
                "WHERE state_key='canonical'"
            ).fetchone()
        if row is None:
            return None, "no committed avatar presentation in canonical database"
        snapshot = json.loads(row[0])
        if not isinstance(snapshot, dict):
            return None, "invalid canonical presentation snapshot"
        current = snapshot.get("current")
        fallback = snapshot.get("last_daily")
        if not isinstance(current, dict) or not isinstance(fallback, dict):
            return None, "invalid canonical presentation state"
        # Report only the PUBLIC view. Do not print private current outfit IDs.
        if current.get("private_only") or current.get("attire") != "clothed":
            return fallback, "public last-daily fallback (private current hidden)"
        return current, "current public outfit"
    except (sqlite3.Error, ValueError, OSError, KeyError) as exc:
        return None, f"read-only canonical presentation unavailable: {type(exc).__name__}"


def diagnose_public_avatar2d(
    *,
    state_path: Path,
    local_app_data: str | None,
    configured_root: str | None,
) -> dict[str, object]:
    """Produce safe, deterministic diagnostic evidence without side effects."""
    root = discover_public_avatar2d_root(
        configured_root, local_app_data=local_app_data,
    )
    report: dict[str, object] = {
        "module": __file__,
        "canonical_db": str(state_path),
        "root_selection": (
            "explicit environment override" if configured_root and configured_root.strip()
            else "automatic Public-V2/Public-All/Public discovery"
        ),
        "effective_root": str(root) if root is not None else None,
    }
    if root is None:
        report["status"] = "NO_PUBLIC_ASSET_ROOT"
        report["action"] = (
            "Install public 2D pack or set SOFIA_AVATAR2D_PUBLIC_ROOT "
            "to the directory containing portraits/ and outfits/."
        )
        return report

    report["day_manifest_present"] = (
        root / "outfits" / "day.default" / "manifest.json"
    ).is_file()
    report["character_manifest_present"] = (
        root / "character" / "manifest.json"
    ).is_file()
    if not (report["day_manifest_present"] and report["character_manifest_present"]):
        report["status"] = "INCOMPLETE_PUBLIC_ASSET_ROOT"
        report["action"] = "Check SOFIA_AVATAR2D_PUBLIC_ROOT and reinstall into a fresh root."
        return report

    snapshot, explanation = _public_snapshot(state_path)
    report["presentation_source"] = explanation
    if snapshot is None:
        report["status"] = "CANNOT_IDENTIFY_ACTIVE_PUBLIC_OUTFIT"
        report["action"] = "Check the canonical db path and runtime startup configuration."
        return report

    outfit_id = snapshot.get("outfit_id")
    items = snapshot.get("item_ids")
    report["active_public_outfit"] = outfit_id
    report["active_item_count"] = len(items) if isinstance(items, list) else None
    if not isinstance(outfit_id, str) or not isinstance(items, list):
        report["status"] = "INVALID_PUBLIC_PRESENTATION"
        return report

    directory = root / "portraits" / outfit_id
    report["portrait_manifest_present"] = (
        directory / "manifest.json"
    ).is_file()
    # Inspect current approved public wardrobe without constructing any
    # database-writing Store object. Review overlay rows are read-only.
    catalog = build_starter_wardrobe(state_path=state_path)
    if state_path.is_file():
        try:
            from .wardrobe_review import apply_document
            uri = sqlite_file_uri(state_path.resolve(), read_only=True)
            with sqlite3.connect(uri, uri=True, timeout=2) as db:
                try:
                    reviews = db.execute(
                        "SELECT kind,payload_json FROM avatar_wardrobe_reviews "
                        "WHERE status='approved' ORDER BY sequence"
                    ).fetchall()
                except sqlite3.OperationalError as exc:
                    if "no such table" not in str(exc):
                        raise
                    reviews = []
            for kind, encoded in reviews:
                catalog = apply_document(catalog, kind, json.loads(encoded))
        except (sqlite3.Error, ValueError, OSError, TypeError) as exc:
            report["status"] = "CANNOT_READ_APPROVED_WARDROBE"
            report["detail"] = type(exc).__name__
            return report

    preset = next((
        p for p in catalog.presets if p.outfit_id == outfit_id
        and not p.private_only
    ), None)
    if preset is None or list(preset.item_ids) != items:
        report["status"] = "ACTIVE_OUTFIT_ITEMS_DIFFER_FROM_PRESET"
        report["action"] = "The current public outfit does not match its approved preset."
        return report

    try:
        projection = PresentationProjection(
            audience=AudienceScope.PUBLIC,
            source_revision=int(snapshot.get("revision", 1)),
            attire=AttireMode.CLOTHED,
            outfit_id=outfit_id,
            item_ids=tuple(items),
            appearance=AppearanceState(
                hairstyle="layered", hair_color="deep crimson",
                tail_color="dark violet",
            ),
            private_fallback_used=False,
            reason="read-only static portrait verification",
        )
        png = load_public_static_portrait(root, projection, catalog=catalog)
    except (Avatar2DAssetError, ValueError, TypeError, OSError) as exc:
        report["status"] = "ILLUSTRATED_PORTRAIT_REJECTED"
        report["detail"] = f"{type(exc).__name__}: {exc}"
        report["action"] = "Check the portrait manifest, garment IDs, and PNG digest."
        return report
    # Evaluate independent owner-saved static scenes as well. The portrait
    # may be valid while its background is missing, tampered, or stale.
    try:
        scene = load_scene_preset(root, projection, catalog=catalog)
        report["scene_manifest_present"] = scene is not None
        if scene is None:
            report["scene_status"] = "NO_SAVED_PUBLIC_SCENE"
        else:
            composite, source = scene_png_bytes(
                root, projection, catalog=catalog, scene=scene,
            )
            report["scene_status"] = "SAVED_PUBLIC_SCENE_VALID"
            report["scene_source"] = source
            report["scene_png_bytes"] = len(composite)
    except (Avatar2DAssetError, ValueError, TypeError, OSError, RuntimeError) as exc:
        report["scene_status"] = "SAVED_PUBLIC_SCENE_REJECTED"
        report["scene_detail"] = f"{type(exc).__name__}: {exc}"
        report["status"] = "SAVED_PUBLIC_SCENE_REJECTED"
        report["action"] = "Review the saved public scene preset and imported background."
        return report
    if png is not None:
        report["status"] = "ILLUSTRATED_PORTRAIT_VALID"
        report["portrait_bytes"] = len(png)
    elif report.get("scene_status") == "SAVED_PUBLIC_SCENE_VALID":
        report["status"] = "SAVED_PUBLIC_SCENE_VALID"
    else:
        report["status"] = "NO_ILLUSTRATED_PORTRAIT_FOR_ACTIVE_OUTFIT"
        report["action"] = (
            "The active public outfit has no illustrated portrait or verified "
            "saved background scene. Select an included outfit or install "
            "an exact portrait for the current public outfit."
        )
        return report
    report["action"] = (
        "If the old sprite is still displayed, restart Sofía and check the "
        "renderer instance, 2D mode, and SOFIA_AVATAR2D_PUBLIC_ROOT override."
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only diagnostic for the active PUBLIC illustrated 2D portrait",
    )
    parser.add_argument("--state-path", type=Path, default=None)
    args = parser.parse_args(argv)
    result = diagnose_public_avatar2d(
        state_path=args.state_path or production_state_path(),
        local_app_data=os.getenv("LOCALAPPDATA"),
        configured_root=os.getenv("SOFIA_AVATAR2D_PUBLIC_ROOT"),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ILLUSTRATED_PORTRAIT_VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
