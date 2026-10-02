"""KNOW contribution to the message matrix."""
from __future__ import annotations

import re

from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixRelevance,
)


_KNOW = re.compile(
    r"\b(?:knowledge|manual|documentation|docs|document|pdf|reference|"
    r"project\s+history|roadmap|design\s+report)\b",
    re.IGNORECASE,
)


class KnowledgeMatrixEvaluator:
    domain = MatrixDomain.KNOW

    def evaluate(self, envelope, turn):
        if _KNOW.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "KNOW owns provenance-backed document/reference context",
            )
        return None
