"""INTERACT contribution to the message matrix."""
import re
from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
)
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.core import looks_like_text_interaction


_CONTROL = re.compile(
    r"^\s*(?:sof[ií]a,\s*)?(?:stop|pause|resume)\s+"
    r"(?:body\s+)?(?:interactions?|gestures?)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_TOUCH_SCOPE = re.compile(
    r"^\s*(?:so\s+)?(?:question\s+)?what\s+can\s+i\s+touch\s*[?!.]*\s*$",
    re.IGNORECASE,
)



class InteractionMatrixEvaluator:
    domain = MatrixDomain.INTERACTION

    def evaluate(self, envelope, turn):
        if _TOUCH_SCOPE.fullmatch(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "open-ended represented touch scope question",
            )
        if _CONTROL.fullmatch(envelope.content):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "host-defined represented-interaction safety control",
            )
        if turn.intent is MatrixIntent.INTERACTION_FOLLOWUP:
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "INTERACT owns represented-action and follow-up constraints",
            )
        if turn.intent is MatrixIntent.AVATAR_QUERY:
            return DomainContribution(
                self.domain,
                MatrixRelevance.CONTEXTUAL,
                "presentation requests may carry interaction constraints",
            )
        if (
            looks_like_text_interaction(envelope.content)
            or parse_user_action(
                envelope.content,
                message_id=envelope.message_id,
            )
            is not None
        ):
            return DomainContribution(
                self.domain,
                MatrixRelevance.REQUIRED,
                "message matches a reviewed represented-interaction grammar",
            )
        return None
