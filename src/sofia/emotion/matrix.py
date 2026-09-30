"""EMOTION contribution to the message matrix."""
import re

from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_EMOTION = re.compile(
    r"\b(?:hru|how\s+(?:are|r)\s+(?:you|u)|feel|feeling|emotion|"
    r"happy|sad|upset|angry|mad|excited|calm|worried|nervous|"
    r"frustrated|content)\b",
    re.IGNORECASE,
)


class EmotionMatrixEvaluator:
    domain = MatrixDomain.EMOTION

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.INTERACTION_FOLLOWUP:
            return DomainContribution(
                self.domain,
                MatrixRelevance.RELEVANT,
                "modeled emotion is relevant to represented-experience follow-up",
            )
        if _EMOTION.search(envelope.content):
            return DomainContribution(
                self.domain,
                (
                    MatrixRelevance.RELEVANT
                    if turn.intent is MatrixIntent.SOCIAL_CHECKIN
                    else MatrixRelevance.REQUIRED
                ),
                "EMOTION owns modeled emotional-state projection",
            )
        return None
