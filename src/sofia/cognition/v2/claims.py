"""Claim planning and validation over exact Cognition v2 evidence keys."""
from __future__ import annotations

import json

from .contracts import (
    AcquisitionState,
    AnswerPlan,
    ClaimPlan,
    EpistemicState,
    EvidenceAtom,
    TurnPlan,
)


class EvidenceClaimPlanner:
    """Build claims only from eligible evidence supplied by the host."""

    def build(
        self,
        plan: TurnPlan,
        evidence: tuple[EvidenceAtom, ...],
    ) -> AnswerPlan:
        if not isinstance(plan, TurnPlan):
            raise TypeError("plan must be TurnPlan")
        if not isinstance(evidence, tuple) or any(
            not isinstance(atom, EvidenceAtom) for atom in evidence
        ):
            raise TypeError("evidence must contain EvidenceAtom values")
        claims = []
        unknown = []
        for need in plan.evidence_needs:
            matches = tuple(
                atom for atom in evidence
                if atom.subject_id == need.subject_id
                and atom.predicate == need.predicate
                and atom.scope_id == need.scope_id
                and atom.acquisition_state is AcquisitionState.CURRENT
                and atom.epistemic_state is not EpistemicState.UNKNOWN
            )
            if not matches:
                unknown.append(need.need_id)
                continue
            atom = max(matches, key=lambda item: item.observed_at)
            claims.append(ClaimPlan(
                claim_id=f"claim:{need.need_id}",
                subject_id=need.subject_id,
                predicate=need.predicate,
                rendered_value=self._render_value(atom.value_json),
                epistemic_state=atom.epistemic_state,
                evidence_refs=(atom.evidence_id,),
            ))
        return AnswerPlan(
            turn_id=plan.turn_id,
            claims=tuple(claims),
            unknown_need_ids=tuple(unknown),
        )

    @staticmethod
    def _render_value(value_json: str) -> str:
        value = json.loads(value_json)
        if isinstance(value, str):
            return value
        return json.dumps(value, sort_keys=True, ensure_ascii=False)


class EvidenceClaimValidator:
    """Reject claims that do not have an exact supplied evidence atom."""

    def validate(
        self,
        answer: AnswerPlan,
        evidence: tuple[EvidenceAtom, ...],
    ) -> AnswerPlan:
        if not isinstance(answer, AnswerPlan):
            raise TypeError("answer must be AnswerPlan")
        by_id = {atom.evidence_id: atom for atom in evidence}
        for claim in answer.claims:
            if claim.epistemic_state in {
                EpistemicState.OBSERVED,
                EpistemicState.KNOWN,
                EpistemicState.USER_REPORTED,
                EpistemicState.INFERRED,
            } and not claim.evidence_refs:
                raise ValueError("factual claims require evidence")
            for evidence_id in claim.evidence_refs:
                atom = by_id.get(evidence_id)
                if atom is None:
                    raise ValueError("claim references evidence outside the answer set")
                if (
                    atom.subject_id != claim.subject_id
                    or atom.predicate != claim.predicate
                    or atom.acquisition_state is not AcquisitionState.CURRENT
                    or atom.epistemic_state != claim.epistemic_state
                ):
                    raise ValueError("claim does not match exact current evidence")
        return answer
