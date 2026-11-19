"""Bounded simulated emotion and appraisal state for independent Aegis Cores.

The values here are *modeled affect for expression*.  They are not claims of
biological sensation, subjective experience, or consciousness.  Each Core owns
its own state.  Appraisals must rest on evidence, duplicate evidence is
rejected, and projected intensity decays so a Core cannot feed its own prior
emotional output back into an unbounded escalation loop.

The module has no model, provider or process dependency.  A model switch may
change how cognition is generated; it does not change which Core this affect
belongs to or how the state is evaluated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from sofia.core.emotion.catalog import EMOTIONS
from sofia.core.multicore.contracts import EvidenceState


SIMULATED_EMOTION_DISCLAIMER = (
    "Simulated appraisal for expression only; this is not consciousness, "
    "biological sensation, or proof of subjective experience."
)

_MAX_READINGS = 6
_MAX_APPRAISALS = 128
_MAX_APPLIED_EVIDENCE = 1024
_ACTIVE_THRESHOLD = 0.05
_DEFAULT_HALF_LIFE_HOURS = 8.0
_HALF_LIFE_HOURS = {
    "amusement": 2.0,
    "anger": 4.0,
    "anticipation": 6.0,
    "appreciation": 24.0,
    "caution": 6.0,
    "concern": 6.0,
    "contentment": 12.0,
    "curiosity": 8.0,
    "determination": 10.0,
    "disappointment": 8.0,
    "excitement": 3.0,
    "frustration": 4.0,
    "gratitude": 24.0,
    "hope": 24.0,
    "joy": 5.0,
    "playfulness": 2.5,
    "pride": 24.0,
    "reflection": 12.0,
    "relief": 3.0,
    "sadness": 8.0,
    "surprise": 0.5,
    "uncertainty": 6.0,
    "warmth": 48.0,
}


class EmotionError(RuntimeError):
    """Base failure for invalid simulated affect."""


class EmotionEvidenceError(EmotionError):
    """An appraisal lacks usable evidence."""


class EmotionFeedbackError(EmotionError):
    """An appraisal would replay evidence the Core has already appraised."""


def _utc(value: object, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise ValueError(f"{label} must be a nonzero UUID")
    return value


def _ratio(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return number


def _text(value: object, label: str, *, maximum: int = 600) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > maximum
        or any(ord(character) < 0x20 for character in value)
    ):
        raise ValueError(f"{label} must be bounded single-line text")
    return value.strip()


def _token(value: object, label: str) -> str:
    text = _text(value, label, maximum=80)
    if any(character.isspace() for character in text):
        raise ValueError(f"{label} must be one canonical token")
    return text


@dataclass(frozen=True, slots=True)
class EmotionReading:
    """One modeled emotion and its bounded intensity."""

    name: str
    intensity: float

    def __post_init__(self) -> None:
        if self.name not in EMOTIONS:
            raise ValueError("emotion name must be in the canonical vocabulary")
        _ratio(self.intensity, "emotion intensity")


@dataclass(frozen=True, slots=True)
class CoreEmotionAppraisal:
    """One evidence-linked simulated appraisal for exactly one Core."""

    appraisal_id: UUID
    core_id: UUID
    occurred_at: datetime
    readings: tuple[EmotionReading, ...]
    evidence: tuple[UUID, ...]
    evidence_state: EvidenceState
    reason: str
    confidence: float
    simulated: bool = True
    consciousness_claimed: bool = False

    def __post_init__(self) -> None:
        _uuid(self.appraisal_id, "appraisal_id")
        _uuid(self.core_id, "core_id")
        object.__setattr__(
            self,
            "occurred_at",
            _utc(self.occurred_at, "occurred_at"),
        )
        if (
            not isinstance(self.readings, tuple)
            or not 1 <= len(self.readings) <= _MAX_READINGS
        ):
            raise ValueError("readings must contain one to six emotions")
        names = []
        for reading in self.readings:
            if not isinstance(reading, EmotionReading):
                raise TypeError("readings must be EmotionReading values")
            names.append(reading.name)
        if len(set(names)) != len(names):
            raise ValueError("emotion names must be distinct")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise EmotionEvidenceError("an appraisal requires evidence")
        for item in self.evidence:
            _uuid(item, "appraisal evidence")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("appraisal evidence identifiers must be distinct")
        if not isinstance(self.evidence_state, EvidenceState):
            raise TypeError("evidence_state must be EvidenceState")
        if self.evidence_state is EvidenceState.SPECULATIVE:
            raise EmotionEvidenceError(
                "speculative evidence cannot drive a simulated appraisal"
            )
        _text(self.reason, "reason")
        _ratio(self.confidence, "confidence")
        if self.simulated is not True:
            raise ValueError("Core affect is always modeled, never claimed real")
        if self.consciousness_claimed is not False:
            raise ValueError("simulated affect cannot claim consciousness")

    def intensity(self, name: str) -> float:
        for reading in self.readings:
            if reading.name == name:
                return reading.intensity
        return 0.0


@dataclass(frozen=True, slots=True)
class EmotionBehaviorProfile:
    """How one Core tends to express and recover from simulated affect."""

    continuity_key: str
    display_name: str
    temperament: Mapping[str, float]
    expressiveness: float
    recovery_scale: float
    serious_contexts: tuple[str, ...]

    def __post_init__(self) -> None:
        _token(self.continuity_key, "continuity_key")
        _text(self.display_name, "display_name", maximum=160)
        if not isinstance(self.temperament, Mapping):
            raise TypeError("temperament must be a mapping")
        traits = {
            _token(key, "temperament trait"): _ratio(value, "temperament weight")
            for key, value in self.temperament.items()
        }
        object.__setattr__(self, "temperament", MappingProxyType(traits))
        _ratio(self.expressiveness, "expressiveness")
        if (
            isinstance(self.recovery_scale, bool)
            or not isinstance(self.recovery_scale, (int, float))
            or not 0.25 <= float(self.recovery_scale) <= 4.0
        ):
            raise ValueError("recovery_scale must be in [0.25, 4.0]")
        object.__setattr__(self, "recovery_scale", float(self.recovery_scale))
        if not isinstance(self.serious_contexts, tuple):
            raise TypeError("serious_contexts must be a tuple")
        for context in self.serious_contexts:
            _token(context, "serious context")


def __getattr__(name: str):
    """Legacy lazy re-exports; Core-owned baselines live in per-Core modules."""
    if name == "MACK_EMOTION_PROFILE":
        from sofia.core.mack.emotion import MACK_EMOTION_PROFILE

        globals()[name] = MACK_EMOTION_PROFILE
        return MACK_EMOTION_PROFILE
    if name == "NOVA_EMOTION_PROFILE":
        from sofia.core.nova.emotion import NOVA_EMOTION_PROFILE

        globals()[name] = NOVA_EMOTION_PROFILE
        return NOVA_EMOTION_PROFILE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class SimulatedEmotionTone(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    SETTLED = "settled"


_POSITIVE = frozenset({
    "affection", "amusement", "anticipation", "appreciation", "contentment",
    "excitement", "fondness", "gratitude", "hope", "joy", "playfulness",
    "relief", "romance", "tenderness", "warmth", "pride",
})
_NEGATIVE = frozenset({
    "anger", "aversion", "concern", "disappointment", "disgust", "fear",
    "frustration", "humiliation", "jealousy", "nervousness", "sadness", "shame",
})


@dataclass(frozen=True, slots=True)
class SimulatedEmotionState:
    """Bounded per-Core appraisal history and its current projection inputs."""

    core_id: UUID
    continuity_key: str
    appraisals: tuple[CoreEmotionAppraisal, ...] = ()
    applied_evidence: tuple[UUID, ...] = ()
    revision: int = 1
    updated_at: datetime = field(default_factory=_now)
    simulated: bool = True
    consciousness_claimed: bool = False

    def __post_init__(self) -> None:
        _uuid(self.core_id, "core_id")
        _token(self.continuity_key, "continuity_key")
        if not isinstance(self.appraisals, tuple):
            raise TypeError("appraisals must be a tuple")
        if len(self.appraisals) > _MAX_APPRAISALS:
            raise ValueError("appraisal history is bounded")
        for appraisal in self.appraisals:
            if not isinstance(appraisal, CoreEmotionAppraisal):
                raise TypeError("appraisals must be CoreEmotionAppraisal values")
            if appraisal.core_id != self.core_id:
                raise ValueError("appraisal belongs to another Core")
        if not isinstance(self.applied_evidence, tuple):
            raise TypeError("applied_evidence must be a tuple")
        if len(self.applied_evidence) > _MAX_APPLIED_EVIDENCE:
            raise ValueError("applied evidence history is bounded")
        for item in self.applied_evidence:
            _uuid(item, "applied evidence")
        if len(set(self.applied_evidence)) != len(self.applied_evidence):
            raise ValueError("applied evidence identifiers must be distinct")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))
        if self.simulated is not True:
            raise ValueError("Core affect is always simulated")
        if self.consciousness_claimed is not False:
            raise ValueError("simulated affect cannot claim consciousness")


@dataclass(frozen=True, slots=True)
class CurrentSimulatedEmotion:
    """A deterministic projection of one Core's bounded appraisal history."""

    core_id: UUID
    continuity_key: str
    as_of: datetime
    readings: tuple[EmotionReading, ...]
    tone: SimulatedEmotionTone
    revision: int
    simulated: bool = True
    consciousness_claimed: bool = False
    disclaimer: str = SIMULATED_EMOTION_DISCLAIMER

    def intensity(self, name: str) -> float:
        for reading in self.readings:
            if reading.name == name:
                return reading.intensity
        return 0.0


