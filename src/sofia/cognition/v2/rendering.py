"""Personality rendering after factual AnswerPlan validation."""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256

from sofia.cognition.model import CognitiveResponse
from sofia.personality.modulation import ExpressionModulation

from .contracts import AnswerPlan


@dataclass(frozen=True, slots=True)
class ValidatedAnswerDraft:
    """Validated facts plus conservative pre-personality wording."""

    answer: AnswerPlan
    content: str
    evidence_refs: tuple[str, ...]
    domain: str

    def __post_init__(self) -> None:
        if not isinstance(self.answer, AnswerPlan):
            raise TypeError("answer must be AnswerPlan")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be nonempty")
        if not isinstance(self.evidence_refs, tuple) or any(
            not isinstance(value, str) or not value.strip()
            for value in self.evidence_refs
        ):
            raise ValueError("evidence_refs must contain nonempty strings")
        if not isinstance(self.domain, str) or not self.domain.strip():
            raise ValueError("domain must be nonempty")


class PersonalityAfterTruthRenderer:
    """Add bounded expression without acquiring facts or changing claims."""

    _OPERATIONAL_OPENERS = (
        "Clean read:",
        "Here’s the grounded read:",
        "Evidence first:",
    )
    _KNOWLEDGE_OPENERS = (
        "Source-backed answer:",
        "I found the relevant source material:",
        "Grounded in the indexed sources:",
    )
    _PERSONAL_OPENERS = (
        "Grounded answer:",
        "Here’s what I can actually support:",
        "The honest read:",
    )

    def render(
        self,
        draft: ValidatedAnswerDraft,
        *,
        expression_context: ExpressionModulation,
    ) -> CognitiveResponse:
        if not isinstance(draft, ValidatedAnswerDraft):
            raise TypeError("draft must be ValidatedAnswerDraft")
        if not isinstance(expression_context, ExpressionModulation):
            raise TypeError("expression_context must be ExpressionModulation")
        if expression_context.kurisu_influence_weight < 0.30:
            raise ValueError("Kurisu-inspired influence cannot fall below 30%")

        # Bind the exact expression decision to the already-validated plan.
        context_id = (
            "personality:"
            + sha256(expression_context.prompt().encode("utf-8")).hexdigest()[:24]
        )
        answer = replace(draft.answer, personality_context_id=context_id)
        if answer.claims != draft.answer.claims:
            raise RuntimeError("personality rendering changed validated claims")

        choices = (
            self._OPERATIONAL_OPENERS
            if draft.domain in {"fleet", "machine", "ops"}
            else self._KNOWLEDGE_OPENERS
            if draft.domain == "know"
            else self._PERSONAL_OPENERS
            if draft.domain in {"environment", "avatar", "memory"}
            else ()
        )
        content = draft.content.strip()
        if choices and answer.claims:
            digest = sha256(
                f"{answer.turn_id}:{context_id}".encode("utf-8")
            ).digest()
            content = f"{choices[digest[0] % len(choices)]} {content}"
        return CognitiveResponse(
            content=content,
            evidence_refs=draft.evidence_refs,
        )
