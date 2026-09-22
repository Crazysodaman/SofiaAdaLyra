"""Opt-in bridge from a trusted conversation request to staged avatar-offer inference.

Unlike the original two-message synthetic probe, this preserves the exact
provider-bound conversation history and trusted projections. It never elevates
past assistant prose to policy, grants tools, saves state or chooses consent.
The trusted host must authenticate the session and supply the original saved
user turn. This module does not do either job.
"""
from __future__ import annotations

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.interaction.architecture_compare import OFFER, routed_choice_request
from sofia.interaction.decision_expression import (
    CandidateChoice, ReviewedFrame, expression_request,
)


def _parts(base: CognitiveRequest, frame: ReviewedFrame) -> tuple[
    CognitiveMessage, tuple[CognitiveMessage, ...], CognitiveMessage
]:
    """Reject unreviewed, tool-bearing or mismatched conversation projections."""
    if (not isinstance(base, CognitiveRequest) or base.tools
            or not isinstance(frame, ReviewedFrame) or frame.kind != 'offer'
            or frame.user_text != OFFER or frame.reviewed is None
            or len(base.messages) < 2):
        raise ValueError('A tool-free reviewed offer conversation is required.')
    canonical, user = base.messages[0], base.messages[-1]
    if (canonical.role is not CognitiveRole.SYSTEM
            or 'AUTHORITATIVE SELF-STATE PROJECTION' not in canonical.content
            or user.role is not CognitiveRole.USER
            or user.content != frame.user_text):
        raise ValueError('Canonical self-state and exact saved user offer are required.')
    if any(message.tool_calls or message.tool_call_id is not None
           or message.role not in (
               CognitiveRole.SYSTEM, CognitiveRole.USER, CognitiveRole.ASSISTANT,
           ) for message in base.messages):
        raise ValueError('Tool turns cannot enter the isolated social choice path.')
    middle = base.messages[1:-1]
    if middle:
        # A trusted host must supply precisely one independently reviewed
        # classification; prior assistant dialogue is never a substitute.
        if sum(message == frame.reviewed for message in middle) != 1:
            raise ValueError('Exactly one trusted reviewed offer projection is required.')
    return canonical, middle, user


def routed_conversation_choice_request(
    base: CognitiveRequest, frame: ReviewedFrame,
) -> CognitiveRequest:
    """Preserve entire original history while replacing only the choice task."""
    canonical, middle, user = _parts(base, frame)
    template = routed_choice_request(
        CognitiveRequest(messages=(canonical, user), tools=()), frame,
    )
    reviewed = (frame.reviewed,) if not middle else ()
    return CognitiveRequest(messages=(
        canonical, *reviewed, *middle, template.messages[-2], user,
    ), tools=())


def routed_conversation_expression_request(
    base: CognitiveRequest, frame: ReviewedFrame, choice: CandidateChoice,
) -> CognitiveRequest:
    """Reuse the original context; pass choice, never the diagnostic reason."""
    canonical, middle, user = _parts(base, frame)
    template = expression_request(
        CognitiveRequest(messages=(canonical, user), tools=()), frame, choice,
    )
    reviewed = (frame.reviewed,) if not middle else ()
    return CognitiveRequest(messages=(
        canonical, *reviewed, *middle, template.messages[-2], user,
    ), tools=())
