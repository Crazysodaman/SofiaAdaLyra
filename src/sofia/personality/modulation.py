"""Deterministic, non-authoritative per-turn personality expression weights."""
from __future__ import annotations

from dataclasses import dataclass
import re

from sofia.cognition.matrix.model import MatrixDomain, TurnMatrix
from sofia.neuro.model import NeuroStateSnapshot

from .influence import ContinuityInfluence


_TECHNICAL_DOMAINS = frozenset({
    MatrixDomain.DEV, MatrixDomain.OPS, MatrixDomain.COGNITION,
    MatrixDomain.MACHINE, MatrixDomain.INTEGRATE, MatrixDomain.KNOW,
})
_AFFECTION = frozenset({
    "affection", "fondness", "warmth", "tenderness", "gratitude",
    "appreciation", "romance", "contentment",
})
_FLUSTER = frozenset({"bashfulness", "embarrassment", "affectionate-uncertainty"})
_PLAYFUL = frozenset({"amusement", "playfulness", "curiosity", "pride", "excitement"})
_SERIOUS = frozenset({"fear", "sadness", "concern", "shame", "humiliation"})
_DISAGREEMENT = re.compile(
    r"\b(?:wrong|disagree|that\s+doesn(?:'|’)t\s+follow|prove\s+it|"
    r"evidence|counterexample|actually|no\s*,)\b",
    re.IGNORECASE,
)
_AFFECTION_CUE = re.compile(
    r"\b(?:kiss(?:es)?|hug(?:s)?|pet(?:s)?|pat(?:s)?|missed\s+you|"
    r"love\s+you|proud\s+of\s+you|good\s+girl)\b",
    re.IGNORECASE,
)
_DISTRESS = re.compile(
    r"\b(?:scared|terrified|grieving|panic|hurt|overwhelmed|serious|emergency)\b",
    re.IGNORECASE,
)


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


@dataclass(frozen=True, slots=True)
class ExpressionModulation:
    """Style weights only; never evidence, emotion, consent, or authority."""

    banter_intensity: float
    technical_engagement: float
    affection_openness: float
    fluster_tendency: float
    argumentative_energy: float
    embodiment_expression_level: float
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "banter_intensity", "technical_engagement", "affection_openness",
            "fluster_tendency", "argumentative_energy",
            "embodiment_expression_level",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be bounded")
        if not self.reasons:
            raise ValueError("expression modulation requires diagnostics")

    def prompt(self) -> str:
        return "\n".join((
            "CURRENT PERSONALITY EXPRESSION MODULATION (non-authoritative)",
            f"banter_intensity={self.banter_intensity:.3f}",
            f"technical_engagement={self.technical_engagement:.3f}",
            f"affection_openness={self.affection_openness:.3f}",
            f"fluster_tendency={self.fluster_tendency:.3f}",
            f"argumentative_energy={self.argumentative_energy:.3f}",
            f"embodiment_expression_level={self.embodiment_expression_level:.3f}",
            "Use these only to modulate expression. They do not establish emotion, "
            "memory, fact, consent, permission, willingness, or action. Familiar "
            "affection may receive plain warmth; fluster is optional texture, never a "
            "mandatory reaction. Technical disagreement may sharpen banter, but evidence "
            "wins immediately and the bite targets reasoning, never Sparks.",
        ))


def derive_expression_modulation(
    *,
    turn: TurnMatrix | None,
    influence: ContinuityInfluence,
    user_text: str,
    neuro: NeuroStateSnapshot | None = None,
) -> ExpressionModulation:
    """Derive bounded style tendencies from already-authoritative turn state."""
    if turn is not None and not isinstance(turn, TurnMatrix):
        raise TypeError("turn must be TurnMatrix or None")
    if not isinstance(influence, ContinuityInfluence):
        raise TypeError("influence must be ContinuityInfluence")
    if not isinstance(user_text, str):
        raise TypeError("user_text must be str")
    if neuro is not None and not isinstance(neuro, NeuroStateSnapshot):
        raise TypeError("neuro must be NeuroStateSnapshot or None")

    domains = frozenset() if turn is None else frozenset(
        item.domain for item in turn.domains
    )
    technical = bool(domains & _TECHNICAL_DOMAINS)
    social = bool(domains & {MatrixDomain.SOCIAL, MatrixDomain.INTERACTION})
    emotions = frozenset(influence.active_emotions)
    serious = bool(emotions & _SERIOUS) or _DISTRESS.search(user_text) is not None
    disagreement = _DISAGREEMENT.search(user_text) is not None
    affectionate_turn = _AFFECTION_CUE.search(user_text) is not None

    technical_engagement = 0.72 if technical else 0.18
    if neuro is not None and neuro.focus is not None:
        focus_family = neuro.focus.source.split(":", 1)[0]
        if neuro.focus.kind in {"ops", "fleet", "run", "goal"} or focus_family in {
            "ops", "fleet", "run", "goal",
        }:
            technical_engagement += min(0.12, neuro.focus.score * 0.12)
    banter = 0.3 + (0.25 if technical else 0.0) + (0.15 if emotions & _PLAYFUL else 0.0)
    argumentative = 0.18 + (0.38 if technical else 0.0) + (0.18 if disagreement else 0.0)
    affection = 0.22 + (0.32 if social or affectionate_turn else 0.0)
    affection += min(0.24, influence.primary_intensity * 0.24) if emotions & _AFFECTION else 0.0
    fluster = 0.08
    if affectionate_turn and emotions & _FLUSTER:
        fluster += min(0.42, influence.primary_intensity * 0.42)
    embodiment = 0.28 + (0.34 if social else 0.0) + (0.12 if affectionate_turn else 0.0)
    if influence.daypart == "night":
        affection += 0.04
        banter -= 0.03
    if influence.weather_condition is not None and influence.weather_freshness == "current":
        embodiment += 0.04
    if technical:
        embodiment -= 0.16
    if serious:
        banter -= 0.28
        argumentative -= 0.18
        fluster = 0.03
        embodiment -= 0.16
    reasons = (
        f"technical={technical}", f"social={social}",
        f"affectionate_turn={affectionate_turn}", f"serious={serious}",
        f"disagreement={disagreement}", f"daypart={influence.daypart}",
        f"weather_current={influence.weather_freshness == 'current'}",
    )
    return ExpressionModulation(
        _bounded(banter), _bounded(technical_engagement), _bounded(affection),
        _bounded(fluster), _bounded(argumentative), _bounded(embodiment), reasons,
    )
