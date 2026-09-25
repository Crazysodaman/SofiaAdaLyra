from __future__ import annotations

import json

import pytest

from sofia.avatar.presentation import (
    AppearanceState,
    AttireMode,
    PresentationAuthority,
    PrivatePresentationGrant,
)
from sofia.avatar.presentation_store import PresentationStore, PresentationStoreError
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe


def setup_authority():
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    authority = PresentationAuthority(
        catalog.wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle="long layered",
            hair_color="#8B1E3F",
            tail_color="#3A245C",
            style_tags=("engineer",),
        ),
    )
    return catalog, outfits, authority


def grant():
    return PrivatePresentationGrant(True, True, True, True, False)


def test_store_round_trip_preserves_current_and_daily(tmp_path):
    catalog, outfits, authority = setup_authority()
    authority.propose_outfit(
        operation_id="op.lounge",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="late night",
        daily=True,
    )
    authority.commit_text(operation_id="op.lounge", renderer_unavailable=True)
    authority.propose_nude(
        operation_id="op.nude",
        expected_revision=2,
        reason="private state",
        grant=grant(),
    )
    authority.commit_text(
        operation_id="op.nude",
        renderer_unavailable=True,
        grant=grant(),
    )

    store = PresentationStore(tmp_path / "presentation.json")
    store.save(authority)
    restored = store.load(catalog.wardrobe, outfits=outfits)

    assert restored.current.attire is AttireMode.NUDE
    assert restored.last_daily.outfit_id == "lounge.relaxed"


def test_store_write_is_json_and_atomic_target_exists(tmp_path):
    _, _, authority = setup_authority()
    path = tmp_path / "presentation.json"
    PresentationStore(path).save(authority)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["schema"] == "sofia.avatar.presentation.v1"
    assert not path.with_suffix(".json.tmp").exists()


def test_store_refuses_unsettled_transition(tmp_path):
    _, _, authority = setup_authority()
    authority.propose_outfit(
        operation_id="op.pending",
        expected_revision=1,
        outfit_id="lounge.relaxed",
        reason="pending",
    )
    with pytest.raises(Exception, match="unresolved"):
        PresentationStore(tmp_path / "presentation.json").save(authority)


def test_store_rejects_corrupt_json(tmp_path):
    path = tmp_path / "presentation.json"
    path.write_text("{broken", encoding="utf-8")
    catalog, outfits, _ = setup_authority()
    with pytest.raises(PresentationStoreError):
        PresentationStore(path).load(catalog.wardrobe, outfits=outfits)
