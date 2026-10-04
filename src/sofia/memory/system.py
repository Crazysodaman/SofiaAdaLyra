from sofia.memory.chatgpt_export_store import ChatGPTExportEvidenceStore
from sofia.memory.historical import HistoricalConversationEvidence
from sofia.memory.model import MemoryRecord
from sofia.memory.promoted_retrieval import retrieve_promoted
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.personality.influence import ContinuityInfluence
from sofia.social.model import AudienceKind, PrincipalContext


class MemorySystem:
    """
    Coordinates Sofía's persistent memory operations.

    Relevance retrieval uses only explicitly promoted, provenance-backed
    reviewed memories. Imported conversation history remains source evidence.
    """

    DEFAULT_RETRIEVAL_BUDGET_CHARACTERS = 4000

    def __init__(
        self,
        candidate_store: DurableMemoryCandidateStore,
        historical_store: ChatGPTExportEvidenceStore | None = None,
    ) -> None:
        if (
            not isinstance(
                candidate_store,
                DurableMemoryCandidateStore,
            )
        ):
            raise TypeError(
                "MemorySystem candidate_store must be a "
                "DurableMemoryCandidateStore."
            )

        if (
            historical_store is not None
            and not isinstance(
                historical_store,
                ChatGPTExportEvidenceStore,
            )
        ):
            raise TypeError(
                "MemorySystem historical_store must be a "
                "ChatGPTExportEvidenceStore or None."
            )

        self._candidate_store = candidate_store
        self._historical_store = historical_store

    @property
    def candidate_store(
        self,
    ) -> DurableMemoryCandidateStore:
        return self._candidate_store


    @property
    def historical_store(self) -> ChatGPTExportEvidenceStore | None:
        return self._historical_store


    def recall_relevant(
        self,
        query: str,
        limit: int = 5,
        *,
        principal: PrincipalContext | None = None,
        influence: ContinuityInfluence | None = None,
    ) -> tuple[MemoryRecord, ...]:
        """
        Retrieve memories relevant to a textual query.

        Only PROMOTED provenance-backed memories are eligible for cognition.
        """

        if not isinstance(query, str):
            raise TypeError(
                "MemorySystem query must be a string."
            )

        if principal is not None and not isinstance(
            principal,
            PrincipalContext,
        ):
            raise TypeError(
                "MemorySystem principal must be a PrincipalContext or None."
            )

        if influence is not None and not isinstance(
            influence,
            ContinuityInfluence,
        ):
            raise TypeError(
                "MemorySystem influence must be a ContinuityInfluence or None."
            )

        if not isinstance(limit, int):
            raise TypeError(
                "MemorySystem limit must be an integer."
            )

        if limit < 1:
            raise ValueError(
                "MemorySystem limit must be greater than zero."
            )

        # Unbound requests fail closed rather than spanning principals.
        if principal is None:
            return ()
        return self._recall_promoted(
            query, limit=limit, principal=principal, influence=influence,
        )

    def recall_historical_evidence(
        self,
        query: str,
        limit: int = 4,
        *,
        principal: PrincipalContext | None = None,
    ) -> tuple[HistoricalConversationEvidence, ...]:
        """Retrieve imported ChatGPT history as evidence, never as memory."""
        if not isinstance(query, str):
            raise TypeError(
                "MemorySystem historical query must be a string."
            )
        if type(limit) is not int or limit < 1:
            raise ValueError(
                "MemorySystem historical limit must be positive."
            )
        if self._historical_store is None or principal is None:
            return ()
        if not isinstance(principal, PrincipalContext):
            raise TypeError(
                "MemorySystem principal must be a PrincipalContext or None."
            )
        if principal.audience_kind is not AudienceKind.PRIVATE:
            return ()
        return self._historical_store.search_relevant(
            query,
            principal_id=principal.principal_id,
            limit=limit,
        )

    def _recall_promoted(
        self,
        query: str,
        *,
        limit: int,
        principal: PrincipalContext,
        influence: ContinuityInfluence | None = None,
    ) -> tuple[MemoryRecord, ...]:
        candidate_store = self._candidate_store

        projection = retrieve_promoted(
            candidate_store,
            query,
            limit=limit,
            budget_characters=(
                self.DEFAULT_RETRIEVAL_BUDGET_CHARACTERS
            ),
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            influence=influence,
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


    def open(self) -> None:
        """Reopen persistent stores after a runtime STOPPED transition."""
        self._candidate_store.open()

    def close(self) -> None:
        """Close all persistent memory stores owned by this system."""
        self._candidate_store.close()
