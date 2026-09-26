from __future__ import annotations

from pathlib import Path

from sofia.avatar.presentation import AppearanceState, PresentationAuthority
from sofia.avatar.presentation_store import PresentationStore
from sofia.avatar.runtime_state import load_or_bootstrap_presentation
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.embodiment.store import AvatarStore


ROOT = Path(__file__).resolve().parents[1]
AVATAR_PATH = ROOT / "src" / "sofia" / "data" / "avatar.json"


def embodiment():
    return AvatarStore(AVATAR_PATH).load()


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
    store = PresentationStore(tmp_path / "avatar-presentation.json")
    store.save(legacy)

    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=tmp_path / "sofia.db",
    )
    assert bundle.authority.current.revision == 1
    assert bundle.authority.current.appearance.hair_color == "deep crimson"
    assert bundle.authority.current.appearance.tail_color == "dark violet"

    restored = store.load(catalog.wardrobe, outfits=outfits)
    assert restored.current.appearance.hair_color == "deep crimson"
    assert restored.current.appearance.tail_color == "dark violet"


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
    PresentationStore(tmp_path / "avatar-presentation.json").save(authority)

    bundle = load_or_bootstrap_presentation(
        embodiment=embodiment(),
        state_path=tmp_path / "sofia.db",
    )
    assert bundle.authority.current.revision == 2
    assert bundle.authority.current.appearance.hair_color == "#A63D5E"
    assert bundle.authority.current.appearance.tail_color == "#43265F"
