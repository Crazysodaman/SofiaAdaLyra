"""REL contribution to the message matrix."""
from __future__ import annotations

import re

from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
)


_RELATIONSHIP = re.compile(
    r"\b(?:relationship|how\s+long\s+(?:have\s+)?i\s+been\s+(?:gone|away)|"
    r"how\s+long\s+was\s+i\s+(?:gone|away)|when\s+(?:did\s+)?we\s+last\s+"
    r"(?:talk|speak|chat)|last\s+(?:talked|spoke|chatted)|"
    r"did\s+you\s+miss\s+me|missed\s+me|i(?:'|’)m\s+back)\b",
    re.IGNORECASE,
)


class RelationshipMatrixEvaluator:
    domain = MatrixDomain.REL

    def evaluate(self, envelope, turn):
        if _RELATIONSHIP.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "REL owns principal-bound prior-contact continuity evidence",
            )
        if turn.intent is MatrixIntent.SOCIAL_CHECKIN:
            return DomainContribution(
                self.domain,
                MatrixRelevance.CONTEXTUAL,
                "a social check-in may use prior-contact continuity when available",
            )
        return None
