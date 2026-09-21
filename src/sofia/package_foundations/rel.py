"""PKG-REL: source-linked candidate preference; no automatic emotion inference."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Stance(str, Enum):
    LIKES = 'likes'
    DISLIKES = 'dislikes'
    UNCERTAIN = 'uncertain'


@dataclass(frozen=True)
class PreferenceRevision:
    subject_id: str
    topic: str
    stance: Stance
    source_message_id: str
    reviewed_by: str | None = None

    def __post_init__(self) -> None:
        for field in ('subject_id', 'topic', 'source_message_id'):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{field} requires explicit nonempty text.')
        if not isinstance(self.stance, Stance):
            raise TypeError('An explicit stance is required.')
        if self.reviewed_by is not None and (
            not isinstance(self.reviewed_by, str) or not self.reviewed_by.strip()
        ):
            raise ValueError('Reviewer must be nonempty when provided.')

    @property
    def reviewed(self) -> bool:
        """A source-linked review marker, not consent or permission."""
        return self.reviewed_by is not None
