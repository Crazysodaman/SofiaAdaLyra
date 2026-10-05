"""Contextual influence policy for behavior-facing matrix decisions.

This matrix is a whitelist over trusted non-authoritative context. It decides
where emotion, weather, daypart and season may shape a choice and how strongly.
It never grants truth, consent, capability authority or execution rights.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.personality.influence import ContinuityInfluence


class InfluenceSignal(str, Enum):
    EMOTION = "emotion"
    WEATHER = "weather"
    DAYPART = "daypart"
    SEASON = "season"


class InfluenceSurface(str, Enum):
    CONVERSATION_EXPRESSION = "conversation_expression"
    REFLECTION = "reflection"
    OUTREACH_SALIENCE = "outreach_salience"
    AVATAR_APPEARANCE = "avatar_appearance"
    AUTO_OUTFIT = "auto_outfit"
    WARDROBE_REQUEST_AUTONOMY = "wardrobe_request_autonomy"
    UI_THEME = "ui_theme"
    INTERACTION_WILLINGNESS = "interaction_willingness"
    INTERACTION_EXPRESSION = "interaction_expression"
    VOICE_EXPRESSION = "voice_expression"
    HABIT_LEARNING = "habit_learning"
    MEMORY_RERANK = "memory_rerank"
    SOCIAL_GOAL_PRIORITY = "social_goal_priority"
    TOOL_AUTHORITY = "tool_authority"
    SAFE_POLICY = "safe_policy"
    RELEASE_VERIFY = "release_verify"
    FLEET_AUTHORITY = "fleet_authority"
    BODY_SAFETY = "body_safety"


class InfluenceMode(str, Enum):
    NONE = "none"
    EXPRESSION_ONLY = "expression_only"
    BOUNDED_BIAS = "bounded_bias"
    STRONG_PREFERENCE = "strong_preference"
    HARD_COMPATIBILITY = "hard_compatibility"


@dataclass(frozen=True, slots=True)
class InfluenceDecision:
    signal: InfluenceSignal
    mode: InfluenceMode
    reason: str
    evidence_refs: tuple[str, ...] = ()
    freshness: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.signal, InfluenceSignal):
            raise TypeError("signal must be InfluenceSignal")
        if not isinstance(self.mode, InfluenceMode):
            raise TypeError("mode must be InfluenceMode")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("influence reason must be nonempty")
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be a tuple")
        for ref in self.evidence_refs:
            if not isinstance(ref, str) or not ref.strip():
                raise ValueError("evidence_refs must contain nonempty strings")
        if self.freshness is not None and (
            not isinstance(self.freshness, str)
            or not self.freshness.strip()
        ):
            raise ValueError("freshness must be None or nonempty")
        if self.mode is not InfluenceMode.NONE:
            if not self.evidence_refs:
                raise ValueError(
                    "active contextual influence requires provenance"
                )
            if self.freshness is None:
                raise ValueError(
                    "active contextual influence requires freshness/grounding"
                )


@dataclass(frozen=True, slots=True)
class ContextualInfluencePlan:
    surface: InfluenceSurface
    decisions: tuple[InfluenceDecision, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.surface, InfluenceSurface):
            raise TypeError("surface must be InfluenceSurface")
        if not isinstance(self.decisions, tuple):
            raise TypeError("decisions must be a tuple")
        seen: set[InfluenceSignal] = set()
        for decision in self.decisions:
            if not isinstance(decision, InfluenceDecision):
                raise TypeError("decisions must contain InfluenceDecision")
            if decision.signal in seen:
                raise ValueError("influence signals must be unique")
            seen.add(decision.signal)
        if seen != set(InfluenceSignal):
            raise ValueError(
                "plan must include every influence signal exactly once"
            )

    def decision_for(self, signal: InfluenceSignal) -> InfluenceDecision:
        if not isinstance(signal, InfluenceSignal):
            raise TypeError("signal must be InfluenceSignal")
        for decision in self.decisions:
            if decision.signal is signal:
                return decision
        raise RuntimeError("influence signal missing from validated plan")

    def mode_for(self, signal: InfluenceSignal) -> InfluenceMode:
        return self.decision_for(signal).mode


_POLICY: dict[InfluenceSurface, dict[InfluenceSignal, InfluenceMode]] = {
    InfluenceSurface.CONVERSATION_EXPRESSION: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.EXPRESSION_ONLY,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.EXPRESSION_ONLY,
    },
    InfluenceSurface.REFLECTION: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.BOUNDED_BIAS,
    },
    InfluenceSurface.OUTREACH_SALIENCE: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.NONE,
    },
    InfluenceSurface.AVATAR_APPEARANCE: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.BOUNDED_BIAS,
    },
    InfluenceSurface.AUTO_OUTFIT: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.STRONG_PREFERENCE,
        InfluenceSignal.DAYPART: InfluenceMode.STRONG_PREFERENCE,
        InfluenceSignal.SEASON: InfluenceMode.HARD_COMPATIBILITY,
    },
    InfluenceSurface.WARDROBE_REQUEST_AUTONOMY: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.STRONG_PREFERENCE,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.HARD_COMPATIBILITY,
    },
    InfluenceSurface.UI_THEME: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.BOUNDED_BIAS,
    },
    InfluenceSurface.INTERACTION_WILLINGNESS: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.NONE,
        InfluenceSignal.DAYPART: InfluenceMode.NONE,
        InfluenceSignal.SEASON: InfluenceMode.NONE,
    },
    InfluenceSurface.INTERACTION_EXPRESSION: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.EXPRESSION_ONLY,
        InfluenceSignal.DAYPART: InfluenceMode.EXPRESSION_ONLY,
        InfluenceSignal.SEASON: InfluenceMode.EXPRESSION_ONLY,
    },
    InfluenceSurface.VOICE_EXPRESSION: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.EXPRESSION_ONLY,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.EXPRESSION_ONLY,
    },
    InfluenceSurface.HABIT_LEARNING: {
        InfluenceSignal.EMOTION: InfluenceMode.NONE,
        InfluenceSignal.WEATHER: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.BOUNDED_BIAS,
    },
    InfluenceSurface.MEMORY_RERANK: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.BOUNDED_BIAS,
    },
    InfluenceSurface.SOCIAL_GOAL_PRIORITY: {
        InfluenceSignal.EMOTION: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.WEATHER: InfluenceMode.NONE,
        InfluenceSignal.DAYPART: InfluenceMode.BOUNDED_BIAS,
        InfluenceSignal.SEASON: InfluenceMode.NONE,
    },
    InfluenceSurface.TOOL_AUTHORITY: {
        signal: InfluenceMode.NONE for signal in InfluenceSignal
    },
    InfluenceSurface.SAFE_POLICY: {
        signal: InfluenceMode.NONE for signal in InfluenceSignal
    },
    InfluenceSurface.RELEASE_VERIFY: {
        signal: InfluenceMode.NONE for signal in InfluenceSignal
    },
    InfluenceSurface.FLEET_AUTHORITY: {
        signal: InfluenceMode.NONE for signal in InfluenceSignal
    },
    InfluenceSurface.BODY_SAFETY: {
        signal: InfluenceMode.NONE for signal in InfluenceSignal
    },
}


class ContextualInfluenceMatrix:
    """Project trusted context into a bounded behavior influence plan."""

    _DAYPARTS = frozenset({"morning", "afternoon", "evening", "night"})

    @staticmethod
    def policy_mode(
        surface: InfluenceSurface,
        signal: InfluenceSignal,
    ) -> InfluenceMode:
        """Return the reviewed surface policy before evidence availability."""
        if not isinstance(surface, InfluenceSurface):
            raise TypeError("surface must be InfluenceSurface")
        if not isinstance(signal, InfluenceSignal):
            raise TypeError("signal must be InfluenceSignal")
        return _POLICY[surface][signal]
    _SEASONS = frozenset({"winter", "spring", "summer", "autumn"})

    def plan(
        self,
        surface: InfluenceSurface,
        influence: ContinuityInfluence,
    ) -> ContextualInfluencePlan:
        if not isinstance(surface, InfluenceSurface):
            raise TypeError("surface must be InfluenceSurface")
        if not isinstance(influence, ContinuityInfluence):
            raise TypeError("influence must be ContinuityInfluence")

        policy = _POLICY[surface]
        decisions = tuple(
            self._decision(
                surface=surface,
                signal=signal,
                requested=policy[signal],
                influence=influence,
            )
            for signal in InfluenceSignal
        )
        return ContextualInfluencePlan(
            surface=surface,
            decisions=decisions,
        )

    def _decision(
        self,
        *,
        surface: InfluenceSurface,
        signal: InfluenceSignal,
        requested: InfluenceMode,
        influence: ContinuityInfluence,
    ) -> InfluenceDecision:
        if requested is InfluenceMode.NONE:
            return InfluenceDecision(
                signal,
                InfluenceMode.NONE,
                "this decision surface does not permit this contextual signal",
            )

        if signal is InfluenceSignal.EMOTION:
            expression_surface = surface in {
                InfluenceSurface.CONVERSATION_EXPRESSION,
                InfluenceSurface.INTERACTION_EXPRESSION,
                InfluenceSurface.VOICE_EXPRESSION,
            }
            emotion = (
                (
                    influence.foreground_emotion
                    or influence.primary_emotion
                )
                if expression_surface
                else influence.primary_emotion
            )
            intensity = (
                (
                    influence.foreground_intensity
                    if influence.foreground_emotion is not None
                    else min(influence.primary_intensity, 0.20)
                )
                if expression_surface
                else influence.primary_intensity
            )
            evidence_refs = (
                (
                    influence.foreground_emotion_evidence_refs
                    if influence.foreground_emotion is not None
                    else influence.primary_emotion_evidence_refs
                )
                if expression_surface
                else influence.primary_emotion_evidence_refs
            )
            if (
                emotion is None
                or intensity <= 0.0
                or not evidence_refs
            ):
                return InfluenceDecision(
                    signal,
                    InfluenceMode.NONE,
                    (
                        "no evidence-linked expressive emotion is available"
                        if expression_surface
                        else "no evidence-linked modeled emotion is available"
                    ),
                )
            return InfluenceDecision(
                signal,
                requested,
                (
                    (
                        "evidence-linked foreground emotion is available for expression"
                        if influence.foreground_emotion is not None
                        else "evidence-linked relational emotion is available for subtle expression"
                    )
                    if expression_surface
                    else "evidence-linked modeled emotion is available as bounded context"
                ),
                evidence_refs,
                "modeled-current",
            )

        if signal is InfluenceSignal.WEATHER:
            if (
                influence.weather_freshness != "current"
                or not influence.weather_condition
                or not influence.weather_evidence_refs
            ):
                return InfluenceDecision(
                    signal,
                    InfluenceMode.NONE,
                    "current weather evidence is unavailable, unprovenanced, or not fresh",
                    influence.weather_evidence_refs,
                    influence.weather_freshness,
                )
            return InfluenceDecision(
                signal,
                requested,
                "fresh current weather may influence this surface",
                influence.weather_evidence_refs,
                influence.weather_freshness,
            )

        if signal is InfluenceSignal.DAYPART:
            if (
                influence.daypart not in self._DAYPARTS
                or not influence.daypart_evidence_refs
            ):
                return InfluenceDecision(
                    signal,
                    InfluenceMode.NONE,
                    "trusted, provenanced local daypart is unavailable",
                    influence.daypart_evidence_refs,
                    None,
                )
            return InfluenceDecision(
                signal,
                requested,
                "trusted local daypart may influence this surface",
                influence.daypart_evidence_refs,
                "current",
            )

        if signal is InfluenceSignal.SEASON:
            if (
                influence.season not in self._SEASONS
                or not influence.season_evidence_refs
            ):
                return InfluenceDecision(
                    signal,
                    InfluenceMode.NONE,
                    "grounded, provenanced season is unavailable",
                    influence.season_evidence_refs,
                    None,
                )
            return InfluenceDecision(
                signal,
                requested,
                "grounded season may influence this surface",
                influence.season_evidence_refs,
                "grounded",
            )

        raise RuntimeError("unhandled contextual influence signal")
