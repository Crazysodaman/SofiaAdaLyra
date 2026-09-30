"""MACHINE contribution to the message matrix."""
import re

from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_MACHINE = re.compile(
    r"\b(?:cpu|gpu|ram|memory\s+usage|disk|storage|process|service|"
    r"network|adapter|route|dns|host|machine|computer)\b",
    re.IGNORECASE,
)


class MachineMatrixEvaluator:
    domain = MatrixDomain.MACHINE

    def evaluate(self, envelope, turn):
        if (
            turn.intent is MatrixIntent.OPERATIONAL_QUERY
            and _MACHINE.search(envelope.content)
        ):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "MACHINE owns host-local inspection evidence",
            )
        return None
