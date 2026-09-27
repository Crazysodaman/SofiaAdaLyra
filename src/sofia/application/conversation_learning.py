"""Conservative automatic conversation-to-memory candidate generation.

The coordinator runs only after a user message has been durably persisted.
It may create PROPOSED provenance-backed memory candidates, never promote them.
Candidate content is the exact saved user text so no model-generated paraphrase
can silently become memory truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID, NAMESPACE_URL, uuid5

from sofia.application.memory_review import MemoryReviewService
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.memory.provenance import CandidateStatus
from sofia.social.model import PrincipalContext


_EXPLICIT_MEMORY = re.compile(
    r"^\s*(?:please\s+)?remember\s+(?:that\s+)?\S+",
    re.IGNORECASE,
)
_STABLE_FIRST_PERSON = re.compile(
    r"^\s*(?:"
    r"i\s+(?:really\s+)?(?:like|love|prefer|hate|dislike|use|work\s+(?:as|at)|"
    r"live\s+in|want|don't\s+want|do\s+not\s+want)\b|"
    r"i(?:'m|\s+am)\s+(?:a|an)\b|"
    r"my\s+[a-z0-9 _'’-]{1,80}\s+is\b|"
    r"call\s+me\b"
    r")",
    re.IGNORECASE,
)
_CORRECTION_ONLY = re.compile(
    r"^\s*(?:forget\b|stop\s+tracking\b|that's\s+not\s+a\s+habit\b|"
    r"that\s+is\s+not\s+a\s+habit\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LearningResult:
    source_message_id: str
    candidate_id: UUID | None
    proposed: bool
    reason: str


class ConversationLearningCoordinator:
    """Create reviewable candidates from explicit durable user evidence."""

    def __init__(self, memory_review: MemoryReviewService) -> None:
        if not isinstance(memory_review, MemoryReviewService):
            raise TypeError("memory_review must be a MemoryReviewService")
        self._memory_review = memory_review

    @staticmethod
    def _candidate_id(message: ConversationMessage) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"sofia-memory-candidate:{message.session_id}:{message.id}",
        )

    @staticmethod
    def _is_learnable(content: str) -> tuple[bool, str]:
        text = content.strip()
        if not 4 <= len(text) <= 1000:
            return False, "outside bounded learning length"
        if "\x00" in text or chr(96) * 3 in text:
            return False, "code/binary-like content is not auto-proposed"
        if _CORRECTION_ONLY.search(text):
            return False, "correction commands are handled by explicit controls"
        if _EXPLICIT_MEMORY.search(text):
            return True, "explicit remember request"
        if _STABLE_FIRST_PERSON.search(text):
            return True, "explicit first-person preference or stable fact"
        return False, "no reviewed automatic-learning pattern matched"

    def observe_user_message(
        self,
        *,
        message: ConversationMessage,
        principal: PrincipalContext | None,
    ) -> LearningResult:
        if not isinstance(message, ConversationMessage):
            raise TypeError("message must be a ConversationMessage")
        if message.role is not ConversationRole.USER:
            raise ValueError("automatic learning accepts only saved user messages")
        if principal is None:
            return LearningResult(
                message.id,
                None,
                False,
                "unbound conversations cannot create personal memory candidates",
            )
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext or None")

        learnable, reason = self._is_learnable(message.content)
        if not learnable:
            return LearningResult(message.id, None, False, reason)

        candidate_id = self._candidate_id(message)
        existing = self._memory_review.status(candidate_id)
        if existing is not None:
            return LearningResult(
                message.id,
                candidate_id,
                existing is CandidateStatus.PROPOSED,
                f"candidate already exists with status {existing.value}",
            )

        candidate = self._memory_review.propose(
            session_id=message.session_id,
            message_ids=(message.id,),
            content=message.content.strip(),
            created_at=message.created_at,
            candidate_id=candidate_id,
        )
        return LearningResult(
            message.id,
            candidate.candidate_id,
            True,
            reason,
        )
