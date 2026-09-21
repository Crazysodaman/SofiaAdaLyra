"""PKG-EVOLVE: review-only protected amendment proposal, no mutation facility."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class AmendmentDomain(str, Enum):
    MUTABLE_PREFERENCE = 'mutable_preference'
    PROTECTED_IDENTITY = 'protected_identity'
    CONSTITUTION = 'constitution'


@dataclass(frozen=True)
class AmendmentProposal:
    domain: AmendmentDomain
    expected_source_sha256: str
    change_summary: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.domain, AmendmentDomain):
            raise TypeError('Explicit amendment domain required.')
        if not isinstance(self.expected_source_sha256, str) or not re.fullmatch(
            r'[a-fA-F0-9]{64}', self.expected_source_sha256
        ):
            raise ValueError('A pinned source SHA-256 is required.')
        if not isinstance(self.change_summary, str) or not self.change_summary.strip():
            raise ValueError('A change summary is required.')
        if (not isinstance(self.evidence_ids, tuple) or not self.evidence_ids
                or any(not isinstance(item, str) or not item.strip() for item in self.evidence_ids)):
            raise ValueError('Supporting source identifiers are required.')

    @property
    def protected_procedure_required(self) -> bool:
        return self.domain in (AmendmentDomain.PROTECTED_IDENTITY, AmendmentDomain.CONSTITUTION)

    @property
    def automatically_applicable(self) -> bool:
        """Proposals must never self-authorize protected or mutable changes."""
        return False
