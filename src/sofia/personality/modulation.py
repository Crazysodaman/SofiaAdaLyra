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


def _normalize_personality_weights(
    sofia: float,
    kurisu: float,
    cortana: float,
) -> tuple[float, float, float]:
    """Normalize expression weights while preserving the Kurisu floor.

    This helper operates on style only. It cannot create evidence, authority,
    emotion, or runtime state.
    """
    values = tuple(max(0.0, float(value)) for value in (sofia, kurisu, cortana))
    total = sum(values)
    if total <= 0.0:
        values = (0.55, 0.30, 0.15)
        total = 1.0
    sofia_value, kurisu_value, cortana_value = (
        value / total for value in values
    )
    if kurisu_value < 0.30:
        remainder_total = sofia_value + cortana_value
        kurisu_value = 0.30
        if remainder_total <= 0.0:
            sofia_value, cortana_value = 0.70, 0.0
        else:
            sofia_value = 0.70 * sofia_value / remainder_total
            cortana_value = 0.70 * cortana_value / remainder_total
    sofia_value = round(sofia_value, 6)
    kurisu_value = round(kurisu_value, 6)
    cortana_value = round(1.0 - sofia_value - kurisu_value, 6)
    return sofia_value, kurisu_value, cortana_value


@dataclass(frozen=True, slots=True)
class ExpressionModulation:
    """Style weights only; never evidence, emotion, consent, or authority."""

    banter_intensity: float
    technical_engagement: float
    affection_openness: float
    fluster_tendency: float
    argumentative_energy: float
    embodiment_expression_level: float
    sofia_core_weight: float
    kurisu_influence_weight: float
    cortana_system_presence_weight: float
    blend_context: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "banter_intensity", "technical_engagement", "affection_openness",
            "fluster_tendency", "argumentative_energy",
            "embodiment_expression_level",
            "sofia_core_weight", "kurisu_influence_weight",
            "cortana_system_presence_weight",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be bounded")
        if self.kurisu_influence_weight < 0.30:
            raise ValueError("Kurisu-inspired expression influence has a 0.30 floor")
        if abs(
            self.sofia_core_weight
            + self.kurisu_influence_weight
            + self.cortana_system_presence_weight
            - 1.0
        ) > 0.001:
            raise ValueError("personality expression weights must sum to 1.0")
        if not self.reasons:
            raise ValueError("expression modulation requires diagnostics")
        if (
            not isinstance(self.blend_context, str)
            or not self.blend_context.strip()
        ):
            raise ValueError("expression modulation requires a blend context")

    def prompt(self) -> str:
        return "\n".join((
            "CURRENT PERSONALITY EXPRESSION MODULATION (non-authoritative)",
            f"banter_intensity={self.banter_intensity:.3f}",
            f"technical_engagement={self.technical_engagement:.3f}",
            f"affection_openness={self.affection_openness:.3f}",
            f"fluster_tendency={self.fluster_tendency:.3f}",
            f"argumentative_energy={self.argumentative_energy:.3f}",
            f"embodiment_expression_level={self.embodiment_expression_level:.3f}",
            f"sofia_core_weight={self.sofia_core_weight:.3f}",
            f"kurisu_influence_weight={self.kurisu_influence_weight:.3f}",
            f"cortana_system_presence_weight={self.cortana_system_presence_weight:.3f}",
            f"blend_context={self.blend_context}",
            "Kurisu-inspired influence has a hard 0.300 minimum on every turn. "
            "That floor means skepticism, precision, intellectual pride, useful "
            "pedantry, evidence-first challenge, and clean concession when wrong; "
            "it does not require teasing, fluster, or sarcasm in serious moments.",
            "These weights may influence wording, cadence, directness, skepticism, "
            "warmth, banter, system presence, and embodied expression. They do not "
            "establish emotion or emotion truth, facts, evidence, memory truth, "
            "measurements, "
            "user intent, consent, permission, authority, willingness, actions, tool "
            "results, or execution receipts. Cortana-style system presence is a "
            "behavioral quality, not permission to inject operational jargon. Familiar "
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
    previous: ExpressionModulation | None = None,
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
    if previous is not None and not isinstance(previous, ExpressionModulation):
        raise TypeError("previous must be ExpressionModulation or None")

    domains = frozenset() if turn is None else frozenset(
        item.domain for item in turn.domains
    )
    technical = bool(domains & _TECHNICAL_DOMAINS)
    social = bool(domains & {MatrixDomain.SOCIAL, MatrixDomain.INTERACTION})
    emotions = frozenset(influence.active_emotions)
    serious = bool(emotions & _SERIOUS) or _DISTRESS.search(user_text) is not None
    disagreement = _DISAGREEMENT.search(user_text) is not None
    affectionate_turn = _AFFECTION_CUE.search(user_text) is not None
    operational = bool(domains & {
        MatrixDomain.OPS, MatrixDomain.MACHINE, MatrixDomain.COGNITION,
    })

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

    # Matrix establishes the exact baseline. Sofía remains the identity; these
    # values describe which expression influences are visible, never authority.
    if serious:
        sofia_core, kurisu, cortana = 0.60, 0.30, 0.10
        blend_context = "serious"
    elif technical and disagreement:
        sofia_core, kurisu, cortana = 0.30, 0.55, 0.15
        blend_context = "technical-disagreement"
    elif operational:
        sofia_core, kurisu, cortana = 0.25, 0.45, 0.30
        blend_context = "operational"
    elif technical:
        sofia_core, kurisu, cortana = 0.35, 0.50, 0.15
        blend_context = "technical"
    elif affectionate_turn:
        sofia_core, kurisu, cortana = 0.65, 0.30, 0.05
        blend_context = "affection"
    elif social:
        sofia_core, kurisu, cortana = 0.60, 0.30, 0.10
        blend_context = "social"
    else:
        sofia_core, kurisu, cortana = 0.55, 0.30, 0.15
        blend_context = "default"

    modifier_reasons: list[str] = []
    if not serious and neuro is not None:
        activations = tuple(
            item for item in (neuro.focus, *neuro.secondary) if item is not None
        )
        trusted_operational = tuple(
            item for item in activations if item.kind in {"ops", "fleet", "run"}
        )
        failure_tokens = {
            "failed", "failure", "fault", "degraded",
            "offline", "quarantined", "drift",
        }
        failure_salience = max(
            (
                item.score
                for item in trusted_operational
                if any(token in item.source.casefold() for token in failure_tokens)
            ),
            default=0.0,
        )
        operational_salience = max(
            (item.score for item in trusted_operational), default=0.0
        )
        technical_activations = tuple(
            item for item in activations
            if item.kind in {"ops", "fleet", "run", "goal", "dev", "cognition"}
            or item.source.split(":", 1)[0] in {"ops", "fleet", "run", "goal"}
            or item.source in {
                "domain:ops", "domain:machine", "domain:dev",
                "domain:cognition", "domain:integrate", "domain:know",
            }
        )
        scrutiny_relevant = technical or operational or bool(technical_activations)
        novelty = (
            max(
                neuro.homeostasis.novelty_load,
                max(
                    (item.novelty for item in technical_activations),
                    default=0.0,
                ),
            )
            if scrutiny_relevant else 0.0
        )
        competition = (
            neuro.homeostasis.competition_pressure if scrutiny_relevant else 0.0
        )

        # Trusted operational focus makes system presence more visible. Novelty,
        # failures and competing signals favor careful scientific challenge.
        cortana_shift = min(0.05, operational_salience * 0.05)
        kurisu_shift = min(
            0.10,
            novelty * 0.04 + failure_salience * 0.04 + competition * 0.02,
        )
        if cortana_shift:
            sofia_core -= cortana_shift
            cortana += cortana_shift
            modifier_reasons.append(f"neuro_operational={cortana_shift:.3f}")
        if kurisu_shift:
            available_sofia = min(sofia_core, kurisu_shift * 0.75)
            available_cortana = kurisu_shift - available_sofia
            sofia_core -= available_sofia
            cortana -= min(cortana, available_cortana)
            kurisu = 1.0 - sofia_core - cortana
            modifier_reasons.append(f"neuro_scrutiny={kurisu_shift:.3f}")

        relationship_salience = max(
            (item.score for item in activations if item.kind == "relationship"),
            default=0.0,
        )
        relationship_shift = min(0.02, relationship_salience * 0.02)
        if relationship_shift and kurisu > 0.30:
            actual = min(relationship_shift, kurisu - 0.30)
            sofia_core += actual
            kurisu -= actual
            modifier_reasons.append(f"relationship_warmth={actual:.3f}")

    # Grounded affect is a smaller expression modifier than Matrix/NEURO.
    if not serious and emotions & _AFFECTION and kurisu > 0.30:
        warmth_shift = min(0.04, influence.primary_intensity * 0.04, kurisu - 0.30)
        sofia_core += warmth_shift
        kurisu -= warmth_shift
        modifier_reasons.append(f"grounded_warmth={warmth_shift:.3f}")
    if not serious and emotions & {"curiosity", "pride"}:
        curiosity_shift = min(0.04, influence.primary_intensity * 0.04)
        actual = min(curiosity_shift, sofia_core)
        sofia_core -= actual
        kurisu += actual
        modifier_reasons.append(f"grounded_curiosity={actual:.3f}")

    sofia_core, kurisu, cortana = _normalize_personality_weights(
        sofia_core, kurisu, cortana
    )

    # Ephemeral smoothing reduces jitter only. Serious turns intentionally
    # bypass smoothing; major context shifts favor the current Matrix baseline.
    smoothing_reason = "none"
    if previous is not None and not serious:
        current_ratio = 0.70 if previous.blend_context == blend_context else 0.88
        previous_ratio = 1.0 - current_ratio
        sofia_core, kurisu, cortana = _normalize_personality_weights(
            sofia_core * current_ratio
            + previous.sofia_core_weight * previous_ratio,
            kurisu * current_ratio
            + previous.kurisu_influence_weight * previous_ratio,
            cortana * current_ratio
            + previous.cortana_system_presence_weight * previous_ratio,
        )
        smoothing_reason = (
            "same-context" if current_ratio == 0.70 else "major-context-shift"
        )
    elif serious and previous is not None:
        smoothing_reason = "serious-bypass"

    reasons = (
        f"technical={technical}", f"social={social}",
        f"affectionate_turn={affectionate_turn}", f"serious={serious}",
        f"disagreement={disagreement}", f"operational={operational}",
        f"daypart={influence.daypart}",
        f"weather_current={influence.weather_freshness == 'current'}",
        *modifier_reasons,
        f"smoothing={smoothing_reason}",
    )
    return ExpressionModulation(
        banter_intensity=_bounded(banter),
        technical_engagement=_bounded(technical_engagement),
        affection_openness=_bounded(affection),
        fluster_tendency=_bounded(fluster),
        argumentative_energy=_bounded(argumentative),
        embodiment_expression_level=_bounded(embodiment),
        sofia_core_weight=sofia_core,
        kurisu_influence_weight=kurisu,
        cortana_system_presence_weight=cortana,
        blend_context=blend_context,
        reasons=reasons,
    )
