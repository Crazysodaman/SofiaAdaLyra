"""Source-aware defaults for the rebuilt wardrobe."""
from sofia.avatar.wardrobe_catalog import (
    DAY_DEFAULT_OUTFIT_ID,
    NIGHT_LOUNGE_OUTFIT_ID,
    RequestStatus,
    build_starter_wardrobe,
)


def test_new_day_and_night_defaults_are_explicit_requests():
    catalog = build_starter_wardrobe()
    requests = tuple(
        item for item in catalog.inputs
        if item.status is RequestStatus.USER_REQUESTED
    )

    assert {item.subject_id for item in requests} == {
        DAY_DEFAULT_OUTFIT_ID,
        NIGHT_LOUNGE_OUTFIT_ID,
    }
    assert all(item.source_id.startswith("chat.2026-10-04.") for item in requests)
    assert all(item.detail.strip() for item in requests)


def test_reset_does_not_invent_confirmed_likes():
    catalog = build_starter_wardrobe()

    assert not any(
        item.status is RequestStatus.USER_LIKED
        for item in catalog.inputs
    )
    assert catalog.reviewed_preferences() == ()
