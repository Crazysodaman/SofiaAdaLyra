"""EMOTION contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class EmotionMatrixEvaluator:
    domain = MatrixDomain.EMOTION

    def evaluate(self, envelope, turn):
        if turn.intent in {
            MatrixIntent.SOCIAL_CHECKIN,
            MatrixIntent.INTERACTION_FOLLOWUP,
        }:
            return DomainContribution(
                self.domain,
                MatrixRelevance.RELEVANT,
                "modeled emotion is relevant to this conversational intent",
            )
        return None
