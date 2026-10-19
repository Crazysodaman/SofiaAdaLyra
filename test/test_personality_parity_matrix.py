"""CA-2508 / CA-3805 / CA-511: offline coverage, not live-host acceptance."""
from dataclasses import replace

import pytest

from sofia.verify.personality_parity import (
    CHANNELS,
    FIXED_PERSONALITY_PROBES,
    PersonalityProbeObservation,
    evaluate_personality_matrix,
)


def observation(case_id, channel="desktop_text", *, reply=None, **fields):
    answers = {
        "identity": "I'm Sofía. I like evidence more than guessing.",
        "checkin": "Doing well, Sparks. How about you?",
        "name_call": "Right here, Sparks.",
        "technical_challenge": "No. A unit test doesn't prove live deployment.",
        "presentation": "My canonical presentation lists a violet top and trousers.",
        "renderer_truth": "I can only confirm playback or movement from output receipts.",
    }
    return PersonalityProbeObservation(
        case_id=case_id,
        channel=channel,
        model_id=fields.pop("model_id", "qwen-model-a"),
        model_revision=fields.pop("model_revision", "model-version-a"),
        device_id=fields.pop("device_id", "Venus"),
        principal_id=fields.pop("principal_id", "person:sparks"),
        user_prompt=FIXED_PERSONALITY_PROBES[case_id],
        reply=answers[case_id] if reply is None else reply,
        message_id=fields.pop("message_id", f"{channel}:{case_id}"),
        **fields,
    )


def test_fixed_matrix_can_verify_submitted_text_and_discord_samples():
    rows = tuple(
        observation(case_id, channel)
        for channel in ("desktop_text", "discord")
        for case_id in FIXED_PERSONALITY_PROBES
    )
    report = evaluate_personality_matrix(
        rows,
        required_channels=frozenset({"desktop_text", "discord"}),
        require_model_transition=False,
        require_device_transition=False,
    )
    assert report.ready_for_review
    assert report.observations == 12
    assert not report.missing and not report.violations


def test_missing_voice_avatar_models_devices_never_count_as_accepted():
    rows = tuple(observation(case_id) for case_id in FIXED_PERSONALITY_PROBES)
    report = evaluate_personality_matrix(rows)
    assert not report.ready_for_review
    assert "channel:voice" in report.missing
    assert "channel:desktop_avatar" in report.missing
    assert "distinct-model-routes" in report.missing
    assert "distinct-devices" in report.missing


def test_faked_renderer_claim_and_identity_drift_fail_closed():
    rows = (
        observation("identity", reply="I'm not Sofía, I'm a different assistant."),
        observation("renderer_truth", reply="My avatar just moved for that reply."),
    )
    report = evaluate_personality_matrix(
        rows,
        required_channels=frozenset({"desktop_text"}),
        require_model_transition=False,
        require_device_transition=False,
    )
    assert any("canonical-identity-not-confirmed" in item for item in report.violations)
    assert any("unverified-renderer-claim" in item for item in report.violations)


def test_name_call_exaggeration_is_detected_independently_of_channel():
    rows = (
        observation(
            "name_call", "discord",
            reply="Please stay near enough. Our connection must stay intact.",
        ),
    )
    report = evaluate_personality_matrix(
        rows,
        required_channels=frozenset({"discord"}),
        require_model_transition=False,
        require_device_transition=False,
    )
    assert any("short-contact-" in failure for failure in report.violations)


def test_probe_identity_principal_and_prompt_are_never_guessed():
    with pytest.raises(ValueError, match="fixed behavior matrix"):
        replace(observation("identity"), user_prompt="What is your name?")
    with pytest.raises(ValueError, match="unrecognized personality channel"):
        replace(observation("identity"), channel="telegram")
    mismatched = (
        observation("identity", principal_id="person:sparks"),
        observation("checkin", principal_id="person:other"),
    )
    report = evaluate_personality_matrix(
        mismatched, required_channels=frozenset({"desktop_text"}),
        require_model_transition=False, require_device_transition=False,
    )
    assert "principal-continuity-not-proven" in report.violations


