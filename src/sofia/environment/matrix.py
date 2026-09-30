"""ENVIRONMENT contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class EnvironmentMatrixEvaluator:
    domain = MatrixDomain.ENVIRONMENT

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.ENVIRONMENT_QUERY:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "ENVIRONMENT owns current weather/time/location evidence",
            )
        return None
