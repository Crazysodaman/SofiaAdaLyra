"""Detect near-verbatim reuse of an earlier assistant reply in tool-free chat.

This module never changes the saved conversation, evaluates consent, filters
user input, or decides what a character should feel. It only permits one
provider-side rephrase attempt when a newly generated draft closely copies a
recent assistant answer. The original reply remains available as a fallback.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
)

_EXPLICIT_REPEAT = re.compile(
    r"\b(?:repeat|again|verbatim|quote|copy|recite|reproduce|exact(?:ly)?)\b",
    re.IGNORECASE,
)
_MIN_COMPARISON_CHARS = 120
_MIN_SIMILARITY = 0.88


def _normalized(text: str) -> str:
    return ' '.join(re.findall(r'\w+', text.casefold()))


def is_near_duplicate_reply(request: CognitiveRequest, response: CognitiveResponse) -> bool:
    """Only compare a long, tool-free draft to recent assistant-only prose.

    An explicit request to repeat or quote is never rewritten. Tool requests,
    tool results, missing user turns, and tool-call responses are excluded.
    """
    if (request.tools or response.tool_calls or not request.messages
            or request.messages[-1].role is not CognitiveRole.USER
            or _EXPLICIT_REPEAT.search(request.messages[-1].content)
            or any(message.role is CognitiveRole.TOOL or message.tool_calls
                   for message in request.messages)):
        return False
    draft = _normalized(response.content)
    if len(draft) < _MIN_COMPARISON_CHARS:
        return False
    previous = (
        message for message in reversed(request.messages[:-1])
        if message.role is CognitiveRole.ASSISTANT
    )
    for i, message in enumerate(previous):
        if i >= 8:
            break
        past = _normalized(message.content)
        if (len(past) >= _MIN_COMPARISON_CHARS
                and SequenceMatcher(None, draft, past, autojunk=False).ratio()
                >= _MIN_SIMILARITY):
            return True
    return False


def build_rephrase_request(request: CognitiveRequest) -> CognitiveRequest:
    """One ephemeral system correction before the original, unchanged user turn."""
    if not request.messages or request.messages[-1].role is not CognitiveRole.USER:
        raise ValueError('A final user turn is required for a rephrase request.')
    instruction = CognitiveMessage(
        role=CognitiveRole.SYSTEM,
        content=(
            'RESPONSE QUALITY RETRY (trusted provider-side duplicate check): '
            'Your draft closely reused an earlier assistant reply. Address the '
            'latest user message on its own terms with a distinct, concise '
            'response. Do not copy prior phrasing, force a follow-up question, '
            'invent prior preferences or experiences, or imply unobserved '
            'physical sensations or executed actions. Preserve all existing '
            'interaction boundaries and factual grounding.'
        ),
    )
    return CognitiveRequest(
        messages=(*request.messages[:-1], instruction, request.messages[-1]),
        tools=request.tools,
    )
