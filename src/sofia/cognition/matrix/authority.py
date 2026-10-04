"""Authority/action planning for matrix-controlled turns."""
from __future__ import annotations

import re

from sofia.authority.model import Authority

from .model import (
    AuthorityDecision,
    AuthorityPlan,
    MatrixIntent,
    TurnEnvelope,
    TurnMatrix,
)


_AMBIGUOUS_PRIMARY = re.compile(
    r"\b(?:make|set|switch)\s+(?P<target>[A-Za-z0-9_.-]+)\s+primary\b",
    re.IGNORECASE,
)
_EXPLICIT_PRIMARY_KIND = re.compile(
    r"\b(?:model|llm|database|db|runtime|fleet\s+controller|controller|"
    r"worker|host|node)\b",
    re.IGNORECASE,
)


_INTERACTION_SAFETY_CONTROL = re.compile(
    r"^\s*(?:sof[ií]a,\s*)?(?:stop|pause|resume)\s+"
    r"(?:body\s+)?(?:interactions?|gestures?)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_SELF_PRESENTATION_SUGGESTION = re.compile(
    r"^\s*(?:please\s+)?(?:"
    r"(?:wear|change\s+into|change\s+(?:your\s+)?outfit\s+(?:to|into)|"
    r"put\s+on|take\s+off|take\s+.+?\s+off|swap|switch|undress|"
    r"get\s+undressed)\b"
    r"|"
    r"(?:design|generate|create|make)\s+.*"
    r"\b(?:garment|clothing|shirt|tee|top|tank|hoodie|sweater|"
    r"pants|trousers|jeans|shorts|skirt|dress|jumpsuit|romper|"
    r"bodysuit|bra|bralette|briefs|panties|underwear|socks|"
    r"stockings|shoes|boots|sandals|slippers|jacket|coat|vest|"
    r"belt|gloves|bracelet|necklace|choker|collar|accessory)\b"
    r")",
    re.IGNORECASE,
)


class MatrixAuthorityPlanner:
    """Translate an action request into a plan without granting authority."""

    def plan(
        self,
        envelope: TurnEnvelope,
        turn: TurnMatrix,
        authority: Authority,
    ) -> AuthorityPlan:
        if not isinstance(envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope")
        if not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")
        if not isinstance(authority, Authority):
            raise TypeError("authority must be Authority")

        if turn.intent is not MatrixIntent.ACTION_REQUEST:
            return AuthorityPlan(
                AuthorityDecision.NOT_REQUIRED,
                reason="turn does not request an executable action",
            )

        text = envelope.content.strip()

        if _INTERACTION_SAFETY_CONTROL.fullmatch(text):
            return AuthorityPlan(
                AuthorityDecision.ALLOWED,
                requested_action=text,
                reason=(
                    "host-defined representational interaction safety "
                    "control is directly enforceable"
                ),
            )

        if _SELF_PRESENTATION_SUGGESTION.search(text):
            return AuthorityPlan(
                AuthorityDecision.NOT_REQUIRED,
                reason=(
                    "self-presentation requests are proposals evaluated by "
                    "the dedicated AVATAR autonomy/ownership gate, not generic "
                    "host execution authority"
                ),
            )

        if (
            _AMBIGUOUS_PRIMARY.search(text)
            and _EXPLICIT_PRIMARY_KIND.search(text) is None
        ):
            return AuthorityPlan(
                AuthorityDecision.CLARIFY,
                requested_action=text,
                reason=(
                    "primary target is ambiguous across runtime/model/"
                    "database/Fleet authority domains"
                ),
            )

        if authority.can_execute_actions:
            return AuthorityPlan(
                AuthorityDecision.ALLOWED,
                requested_action=text,
                reason="host authority permits action execution",
            )

        if authority.can_propose_actions:
            return AuthorityPlan(
                AuthorityDecision.REQUIRES_APPROVAL,
                requested_action=text,
                reason=(
                    "host authority permits proposals but not execution "
                    "without approval"
                ),
            )

        return AuthorityPlan(
            AuthorityDecision.DENIED,
            requested_action=text,
            reason="host authority does not permit action proposal or execution",
        )
