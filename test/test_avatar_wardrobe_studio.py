from __future__ import annotations

import pytest

from sofia.avatar.presentation import AppearanceState, PresentationAuthority
from sofia.avatar.presentation_store import PresentationStore
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_planner import Activity, Season
from sofia.avatar.wardrobe_studio import WardrobeStudio


def setup(tmp_path):
    catalog = build_starter_wardrobe()
    outfits = {
        plan.outfit_id: plan.item_ids
        for plan in catalog.presets
    }
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            "long layered",
            "deep crimson",
            "dark violet",
            ("engineer",),
        ),
    )
    store = PresentationStore(tmp_path / "sofia.db")
    store.save(authority)
    return catalog, outfits, authority, store


def test_registered_composition_is_durable(tmp_path):
    catalog, outfits, authority, store = setup(tmp_path)
    studio = WardrobeStudio(
        catalog,
        authority=authority,
        store=store,
    )
    item_ids = catalog.preset("lounge.relaxed").item_ids

    plan = studio.compose(
        outfit_id="dynamic.studio.lounge",
        item_ids=item_ids,
        activities=frozenset({Activity.CONVERSATION}),
        seasons=frozenset(Season),
        lounge=True,
        register=True,
    )

    assert plan.outfit_id in authority.available_outfit_ids
    restored = store.load(
        catalog.wardrobe,
        outfits=outfits,
    )
    assert plan.outfit_id in restored.available_outfit_ids


def test_standalone_studio_can_register_in_memory_for_authoring(tmp_path):
    catalog, _, authority, _ = setup(tmp_path)
    studio = WardrobeStudio(
        catalog,
        authority=authority,
    )

    plan = studio.compose(
        outfit_id="dynamic.studio.authoring",
        item_ids=catalog.preset("lounge.relaxed").item_ids,
        activities=frozenset({Activity.CONVERSATION}),
        seasons=frozenset(Season),
        lounge=True,
        register=True,
    )

    assert plan.outfit_id in authority.available_outfit_ids


def test_studio_can_author_manual_only_outfit_without_auto_rotation():
    catalog = build_starter_wardrobe()
    studio = WardrobeStudio(catalog)
    plan = studio.compose(
        outfit_id="manual.test",
        item_ids=catalog.preset("lounge.relaxed").item_ids,
        activities=frozenset({Activity.RELAXING}),
        seasons=frozenset({Season.AUTUMN}),
        manual_only=True,
    )
    assert plan.manual_only is True
