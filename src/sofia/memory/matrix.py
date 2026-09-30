"""MEMORY contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class MemoryMatrixEvaluator:
    domain = MatrixDomain.MEMORY

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.MEMORY_QUERY:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "MEMORY retrieval is explicitly requested",
            )
        return None
