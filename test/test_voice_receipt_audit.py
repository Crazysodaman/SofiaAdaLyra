"""Safety and truthfulness tests for RM-VOICE supplied receipt correlation."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.voice.receipts import review_voice_receipts, capability_registrations
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def receipt(utterance_id="utt:1", correlation_ref="corr:1", stage="synthesis",
            state="queued", sequence=1, recorded_at=None, note=None, **change):
    when = recorded_at if recorded_at is not None else (NOW - timedelta(seconds=10))
    data = {
        "utterance_id": utterance_id,
        "correlation_ref": correlation_ref,
        "stage": stage,
        "state": state,
        "sequence": sequence,
        "recorded_at": when.isoformat() if hasattr(when, "isoformat") else when,
    }
    if note is not None:
        data["note"] = note
    data.update(change)
    return data


def snapshot(receipts, observed=None, source_ref="voice:local"):
    return {
        "source_ref": source_ref,
        "observed_at": (observed or NOW).isoformat(),
        "receipts": receipts,
    }


def complete_pair(**change):
    rows = [
        receipt(state="queued", sequence=1, recorded_at=NOW - timedelta(seconds=9)),
        receipt(state="started", sequence=2, recorded_at=NOW - timedelta(seconds=8)),
        receipt(state="completed", sequence=3, recorded_at=NOW - timedelta(seconds=7)),
        receipt(stage="playback", state="queued", sequence=1, recorded_at=NOW - timedelta(seconds=6)),
        receipt(stage="playback", state="started", sequence=2, recorded_at=NOW - timedelta(seconds=5)),
        receipt(stage="playback", state="completed", sequence=3, recorded_at=NOW - timedelta(seconds=4)),
    ]
    for row in rows:
        row.update(change)
    return rows


def test_voice_correlates_complete_supplied_receipts_without_audio_claim():
    report = review_voice_receipts(snapshot(complete_pair()), now=NOW)
    assert report["status"] == "reviewed"
    assert report["counts"] == {
        "utterances": 1, "correlated_complete": 1, "interrupted": 0,
        "cancelled": 0, "failed": 0, "not_played": 0, "incomplete": 0,
        "unverified": 0,
    }
    row = report["utterances"][0]
    assert (row["synthesis_state"], row["playback_state"]) == ("completed", "completed")
    assert (row["outcome"], row["flags"]) == ("correlated_complete", [])
    assert report["audio_device_accessed"] is False
    assert report["playback_authenticated"] is False
    assert report["synthesis_authenticated"] is False
    assert report["effect"] == "none"
    assert report["evidence_class"] == "supplied_unverified"


def test_voice_audits_interruption_without_claiming_completion():
    rows = [
        receipt(state="queued", sequence=1),
        receipt(state="started", sequence=2),
        receipt(state="completed", sequence=3),
        receipt(stage="playback", state="queued", sequence=1),
        receipt(stage="playback", state="started", sequence=2),
        receipt(stage="playback", state="interrupted", sequence=3),
    ]
    report = review_voice_receipts(snapshot(rows), now=NOW)
    row = report["utterances"][0]
    assert row["outcome"] == "interrupted"
    assert "playback_interrupted_reported" in row["flags"]
    assert report["interruptions"] == ["utt:1"]
    assert report["counts"]["interrupted"] == 1
    assert report["playback_authenticated"] is False


def test_voice_playback_without_synthesis_is_unverified_not_invented():
    rows = [
        receipt(stage="playback", state="started", sequence=1),
        receipt(stage="playback", state="completed", sequence=2),
    ]
    report = review_voice_receipts(snapshot(rows), now=NOW)
    row = report["utterances"][0]
    assert row["outcome"] == "unverified"
    assert row["synthesis_state"] is None
    assert {"synthesis_receipt_missing", "playback_without_synthesis_completion"}.issubset(row["flags"])
    assert report["counts"]["unverified"] == 1
    assert report["counts"]["correlated_complete"] == 0


def test_voice_synthesis_completed_without_playback_is_not_played():
    rows = [
        receipt(state="queued", sequence=1),
        receipt(state="completed", sequence=2),
    ]
    report = review_voice_receipts(snapshot(rows), now=NOW)
    assert report["utterances"][0]["outcome"] == "not_played"
    assert report["counts"]["not_played"] == 1


@pytest.mark.parametrize("observed", [NOW + timedelta(minutes=1), NOW - timedelta(hours=1)])
def test_voice_stale_or_future_snapshot_is_truthfully_unknown(observed):
    rows = [
        receipt(state="queued", sequence=1, recorded_at=observed - timedelta(seconds=9)),
        receipt(state="started", sequence=2, recorded_at=observed - timedelta(seconds=8)),
        receipt(state="completed", sequence=3, recorded_at=observed - timedelta(seconds=7)),
        receipt(stage="playback", state="queued", sequence=1,
                recorded_at=observed - timedelta(seconds=6)),
        receipt(stage="playback", state="started", sequence=2,
                recorded_at=observed - timedelta(seconds=5)),
        receipt(stage="playback", state="completed", sequence=3,
                recorded_at=observed - timedelta(seconds=4)),
    ]
    report = review_voice_receipts(snapshot(rows, observed=observed), now=NOW)
    assert report["status"] == "unknown"
    assert report["counts"] == {}
    assert report["utterances"] == []
    assert report["interruptions"] == []
    assert report["playback_authenticated"] is False


@pytest.mark.parametrize("change", [
    {"stage": "microphone"},
    {"state": "interrupted"},
    {"sequence": 0},
    {"sequence": True},
    {"recorded_at": "not-a-date"},
    {"recorded_at": "2026-11-16T12:00:00"},
    {"recorded_at": (NOW + timedelta(minutes=5)).isoformat()},
    {"utterance_id": "C:/Users/alice/voice"},
    {"correlation_ref": "token:prod"},
    {"utterance_id": "a/../../secret"},
    {"note": "x" * 281},
    {"note": "line\nbreak"},
    {"extra": "field"},
])
def test_voice_rejects_malformed_or_unsafe_receipts(change):
    with pytest.raises(ValueError):
        review_voice_receipts(snapshot([receipt(**change)]), now=NOW)


def test_voice_rejects_invalid_transition_and_backwards_timeline():
    rows = [
        receipt(state="queued", sequence=1, recorded_at=NOW - timedelta(seconds=9)),
        receipt(state="started", sequence=2, recorded_at=NOW - timedelta(seconds=8)),
        receipt(state="queued", sequence=3, recorded_at=NOW - timedelta(seconds=7)),
    ]
    with pytest.raises(ValueError):
        review_voice_receipts(snapshot(rows), now=NOW)
    backwards = [
        receipt(state="started", sequence=1, recorded_at=NOW - timedelta(seconds=5)),
        receipt(state="completed", sequence=2, recorded_at=NOW - timedelta(seconds=6)),
    ]
    with pytest.raises(ValueError):
        review_voice_receipts(snapshot(backwards), now=NOW)


def test_voice_rejects_duplicate_and_oversized_input():
    with pytest.raises(ValueError):
        review_voice_receipts(
            snapshot([receipt(sequence=1), receipt(sequence=1)]), now=NOW,
        )
    with pytest.raises(ValueError):
        review_voice_receipts(snapshot([]), now=NOW)
    oversized = [
        receipt(utterance_id=f"utt:{index}", correlation_ref=f"corr:{index}")
        for index in range(129)
    ]
    with pytest.raises(ValueError):
        review_voice_receipts(snapshot(oversized), now=NOW)


def test_voice_rejects_correlation_reference_change_within_utterance():
    rows = [
        receipt(state="queued", sequence=1),
        receipt(state="completed", sequence=2, correlation_ref="corr:2"),
    ]
    with pytest.raises(ValueError):
        review_voice_receipts(snapshot(rows), now=NOW)


def test_voice_redacts_sensitive_receipt_notes():
    rows = [
        receipt(state="queued", sequence=1),
        receipt(
            state="completed", sequence=2,
            note="token=abc123 C:\\Users\\alice\\voice.wav",
        ),
        receipt(stage="playback", state="queued", sequence=1),
        receipt(
            stage="playback", state="completed", sequence=2,
            note="secret=hunter2 /home/bob/audio.wav alice@example.com",
        ),
    ]
    report = review_voice_receipts(snapshot(rows), now=NOW)
    assert report["redactions"] >= 4
    serialized = json.dumps(report)
    for secret in ("abc123", "Users", "/home/bob", "hunter2", "alice@example.com"):
        assert secret not in serialized
    assert "<redacted>" in serialized


def test_voice_capability_registration_shape():
    registrations = capability_registrations()
    assert isinstance(registrations, tuple) and len(registrations) == 1
    capability, handler = registrations[0]
    assert isinstance(capability, Capability) and callable(handler)
    observed = datetime.now(timezone.utc)
    payload = snapshot([
        receipt(state="queued", sequence=1, recorded_at=observed - timedelta(seconds=2)),
        receipt(state="completed", sequence=2, recorded_at=observed - timedelta(seconds=1)),
    ], observed=observed)
    result = handler(CapabilityRequest(capability, {"snapshot": payload}, None, "review receipts"))
    assert result["status"] == "reviewed"
    assert result["effect"] == "none"
    assert result["audio_device_accessed"] is False
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            Capability(capability.name, "Forged descriptor"),
            {"snapshot": payload}, None, "forged",
        ))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            capability, dict({"snapshot": payload}, command="speak"), None, "invalid",
        ))
