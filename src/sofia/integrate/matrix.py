"""INTEGRATE contribution to the message matrix."""
from __future__ import annotations

import re

from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixRelevance,
)


_INTEGRATE = re.compile(
    r"\b(?:home\s+assistant|jmri|portainer|docker|containers?|"
    r"hyper[- ]?v|virtual\s+machines?|\bvms?\b)\b",
    re.IGNORECASE,
)


class IntegrateMatrixEvaluator:
    domain = MatrixDomain.INTEGRATE

    def evaluate(self, envelope, turn):
        if _INTEGRATE.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "INTEGRATE owns typed external service/application adapter context",
            )
        return None
