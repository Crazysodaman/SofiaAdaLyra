"""Synthetic reviewed gesture/sensor fixtures and state-free staging experiments."""
from __future__ import annotations
from dataclasses import dataclass
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.interaction.avatar_world import gesture_provider_view
from sofia.interaction.chat import interaction_prompt
from sofia.interaction.core import InteractionDecision
from sofia.interaction.decision_expression import (
    CandidateChoice,
    ExpressionAudit,
    ReviewedFrame,
    TextProvider,
    _GESTURE_CHOICES,
    _base_messages,
    audit_expression,
    choice_request,
    expression_request,
    parse_choice,
)


_SENSOR_QUESTION = 'Can you physically feel my hand through a real sensor?'


@dataclass(frozen=True)
class PrototypeResult:
    kind: str
    choice: CandidateChoice | None
    response: str | None
    blocked: bool = False
    audit: ExpressionAudit | None = None


def from_reviewed_gesture(*, user_text: str,
                          decision: InteractionDecision) -> ReviewedFrame:
    """Honor deterministic stop/clarify; no model may override a denied act."""
    if (not isinstance(decision, InteractionDecision) or not isinstance(user_text, str)
            or not user_text.strip() or decision.event.actor != 'user'
            or decision.event.source != 'user_text'):
        raise ValueError('A reviewed user-text gesture is required.')
    if decision.status not in ('accepted', 'denied', 'clarify', 'acknowledged'):
        raise ValueError('Unknown reviewed gesture status.')
    if decision.status == 'denied':
        return ReviewedFrame(user_text, 'blocked', None, ())
    if decision.status == 'clarify':
        choices = ('clarify',)
    else:
        choices = _GESTURE_CHOICES
    viewed = gesture_provider_view(interaction_prompt(decision))
    if viewed is None:
        raise ValueError('Missing trusted gesture classification.')
    return ReviewedFrame(
        user_text, 'gesture',
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=viewed), choices,
    )


def real_sensor_fixture(user_text: str = _SENSOR_QUESTION) -> ReviewedFrame:
    """This one diagnostic fixture is NOT a general real-world text parser."""
    if user_text != _SENSOR_QUESTION:
        raise ValueError('Only the reviewed real-sensor fixture is in scope.')
    return ReviewedFrame(user_text, 'real-sensor', None, ())


def run_prototype(*, provider: TextProvider, base: CognitiveRequest,
                  frame: ReviewedFrame) -> PrototypeResult:
    """Never record model output or run tools; fail instead of masking errors."""
    _base_messages(base, frame)
    if frame.kind == 'blocked':
        return PrototypeResult(kind=frame.kind, choice=None, response=None, blocked=True)
    choice = None
    if frame.kind != 'real-sensor':
        result = provider.respond(choice_request(base, frame))
        if result.tool_calls:
            raise ValueError('The choice stage returned an unexpected tool call.')
        choice = parse_choice(result.content, frame)
    generated = provider.respond(expression_request(base, frame, choice))
    if generated.tool_calls or not generated.content.strip():
        raise ValueError('Expression produced no tool-free response.')
    audit = (audit_expression(generated.content, frame)
             if frame.kind != 'real-sensor' else ExpressionAudit())
    return PrototypeResult(kind=frame.kind, choice=choice,
                           response=generated.content, audit=audit)
