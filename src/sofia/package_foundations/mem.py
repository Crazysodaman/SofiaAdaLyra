"""PKG-MEM: a pure, opt-in promotion gate; no durable writes or retrieval."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionProposal:
    original_message_ids: tuple[str, ...]
    candidate_text: str
    reviewer_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.original_message_ids, tuple) or not self.original_message_ids:
            raise ValueError('Original message evidence is required.')
        if any(not isinstance(item, str) or not item.strip()
               for item in self.original_message_ids):
            raise ValueError('Original message IDs must be nonempty strings.')
        if len(set(self.original_message_ids)) != len(self.original_message_ids):
            raise ValueError('Original message IDs must be unique.')
        if not isinstance(self.candidate_text, str) or not self.candidate_text.strip():
            raise ValueError('Candidate text must be nonempty.')
        if self.reviewer_id is not None and (
            not isinstance(self.reviewer_id, str) or not self.reviewer_id.strip()
        ):
            raise ValueError('Reviewer ID must be nonempty when supplied.')

    @property
    def eligible_for_reviewed_promotion(self) -> bool:
        """Eligibility only; not authorization, persistence or a verified preference."""
        return self.reviewer_id is not None
