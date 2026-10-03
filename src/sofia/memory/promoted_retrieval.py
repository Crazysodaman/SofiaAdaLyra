"""Deterministic retrieval over currently promoted provenance-backed memory."""
from __future__ import annotations

import re

from sofia.cognition.matrix.influence import (
    ContextualInfluenceMatrix,
    InfluenceMode,
    InfluenceSignal,
    InfluenceSurface,
)
from sofia.memory.cognition_projection import (
    MemoryProjection,
    project_promoted_memories,
)
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.personality.influence import ContinuityInfluence


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
) -> MemoryProjection:
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive integer")

    query_tokens = _tokens(query)
    if not query_tokens:
        return MemoryProjection((), (), ())

    contextual_tokens = _contextual_rerank_tokens(influence)
    ranked: list[tuple[int, int, int, object]] = []

    for order, candidate_id in enumerate(
        store.list_ids(
            status=CandidateStatus.PROMOTED,
            principal_id=principal_id,
            audience_id=audience_id,
        )
    ):
        memory = store.get(candidate_id)
        if memory is None:
            continue

        memory_tokens = _tokens(memory.content)
        query_score = len(query_tokens & memory_tokens)

        # Hard relevance gate: contextual salience cannot summon an unrelated
        # memory merely because weather, season, daypart, or emotion matches.
        if query_score <= 0:
            continue

        context_score = len(contextual_tokens & memory_tokens)
        ranked.append(
            (
                -query_score,
                -context_score,
                order,
                candidate_id,
            )
        )

    ranked.sort()
    ids = [
        candidate_id
        for _, _, _, candidate_id in ranked[:limit]
    ]
    return project_promoted_memories(
        store,
        ids,
        budget_characters=budget_characters,
    )
