"""Deterministic retrieval over currently promoted provenance-backed memory."""
from __future__ import annotations

import re
from heapq import nsmallest
from dataclasses import dataclass
from uuid import UUID

from sofia.cognition.matrix.influence import (
    ContextualInfluenceMatrix,
    InfluenceMode,
    InfluenceSignal,
    InfluenceSurface,
)
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.personality.influence import ContinuityInfluence



@dataclass(frozen=True, slots=True)
class ProjectedMemory:
    candidate_id: UUID
    content: str


@dataclass(frozen=True, slots=True)
class MemoryProjection:
    selected: tuple[ProjectedMemory, ...]
    omitted_ids: tuple[UUID, ...]
    missing_or_inactive_ids: tuple[UUID, ...]


def project_promoted_memories(store: DurableMemoryCandidateStore, candidate_ids, *, budget_characters: int) -> MemoryProjection:
    if not isinstance(store, DurableMemoryCandidateStore):
        raise TypeError("store must be a DurableMemoryCandidateStore")
    if type(budget_characters) is not int or budget_characters < 0:
        raise ValueError("budget_characters must be a nonnegative integer")
    selected=[]; omitted=[]; inactive=[]; seen=set(); remaining=budget_characters
    for candidate_id in candidate_ids:
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate IDs must be UUIDs")
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        if not store.is_recall_eligible(candidate_id):
            inactive.append(candidate_id); continue
        memory=store.get(candidate_id)
        if memory is None:
            inactive.append(candidate_id); continue
        if len(memory.content) > remaining:
            omitted.append(candidate_id); continue
        selected.append(ProjectedMemory(candidate_id,memory.content))
        remaining-=len(memory.content)
    return MemoryProjection(tuple(selected),tuple(omitted),tuple(inactive))



def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9À-ÿ']+", value)
        if len(token) > 1
    }


def _contextual_rerank_tokens(
    influence: ContinuityInfluence | None,
) -> set[str]:
    """Return only matrix-authorized contextual tie-breaker terms.

    These terms never create retrieval eligibility. They are consulted only
    after a promoted memory already overlaps the user's explicit query.
    """
    if influence is None:
        return set()
    if not isinstance(influence, ContinuityInfluence):
        raise TypeError("influence must be ContinuityInfluence or None")

    plan = ContextualInfluenceMatrix().plan(
        InfluenceSurface.MEMORY_RERANK,
        influence,
    )
    terms: set[str] = set()

    if (
        plan.mode_for(InfluenceSignal.EMOTION)
        is not InfluenceMode.NONE
        and influence.primary_emotion
    ):
        terms.update(_tokens(influence.primary_emotion))

    if (
        plan.mode_for(InfluenceSignal.WEATHER)
        is not InfluenceMode.NONE
        and influence.weather_condition
    ):
        terms.update(_tokens(influence.weather_condition))

    if (
        plan.mode_for(InfluenceSignal.DAYPART)
        is not InfluenceMode.NONE
    ):
        terms.update(_tokens(influence.daypart))

    if (
        plan.mode_for(InfluenceSignal.SEASON)
        is not InfluenceMode.NONE
        and influence.season
    ):
        terms.update(_tokens(influence.season))

    return terms


def retrieve_promoted(
    store: DurableMemoryCandidateStore,
    query: str,
    *,
    limit: int = 5,
    budget_characters: int = 4000,
    principal_id: str | None = None,
    audience_id: str | None = None,
    influence: ContinuityInfluence | None = None,
    association_store=None,
) -> MemoryProjection:
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive integer")

    query_tokens = _tokens(query)
    if not query_tokens:
        return MemoryProjection((), (), ())

    contextual_tokens = _contextual_rerank_tokens(influence)
    def ranked_matches():
        # Stable keyset SQL batches keep memory bounded even when the owner
        # retains years of reviewed candidates. Only the top `limit` IDs
        # survive scoring; source provenance remains on canonical SQLite.
        for order, (candidate_id, content) in enumerate(
            store.iter_promoted_summaries(
                principal_id=principal_id, audience_id=audience_id,
            )
        ):
            memory_tokens = _tokens(content)
            query_score = len(query_tokens & memory_tokens)

            # Salience from emotion/weather/daypart cannot grant eligibility.
            if query_score <= 0:
                continue
            context_score = len(contextual_tokens & memory_tokens)
            yield (-query_score, -context_score, order, candidate_id)

    # NEURO sees only a small, already promoted, principal/audience-filtered
    # and query-overlapping lexical shortlist. It never supplies an ID, query
    # term, scope or eligibility rule to MEM. Original lexical relevance and
    # context retain precedence; associations can break eligible ties only.
    window = nsmallest(
        (max(limit, 16) if limit <= 64 and association_store is not None else limit),
        ranked_matches(),
    )
    if (
        association_store is not None and principal_id is not None
        and audience_id is not None and limit <= 64 and window
    ):
        try:
            strengths = association_store.scores(
                principal_id=principal_id, audience_id=audience_id,
                query=query,
                eligible_ids=tuple(row[3] for row in window),
            )
        except Exception:
            # Invalid/disabled/unavailable association state cannot block
            # reviewed MEM retrieval or broaden eligibility.
            strengths = {}
        window.sort(
            key=lambda row: (
                row[0], row[1], -strengths.get(row[3], 0.0),
                row[2], str(row[3]),
            )
        )
    ids = [row[3] for row in window[:limit]]
    return project_promoted_memories(
        store,
        ids,
        budget_characters=budget_characters,
    )
