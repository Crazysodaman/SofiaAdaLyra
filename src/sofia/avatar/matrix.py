"""AVATAR contribution to the message matrix."""
import re

from sofia.cognition.matrix.model import (
    DomainContribution, MatrixDomain, MatrixIntent, MatrixRelevance,
)


_AVATAR = re.compile(
    r"\b(?:wearing|outfit|clothes|clothing|panties|underwear|bra|lingerie|"
    r"hair|tail|ears|appearance|look\s+like|body|height|weight|lounge|loungewear|night\s*wear|nightwear|wear\b|socks?|boots?|shoes?|bare\s*foot|barefoot)\b",
    re.IGNORECASE,
)


class AvatarMatrixEvaluator:
    domain = MatrixDomain.AVATAR

    def evaluate(self, envelope, turn):
        if _AVATAR.search(envelope.content):
            return DomainContribution(
                self.domain,
                (
                    MatrixRelevance.REQUIRED
                    if turn.intent is MatrixIntent.AVATAR_QUERY
                    else MatrixRelevance.RELEVANT
                ),
                "AVATAR owns current presentation and embodiment projection",
            )
        if turn.intent is MatrixIntent.INTERACTION_FOLLOWUP:
            return DomainContribution(
                self.domain,
                MatrixRelevance.CONTEXTUAL,
                "represented interaction may reference avatar state",
            )
        return None
