"""AVATAR contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class AvatarMatrixEvaluator:
    domain = MatrixDomain.AVATAR

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.AVATAR_QUERY:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "AVATAR owns current presentation and embodiment projection",
            )
        if turn.intent is MatrixIntent.INTERACTION_FOLLOWUP:
            return DomainContribution(
                self.domain,
                MatrixRelevance.CONTEXTUAL,
                "represented interaction may reference avatar state",
            )
        return None
