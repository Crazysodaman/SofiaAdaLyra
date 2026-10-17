"""Actual committed PNG archive + read-only public startup diagnostics."""
from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
import json
import sqlite3
import zipfile

from sofia.avatar.vtuber_public_diagnose import diagnose_public_avatar2d
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


_ARCHIVE = files("sofia.avatar").joinpath(
    "assets/sofia2d_public_illustrated_candidates_v1.zip"
)


def _setup(tmp_path, *, outfit="day.default", private=False, corrupted=False):
    catalog = build_starter_wardrobe()
    preset = next(p for p in catalog.presets if p.outfit_id == outfit)
    default = next(p for p in catalog.presets if p.outfit_id == "day.default")
    root = tmp_path / "Local" / "SofiaAdaLyra" / "Avatar2D" / "Public-V2"
    (root / "character").mkdir(parents=True)
    (root / "outfits" / "day.default").mkdir(parents=True)
    (root / "character" / "manifest.json").write_text("{}")
    (root / "outfits" / "day.default" / "manifest.json").write_text("{}")
    with as_file(_ARCHIVE) as archive_path:
        with zipfile.ZipFile(archive_path) as archive:
            for entry in archive.namelist():
                if entry.startswith("portraits/day.default/"):
                    target = root / entry
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))
    if corrupted:
        (root / "portraits" / "day.default" / "portrait.png").write_bytes(b"broken")

    state = tmp_path / "sofia.db"
    with sqlite3.connect(state) as db:
        db.execute(
            "CREATE TABLE avatar_presentation_state ("
            "state_key TEXT PRIMARY KEY, snapshot_json TEXT, updated_at TEXT)"
        )
        public = {
            "revision": 2, "attire": "clothed",
            "outfit_id": preset.outfit_id, "item_ids": list(preset.item_ids),
            "private_only": False,
        }
        if private:
            public = {
                "revision": 3, "attire": "nude",
                "outfit_id": None, "item_ids": [], "private_only": True,
            }
        safe = {
            "revision": 1, "attire": "clothed",
            "outfit_id": default.outfit_id,
            "item_ids": list(default.item_ids), "private_only": False,
        }
        db.execute(
            "INSERT INTO avatar_presentation_state VALUES ('canonical', ?, '')",
            (json.dumps({"current": public, "last_daily": safe}),),
        )
    return root, state


def test_actual_binary_pack_selected_for_public_day_default(tmp_path):
    root, state = _setup(tmp_path)
    actual = diagnose_public_avatar2d(
        state_path=state, local_app_data=str(tmp_path / "Local"),
        configured_root=None,
    )
    assert actual["status"] == "ILLUSTRATED_PORTRAIT_VALID"
    assert actual["portrait_bytes"] > 50000
    assert actual["active_public_outfit"] == "day.default"


def test_diagnostic_reports_old_explicit_path_even_when_v2_exists(tmp_path):
    root, state = _setup(tmp_path)
    old = tmp_path / "old-install"
    old.mkdir()
    report = diagnose_public_avatar2d(
        state_path=state, local_app_data=str(tmp_path / "Local"),
        configured_root=str(old),
    )
    assert report["root_selection"] == "explicit environment override"
    assert report["effective_root"] == str(old)
    assert report["status"] == "INCOMPLETE_PUBLIC_ASSET_ROOT"


def test_diagnostic_reports_unillustrated_current_outfit(tmp_path):
    root, state = _setup(tmp_path, outfit="outfit.circuit_casual")
    actual = diagnose_public_avatar2d(
        state_path=state, local_app_data=str(tmp_path / "Local"),
        configured_root=None,
    )
    assert actual["status"] == "NO_ILLUSTRATED_PORTRAIT_FOR_ACTIVE_OUTFIT"
    assert actual["active_public_outfit"] == "outfit.circuit_casual"


def test_diagnostic_rejects_corrupted_binary_pack(tmp_path):
    root, state = _setup(tmp_path, corrupted=True)
    actual = diagnose_public_avatar2d(
        state_path=state, local_app_data=str(tmp_path / "Local"),
        configured_root=None,
    )
    assert actual["status"] == "ILLUSTRATED_PORTRAIT_REJECTED"
    assert "checksum" in actual["detail"]


def test_diagnostic_uses_safe_daily_if_current_is_private(tmp_path):
    root, state = _setup(tmp_path, private=True)
    result = diagnose_public_avatar2d(
        state_path=state, local_app_data=str(tmp_path / "Local"),
        configured_root=None,
    )
    assert result["status"] == "ILLUSTRATED_PORTRAIT_VALID"
    assert result["active_public_outfit"] == "day.default"
    assert "private current hidden" in result["presentation_source"]


def test_diagnostic_does_not_create_missing_database_or_art_root(tmp_path):
    state = tmp_path / "missing" / "sofia.db"
    result = diagnose_public_avatar2d(
        state_path=state, local_app_data=str(tmp_path / "Local"),
        configured_root=None,
    )
    assert result["status"] == "NO_PUBLIC_ASSET_ROOT"
    assert not state.exists()
    assert not (tmp_path / "Local").exists()
