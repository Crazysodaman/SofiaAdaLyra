"""SOCIAL contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class SocialMatrixEvaluator:
    domain = MatrixDomain.SOCIAL

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.SOCIAL_CHECKIN:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "SOCIAL owns principal-facing conversational context",
            )
        if turn.intent is MatrixIntent.GENERAL:
            return DomainContribution(
                self.domain,
                MatrixRelevance.CONTEXTUAL,
                "ordinary conversation may use social context",
            )
        return None
