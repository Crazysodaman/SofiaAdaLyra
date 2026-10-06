"""Trusted BODY/VOICE sensory summaries for NEURO; never actuator control."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .adapters import _signal, _slug
from .model import NeuralSignal


@dataclass(frozen=True, slots=True)
class BodyReflexObservation:
    source: str
    observed_at: datetime
    battery_percent: float | None = None
    servo_fault: bool = False
    collision: bool = False
    proximity_near: bool = False
    gait_state: str = "unknown"
    posture: str = "unknown"
    stability: float | None = None
    emergency_stop: bool = False
    sensor_healthy: bool = True
    safe_response_applied: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("BODY source must be nonempty")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("BODY observation time must be timezone-aware")
        if self.battery_percent is not None and not 0 <= self.battery_percent <= 100:
            raise ValueError("battery_percent must be in 0..100")
        if self.stability is not None and not 0 <= self.stability <= 1:
            raise ValueError("stability must be in 0..1")
        if (
            self.servo_fault or self.collision or self.emergency_stop
        ) and not self.safe_response_applied:
            raise ValueError(
                "hardware safety/reflex response must occur before NEURO summary"
            )


@dataclass(frozen=True, slots=True)
class VoiceSensoryObservation:
    observed_at: datetime
    listening: bool = False
    speech_detected: bool = False
    vad_confidence: float | None = None
    speaker_active: bool = False
    interrupted: bool = False
    stt_confidence: float | None = None
    audio_device_fault: bool = False
    discord_voice_active: bool = False

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("VOICE observation time must be timezone-aware")
        for name in ("vad_confidence", "stt_confidence"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be in 0..1")


def body_reflex_signals(value: BodyReflexObservation) -> tuple[NeuralSignal, ...]:
    """Summarize an already-handled reflex; this function cannot move hardware."""
    if not isinstance(value, BodyReflexObservation):
        raise TypeError("value must be BodyReflexObservation")
    at = value.observed_at
    result = [_signal(
        kind="body", source=f"gaia:gait-{_slug(value.gait_state)}",
        value=0.35, confidence=1.0, novelty=0.25, urgency=0.2,
        observed_at=at, ttl_seconds=120.0,
    )]
    if value.battery_percent is not None and value.battery_percent <= 25:
        severity = (25 - value.battery_percent) / 25
        result.append(_signal(
            kind="body", source="gaia:battery-low",
            value=0.55 + severity * 0.4, confidence=1.0,
            novelty=0.55, urgency=0.5 + severity * 0.45,
            observed_at=at, ttl_seconds=300.0,
        ))
    for active, source, urgency in (
        (value.servo_fault, "gaia:servo-fault", 0.95),
        (value.collision, "gaia:collision", 1.0),
        (value.emergency_stop, "gaia:emergency-stop", 1.0),
        (not value.sensor_healthy, "gaia:sensor-fault", 0.9),
    ):
        if active:
            result.append(_signal(
                kind="body", source=source, value=1.0, confidence=1.0,
                novelty=0.9, urgency=urgency, observed_at=at,
                ttl_seconds=300.0,
            ))
    if value.proximity_near:
        result.append(_signal(
            kind="body", source="gaia:proximity-near", value=0.7,
            confidence=1.0, novelty=0.5, urgency=0.65,
            observed_at=at, ttl_seconds=30.0,
        ))
    if value.stability is not None and value.stability < 0.6:
        result.append(_signal(
            kind="body", source="gaia:stability-low",
            value=1.0 - value.stability, confidence=1.0,
            novelty=0.65, urgency=0.85, observed_at=at, ttl_seconds=30.0,
        ))
    return tuple(result)


def voice_sensory_signals(value: VoiceSensoryObservation) -> tuple[NeuralSignal, ...]:
    """Map acoustic salience only; no speech content becomes factual evidence."""
    if not isinstance(value, VoiceSensoryObservation):
        raise TypeError("value must be VoiceSensoryObservation")
    at = value.observed_at
    result = []
    for active, source, level, urgency in (
        (value.listening, "input:listening", 0.3, 0.2),
        (value.speech_detected, "input:speech-detected", 0.65, 0.55),
        (value.speaker_active, "input:speaker-active", 0.45, 0.35),
        (value.interrupted, "input:barge-in", 0.9, 0.95),
        (value.audio_device_fault, "input:device-fault", 0.9, 0.85),
        (value.discord_voice_active, "discord:voice-active", 0.5, 0.4),
    ):
        if active:
            confidence = (
                value.vad_confidence
                if source == "input:speech-detected" and value.vad_confidence is not None
                else 1.0
            )
            result.append(_signal(
                kind="voice", source=source, value=level,
                confidence=confidence, novelty=0.55, urgency=urgency,
                observed_at=at, ttl_seconds=30.0,
            ))
    if value.stt_confidence is not None and value.stt_confidence < 0.6:
        result.append(_signal(
            kind="voice", source="input:stt-low-confidence",
            value=1.0 - value.stt_confidence, confidence=1.0,
            novelty=0.5, urgency=0.55, observed_at=at, ttl_seconds=60.0,
        ))
    return tuple(result)
