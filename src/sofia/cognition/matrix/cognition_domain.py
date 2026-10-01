"""COGNITION/model contribution to the message matrix."""
import re

from .model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_MODEL = re.compile(
    r"\b(?:llm|model|ollama|primary|secondary|routing|cognition|"
    r"matrix|matrixes|matrices|matrixs)\b",
    re.IGNORECASE,
)


class CognitionMatrixEvaluator:
    domain = MatrixDomain.COGNITION

    def evaluate(self, envelope, turn):
        if _MODEL.search(envelope.content):
            return DomainContribution(
                self.domain,
                (
                    MatrixRelevance.REQUIRED
                    if turn.intent in {
                        MatrixIntent.OPERATIONAL_QUERY,
                        MatrixIntent.ACTION_REQUEST,
                    }
                    else MatrixRelevance.RELEVANT
                ),
                "COGNITION owns Sofía model/routing/matrix architecture context",
            )
        return None