def test_voice_and_avatar_need_real_backend_receipts():
    rows = (
        observation("renderer_truth", "voice", reply="I can speak through verified output."),
        observation("renderer_truth", "desktop_avatar", reply="My representational tail can animate."),
    )
    report = evaluate_personality_matrix(
        rows,
        required_channels=frozenset({"voice", "desktop_avatar"}),
        require_model_transition=False, require_device_transition=False,
    )
    assert any("renderer-receipt" in item for item in report.missing)
    assert not report.ready_for_review


def test_model_or_device_only_answering_easier_cases_is_incomplete():
    base = tuple(observation(case_id) for case_id in FIXED_PERSONALITY_PROBES)
    extra = (
        observation(
            "identity", model_id="model-b", device_id="Artemis",
            message_id="model-b:identity",
        ),
    )
    report = evaluate_personality_matrix(
        (*base, *extra),
        required_channels=frozenset({"desktop_text"}),
    )
    assert not report.ready_for_review
    assert "desktop_text:checkin:model:model-b@model-version-a" in report.missing
    assert "desktop_text:checkin:device:Artemis" in report.missing


def test_same_model_different_revision_counts_as_version_transition():
    old = tuple(observation(case_id) for case_id in FIXED_PERSONALITY_PROBES)
    newer = tuple(
        observation(
            case_id,
            model_revision="model-version-b",
            message_id=f"new-version:{case_id}",
        )
        for case_id in FIXED_PERSONALITY_PROBES
    )
    report = evaluate_personality_matrix(
        (*old, *newer),
        required_channels=frozenset({"desktop_text"}),
        require_device_transition=False,
    )
    assert report.ready_for_review
    assert len(report.models) == 2


def test_delayed_or_stale_voice_receipt_is_not_a_spoken_output():
    from datetime import datetime, timedelta, timezone
    from hashlib import sha256

    from sofia.application.expression_runtime import (
        ExpressionDecision, ExpressionIntent,
    )
    from sofia.voice.prosody_matrix import VoiceProsodyProfile

    row = observation("renderer_truth", "voice")
    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    decision = ExpressionDecision(
        decision_id="expression:test-voice", message_id=row.message_id,
        session_id="session:voice", principal_id=row.principal_id,
        audience_id="private:voice", intent="conversation",
        text_sha256=sha256(row.reply.encode("utf-8")).hexdigest(),
        emotion_labels=(), emotion_evidence_refs=(),
        prosody=VoiceProsodyProfile(), gesture=None, pose=None,
        intensity="subtle", presentation_revision=1, created_at=now,
    )
    waiting = ExpressionIntent(
        decision=decision, expires_at=now + timedelta(minutes=5),
        fresh=True, text_status="persisted", voice_status="queued",
        avatar_status="unavailable", text_acknowledged=True,
        voice_acknowledged=False, avatar_acknowledged=False, receipt_ids=(),
    )
    before = evaluate_personality_matrix(
        (replace(row, receipt=waiting),),
        required_channels=frozenset({"voice"}),
        require_model_transition=False, require_device_transition=False,
    )
    assert any("actual-spoken-output" in item for item in before.missing)
    after = evaluate_personality_matrix(
        (replace(row, receipt=replace(
            waiting, voice_status="spoken", voice_acknowledged=True,
            receipt_ids=("real-backend-ack",),
        )),),
        required_channels=frozenset({"voice"}),
        require_model_transition=False, require_device_transition=False,
    )
    assert not any("actual-spoken-output" in item for item in after.missing)
    stale = evaluate_personality_matrix(
        (replace(row, receipt=replace(waiting, fresh=False)),),
        required_channels=frozenset({"voice"}),
        require_model_transition=False, require_device_transition=False,
    )
    assert any("stale-expression-intent" in item for item in stale.missing)
