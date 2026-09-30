"""MEMORY contribution to the message matrix."""
import re

from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_MEMORY = re.compile(
    r"\b(?:remember|remembered|memory|earlier|last\s+time|"
    r"what\s+did\s+i\s+say|what\s+did\s+we\s+talk)\b",
    re.IGNORECASE,
)


class MemoryMatrixEvaluator:
    domain = MatrixDomain.MEMORY

    def evaluate(self, envelope, turn):
        if _MEMORY.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "MEMORY retrieval is explicitly requested",
            )
        return None
