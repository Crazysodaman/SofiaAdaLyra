"""AUTHORITY contribution to the message matrix.

This evaluator can request an authority decision. It never grants one.
"""
from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


class AuthorityMatrixEvaluator:
    domain = MatrixDomain.AUTHORITY

    def evaluate(self, envelope, turn):
        if turn.intent is MatrixIntent.ACTION_REQUEST:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "an action request requires independent authority evaluation",
            )
        return None
