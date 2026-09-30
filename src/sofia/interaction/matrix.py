"""INTERACT contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class InteractionMatrixEvaluator:
    domain = MatrixDomain.INTERACTION

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.INTERACTION_FOLLOWUP:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "INTERACT owns represented-action and follow-up constraints",
            )
        if turn.intent is MatrixIntent.AVATAR_QUERY:
            return DomainContribution(
                self.domain,
                MatrixRelevance.CONTEXTUAL,
                "presentation requests may carry interaction constraints",
            )
        return None
