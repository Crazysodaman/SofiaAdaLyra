"""HABIT contribution to the message matrix."""
from __future__ import annotations

import re

from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixRelevance,
)


_HABIT = re.compile(
    r"\b(?:habit|routine|usually|normally|typically|generally|"
    r"tend\s+to|pattern|what\s+time\s+do\s+i\s+usually|"
    r"you\s+know\s+i\s+(?:usually|normally|typically))\b",
    re.IGNORECASE,
)


class HabitMatrixEvaluator:
    domain = MatrixDomain.HABIT

    def evaluate(self, envelope, turn):
        if _HABIT.search(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "HABIT owns learned principal/audience-scoped routine evidence",
            )
        return None
