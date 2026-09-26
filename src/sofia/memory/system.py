import re

from sofia.memory.model import MemoryRecord
from sofia.memory.promoted_retrieval import retrieve_promoted
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.store import MemoryStore


class MemorySystem:
    """
    Coordinates Sofía's persistent memory operations.

    Legacy memory records remain available through explicit remember/recall
    APIs for compatibility. When a provenance-backed candidate store is
    configured, normal relevance retrieval uses only explicitly promoted
    reviewed memories.
    """

    DEFAULT_RETRIEVAL_BUDGET_CHARACTERS = 4000

    def __init__(
        self,
        store: MemoryStore,
        candidate_store: DurableMemoryCandidateStore | None = None,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "MemorySystem store must be a MemoryStore."
            )

        if (
            candidate_store is not None
            and not isinstance(
                candidate_store,
                DurableMemoryCandidateStore,
            )
        ):
            raise TypeError(
                "MemorySystem candidate_store must be a "
                "DurableMemoryCandidateStore or None."
            )

        self._store = store
        self._candidate_store = candidate_store

    @property
    def candidate_store(
        self,
    ) -> DurableMemoryCandidateStore | None:
        return self._candidate_store

    @property
    def uses_reviewed_memory(self) -> bool:
        return self._candidate_store is not None

    def remember(
        self,
        memory: MemoryRecord,
    ) -> None:
        self._store.save(memory)

    def recall(
        self,
        memory_id: str,
    ) -> MemoryRecord | None:
        return self._store.get(memory_id)

    def recall_relevant(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[MemoryRecord, ...]:
        """
        Retrieve memories relevant to a textual query.

        With a reviewed candidate store configured, only PROMOTED
        provenance-backed memories are eligible for cognition. Legacy
        token-overlap retrieval remains available only for MemorySystem
        instances constructed without the reviewed store.
        """

        if not isinstance(query, str):
            raise TypeError(
                "MemorySystem query must be a string."
            )

        if not isinstance(limit, int):
            raise TypeError(
                "MemorySystem limit must be an integer."
            )

        if limit < 1:
            raise ValueError(
                "MemorySystem limit must be greater than zero."
            )

        if self._candidate_store is not None:
            return self._recall_promoted(
                query,
                limit=limit,
            )

        return self._recall_legacy(
            query,
            limit=limit,
        )

    def _recall_promoted(
        self,
        query: str,
        *,
        limit: int,
    ) -> tuple[MemoryRecord, ...]:
        candidate_store = self._candidate_store

        if candidate_store is None:
            return ()

        projection = retrieve_promoted(
            candidate_store,
            query,
            limit=limit,
            budget_characters=(
                self.DEFAULT_RETRIEVAL_BUDGET_CHARACTERS
            ),
        )

        records: list[MemoryRecord] = []

        for projected in projection.selected:
            # Re-check status immediately before projection into the
            # cognitive MemoryRecord shape. A revoke that lands between
            # retrieval and projection must fail closed.
            if (
                candidate_store.status(
                    projected.candidate_id
                )
                is not CandidateStatus.PROMOTED
            ):
                continue

            candidate = candidate_store.get(
                projected.candidate_id
            )

            if candidate is None:
                continue

            records.append(
                MemoryRecord(
                    id=str(candidate.candidate_id),
                    content=candidate.content,
                    created_at=candidate.created_at,
                )
            )

        return tuple(records)

    def _recall_legacy(
        self,
        query: str,
        *,
        limit: int,
    ) -> tuple[MemoryRecord, ...]:
        """
        Compatibility retrieval for callers that have not yet been wired to
        the reviewed memory pipeline.
        """

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return ()

        scored: list[
            tuple[int, int, MemoryRecord]
        ] = []

        for index, memory in enumerate(
            self._store.list_all()
        ):
            memory_tokens = self._tokenize(
                memory.content
            )

            score = len(
                query_tokens.intersection(
                    memory_tokens
                )
            )

            if score > 0:
                scored.append(
                    (
                        score,
                        index,
                        memory,
                    )
                )

        scored.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        return tuple(
            memory
            for _, _, memory in scored[:limit]
        )

    @staticmethod
    def _tokenize(
        content: str,
    ) -> set[str]:
        return {
            token.lower()
            for token in re.findall(
                r"[A-Za-z0-9À-ÿ']+",
                content,
            )
            if len(token) > 1
        }
