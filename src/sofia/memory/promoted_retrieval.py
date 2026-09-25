"""Deterministic retrieval over currently promoted provenance-backed memory."""
from __future__ import annotations
import re
from sofia.memory.cognition_projection import MemoryProjection, project_promoted_memories
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore


def _tokens(value: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[A-Za-z0-9À-ÿ']+", value) if len(x) > 1}


def retrieve_promoted(store: DurableMemoryCandidateStore, query: str, *, limit: int = 5,
                      budget_characters: int = 4000) -> MemoryProjection:
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive integer")
    query_tokens=_tokens(query)
    if not query_tokens:
        return MemoryProjection((),(),())
    ranked=[]
    for order,candidate_id in enumerate(store.list_ids(status=CandidateStatus.PROMOTED)):
        memory=store.get(candidate_id)
        if memory is None:
            continue
        score=len(query_tokens & _tokens(memory.content))
        if score:
            ranked.append((-score,order,candidate_id))
    ranked.sort()
    ids=[candidate_id for _,_,candidate_id in ranked[:limit]]
    return project_promoted_memories(store,ids,budget_characters=budget_characters)
