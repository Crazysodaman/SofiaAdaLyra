"""SDK/Platform-only handoff checks. No microphone, model or live host required."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from sofia.modules.voice.prosody_matrix import VoiceProsodyProfile
from sofia.platform.application.voice_expression_bridge import PlatformVoiceExpressionBroker
from sofia.sdk.contracts import (
    AuthorityProjection, ComponentEndpoint, ComponentKind,
    ComponentRequestEnvelope, SDK_PROTOCOL_VERSION,
)
from sofia.sdk.contract_wire import canonical_sha256, canonical_json_bytes
from sofia.sdk.voice_expression import (
    VOICE_EXPRESSION_SCHEMA, VOICE_SYNTHESIZE_SCOPE, VoiceExpressionCue,
)

pytestmark = [pytest.mark.pkg_voice]
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
TEXT = "Hi, I'm Sofia. The system checks out."
CORE = ComponentEndpoint(
    "core:sofia", ComponentKind.CORE, "a" * 64, 2, "platform:artemis",
    "identity:sofia",
)
MODULE = ComponentEndpoint(
    "module:voice", ComponentKind.MODULE, "b" * 64, 4, "platform:venus",
)
AUTH = AuthorityProjection(
    "principal:owner", "audience:owner-private", "private",
    "grant:voice-1", (VOICE_SYNTHESIZE_SCOPE,), NOW + timedelta(minutes=4),
)


class FakeSink:
    def __init__(self):
        self.calls = []

    def submit(self, text, *, profile, correlation_id=None):
        self.calls.append((text, profile, correlation_id))
        return ("queued", len(self.calls))


def cue():
    return VoiceExpressionCue.from_profile(
        core_identity_id=CORE.core_identity_id,
        voice_profile_id="voice:sofia",
        voice_profile_revision=3,
        decision_id="expression:assistant-1",
        message_id="assistant-1",
        audience_id=AUTH.audience_id,
        text_sha256=sha256(TEXT.encode("utf-8")).hexdigest(),
        profile=VoiceProsodyProfile(
            rate_scale=1.0345, pitch_semitones=0.1234,
            energy_scale=1.1, pause_scale=0.97,
            tone_tags=("emotion:amusement",), ambient_context=("season:autumn",),
        ),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=2),
    )


def request(c):
    return ComponentRequestEnvelope(
        protocol=SDK_PROTOCOL_VERSION,
        request_id="request:voice-1",
        correlation_id=c.decision_id,
        idempotency_key="voice:assistant-1",
        source=CORE, destination=MODULE,
        authority=AUTH,
        payload_type=VOICE_EXPRESSION_SCHEMA,
        payload_digest=canonical_sha256(c.to_payload()),
        created_at=NOW,
        deadline=NOW + timedelta(minutes=3),
    )


def harness():
    flags = dict(core=CORE, module=MODULE, authorized=True, output=True, profile=True, text=TEXT)
    seen = set()
    sink = FakeSink()

    def claim_once(key):
        if key in seen:
            return False
        seen.add(key)
        return True

    broker = PlatformVoiceExpressionBroker(
        current_core=lambda _id: flags["core"],
        current_module=lambda _id: flags["module"],
        authorize=lambda _request, _cue: flags["authorized"],
        output_allowed=lambda _id, _aud: flags["output"],
        profile_allowed=lambda _core, _profile, _revision: flags["profile"],
        settled_text=lambda _id, _aud: flags["text"],
        claim_once=claim_once,
        sink=sink,
    )
    return broker, flags, sink


def test_versioned_cue_round_trip_is_canonical_integer_only():
    original = cue()
    raw = original.to_payload()
    assert original == VoiceExpressionCue.from_payload(raw)
    assert original.rate_units == 10345
    assert original.pitch_units == 1234
    assert raw["schema"] == VOICE_EXPRESSION_SCHEMA
    assert b"Hi, I'm Sofia" not in canonical_json_bytes(raw)
    assert b"private key" not in canonical_json_bytes(raw)
    assert len(canonical_sha256(raw)) == 64


def test_broker_hands_authorized_cue_to_sink_once_without_modifying_voice():
    c = cue()
    b, _flags, sink = harness()
    assert b.submit(request(c), c.to_payload(), now=NOW) == ("queued", 1)
    assert len(sink.calls) == 1
    text, profile, correlation = sink.calls[0]
    assert text == TEXT
    assert correlation == c.decision_id
    assert profile.pitch_semitones == pytest.approx(0.1234)
    assert profile.rate_scale == pytest.approx(1.0345)
    assert profile.tone_tags == ("emotion:amusement",)
    with pytest.raises(PermissionError, match="replay"):
        b.submit(request(c), c.to_payload(), now=NOW)
    assert len(sink.calls) == 1


@pytest.mark.parametrize("change", [
    "unauthorized", "muted", "wrong_text", "wrong_core", "wrong_module",
    "no_core", "no_module", "wrong_scope", "wrong_audience", "profile_denied",
    "tampered_payload", "wrong_generation", "expired_cue", "future_cue",
    "wrong_correlation", "wrong_core_id",
])
def test_broker_denies_untrusted_or_stale_handoff_before_tts(change):
    c = cue()
    req = request(c)
    broker, flags, sink = harness()
    at = NOW
    payload = c.to_payload()
    if change == "unauthorized":
        flags["authorized"] = False
    elif change == "muted":
        flags["output"] = False
    elif change == "profile_denied":
        flags["profile"] = False
    elif change == "wrong_text":
        flags["text"] = "Different already-settled message"
    elif change == "wrong_core":
        flags["core"] = replace(CORE, generation=3)
    elif change == "wrong_module":
        flags["module"] = replace(MODULE, release_digest="c" * 64)
    elif change == "no_core":
        flags["core"] = None
    elif change == "no_module":
        flags["module"] = None
    elif change == "wrong_scope":
        req = replace(req, authority=replace(AUTH, scopes=("voice.listen",)))
    elif change == "wrong_audience":
        req = replace(req, authority=replace(AUTH, audience_id="audience:public"))
    elif change == "tampered_payload":
        payload["rate_units"] = 12500
    elif change == "wrong_generation":
        req = replace(req, destination=replace(MODULE, generation=9))
    elif change == "expired_cue":
        at = NOW + timedelta(minutes=2, seconds=1)
    elif change == "future_cue":
        at = NOW - timedelta(seconds=1)
    elif change == "wrong_correlation":
        req = replace(req, correlation_id="expression:another")
    elif change == "wrong_core_id":
        req = replace(req, source=replace(CORE, core_identity_id="identity:other"))
    with pytest.raises((PermissionError, TimeoutError)):
        broker.submit(req, payload, now=at)
    assert sink.calls == []


def test_malformed_unbounded_or_extra_fields_are_rejected():
    raw = cue().to_payload()
    for key, value in (
        ("rate_units", 20000),
        ("pitch_units", True),
        ("tone_tags", ["x" * 100]),
        ("voice_profile_revision", 0),
        ("created_at", "not-a-date"),
    ):
        broken = dict(raw, **{key: value})
        with pytest.raises((ValueError, TypeError)):
            VoiceExpressionCue.from_payload(broken)
    with pytest.raises(ValueError, match="missing or extra"):
        VoiceExpressionCue.from_payload(dict(raw, untrusted="extra"))
    with pytest.raises(ValueError, match="missing or extra"):
        VoiceExpressionCue.from_payload({k: v for k, v in raw.items() if k != "schema"})
