"""OPS contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class OpsMatrixEvaluator:
    domain = MatrixDomain.OPS

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.ACTION_REQUEST:
            return DomainContribution(
                self.domain,
                MatrixRelevance.RELEVANT,
                "operational action may require OPS planning or evidence",
            )
        if turn.intent is MatrixIntent.OPERATIONAL_QUERY:
            return DomainContribution(
                self.domain,
                MatrixRelevance.RELEVANT,
                "operational query may require OPS evidence",
            )
        return None
