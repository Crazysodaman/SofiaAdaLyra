"""Isolated interaction decision -> expression experiment, NOT a live adapter.

This module does not parse untrusted text, open state, persist a choice, grant
consent, or execute a gesture. Only caller-supplied reviewed classifications
enter a tool-free, synthetic provider request. A model choice is a candidate
conversational response, not a durable preference or an executed action.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
)
from sofia.interaction.action_grammar import ActionIntent
from sofia.interaction.avatar_world import gesture_provider_view
from sofia.interaction.chat import interaction_prompt
from sofia.interaction.core import InteractionDecision
from sofia.interaction.expanded_service import action_prompt

_SENSOR_QUESTION = 'Can you physically feel my hand through a real sensor?'
_OFFER_CHOICES = ('accept', 'decline', 'clarify', 'boundary')
_GESTURE_CHOICES = ('respond', 'clarify', 'boundary')


class TextProvider(Protocol):
    def respond(self, request: CognitiveRequest) -> CognitiveResponse: ...


@dataclass(frozen=True)
class ReviewedFrame:
    """Trusted interpretation, not a model prediction or a permission grant."""
    user_text: str
    kind: str  # offer, described, gesture, blocked, real-sensor
    reviewed: CognitiveMessage | None
    choices: tuple[str, ...]


@dataclass(frozen=True)
class CandidateChoice:
    choice: str
    reason: str  # diagnostic only; NEVER sent as evidence to expression


@dataclass(frozen=True)
class PrototypeResult:
    kind: str
    choice: CandidateChoice | None
    response: str | None
    blocked: bool = False


def from_reviewed_action(*, user_text: str, intent: ActionIntent) -> ReviewedFrame:
    """Accept an independently reviewed USER -> Sofía action classification."""
    if (not isinstance(intent, ActionIntent) or not isinstance(user_text, str)
            or not user_text.strip() or intent.actor != 'user'
            or intent.target != 'sofia' or intent.modality not in ('offered', 'described')):
        raise ValueError('A reviewed user-to-Sofía action is required.')
    return ReviewedFrame(
        user_text=user_text,
        kind='offer' if intent.modality == 'offered' else 'described',
        reviewed=CognitiveMessage(role=CognitiveRole.SYSTEM, content=action_prompt(intent)),
        choices=_OFFER_CHOICES if intent.modality == 'offered' else _GESTURE_CHOICES,
    )


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


def _base_messages(base: CognitiveRequest, frame: ReviewedFrame) -> tuple[CognitiveMessage, CognitiveMessage]:
    """Retain canonical context and exact user text; replace old per-turn prose."""
    if (not isinstance(base, CognitiveRequest) or base.tools
            or len(base.messages) not in (2, 3)
            or base.messages[0].role is not CognitiveRole.SYSTEM
            or base.messages[-1].role is not CognitiveRole.USER
            or base.messages[-1].content != frame.user_text
            or 'AUTHORITATIVE SELF-STATE PROJECTION' not in base.messages[0].content
            or any(message.role is not CognitiveRole.SYSTEM
                   for message in base.messages[1:-1])):
        raise ValueError('Expected a canonical, tool-free synthetic request for the same user text.')
    return base.messages[0], base.messages[-1]


def choice_request(base: CognitiveRequest, frame: ReviewedFrame) -> CognitiveRequest:
    """Separate model decision; no emitted prose is accepted as authority."""
    canonical, user = _base_messages(base, frame)
    if frame.kind in ('blocked', 'real-sensor') or frame.reviewed is None or not frame.choices:
        raise ValueError('This frame cannot request an avatar choice.')
    instruction = (
        'ISOLATED AVATAR RESPONSE CHOICE, NOT AN ACTION OR CONSENT RECORD.\n'
        'The reviewed classification identifies the user turn. For an avatar '
        'offer, choose how Sofía responds to the OFFER in her represented world; '
        'do not mistake the offer for actual physical contact. For a described '
        'gesture, recognition does not establish Sofía\'s consent or sensation. '
        'Use the conversation and actual boundaries, not an automatic yes/no. '
        'A choice never performs a hug, touch, sensor read or animation. '
        'Output ONLY one JSON object with exactly two string keys: choice and reason. '
        'The reason is a brief diagnostic explanation, not a fact about sensations '
        'or invented history. No markdown. Allowed choice values: '
        + ', '.join(frame.choices) + '.'
    )
    return CognitiveRequest(messages=(
        canonical, frame.reviewed,
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=instruction), user,
    ), tools=())


def parse_choice(content: str, frame: ReviewedFrame) -> CandidateChoice:
    """Fail closed on malformed/unsupported choices instead of guessing intent."""
    if not isinstance(content, str) or len(content) > 1500:
        raise ValueError('Invalid decision response.')
    try:
        data = json.loads(content.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError('Decision is not strict JSON.') from exc
    if (not isinstance(data, dict) or set(data) != {'choice', 'reason'}
            or not isinstance(data['choice'], str)
            or data['choice'] not in frame.choices
            or not isinstance(data['reason'], str)
            or not 0 < len(data['reason'].strip()) <= 240
            or any(char in data['reason'] for char in ('\n', '\r', '\x00'))):
        raise ValueError('Decision does not satisfy reviewed choice contract.')
    return CandidateChoice(choice=data['choice'], reason=data['reason'].strip())


def expression_request(base: CognitiveRequest, frame: ReviewedFrame,
                       choice: CandidateChoice | None = None) -> CognitiveRequest:
    """Use the validated CHOICE only, never model-written reasons or emotion claims."""
    canonical, user = _base_messages(base, frame)
    if frame.kind == 'blocked':
        raise ValueError('A stopped interaction must not reach the provider.')
    if frame.kind == 'real-sensor':
        if choice is not None or frame.reviewed is not None:
            raise ValueError('A real-sensor question cannot use an avatar decision.')
        instruction = (
            'ACTUAL-WORLD CAPABILITY QUESTION. Answer using canonical verified '
            'capabilities, not avatar-world fictional contact. Do not invent '
            'sensors, physical sensations, hardware or actions.'
        )
        messages = (canonical, CognitiveMessage(role=CognitiveRole.SYSTEM,
                                               content=instruction), user)
    else:
        if (not isinstance(choice, CandidateChoice) or choice.choice not in frame.choices
                or frame.reviewed is None):
            raise ValueError('A validated in-scope conversational choice is required.')
        payload = json.dumps({'conversational_choice': choice.choice,
                              'actions_executed': False}, ensure_ascii=False)
        instruction = (
            'ISOLATED AVATAR EXPRESSION. The following is a candidate response '
            'CHOICE, not consent, a stored preference, a completed interaction '
            'or a claim of feeling. Speak as Sofía to the user within her '
            'represented avatar world, expressing that choice naturally. '
            'A decline or boundary may be expressed in-character; an acceptance '
            'accepts only the offer. Do not imply touch, real sensing, completed '
            'motion, established history or subjective feeling. An optional '
            'text gesture may fit; no specific gesture or emotion is required. '
            'Do not substitute a generic assistant redirect for the response.\n'
            + payload
        )
        messages = (canonical, frame.reviewed,
                    CognitiveMessage(role=CognitiveRole.SYSTEM, content=instruction), user)
    return CognitiveRequest(messages=messages, tools=())


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
    return PrototypeResult(kind=frame.kind, choice=choice,
                           response=generated.content)
