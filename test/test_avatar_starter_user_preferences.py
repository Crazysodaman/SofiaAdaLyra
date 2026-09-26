"""Source-aware user preferences, not live INTERACT/renderer integration."""
import pytest

from sofia.avatar.starter_user_preferences import (
    SPARKS_LIKED_OUTFIT_SOURCE_IDS,
    build_sparks_starter_wardrobe,
    with_sparks_outfit_likes,
)
from sofia.avatar.style_context import project_style_context
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import RequestStatus, build_starter_wardrobe


def test_both_likes_are_in_enriched_clothing_data():
    catalog = build_sparks_starter_wardrobe()
    records = [entry for entry in catalog.inputs if entry.status is RequestStatus.USER_LIKED]
    assert {entry.subject_id for entry in records} == {"engineer.signature", "lounge.relaxed"}
    assert {entry.source_id for entry in records} == SPARKS_LIKED_OUTFIT_SOURCE_IDS
    assert len(catalog.presets) == 3


def test_reviewed_likes_are_distinct_from_requests_and_sofia_taste():
    catalog = build_sparks_starter_wardrobe()
    projection = project_style_context(catalog, reviewed_source_ids=SPARKS_LIKED_OUTFIT_SOURCE_IDS)
    assert {entry.subject_id for entry in projection.liked_by_sparks} == {
        "engineer.signature", "lounge.relaxed"
    }
    assert len(projection.requested_by_sparks) == 2
    assert projection.disliked_by_sparks == ()
    assert projection.for_chat()["sofia_preference_claims"] == []


def test_sources_not_reviewed_are_not_claimed_as_likes():
    projection = project_style_context(build_sparks_starter_wardrobe())
    assert projection.liked_by_sparks == ()
    assert {entry.source_id for entry in projection.awaiting_source_review} == SPARKS_LIKED_OUTFIT_SOURCE_IDS


def test_enrichment_is_idempotent_and_preserves_existing_records():
    original = build_starter_wardrobe()
    enriched = with_sparks_outfit_likes(original)
    assert with_sparks_outfit_likes(enriched) == enriched
    assert enriched.inputs[:len(original.inputs)] == original.inputs


def test_invalid_catalog_is_rejected():
    with pytest.raises(WardrobeError):
        with_sparks_outfit_likes(None)
