"""Personality rendering after factual AnswerPlan validation."""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256

from sofia.cognition.model import CognitiveResponse
from sofia.personality.modulation import ExpressionModulation

from .contracts import AnswerPlan, TurnPlan


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


def merge_validated_drafts(
    plan: TurnPlan,
    drafts: tuple[ValidatedAnswerDraft, ...],
) -> ValidatedAnswerDraft | None:
    """Combine independently validated partial answers without inventing facts."""
    if not isinstance(plan, TurnPlan):
        raise TypeError("plan must be TurnPlan")
    if not isinstance(drafts, tuple) or any(
        not isinstance(draft, ValidatedAnswerDraft) for draft in drafts
    ):
        raise TypeError("drafts must contain ValidatedAnswerDraft values")
    if not drafts:
        return None
    claims = {}
    for draft in drafts:
        if draft.answer.turn_id != plan.turn_id:
            raise ValueError("partial answer belongs to another turn")
        for claim in draft.answer.claims:
            existing = claims.get(claim.claim_id)
            if existing is not None and existing != claim:
                raise ValueError("partial answers contain conflicting claims")
            claims[claim.claim_id] = claim
    claimed_need_ids = {
        claim.claim_id.removeprefix("claim:") for claim in claims.values()
    }
    unknown = tuple(
        need.need_id for need in plan.evidence_needs
        if need.need_id not in claimed_need_ids
    )
    handled_predicates = set()
    for draft in drafts:
        handled_predicates.update({
            "machine.cpu", "machine.gpu", "machine.memory_bytes",
            "machine.storage", "ops.cpu_percent",
        } if draft.domain == "machine" else {
            "knowledge.retrieval",
        } if draft.domain == "know" else {
            "environment.current",
        } if draft.domain == "environment" else {
            "avatar.canonical",
        } if draft.domain == "avatar" else {
            "memory.retrieval",
        } if draft.domain == "memory" else set())
    unhandled = tuple(
        need for need in plan.evidence_needs
        if need.predicate not in handled_predicates
    )
    content = "\n\n".join(draft.content.strip() for draft in drafts)
    if unhandled:
        details = ", ".join(
            f"{need.subject_id} / {need.predicate}" for need in unhandled
        )
        content += (
            "\n\nStill unresolved: no validated production evidence resolver "
            f"answered {details}."
        )
    return ValidatedAnswerDraft(
        answer=AnswerPlan(
            turn_id=plan.turn_id,
            claims=tuple(claims.values()),
            unknown_need_ids=unknown,
        ),
        content=content,
        evidence_refs=tuple(dict.fromkeys(
            ref for draft in drafts for ref in draft.evidence_refs
        )),
        domain=(drafts[0].domain if len(drafts) == 1 else "multi"),
    )


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