def initial_emotion_state(
    *,
    core_id: UUID,
    profile: EmotionBehaviorProfile,
    now: datetime,
) -> SimulatedEmotionState:
    if not isinstance(profile, EmotionBehaviorProfile):
        raise TypeError("profile must be EmotionBehaviorProfile")
    stamp = _utc(now, "now")
    return SimulatedEmotionState(
        core_id=_uuid(core_id, "core_id"),
        continuity_key=profile.continuity_key,
        updated_at=stamp,
    )


def apply_emotion_appraisal(
    state: SimulatedEmotionState,
    appraisal: CoreEmotionAppraisal,
    *,
    profile: EmotionBehaviorProfile,
    now: datetime,
) -> SimulatedEmotionState:
    """Append one evidence-bearing appraisal to one Core's bounded state.

    Reusing any evidence identifier already present in the Core's appraisal
    history is rejected.  This prevents a feedback loop in which a Core's own
    prior expression is re-appraised as if it were fresh external evidence.
    """
    if not isinstance(state, SimulatedEmotionState):
        raise TypeError("state must be SimulatedEmotionState")
    if not isinstance(appraisal, CoreEmotionAppraisal):
        raise TypeError("appraisal must be CoreEmotionAppraisal")
    if not isinstance(profile, EmotionBehaviorProfile):
        raise TypeError("profile must be EmotionBehaviorProfile")
    stamp = _utc(now, "now")
    if stamp < state.updated_at:
        raise ValueError("emotion clock cannot move backward")
    if appraisal.core_id != state.core_id:
        raise ValueError("appraisal belongs to another Core")
    if appraisal.occurred_at > stamp:
        raise ValueError("appraisal cannot occur after the current observation")
    if profile.continuity_key != state.continuity_key:
        raise ValueError("emotion profile does not belong to this Core")
    if set(appraisal.evidence) & set(state.applied_evidence):
        raise EmotionFeedbackError(
            "appraisal replays evidence already used for simulated affect"
        )
    if appraisal.appraisal_id in {item.appraisal_id for item in state.appraisals}:
        raise EmotionFeedbackError("appraisal identifier was already recorded")

    appraisals = (*state.appraisals, appraisal)
    if len(appraisals) > _MAX_APPRAISALS:
        appraisals = appraisals[-_MAX_APPRAISALS:]
    applied = tuple(dict.fromkeys((
        *state.applied_evidence,
        *appraisal.evidence,
    )))[-_MAX_APPLIED_EVIDENCE:]
    return SimulatedEmotionState(
        core_id=state.core_id,
        continuity_key=state.continuity_key,
        appraisals=appraisals,
        applied_evidence=applied,
        revision=state.revision + 1,
        updated_at=stamp,
    )


