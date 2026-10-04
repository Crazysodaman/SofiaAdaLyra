from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from sofia.avatar.presentation_store import (
    PresentationStore,
    PresentationStoreError,
)
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.embodiment.store import AvatarStore


ROOT = Path(__file__).resolve().parents[1]
AVATAR_PATH = ROOT / "src" / "sofia" / "data" / "avatar.json"


def embodiment():
    return AvatarStore(AVATAR_PATH).load()


def old_snapshot(
    *,
    hair_color="#8B1E3F",
    tail_color="#3A245C",
    finished=None,
):
    appearance = {
        "hairstyle": "long layered",
        "hair_color": hair_color,
        "tail_color": tail_color,
        "style_tags": ["canonical", "engineer"],
    }
    return {
        "schema": "sofia.avatar.presentation.v1",
        "canonical_daily_outfit_id": "engineer.signature",
        "current": {
            "revision": 7,
            "attire": "clothed",
            "outfit_id": "lounge.relaxed",
            "item_ids": [
                "underlayer.top",
                "underlayer.bottom",
                "lounge.top",
                "lounge.sweats",
            ],
            "appearance": appearance,
            "private_only": False,
            "reason": "legacy late lounge",
        },
        "last_daily": {
            "revision": 6,
            "attire": "clothed",
            "outfit_id": "engineer.signature",
            "item_ids": [
                "underlayer.top",
                "underlayer.bottom",
                "engineer.shirt",
                "engineer.trousers",
            ],
            "appearance": appearance,
            "private_only": False,
            "reason": "legacy daily",
        },
        "finished": [] if finished is None else list(finished),
        "dynamic_outfits": [
            {
                "outfit_id": "dynamic.chat.old",
                "item_ids": ["engineer.shirt", "engineer.trousers"],
                "private_only": False,
            }
        ],
    }


def write_snapshot(path, snapshot):
    store = PresentationStore(path)
    with sqlite3.connect(path) as db:
        db.execute(
            """
            INSERT INTO avatar_presentation_state (
                state_key,
                snapshot_json,
                updated_at
            )
            VALUES ('canonical', ?, '2026-10-04T00:00:00+00:00')
            ON CONFLICT(state_key) DO UPDATE SET
                snapshot_json=excluded.snapshot_json,
                updated_at=excluded.updated_at
            """,
            (json.dumps(snapshot),),
        )
        db.commit()
    return store


def test_new_bootstrap_uses_new_day_default_and_semantic_colors(tmp_path):
    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=tmp_path / "sofia.db",
    )

    assert bundle.authority.current.outfit_id == "day.default"
    assert bundle.authority.current.appearance.hair_color == "deep crimson"
    assert bundle.authority.current.appearance.tail_color == "dark violet"


def test_old_database_wardrobe_snapshot_migrates_to_new_catalog(tmp_path):
    state_path = tmp_path / "sofia.db"
    write_snapshot(
        state_path,
        old_snapshot(finished=("legacy.cancelled",)),
    )

    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=state_path,
    )

    assert bundle.authority.current.outfit_id == "day.default"
    assert bundle.authority.last_daily.outfit_id == "day.default"
    assert bundle.authority.current.appearance.hair_color == "deep crimson"
    assert bundle.authority.current.appearance.tail_color == "dark violet"
    assert bundle.authority.snapshot()["finished"] == ["legacy.cancelled"]
    assert bundle.authority.snapshot()["dynamic_outfits"] == []


def test_old_snapshot_preserves_noncanonical_custom_appearance(tmp_path):
    state_path = tmp_path / "sofia.db"
    write_snapshot(
        state_path,
        old_snapshot(
            hair_color="#A63D5E",
            tail_color="#43265F",
        ),
    )

    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=state_path,
    )

    assert bundle.authority.current.appearance.hair_color == "#A63D5E"
    assert bundle.authority.current.appearance.tail_color == "#43265F"


def test_old_legacy_json_sidecar_is_migrated_and_retired(tmp_path):
    legacy_path = tmp_path / "avatar-presentation.json"
    legacy_path.write_text(
        json.dumps(old_snapshot(finished=("legacy.sidecar",))),
        encoding="utf-8",
    )

    state_path = tmp_path / "sofia.db"
    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=state_path,
    )

    assert bundle.authority.current.outfit_id == "day.default"
    assert bundle.authority.snapshot()["finished"] == ["legacy.sidecar"]
    assert not legacy_path.exists()
    assert (tmp_path / "avatar-presentation.json.migrated").is_file()


def test_unrecognized_invalid_snapshot_still_fails_closed(tmp_path):
    state_path = tmp_path / "sofia.db"
    snapshot = old_snapshot()
    snapshot["canonical_daily_outfit_id"] = "unknown.outfit"
    snapshot["current"]["outfit_id"] = "unknown.outfit"
    snapshot["last_daily"]["outfit_id"] = "unknown.outfit"
    write_snapshot(state_path, snapshot)

    with pytest.raises(PresentationStoreError):
        load_or_bootstrap_presentation(
            embodiment=embodiment(),
            state_path=state_path,
        )
