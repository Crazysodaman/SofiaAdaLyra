"""Source-aware user preferences, not live INTERACT/renderer integration."""
import pytest

from sofia.avatar.wardrobe_catalog import (
    SPARKS_LIKED_OUTFIT_SOURCE_IDS,
    build_sparks_starter_wardrobe,
    with_sparks_outfit_likes,
)
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import RequestStatus, build_starter_wardrobe


def test_both_likes_are_in_enriched_clothing_data():
    catalog = build_sparks_starter_wardrobe()
    records = [entry for entry in catalog.inputs if entry.status is RequestStatus.USER_LIKED]
    assert {entry.subject_id for entry in records} == {"engineer.signature", "lounge.relaxed"}
    assert {entry.source_id for entry in records} == SPARKS_LIKED_OUTFIT_SOURCE_IDS
    assert len(catalog.presets) == 310
    assert len([
        plan for plan in catalog.presets
        if plan.outfit_id.startswith("seasonal.")
    ]) == 300


def test_likes_are_distinct_from_requests_and_remain_source_backed():
    catalog = build_sparks_starter_wardrobe()
    likes = tuple(
        entry
        for entry in catalog.inputs
        if entry.status is RequestStatus.USER_LIKED
    )
    requests = tuple(
        entry
        for entry in catalog.inputs
        if entry.status is RequestStatus.USER_REQUESTED
    )
    assert {entry.subject_id for entry in likes} == {
        "engineer.signature", "lounge.relaxed"
    }
    assert {entry.source_id for entry in likes} == SPARKS_LIKED_OUTFIT_SOURCE_IDS
    assert len(requests) == 2
    assert all(entry.detail.strip() for entry in likes + requests)


def test_base_catalog_does_not_fabricate_likes():
    catalog = build_starter_wardrobe()
    assert not any(
        entry.status is RequestStatus.USER_LIKED
        for entry in catalog.inputs
    )
    assert {
        entry.status for entry in catalog.inputs
    } == {RequestStatus.USER_REQUESTED}


def test_enrichment_is_idempotent_and_preserves_existing_records():
    original = build_starter_wardrobe()
    enriched = with_sparks_outfit_likes(original)
    assert with_sparks_outfit_likes(enriched) == enriched
    assert enriched.inputs[:len(original.inputs)] == original.inputs


def test_invalid_catalog_is_rejected():
    with pytest.raises(WardrobeError):
        with_sparks_outfit_likes(None)
