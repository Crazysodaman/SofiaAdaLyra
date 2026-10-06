"""Matrix relevance for canonical goal lifecycle turns."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class GoalMatrixEvaluator:
    domain = MatrixDomain.GOALS

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.GOAL_MANAGEMENT:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "GOALS owns persistent directions and lifecycle state",
            )
        return None
