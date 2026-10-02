"""DEV contribution to the message matrix."""
from __future__ import annotations

import re

from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixRelevance,
)


_DEV = re.compile(
    r"\b(?:code|codebase|source\s+code|repository|repo|git|github|"
    r"pytest|test\s+suite|tests?|python\s+file|commit|branch|pull\s+request|\bpr\b)\b",
    re.IGNORECASE,
)


class DevMatrixEvaluator:
    domain = MatrixDomain.DEV

    def evaluate(self, envelope, turn):
        if _DEV.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "DEV owns repository/code/test engineering context",
            )
        return None
