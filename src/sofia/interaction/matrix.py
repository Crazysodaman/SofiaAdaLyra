"""INTERACT contribution to the message matrix."""
from sofia.cognition.matrix.model import (
    DomainContribution,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
)
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.core import looks_like_text_interaction


class InteractionMatrixEvaluator:
    domain = MatrixDomain.INTERACTION

    def evaluate(self, envelope, turn):
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
