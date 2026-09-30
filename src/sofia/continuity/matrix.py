"""CONTINUITY contribution to the message matrix."""
import re

from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
)


_CONTINUITY = re.compile(
    r"\b(?:restart(?:ed)?|reboot(?:ed)?|startup|shutdown|previous\s+runtime|"
    r"previous\s+run|continuity|workspace\s+changes?|what\s+changed)\b",
    re.IGNORECASE,
)


class ContinuityMatrixEvaluator:
    domain = MatrixDomain.CONTINUITY

    def evaluate(self, envelope, turn):
        if _CONTINUITY.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "CONTINUITY owns restart/workspace continuity evidence",
            )
        return None
