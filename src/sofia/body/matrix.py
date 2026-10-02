"""BODY contribution to the message matrix."""
from __future__ import annotations

import re

from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixRelevance,
)


_BODY = re.compile(
    r"\b(?:gaia|hexapod|ssc[- ]?32|servo|servos|gait|kinematics|"
    r"robot(?:ic)?\s+(?:body|leg|motion)|physical\s+embodiment|"
    r"move\s+(?:your\s+)?(?:leg|body)|hardware\s+e[- ]?stop)\b",
    re.IGNORECASE,
)


class BodyMatrixEvaluator:
    domain = MatrixDomain.BODY

    def evaluate(self, envelope, turn):
        if _BODY.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "BODY owns physical embodiment/motion context",
            )
        return None
