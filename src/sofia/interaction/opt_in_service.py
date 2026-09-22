"""The normal ExpandedConversationService remains unchanged unless opted in.

Only the exact independently reviewed hug-offer phrase enters the staged
conversation route. Every other turn uses the existing live service, including
stop/resume controls, technical questions, ambiguous offers and general chat.
"""
from __future__ import annotations

from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.expanded_service import ExpandedConversationService
from sofia.interaction.live_offer_service import (
    respond_staged_offer, staged_offers_enabled,
)


class OptInInteractionConversationService(ExpandedConversationService):
    def respond(self, content: str):
        if not staged_offers_enabled() or content != OFFER:
            return super().respond(content)
        return respond_staged_offer(self, content)