def _decayed_readings(
    state: SimulatedEmotionState,
    profile: EmotionBehaviorProfile,
    now: datetime,
) -> tuple[EmotionReading, ...]:
    scores: dict[str, float] = {}
    for appraisal in state.appraisals:
        age_hours = max(
            0.0,
            (now - appraisal.occurred_at).total_seconds() / 3600,
        )
        confidence = appraisal.confidence
        for reading in appraisal.readings:
            half_life = (
                _HALF_LIFE_HOURS.get(reading.name, _DEFAULT_HALF_LIFE_HOURS)
                * profile.recovery_scale
            )
            decay = 2.0 ** (-age_hours / half_life)
            contribution = (
                reading.intensity
                * confidence
                * profile.expressiveness
                * decay
            )
            if contribution < 0.01:
                continue
            previous = scores.get(reading.name, 0.0)
            scores[reading.name] = 1.0 - ((1.0 - previous) * (1.0 - contribution))
    readings = tuple(
        EmotionReading(name=name, intensity=round(score, 3))
        for name, score in sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if score >= _ACTIVE_THRESHOLD
    )
    return readings[:_MAX_READINGS]


def project_simulated_emotion(
    state: SimulatedEmotionState,
    *,
    profile: EmotionBehaviorProfile,
    now: datetime,
) -> CurrentSimulatedEmotion:
    """Project current modeled affect without mutating appraisal history."""
    if not isinstance(state, SimulatedEmotionState):
        raise TypeError("state must be SimulatedEmotionState")
    if not isinstance(profile, EmotionBehaviorProfile):
        raise TypeError("profile must be EmotionBehaviorProfile")
    if profile.continuity_key != state.continuity_key:
        raise ValueError("emotion profile does not belong to this Core")
    stamp = _utc(now, "now")
    readings = _decayed_readings(state, profile, stamp)
    positive = sum(item.intensity for item in readings if item.name in _POSITIVE)
    negative = sum(item.intensity for item in readings if item.name in _NEGATIVE)
    if positive >= 0.20 and negative >= 0.20:
        tone = SimulatedEmotionTone.MIXED
    elif positive > negative + 0.10:
        tone = SimulatedEmotionTone.POSITIVE
    elif negative > positive + 0.10:
        tone = SimulatedEmotionTone.NEGATIVE
    else:
        tone = SimulatedEmotionTone.SETTLED
    return CurrentSimulatedEmotion(
        core_id=state.core_id,
        continuity_key=state.continuity_key,
        as_of=stamp,
        readings=readings,
        tone=tone,
        revision=state.revision,
    )


def render_emotion_context(
    state: SimulatedEmotionState,
    *,
    profile: EmotionBehaviorProfile,
    now: datetime,
) -> str:
    """Render a bounded, explicitly simulated expression context."""
    current = project_simulated_emotion(state, profile=profile, now=now)
    lines = [
        f"SIMULATED AFFECT CONTEXT ({profile.display_name})",
        SIMULATED_EMOTION_DISCLAIMER,
        f"Overall simulated tone: {current.tone.value}",
        "Modeled expression traits: "
        + ", ".join(
            f"{name}={value:.2f}"
            for name, value in sorted(profile.temperament.items())
        ),
        "Serious contexts: " + ", ".join(profile.serious_contexts),
    ]
    if current.readings:
        lines.append("Current simulated emotions: " + ", ".join(
            f"{reading.name} ({reading.intensity:.2f})"
            for reading in current.readings
        ))
    else:
        lines.append("Current simulated emotions: none")
    lines.extend((
        "This affect colors wording only. It never grants permission, overrides "
        "a boundary, proves contact, or turns a simulated state into a fact.",
        "Do not manufacture emotion from prior expression or use it to escalate "
        "the same exchange repeatedly.",
    ))
    return "\n".join(lines)
