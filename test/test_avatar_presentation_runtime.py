from __future__ import annotations

import json
from pathlib import Path

from sofia.avatar.presentation import AppearanceState, PresentationAuthority
from sofia.avatar.presentation_store import PresentationStore
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.embodiment.store import EmbodimentStore


ROOT = Path(__file__).resolve().parents[1]
AVATAR_PATH = ROOT / "src" / "sofia" / "data" / "avatar.json"


def embodiment():
    return EmbodimentStore(AVATAR_PATH).load()


def test_new_bootstrap_prefers_semantic_color_names(tmp_path):
    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=tmp_path / "sofia.db",
    )
    appearance = bundle.authority.current.appearance
    assert appearance.hair_color == "deep crimson"
    assert appearance.tail_color == "dark violet"


def test_legacy_revision_one_hex_bootstrap_is_migrated_and_persisted(tmp_path):
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    legacy = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle="long layered",
            hair_color="#8B1E3F",
            tail_color="#3A245C",
            style_tags=("canonical", "engineer"),
        ),
    )
    legacy_path = tmp_path / "avatar-presentation.json"
    legacy_path.write_text(
        json.dumps(legacy.snapshot()),
        encoding="utf-8",
    )

    state_path = tmp_path / "sofia.db"
    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=state_path,
    )
    assert bundle.authority.current.revision == 1
    assert bundle.authority.current.appearance.hair_color == "deep crimson"
    assert bundle.authority.current.appearance.tail_color == "dark violet"

    restored = PresentationStore(state_path).load(
        catalog.wardrobe,
        outfits=outfits,
    )
    assert restored.current.appearance.hair_color == "deep crimson"
    assert restored.current.appearance.tail_color == "dark violet"
    assert not legacy_path.exists()
    assert (tmp_path / "avatar-presentation.json.migrated").is_file()


def test_later_explicit_hex_appearance_is_not_rewritten(tmp_path):
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle="long layered",
            hair_color="deep crimson",
            tail_color="dark violet",
            style_tags=("canonical", "engineer"),
        ),
    )
    authority.propose_appearance(
        operation_id="appearance.custom",
        expected_revision=1,
        appearance=AppearanceState(
            hairstyle="messy side braid",
            hair_color="#A63D5E",
            tail_color="#43265F",
            style_tags=("lounge", "warm"),
        ),
        reason="reviewed custom appearance",
    )
    authority.commit_text(
        operation_id="appearance.custom",
        renderer_unavailable=True,
    )
    legacy_path = tmp_path / "avatar-presentation.json"
    legacy_path.write_text(
        json.dumps(authority.snapshot()),
        encoding="utf-8",
    )

    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=tmp_path / "sofia.db",
    )
    assert bundle.authority.current.revision == 2
    assert bundle.authority.current.appearance.hair_color == "#A63D5E"
    assert bundle.authority.current.appearance.tail_color == "#43265F"



def test_legacy_color_migration_preserves_finished_operation_history(
    tmp_path,
):
    catalog = build_starter_wardrobe()
    outfits = {
        plan.outfit_id: plan.item_ids
        for plan in catalog.presets
    }
    legacy = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle="long layered",
            hair_color="#8B1E3F",
            tail_color="#3A245C",
            style_tags=("canonical", "engineer"),
        ),
    )
    legacy.propose_outfit(
        operation_id="legacy.cancelled",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="cancelled before migration",
        daily=True,
    )
    legacy.cancel(operation_id="legacy.cancelled")
    assert legacy.current.revision == 1
    assert legacy.snapshot()["finished"] == ["legacy.cancelled"]

    state_path = tmp_path / "sofia.db"
    PresentationStore(state_path).save(legacy)

    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=state_path,
    )

    assert bundle.authority.current.revision == 1
    assert bundle.authority.current.appearance.hair_color == "deep crimson"
    assert bundle.authority.snapshot()["finished"] == ["legacy.cancelled"]
