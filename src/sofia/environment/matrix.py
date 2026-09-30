"""ENVIRONMENT contribution to the message matrix."""
import re

from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_ENVIRONMENT = re.compile(
    r"\b(?:weather|temperature|forecast|humidity|outside|time|timezone|"
    r"location|season|daylight|sunrise|sunset)\b",
    re.IGNORECASE,
)


class EnvironmentMatrixEvaluator:
    domain = MatrixDomain.ENVIRONMENT

    def evaluate(self, envelope, turn):
        if not _ENVIRONMENT.search(envelope.content):
            return None
        return DomainContribution(
            self.domain,
            (
                MatrixRelevance.REQUIRED
                if turn.intent is MatrixIntent.ENVIRONMENT_QUERY
                else MatrixRelevance.RELEVANT
            ),
            "ENVIRONMENT owns current weather/time/location/season evidence",
        )
