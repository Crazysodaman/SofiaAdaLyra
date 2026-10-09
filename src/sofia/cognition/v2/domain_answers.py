"""Validated AnswerPlans for canonical non-operational domain projections."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from uuid import uuid4

from sofia.cognition.model import CognitiveResponse
from sofia.environment.prompt import environment_details_relevant
from sofia.personality.delivery import grounded_weather_delivery
from sofia.social.model import PrincipalContext

from .claims import EvidenceClaimPlanner, EvidenceClaimValidator
from .contracts import (
    AcquisitionState,
    ActionRequirement,
    AnswerPlan,
    EpistemicState,
    EvidenceAtom,
    TurnPlan,
)
from .evidence import CognitiveEvidenceLedger
from .rendering import ValidatedAnswerDraft


class ProjectionAnswerCoordinator:
    """Project trusted ENVIRONMENT, AVATAR and reviewed MEM state into v2."""

    def __init__(self, runtime, ledger: CognitiveEvidenceLedger) -> None:
        self.runtime = runtime
        self.ledger = ledger
        self.claim_planner = EvidenceClaimPlanner()
        self.claim_validator = EvidenceClaimValidator()

    def answer(self, **kwargs) -> CognitiveResponse | None:
        draft = self.planned_answer(**kwargs)
        if draft is None:
            return None
        return CognitiveResponse(draft.content, evidence_refs=draft.evidence_refs)

    def planned_answer(
        self,
        *,
        plan: TurnPlan,
        focus,
        principal: PrincipalContext | None,
        allowed_capabilities: tuple[str, ...],
        query: str | None = None,
    ) -> ValidatedAnswerDraft | None:
        _ = focus, allowed_capabilities
        if (
            plan.action_requirement is ActionRequirement.MUTATION
            or not isinstance(query, str)
            or not query.strip()
        ):
            return None
        by_predicate = {need.predicate: need for need in plan.evidence_needs}
        if "environment.current" in by_predicate:
            return self._environment(
                plan, by_predicate["environment.current"], query,
            )
        if "avatar.canonical" in by_predicate:
            return self._avatar(
                plan, by_predicate["avatar.canonical"], query, principal,
            )
        if "memory.retrieval" in by_predicate:
            if self.runtime._reflection_query_resolver.might_match(query):
                return None
            if re.search(
                r"\b(?:what\s+did\s+i\s+say|what\s+have\s+i\s+said|"
                r"conversation|earlier\s+in\s+(?:this|our)\s+chat)\b",
                query,
                re.IGNORECASE,
            ):
                # Durable transcript recall has its own bounded host retrieval
                # in ConversationService and is not reviewed MEM state.
                return None
            return self._memory(
                plan, by_predicate["memory.retrieval"], query, principal,
            )
        return None

    def _environment(self, plan, need, query) -> ValidatedAnswerDraft | None:
        resolver = self.runtime._environment_query_resolver
        if not resolver.might_match(query):
            return None
        snapshot = self.runtime.environment_service.snapshot(
            refresh_providers=environment_details_relevant(query),
        )
        result = resolver.resolve(query, snapshot=snapshot)
        if not result.recognized:
            return None
        content = grounded_weather_delivery(
            result.content,
            condition=(None if snapshot.weather is None else snapshot.weather.condition),
        )
        if re.search(r"\bi don['’]t have current\b", result.content, re.IGNORECASE):
            atom = self._unknown_atom(
                need,
                source="environment:service",
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            )
        else:
            atom = self._record(
                need,
                value={"answer": result.content},
                source="environment:service",
                trust=0.95,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
            )
        return self._draft(plan, (atom,), content, "environment")

    def _avatar(self, plan, need, query, principal) -> ValidatedAnswerDraft | None:
        if self.runtime.embodiment is None:
            return None
        resolver = self.runtime._avatar_self_fact_resolver
        # The private-grant path remains in the existing runtime boundary; this
        # coordinator never broadens private presentation eligibility.
        if resolver.allows_private_projection(query):
            return None
        projection = self.runtime.avatar_projection_for(principal=principal)
        authority = self.runtime.avatar_presentation
        if projection is None or authority is None:
            return None
        result = resolver.resolve(
            query,
            embodiment=self.runtime.embodiment,
            presentation=projection,
            available_outfit_ids=authority.available_outfit_ids,
            wardrobe_matrix=self.runtime._avatar_matrix_for(projection),
        )
        if not result.recognized:
            return None
        atom = self._record(
            need,
            value={
                "answer": result.content,
                "presentation_revision": projection.source_revision,
            },
            source="state:avatar-presentation",
            trust=1.0,
            expires_at=None,
        )
        return self._draft(plan, (atom,), result.content, "avatar")

    def _memory(self, plan, need, query, principal) -> ValidatedAnswerDraft | None:
        memories = self.runtime.memory_system.recall_relevant(
            query,
            principal=principal,
        )
        now = datetime.now(timezone.utc)
        if memories:
            value = tuple(
                {"id": item.id, "content": item.content}
                for item in memories[:3]
            )
            atom = self._record(
                need,
                value=value,
                source="memory-reviewed:retrieval",
                trust=0.9,
                expires_at=now + timedelta(minutes=5),
            )
            content = "What I can ground from reviewed memory:\n" + "\n".join(
                f"- {item.content}" for item in memories[:3]
            )
            return self._draft(plan, (atom,), content, "memory")
        atom = self._unknown_atom(
            need,
            source="runtime:memory-retrieval",
            expires_at=now + timedelta(minutes=5),
        )
        answer = self.claim_validator.validate(
            self.claim_planner.build(plan, (atom,)), (atom,)
        )
        return ValidatedAnswerDraft(
            answer=answer,
            content=(
                "I don't have an eligible reviewed memory that answers that, "
                "so I won't invent a memory from conversation prose."
            ),
            evidence_refs=(atom.evidence_id,),
            domain="memory",
        )

    def _record(self, need, *, value, source, trust, expires_at) -> EvidenceAtom:
        atom = EvidenceAtom(
            evidence_id=f"evidence:{uuid4()}",
            subject_id=need.subject_id,
            predicate=need.predicate,
            value_json=json.dumps(value, ensure_ascii=False, sort_keys=True),
            source_id=source,
            observed_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            scope_id=need.scope_id,
            trust=trust,
            epistemic_state=EpistemicState.KNOWN,
            acquisition_state=AcquisitionState.CURRENT,
        )
        return self.ledger.append(atom)

    def _unknown_atom(self, need, *, source, expires_at) -> EvidenceAtom:
        atom = EvidenceAtom(
            evidence_id=f"evidence:{uuid4()}",
            subject_id=need.subject_id,
            predicate=need.predicate,
            value_json="null",
            source_id=source,
            observed_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            scope_id=need.scope_id,
            trust=0.0,
            epistemic_state=EpistemicState.UNKNOWN,
            acquisition_state=AcquisitionState.UNAVAILABLE,
        )
        return self.ledger.append(atom)

    def _draft(self, plan, atoms, content, domain) -> ValidatedAnswerDraft:
        answer = self.claim_validator.validate(
            self.claim_planner.build(plan, atoms), atoms,
        )
        return ValidatedAnswerDraft(
            answer=answer,
            content=content,
            evidence_refs=tuple(atom.evidence_id for atom in atoms),
            domain=domain,
        )
