"""Budgeted cognition projection for accepted provenance-backed memories."""
from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore


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
        if store.status(candidate_id) is not CandidateStatus.PROMOTED:
            inactive.append(candidate_id); continue
        memory=store.get(candidate_id)
        if memory is None:
            inactive.append(candidate_id); continue
        if len(memory.content) > remaining:
            omitted.append(candidate_id); continue
        selected.append(ProjectedMemory(candidate_id,memory.content))
        remaining-=len(memory.content)
    return MemoryProjection(tuple(selected),tuple(omitted),tuple(inactive))
