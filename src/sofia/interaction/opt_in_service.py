"""Opt-in adapter: default conversation behavior remains unchanged.

The exact reviewed declarative offer uses staged choice/expression. Only
separately reviewed ambiguous hug questions receive a policy-checked,
non-inferential clarification. Other turns (including hypothetical, sensor,
stop/resume and general chat) use the existing live service.
"""
from __future__ import annotations

from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.expanded_service import ExpandedConversationService
from sofia.interaction.live_offer_service import (
    respond_staged_offer, staged_offers_enabled,
)
from sofia.interaction.question_clarification_service import respond_reviewed_hug_question
from sofia.interaction.reviewed_hug_question import is_reviewed_hug_question
from sofia.social.model import PrincipalContext


class OptInInteractionConversationService(ExpandedConversationService):
    def respond(
        self,
        content: str,
        *,
        principal: PrincipalContext | None = None,
    ):
        if not staged_offers_enabled():
            return super().respond(content) if principal is None else super().respond(
            content, principal=principal
        )
        if content == OFFER:
            return respond_staged_offer(
                self, content, principal=principal
            )
        if is_reviewed_hug_question(content):
            return respond_reviewed_hug_question(
                self, content, principal=principal
            )
        return super().respond(content) if principal is None else super().respond(
            content, principal=principal
        )
