import re

from sofia.memory.model import MemoryRecord
from sofia.memory.store import MemoryStore


class MemorySystem:
    """
    Coordinates Sofía's persistent memory operations.

    Retrieval is deterministic and intentionally dependency-free.
    """

    def __init__(self, store: MemoryStore) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "MemorySystem store must be a MemoryStore."
            )

        self._store = store

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

        Relevance is determined by deterministic token overlap.
        Results are ordered by descending overlap score and then by
        original memory ordering.
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