"""Production KNOW retrieval bridge into cognition v2 evidence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sofia.capability.model import CapabilityResultKind
from sofia.cognition.model import CognitiveResponse, CognitiveToolCall
from sofia.cognition.tools import CognitiveToolDispatcher
from sofia.cognition.v2.contracts import ActionRequirement, ConversationFocus, TurnPlan
from sofia.cognition.v2.evidence import CapabilityEvidencePayload, EvidenceAcquisitionCoordinator
from sofia.social.model import PrincipalContext


class KnowledgeEvidenceCoordinator:
    """Acquire scoped KNOW hits; retrieval is evidence, never model truth."""

    def __init__(
        self,
        dispatcher: CognitiveToolDispatcher,
        acquisition: EvidenceAcquisitionCoordinator,
    ) -> None:
        self.dispatcher = dispatcher
        self.acquisition = acquisition

    def answer(
        self,
        *,
        plan: TurnPlan,
        focus: ConversationFocus,
        principal: PrincipalContext | None,
        allowed_capabilities: tuple[str, ...],
        query: str | None = None,
    ) -> CognitiveResponse | None:
        needs = tuple(
            need for need in plan.evidence_needs
            if need.predicate == "knowledge.retrieval"
        )
        if (
            not needs
            or plan.action_requirement is ActionRequirement.MUTATION
            or "knowledge.search" not in allowed_capabilities
            or not isinstance(query, str)
            or not query.strip()
        ):
            return None
        try:
            result = self.dispatcher.dispatch(
                CognitiveToolCall(
                    name="search_knowledge",
                    arguments={"query": query.strip(), "limit": 5},
                    call_id=f"v2-knowledge:{plan.turn_id}",
                ),
                principal=principal,
                allowed_capabilities=("knowledge.search",),
            )
        except Exception:
            return None
        if result.kind is not CapabilityResultKind.SUCCESS:
            return None
        hits = tuple(result.evidence or ())
        now = datetime.now(timezone.utc)
        atom_ids = []
        for need in needs:
            atom = self.acquisition.record(
                need,
                result,
                CapabilityEvidencePayload(
                    evidence_id=f"evidence:{uuid4()}",
                    subject_id=need.subject_id,
                    predicate=need.predicate,
                    value=hits,
                    source_id="capability:knowledge.search",
                    observed_at=now,
                    expires_at=now + timedelta(minutes=5),
                    scope_id=need.scope_id,
                    trust=0.9,
                ),
            )
            atom_ids.append(atom.evidence_id)
        if not hits:
            return CognitiveResponse(
                content="I searched the eligible knowledge index, but found no active source section matching that request.",
                evidence_refs=("capability:knowledge.search", *atom_ids),
            )
        rendered = []
        for hit in hits[:3]:
            if not isinstance(hit, dict):
                continue
            heading = f" — {hit['heading']}" if hit.get("heading") else ""
            snippet = str(hit.get("statement", "")).replace("\n", " ").strip()
            if len(snippet) > 240:
                snippet = snippet[:237].rstrip() + "..."
            rendered.append(
                f"{hit.get('source_uri', 'source')} ({hit.get('locator', 'unknown location')})"
                f"{heading}: {snippet}"
            )
        if not rendered:
            return None
        return CognitiveResponse(
            content="Knowledge sources found:\n" + "\n".join(f"- {item}" for item in rendered),
            evidence_refs=("capability:knowledge.search", *atom_ids),
        )
