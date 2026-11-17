"""MOD-INTERACTION pointer/hit-region and gesture-offer boundary tests."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.interaction.core import GESTURES
from sofia.modules.interaction.pointer_review import (
    capability_registrations, review_pointer_gesture_offer,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def current_frame(**change):
    data = {
        "frame_id": "visible.frame.6",
        "presentation_revision": 6,
        "bundle_digest": DIGEST,
    }
    data.update(change)
    return data


def pointer(**change):
    data = {
        "pointer_id": "pointer:1",
        "frame_id": "visible.frame.6",
        "presentation_revision": 6,
        "x": 0.3,
        "y": 0.3,
        "phase": "up",
        "occurred_at": (NOW - timedelta(seconds=1)).isoformat(),
    }
    data.update(change)
    return data


def region(region_id="left-ear-tip", layer_id="fox.ear.left", **change):
    data = {
        "region_id": region_id,
        "layer_id": layer_id,
        "z_index": 1,
        "x": 0.2,
        "y": 0.2,
        "width": 0.2,
        "height": 0.2,
        "opaque": True,
        "audience": "public",
        "region_private": False,
    }
    data.update(change)
    return data


def offer(offer_id="offer:1", **change):
    data = {
        "offer_id": offer_id,
        "gesture": "pat",
        "region_id": "left-ear-tip",
        "phase": "end",
        "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
        "audience": "public",
    }
    data.update(change)
    return data


def snapshot(pointer_record=None, regions=None, offers=None, observed=None, **change):
    data = {
        "source_ref": "avatar:local",
        "observed_at": (
            observed.isoformat() if hasattr(observed, "isoformat")
            else observed if isinstance(observed, str) else NOW.isoformat()
        ),
        "audience": "public",
        "private_audience_claimed": False,
        "current_frame": current_frame(),
        "pointer": pointer_record if pointer_record is not None else pointer(),
        "hit_regions": regions if regions is not None else [region()],
        "gesture_offers": offers if offers is not None else [offer()],
    }
    data.update(change)
    return data


def test_valid_pointer_and_offer_are_candidates_without_gesture_or_reaction_claim():
    report = review_pointer_gesture_offer(snapshot(
        regions=[
            region("torso", "body.visible", z_index=1, x=0.0, y=0.0,
                   width=1.0, height=1.0),
            region("left-ear-tip", "fox.ear.left", z_index=5),
        ],
        offers=[offer()],
    ), now=NOW)
    assert report["status"] == "reviewed"
    assert report["pointer"]["outcome"] == "hit"
    assert report["pointer"]["region_id"] == "left-ear-tip"
    assert report["pointer"]["layer_id"] == "fox.ear.left"
    assert report["offers"][0]["outcome"] == "eligible_candidate"
    assert report["counts"] == {
        "pointer_hit": 1, "pointer_miss": 0, "pointer_restricted": 0,
        "offers_eligible": 1, "offers_rejected": 0,
    }
    assert report["effect"] == "none"
    assert report["evidence_class"] == "supplied_unverified"
    assert report["input_captured"] is False
    assert report["frame_authenticated"] is False
    assert report["gesture_claimed"] is False
    assert report["gesture_offer_accepted"] is False
    assert report["consent_granted"] is False
    assert report["reaction_decided"] is False
    assert report["core_reaction_required"] is True


def test_topmost_opaque_region_wins_and_transparent_overlay_falls_through():
    body = region("torso", "body.visible", z_index=1, x=0.0, y=0.0,
                  width=1.0, height=1.0)
    transparent = region("hair", "hair.fringe", z_index=9, x=0.2, y=0.2,
                         width=0.2, height=0.2, opaque=False)
    report = review_pointer_gesture_offer(
        snapshot(regions=[body, transparent], offers=[]), now=NOW,
    )
    assert report["pointer"]["outcome"] == "hit"
    assert report["pointer"]["region_id"] == "torso"
    assert report["offers"] == []


def test_pointer_miss_and_offer_mismatch_never_become_contact():
    report = review_pointer_gesture_offer(snapshot(
        pointer=pointer(x=0.9, y=0.9), regions=[region()], offers=[offer()],
    ), now=NOW)
    assert report["pointer"]["outcome"] == "miss"
    assert report["pointer"].get("region_id") is None
    assert report["offers"][0]["outcome"] == "no_pointer_hit"
    assert report["gesture_claimed"] is False
    mismatch = review_pointer_gesture_offer(snapshot(
        regions=[
            region(),
            region("torso", "body.visible", z_index=2, x=0.6, y=0.6),
        ],
        offers=[offer(region_id="torso")],
    ), now=NOW)
    assert mismatch["offers"][0]["outcome"] == "region_mismatch"


def test_unknown_expired_and_incomplete_offers_fail_closed():
    unknown = review_pointer_gesture_offer(
        snapshot(offers=[offer(region_id="tail-tip")]), now=NOW,
    )
    assert unknown["offers"][0]["outcome"] == "unknown_region"
    assert unknown["counts"]["offers_rejected"] == 1
    expired = review_pointer_gesture_offer(snapshot(offers=[
        offer(expires_at=(NOW - timedelta(seconds=1)).isoformat()),
    ]), now=NOW)
    assert expired["offers"][0]["outcome"] == "expired"
    incomplete = review_pointer_gesture_offer(
        snapshot(offers=[offer(phase="begin")]), now=NOW,
    )
    assert incomplete["offers"][0]["outcome"] == "incomplete"


@pytest.mark.parametrize("point", [
    {"x": float("nan")},
    {"x": float("inf")},
    {"x": 1.0},
    {"y": -0.1},
    {"phase": "hover"},
    {"occurred_at": "not-a-date"},
    {"occurred_at": "2026-11-16T12:00:00"},
    {"pointer_id": "C:/Users/alice/pointer"},
    {"pointer_id": "token:prod"},
    {"pointer_id": "a/../../secret"},
    {"note": "x" * 281},
    {"note": "line\nbreak"},
    {"extra": "field"},
])
def test_pointer_rejects_malformed_or_unsafe_records(point):
    with pytest.raises(ValueError):
        review_pointer_gesture_offer(snapshot(pointer=pointer(**point)), now=NOW)


@pytest.mark.parametrize("bad", [
    {"hit_regions": []},
    {"hit_regions": [region() for _ in range(65)]},
    {"hit_regions": [region(layer_id="same"), region(layer_id="same")]},
    {"hit_regions": [region(width=0.0)]},
    {"hit_regions": [region(x=0.9, width=0.2)]},
    {"hit_regions": [region(z_index=True)]},
    {"hit_regions": [region(audience="private")]},
    {"gesture_offers": [offer(offer_id=f"offer:{index}") for index in range(33)]},
    {"gesture_offers": [offer(offer_id="same"), offer(offer_id="same")]},
    {"gesture_offers": [offer(audience="private")]},
    {"gesture_offers": [offer(gesture="hug")]},
    {"gesture_offers": [offer(phase="hover")]},
    {"current_frame": current_frame(bundle_digest="bad")},
    {"current_frame": current_frame(presentation_revision=True)},
    {"source_ref": "C:/Users/alice/avatar"},
    {"audience": "friends"},
    {"private_audience_claimed": "yes"},
    {"body": "private avatar art"},
])
def test_snapshot_rejects_malformed_duplicate_oversized_or_unsafe_records(bad):
    with pytest.raises(ValueError):
        review_pointer_gesture_offer(snapshot(**bad), now=NOW)


def test_gesture_offers_accept_only_existing_core_vocabulary():
    for gesture in sorted(GESTURES):
        report = review_pointer_gesture_offer(
            snapshot(offers=[offer(gesture=gesture)]), now=NOW,
        )
        assert report["offers"][0]["outcome"] == "eligible_candidate"


@pytest.mark.parametrize("observed", [
    NOW - timedelta(hours=1),
    NOW + timedelta(minutes=1),
])
def test_stale_or_future_snapshot_is_truthfully_unknown(observed):
    report = review_pointer_gesture_offer(snapshot(
        observed=observed.isoformat(),
        pointer=pointer(
            occurred_at=(observed - timedelta(seconds=1)).isoformat(),
        ),
        offers=[],
    ), now=NOW)
    assert report["status"] == "unknown"
    assert report["pointer"] is None
    assert report["offers"] == []
    assert report["counts"] == {}
    assert report["input_captured"] is False
    assert report["gesture_claimed"] is False


def test_stale_pointer_frame_or_age_cannot_be_reused():
    frame_mismatch = review_pointer_gesture_offer(
        snapshot(pointer=pointer(frame_id="last.frame.5")), now=NOW,
    )
    assert frame_mismatch["status"] == "stale"
    assert frame_mismatch["pointer"]["outcome"] == "stale"
    assert frame_mismatch["offers"] == []
    revision_mismatch = review_pointer_gesture_offer(
        snapshot(pointer=pointer(presentation_revision=5)), now=NOW,
    )
    assert revision_mismatch["status"] == "stale"
    old_pointer = review_pointer_gesture_offer(
        snapshot(pointer=pointer(
            occurred_at=(NOW - timedelta(minutes=2)).isoformat(),
        )), now=NOW,
    )
    assert old_pointer["status"] == "stale"
    assert old_pointer["counts"] == {}


def test_private_hit_never_leaks_region_without_supplied_private_audience():
    private_region = region("chest", "private.torso", audience="private",
                            region_private=True)
    with pytest.raises(ValueError, match="private hit region"):
        review_pointer_gesture_offer(snapshot(regions=[private_region]), now=NOW)
    report = review_pointer_gesture_offer(snapshot(
        regions=[private_region], offers=[offer(region_id="chest")],
        audience="private",
    ), now=NOW)
    assert report["status"] == "restricted"
    assert report["pointer"]["outcome"] == "restricted"
    assert report["pointer"].get("region_id") is None
    assert report["pointer"].get("layer_id") is None
    assert report["offers"][0]["outcome"] == "restricted"
    assert report["offers"][0]["region_id"] is None
    assert report["consent_granted"] is False
    allowed = review_pointer_gesture_offer(snapshot(
        regions=[private_region], offers=[offer(region_id="chest")],
        audience="private", private_audience_claimed=True,
    ), now=NOW)
    assert allowed["pointer"]["outcome"] == "hit"
    assert allowed["pointer"]["region_id"] == "chest"
    assert allowed["offers"][0]["outcome"] == "eligible_candidate"


def test_canonical_private_region_on_public_layer_stays_restricted():
    report = review_pointer_gesture_offer(snapshot(
        regions=[region("chest", "misclassified", region_private=True)],
        offers=[offer(region_id="chest")],
    ), now=NOW)
    assert report["status"] == "restricted"
    assert report["pointer"]["outcome"] == "restricted"
    assert report["pointer"].get("region_id") is None
    assert report["offers"][0]["outcome"] == "restricted"


def test_sensitive_notes_are_redacted_without_changing_evidence_class():
    report = review_pointer_gesture_offer(snapshot(
        pointer=pointer(note="token=abc123 C:\\Users\\alice\\pointer.json"),
        offers=[offer(note="secret=hunter2 /home/bob/avatar.png alice@example.com")],
    ), now=NOW)
    assert report["redactions"] >= 3
    serialized = json.dumps(report)
    for secret in ("abc123", "Users", "/home/bob", "hunter2", "alice@example.com"):
        assert secret not in serialized
    assert "<redacted>" in serialized
    assert report["evidence_class"] == "supplied_unverified"


def test_capability_registration_shape_and_exact_parameters():
    registrations = capability_registrations()
    assert isinstance(registrations, tuple) and len(registrations) == 1
    capability, handler = registrations[0]
    assert isinstance(capability, Capability) and callable(handler)
    live = datetime.now(timezone.utc)
    payload = snapshot(
        observed=live.isoformat(),
        pointer=pointer(
            occurred_at=(live - timedelta(seconds=1)).isoformat(),
        ),
        offers=[offer(expires_at=(live + timedelta(seconds=30)).isoformat())],
    )
    result = handler(CapabilityRequest(
        capability, {"snapshot": payload}, None, "review pointer offer",
    ))
    assert result["status"] == "reviewed"
    assert result["effect"] == "none"
    assert result["reaction_decided"] is False
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            Capability(capability.name, "Forged descriptor"),
            {"snapshot": payload}, None, "forged",
        ))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            capability, dict({"snapshot": payload}, capture=True), None, "invalid",
        ))
