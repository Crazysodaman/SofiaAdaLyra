"""Typed contracts for Sofía's lightweight neural/control layer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re


_SIGNAL_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,120}$")


def _unit_interval(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be in 0..1")


@dataclass(frozen=True, slots=True)
class NeuralSignal:
    """One bounded observed input to the attention network.

    A signal may influence priority only. It is not evidence, permission,
    consent, memory promotion, or an execution receipt. Source/kind identifiers
    are intentionally machine-safe because snapshots may enter SYSTEM context.
    """

    source: str
    kind: str
    value: float
    confidence: float
    novelty: float
    urgency: float
    observed_at: datetime
    ttl_seconds: float = 300.0

    def __post_init__(self) -> None:
        for name in ("source", "kind"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SIGNAL_ID.fullmatch(value) is None:
                raise ValueError(
                    f"{name} must be a bounded machine-safe identifier"
                )
        for name in ("value", "confidence", "novelty", "urgency"):
            _unit_interval(name, getattr(self, name))
        if len(f"{self.kind}:{self.source}") > 120:
            raise ValueError("combined signal key must be at most 120 characters")
        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware")
        if (
            isinstance(self.ttl_seconds, bool)
            or not isinstance(self.ttl_seconds, (int, float))
            or not 1.0 <= float(self.ttl_seconds) <= 86400.0
        ):
            raise ValueError("ttl_seconds must be in 1..86400")


@dataclass(frozen=True, slots=True)
class NeuralActivation:
    key: str
    source: str
    kind: str
    score: float
    novelty: float
    updated_at: datetime

    def __post_init__(self) -> None:
        for name in ("key", "source", "kind"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SIGNAL_ID.fullmatch(value) is None:
                raise ValueError(
                    f"{name} must be a bounded machine-safe identifier"
                )
        _unit_interval("score", self.score)
        _unit_interval("novelty", self.novelty)
        if (
            not isinstance(self.updated_at, datetime)
            or self.updated_at.tzinfo is None
            or self.updated_at.utcoffset() is None
        ):
            raise ValueError("updated_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class HomeostaticState:
    cognitive_load: float = 0.0
    novelty_load: float = 0.0
    competition_pressure: float = 0.0

    def __post_init__(self) -> None:
        _unit_interval("cognitive_load", self.cognitive_load)
        _unit_interval("novelty_load", self.novelty_load)
        _unit_interval("competition_pressure", self.competition_pressure)


@dataclass(frozen=True, slots=True)
class NeuroStateSnapshot:
    generated_at: datetime
    focus: NeuralActivation | None
    secondary: tuple[NeuralActivation, ...] = ()
    homeostasis: HomeostaticState = HomeostaticState()
    active_signal_count: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise ValueError("generated_at must be timezone-aware")
        if self.focus is not None and not isinstance(
            self.focus, NeuralActivation
        ):
            raise TypeError("focus must be NeuralActivation or None")
        if not isinstance(self.secondary, tuple) or any(
            not isinstance(item, NeuralActivation)
            for item in self.secondary
        ):
            raise TypeError("secondary must contain NeuralActivation values")
        if not isinstance(self.homeostasis, HomeostaticState):
            raise TypeError("homeostasis must be HomeostaticState")
        if (
            type(self.active_signal_count) is not int
            or self.active_signal_count < 0
        ):
            raise ValueError("active_signal_count must be a nonnegative int")

    def prompt(self) -> str:
        """Return a bounded provider projection with explicit epistemic limits."""
        lines = [
            "NEURAL ATTENTION CONTEXT",
            (
                "This is host-computed prioritization context only. It may "
                "influence attention and response emphasis, but it is NOT "
                "evidence, memory, permission, consent, preference, emotion, "
                "tool authority, or proof that an action occurred."
            ),
            (
                "Never turn a high activation score into a factual claim. "
                "Use normal Matrix evidence and authority rules for truth and action."
            ),
            f"Active signals: {self.active_signal_count}",
            (
                "Homeostasis: "
                f"cognitive_load={self.homeostasis.cognitive_load:.3f}; "
                f"novelty_load={self.homeostasis.novelty_load:.3f}; "
                f"competition_pressure={self.homeostasis.competition_pressure:.3f}"
            ),
        ]
        if self.focus is None:
            lines.append("Primary attention: none")
            return "\n".join(lines)
        lines.append(
            "Primary attention: "
            f"{self.focus.key} ({self.focus.score:.3f})"
        )
        if self.secondary:
            lines.append(
                "Secondary attention: "
                + ", ".join(
                    f"{item.key} ({item.score:.3f})"
                    for item in self.secondary[:3]
                )
            )
        return "\n".join(lines)


class NeuroWakeMode(str, Enum):
    """Advisory compute tier; it never grants execution authority."""

    NONE = "none"
    DETERMINISTIC = "deterministic"
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    VERIFY = "verify"


@dataclass(frozen=True, slots=True)
class NeuroRoutingDecision:
    mode: NeuroWakeMode
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.mode, NeuroWakeMode):
            raise TypeError("mode must be NeuroWakeMode")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("routing reason must be nonempty")
