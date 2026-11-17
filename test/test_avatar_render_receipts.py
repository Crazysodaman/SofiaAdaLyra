"""Boundary tests for RM-AVATAR2D supplied render/frame receipt validation."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.avatar.render_receipts import (
    review_avatar_render_receipts,
    capability_registrations,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def receipt(decision_id="decision:1", revision=7, requested_at=None, callback_at=None,
            rendered=True, visible=True, frame_count=2, note=None, **change):
    requested = requested_at if requested_at is not None else (NOW - timedelta(seconds=2))
    callback = callback_at if callback_at is not None else (NOW - timedelta(seconds=1))
    data = {
        "decision_id": decision_id,
        "revision": revision,
        "requested_at": requested.isoformat() if hasattr(requested, "isoformat") else requested,
        "callback_at": callback.isoformat() if hasattr(callback, "isoformat") else callback,
        "rendered": rendered,
        "visible": visible,
        "frame_count": frame_count,
    }
    if note is not None:
        data["note"] = note
    data.update(change)
    return data


def snapshot(receipts, current_revision=7, observed=None, source_ref="avatar:local"):
    return {
        "source_ref": source_ref,
        "observed_at": (observed or NOW).isoformat(),
        "current_revision": current_revision,
        "receipts": receipts,
    }


def test_avatar_validates_visible_frame_receipt_without_renderer_claim():
    report = review_avatar_render_receipts(snapshot([
        receipt("decision:ok"),
        receipt("decision:hidden", rendered=False, visible=False, frame_count=0),
    ]), now=NOW)
    assert report["status"] == "reviewed"
    assert report["counts"] == {"receipt_validated": 1, "no_frame": 1, "stale": 0}
    ok = next(row for row in report["receipts"] if row["decision_id"] == "decision:ok")
    hidden = next(row for row in report["receipts"] if row["decision_id"] == "decision:hidden")
    assert (ok["outcome"], ok["flags"], ok["frame_count_reported"]) == ("receipt_validated", [], 2)
    assert (hidden["outcome"], hidden["flags"]) == (
        "no_frame", ["no_frame_receipt", "window_not_visible_reported"],
    )
    assert report["renderer_launched"] is False
    assert report["sprite_assets_accessed"] is False
    assert report["frame_authenticated"] is False
    assert report["effect"] == "none"
    assert report["evidence_class"] == "supplied_unverified"


def test_avatar_stale_revision_is_not_current_rendering():
    report = review_avatar_render_receipts(
        snapshot([receipt("decision:old", revision=6)], current_revision=7), now=NOW,
    )
    row = report["receipts"][0]
    assert (row["outcome"], row["flags"]) == ("stale", ["stale_revision"])
    assert report["counts"] == {"receipt_validated": 0, "no_frame": 0, "stale": 1}
    assert report["frame_authenticated"] is False


@pytest.mark.parametrize("observed", [NOW + timedelta(minutes=1), NOW - timedelta(hours=1)])
def test_avatar_stale_or_future_snapshot_is_truthfully_unknown(observed):
    row = receipt(
        requested_at=observed - timedelta(seconds=2),
        callback_at=observed - timedelta(seconds=1),
    )
    report = review_avatar_render_receipts(snapshot([row], observed=observed), now=NOW)
    assert report["status"] == "unknown"
    assert report["counts"] == {}
    assert report["receipts"] == []
    assert report["frame_authenticated"] is False
    assert report["renderer_launched"] is False


@pytest.mark.parametrize("change", [
    {"rendered": True, "visible": False},
    {"rendered": True, "frame_count": 0},
    {"rendered": False, "visible": True, "frame_count": 1},
    {"rendered": False, "visible": False, "frame_count": 1},
    {"revision": 8},
    {"revision": True},
    {"frame_count": True},
    {"requested_at": "not-a-date"},
    {"requested_at": "2026-11-16T12:00:00"},
    {"callback_at": (NOW - timedelta(seconds=3))},
    {"callback_at": NOW + timedelta(minutes=5)},
    {"decision_id": "C:/Users/alice/avatar"},
    {"decision_id": "token:prod"},
    {"decision_id": "a/../../secret"},
    {"note": "x" * 281},
    {"note": "line\nbreak"},
    {"extra": "field"},
])
def test_avatar_rejects_malformed_or_unsafe_receipts(change):
    with pytest.raises(ValueError):
        review_avatar_render_receipts(snapshot([receipt(**change)]), now=NOW)


def test_avatar_rejects_duplicate_oversized_and_bad_snapshot():
    with pytest.raises(ValueError):
        review_avatar_render_receipts(snapshot([receipt(), receipt()]), now=NOW)
    with pytest.raises(ValueError):
        review_avatar_render_receipts(snapshot([]), now=NOW)
    oversized = [receipt(f"decision:{index}") for index in range(65)]
    with pytest.raises(ValueError):
        review_avatar_render_receipts(snapshot(oversized), now=NOW)
    with pytest.raises(ValueError):
        review_avatar_render_receipts(snapshot([receipt()], current_revision=True), now=NOW)
    with pytest.raises(ValueError):
        review_avatar_render_receipts(snapshot([receipt()], source_ref="C:/Users/alice"), now=NOW)
    bad = snapshot([receipt()])
    bad["body"] = "private avatar art"
    with pytest.raises(ValueError):
        review_avatar_render_receipts(bad, now=NOW)


def test_avatar_redacts_sensitive_receipt_notes():
    report = review_avatar_render_receipts(snapshot([
        receipt("decision:one", note="token=abc123 C:\\Users\\alice\\frame.png"),
        receipt("decision:two", note="secret=hunter2 /home/bob/avatar.png alice@example.com"),
    ]), now=NOW)
    assert report["redactions"] >= 4
    serialized = json.dumps(report)
    for secret in ("abc123", "Users", "/home/bob", "hunter2", "alice@example.com"):
        assert secret not in serialized
    assert "<redacted>" in serialized


def test_avatar_capability_registration_shape():
    registrations = capability_registrations()
    assert isinstance(registrations, tuple) and len(registrations) == 1
    capability, handler = registrations[0]
    assert isinstance(capability, Capability) and callable(handler)
    observed = datetime.now(timezone.utc)
    payload = snapshot(
        [receipt(requested_at=observed - timedelta(seconds=2),
                 callback_at=observed - timedelta(seconds=1))],
        observed=observed,
    )
    result = handler(CapabilityRequest(capability, {"snapshot": payload}, None, "review render receipts"))
    assert result["status"] == "reviewed"
    assert result["effect"] == "none"
    assert result["renderer_launched"] is False
    assert result["frame_authenticated"] is False
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            Capability(capability.name, "Forged descriptor"),
            {"snapshot": payload}, None, "forged",
        ))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            capability, dict({"snapshot": payload}, command="render"), None, "invalid",
        ))
