"""Canonical source-aware wardrobe preference evidence."""
from sofia.avatar.wardrobe_catalog import (
    GRAPHIC_REQUEST_SOURCE_ID,
    GRAPHIC_TEE_ID,
    SPARKS_LIKED_OUTFIT_SOURCE_IDS,
    RequestStatus,
    build_starter_wardrobe,
)


def test_confirmed_likes_live_in_the_canonical_catalog():
    catalog = build_starter_wardrobe()
    likes = tuple(
        entry
        for entry in catalog.inputs
        if entry.status is RequestStatus.USER_LIKED
    )

    assert {entry.subject_id for entry in likes} == {
        "engineer.signature",
        "lounge.relaxed",
    }
    assert {entry.source_id for entry in likes} == (
        SPARKS_LIKED_OUTFIT_SOURCE_IDS
    )


def test_requests_and_likes_remain_distinct_source_evidence():
    catalog = build_starter_wardrobe()
    requests = tuple(
        entry
        for entry in catalog.inputs
        if entry.status is RequestStatus.USER_REQUESTED
    )
    likes = tuple(
        entry
        for entry in catalog.inputs
        if entry.status is RequestStatus.USER_LIKED
    )

    assert {entry.subject_id for entry in requests} == {
        "engineer.signature",
        "lounge.relaxed",
        GRAPHIC_TEE_ID,
    }
    assert {entry.subject_id for entry in likes} == {
        "engineer.signature",
        "lounge.relaxed",
    }
    assert next(
        entry for entry in requests
        if entry.subject_id == GRAPHIC_TEE_ID
    ).source_id == GRAPHIC_REQUEST_SOURCE_ID
    assert all(entry.detail.strip() for entry in requests + likes)


def test_canonical_style_evidence_has_no_invented_sofia_preference():
    catalog = build_starter_wardrobe()
    assert len(catalog.inputs) == 5
    assert {
        entry.status
        for entry in catalog.inputs
    } == {
        RequestStatus.USER_REQUESTED,
        RequestStatus.USER_LIKED,
    }


def test_reviewed_catalog_likes_feed_live_planner_preferences():
    catalog = build_starter_wardrobe()
    preferences = catalog.reviewed_preferences()

    assert {
        preference.ids[0]
        for preference in preferences
    } == {
        "engineer.signature",
        "lounge.relaxed",
    }
    assert all(preference.reviewed for preference in preferences)
    assert all(preference.actor.value == "sparks" for preference in preferences)
    assert all(preference.sentiment.value == 1 for preference in preferences)
    assert GRAPHIC_TEE_ID not in {
        preference.ids[0]
        for preference in preferences
    }
