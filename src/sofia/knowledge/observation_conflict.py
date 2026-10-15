"""Sensory contradiction handling and clock-skew detection (V18 CA-6406).

The original requirement asks for explicit handling of contradictions such as
"screen says service running" versus a host reporting stopped, a voice
transcript versus a later correction, and a remote log timestamp versus an
on-device clock: the disagreement must be *stored and verified*, never silently
merged into an enduring false memory.

This module is a pure decision contract. It compares two typed observations of
the same subject/predicate and returns a contradiction record that names the
disagreement, preserves both sources, and prescribes an authorized verification.
It never writes memory and never claims that one transient view is truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ObservationSource(str, Enum):
    HOST_RECEIPT = "host_receipt"
    TRUSTED_VERIFICATION = "trusted_verification"
    APP_API = "app_api"
    SCREEN_CAPTURE = "screen_capture"
    VOICE_TRANSCRIPT = "voice_transcript"
    DEVICE_CLOCK = "device_clock"
    MODEL_INFERENCE = "model_inference"


# Higher rank is more authoritative for an *observation* claim. Model inference
# and raw screen text are deliberately weak; they must not overwrite a host
# receipt or an authorized verification.
_AUTHORITY = {
    ObservationSource.MODEL_INFERENCE: 0,
    ObservationSource.SCREEN_CAPTURE: 1,
    ObservationSource.VOICE_TRANSCRIPT: 1,
    ObservationSource.DEVICE_CLOCK: 1,
    ObservationSource.APP_API: 2,
    ObservationSource.HOST_RECEIPT: 3,
    ObservationSource.TRUSTED_VERIFICATION: 4,
}


class ConflictError(ValueError):
    """Raised when an observation or comparison is malformed."""


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    subject: str
    predicate: str
    value: str
    source: ObservationSource
    observed_at: datetime

    def __post_init__(self) -> None:
        for name, value in (
            ("observation_id", self.observation_id),
            ("subject", self.subject),
            ("predicate", self.predicate),
        ):
            if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
                raise ConflictError(f"{name} must be a bounded identifier")
        if not isinstance(self.value, str) or not self.value.strip():
            raise ConflictError("observation value must be non-empty text")
        if not isinstance(self.source, ObservationSource):
            raise TypeError("source must be ObservationSource")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ConflictError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Contradiction:
    """A preserved disagreement plus the required authorized verification."""

    subject: str
    predicate: str
    first: Observation
    second: Observation
    kind: str
    preferred_source: ObservationSource | None
    requires_verification: bool
    reason: str

    def __post_init__(self) -> None:
        if self.requires_verification is False and self.preferred_source is None:
            raise ConflictError(
                "a settled contradiction must name a preferred source"
            )


def compare_observations(first: Observation, second: Observation) -> Contradiction | None:
    """Return a contradiction if two observations disagree, else ``None``.

    Different subjects or predicates are simply unrelated observations. A clock
    disagreement (same value observed from a device clock versus a trusted
    receipt with a materially different time) is reported as ``clock_skew`` and
    never resolves which statement supersedes another.
    """
    if not isinstance(first, Observation) or not isinstance(second, Observation):
        raise TypeError("compare_observations requires two Observation values")
    if (first.subject, first.predicate) != (second.subject, second.predicate):
        return None
    if first.value == second.value:
        return None
    # Clock skew: an identical value with a large observed_at gap from a device
    # clock is a time-trust problem, not a value disagreement.
    if first.source is ObservationSource.DEVICE_CLOCK or (
        second.source is ObservationSource.DEVICE_CLOCK
    ):
        other = second if first.source is ObservationSource.DEVICE_CLOCK else first
        delta = abs((first.observed_at - second.observed_at).total_seconds())
        if delta >= 60 and other.value == (
            second.value if first.source is ObservationSource.DEVICE_CLOCK
            else first.value
        ):
            return Contradiction(
                subject=first.subject, predicate=first.predicate,
                first=first, second=second, kind="clock_skew",
                preferred_source=None, requires_verification=True,
                reason="device clock disagrees with a trusted observation time; "
                       "do not reorder history from an untrusted wall clock",
            )
    rank_first = _AUTHORITY[first.source]
    rank_second = _AUTHORITY[second.source]
    if rank_first == rank_second:
        return Contradiction(
            subject=first.subject, predicate=first.predicate,
            first=first, second=second, kind="value_conflict",
            preferred_source=None, requires_verification=True,
            reason="equally trusted sources disagree; seek authorized "
                   "verification before concluding",
        )
    winner = first if rank_first > rank_second else second
    if winner.source in (
        ObservationSource.HOST_RECEIPT, ObservationSource.TRUSTED_VERIFICATION,
    ):
        return Contradiction(
            subject=first.subject, predicate=first.predicate,
            first=first, second=second, kind="value_conflict",
            preferred_source=winner.source, requires_verification=False,
            reason="an authoritative verification outranks a transient view; "
                   "still record the lower-trust disagreement",
        )
    return Contradiction(
        subject=first.subject, predicate=first.predicate,
        first=first, second=second, kind="value_conflict",
        preferred_source=None, requires_verification=True,
        reason="no authoritative verification exists between two weak sources",
    )
