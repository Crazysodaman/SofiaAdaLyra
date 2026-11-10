"""Core-neutral, bounded voice-expression handoff payload.

This describes HOW an already authorized utterance should sound. It is never
an authorization to speak, use a microphone, or access a voice asset.
All numeric controls use units of 1/10,000 so the shared SDK's canonical
integer-only JSON digest can bind the payload across Python/Rust workers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import ClassVar, Mapping

VOICE_EXPRESSION_SCHEMA = "aegis.voice.expression.v1"
VOICE_SYNTHESIZE_SCOPE = "voice.synthesize"
_SCALE = 10_000
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TAG = re.compile(r"[a-z][a-z0-9_.:-]{0,79}\Z")
_FIELDS = frozenset({
    "schema", "core_identity_id", "voice_profile_id", "voice_profile_revision",
    "decision_id", "message_id", "audience_id", "text_sha256",
    "rate_units", "pitch_units", "energy_units", "volume_units", "pause_units",
    "tone_tags", "ambient_context", "created_at", "expires_at",
})
_LIMITS = {
    "rate_units": (7500, 12500),
    "pitch_units": (-20000, 20000),
    "energy_units": (6000, 14000),
    "volume_units": (6000, 13000),
    "pause_units": (7000, 14000),
}


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("voice expression timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a bounded canonical identifier")


@dataclass(frozen=True, slots=True)
class VoiceExpressionCue:
    """Versioned metadata for one Core-owned voice decision.

    No speech text, raw emotion journal, biometric voice sample, asset bytes,
    credentials, or authorization token appears in this payload. The Platform
    resolves its own trusted Core binding and authorized settled message.
    """

    core_identity_id: str
    voice_profile_id: str
    voice_profile_revision: int
    decision_id: str
    message_id: str
    audience_id: str
    text_sha256: str
    rate_units: int
    pitch_units: int
    energy_units: int
    volume_units: int
    pause_units: int
    tone_tags: tuple[str, ...]
    ambient_context: tuple[str, ...]
    created_at: datetime
    expires_at: datetime

    schema: ClassVar[str] = VOICE_EXPRESSION_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "core_identity_id", "voice_profile_id", "decision_id",
            "message_id", "audience_id",
        ):
            _identifier(getattr(self, name), name)
        if not isinstance(self.text_sha256, str) or _SHA.fullmatch(self.text_sha256) is None:
            raise ValueError("text_sha256 must be a lowercase SHA-256 digest")
        if type(self.voice_profile_revision) is not int or self.voice_profile_revision < 1:
            raise ValueError("voice profile revision must be positive")
        for name, (minimum, maximum) in _LIMITS.items():
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be a bounded integer")
        for name in ("tone_tags", "ambient_context"):
            values = getattr(self, name)
            if (
                type(values) is not tuple or len(values) > 16
                or any(type(tag) is not str or _TAG.fullmatch(tag) is None
                       for tag in values)
            ):
                raise ValueError(f"{name} must be a bounded tuple of tags")
        created, expires = _utc(self.created_at), _utc(self.expires_at)
        if not created < expires <= created + timedelta(minutes=5):
            raise ValueError("voice expression lifetime must be at most five minutes")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "core_identity_id": self.core_identity_id,
            "voice_profile_id": self.voice_profile_id,
            "voice_profile_revision": self.voice_profile_revision,
            "decision_id": self.decision_id,
            "message_id": self.message_id,
            "audience_id": self.audience_id,
            "text_sha256": self.text_sha256,
            "rate_units": self.rate_units,
            "pitch_units": self.pitch_units,
            "energy_units": self.energy_units,
            "volume_units": self.volume_units,
            "pause_units": self.pause_units,
            "tone_tags": list(self.tone_tags),
            "ambient_context": list(self.ambient_context),
            "created_at": _utc(self.created_at).isoformat(),
            "expires_at": _utc(self.expires_at).isoformat(),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "VoiceExpressionCue":
        if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
            raise ValueError("voice expression payload has missing or extra fields")
        if payload["schema"] != VOICE_EXPRESSION_SCHEMA:
            raise ValueError("unsupported voice expression schema")
        if type(payload["tone_tags"]) is not list or type(payload["ambient_context"]) is not list:
            raise ValueError("voice expression tags must be arrays")
        for name in ("created_at", "expires_at"):
            if not isinstance(payload[name], str):
                raise ValueError(f"{name} must be an ISO timestamp")
        try:
            return cls(
                core_identity_id=payload["core_identity_id"],
                voice_profile_id=payload["voice_profile_id"],
                voice_profile_revision=payload["voice_profile_revision"],
                decision_id=payload["decision_id"],
                message_id=payload["message_id"],
                audience_id=payload["audience_id"],
                text_sha256=payload["text_sha256"],
                rate_units=payload["rate_units"],
                pitch_units=payload["pitch_units"],
                energy_units=payload["energy_units"],
                volume_units=payload["volume_units"],
                pause_units=payload["pause_units"],
                tone_tags=tuple(payload["tone_tags"]),
                ambient_context=tuple(payload["ambient_context"]),
                created_at=datetime.fromisoformat(payload["created_at"]),
                expires_at=datetime.fromisoformat(payload["expires_at"]),
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid voice expression payload") from exc

    def require_fresh(self, now: datetime) -> None:
        moment = _utc(now)
        if not _utc(self.created_at) <= moment < _utc(self.expires_at):
            raise PermissionError("voice expression is stale or from the future")

    @classmethod
    def from_profile(
        cls, *, core_identity_id: str, voice_profile_id: str,
        voice_profile_revision: int, decision_id: str, message_id: str,
        audience_id: str, text_sha256: str, profile: object,
        created_at: datetime, expires_at: datetime,
    ) -> "VoiceExpressionCue":
        """Project a bounded typed prosody profile without importing the TTS model."""
        names = ("rate_scale", "pitch_semitones", "energy_scale",
                 "volume_scale", "pause_scale")
        for name in names:
            value = getattr(profile, name, None)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a numeric prosody control")
        return cls(
            core_identity_id=core_identity_id,
            voice_profile_id=voice_profile_id,
            voice_profile_revision=voice_profile_revision,
            decision_id=decision_id,
            message_id=message_id,
            audience_id=audience_id,
            text_sha256=text_sha256,
            rate_units=round(profile.rate_scale * _SCALE),
            pitch_units=round(profile.pitch_semitones * _SCALE),
            energy_units=round(profile.energy_scale * _SCALE),
            volume_units=round(profile.volume_scale * _SCALE),
            pause_units=round(profile.pause_scale * _SCALE),
            tone_tags=profile.tone_tags,
            ambient_context=profile.ambient_context,
            created_at=created_at,
            expires_at=expires_at,
        )
