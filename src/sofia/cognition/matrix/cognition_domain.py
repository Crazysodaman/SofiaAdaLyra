"""COGNITION/model contribution to the message matrix."""
import re

from .model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_MODEL = re.compile(
    r"\b(?:llm|model|ollama|primary|secondary|routing|cognition)\b",
    re.IGNORECASE,
)


class CognitionMatrixEvaluator:
    domain = MatrixDomain.COGNITION

    def evaluate(self, envelope, turn):
        if (
            turn.intent in {
                MatrixIntent.OPERATIONAL_QUERY,
                MatrixIntent.ACTION_REQUEST,
            }
            and _MODEL.search(envelope.content)
        ):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "COGNITION owns configured model/routing state",
            )
        return None
