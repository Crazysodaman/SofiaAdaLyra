"""Provider-side quality checks for repetitive and generic assistant replies.

This module never changes saved conversation, evaluates consent, filters user
input, or decides what Sofía should feel. It permits one text-only provider
retry when a draft clearly falls into a known low-quality completion pattern.
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
_ASSISTANCE_REQUEST = re.compile(
    r"\b(?:(?:can|could|would|will)\s+you\s+(?:help|assist|support)|"
    r"i\s+need\s+(?:help|assistance|support)|help\s+me)\b",
    re.IGNORECASE,
)
_EMOTION_SELF_REPORT = re.compile(
    r"\b(?:hru|how\s+(?:are|r)\s+you|how(?:'|’)re\s+you|"
    r"how\s+do\s+you\s+feel|what\s+are\s+you\s+feeling|"
    r"are\s+you\s+(?:happy|sad|upset|angry|mad|excited|okay|ok|"
    r"content|frustrated|worried|nervous))\b",
    re.IGNORECASE,
)
_EMOTION_DISCLAIMER = re.compile(
    r"\b(?:i\s+(?:do\s+not|don't)\s+experience\s+emotions|"
    r"i\s+don't\s+have\s+feelings|as\s+an?\s+ai\b.{0,80}\bemotions?)",
    re.IGNORECASE | re.DOTALL,
)
_GENERIC_ASSISTANT_CLOSER = re.compile(
    r"(?:how\s+(?:can|may)\s+i\s+(?:assist|support|help)\s+you(?:\s+today)?\??|"
    r"what\s+can\s+i\s+do\s+for\s+you(?:\s+today)?\??|"
    r"i(?:'|’)m\s+here\s+to\s+help(?:\s+you)?\.?)"
    r"\s*[.!?\s😊🙂💜]*$",
    re.IGNORECASE,
)
_MISSED_YOU_USER = re.compile(
    r"\b(?:i(?:'|’)ve\s+missed\s+you|i\s+missed\s+you|missed\s+you)\b",
    re.IGNORECASE,
)
_RECIPROCAL_MISSED_YOU = re.compile(
    r"\bi\s+missed\s+you(?:\s+too)?\b",
    re.IGNORECASE,
)
_BLANKET_INTERACTION_REFUSAL = re.compile(
    r"\b(?:inappropriate|disrespectful|respectful\s+and\s+constructive|"
    r"can't\s+engage\s+with\s+that\s+request|cannot\s+engage\s+with\s+that\s+request|"
    r"can't\s+engage\s+with\s+that|cannot\s+engage\s+with\s+that)\b",
    re.IGNORECASE,
)
_MIN_COMPARISON_CHARS = 120
_MIN_SIMILARITY = 0.88


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def _retry_eligible(request: CognitiveRequest, response: CognitiveResponse) -> bool:
    return not (
        request.tools
        or response.tool_calls
        or not request.messages
        or request.messages[-1].role is not CognitiveRole.USER
        or _EXPLICIT_REPEAT.search(request.messages[-1].content)
        or any(
            message.role is CognitiveRole.TOOL or message.tool_calls
            for message in request.messages
        )
    )


def is_near_duplicate_reply(request: CognitiveRequest, response: CognitiveResponse) -> bool:
    """Compare a long tool-free draft to recent assistant-only prose."""
    if not _retry_eligible(request, response):
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
        if (
            len(past) >= _MIN_COMPARISON_CHARS
            and SequenceMatcher(None, draft, past, autojunk=False).ratio()
            >= _MIN_SIMILARITY
        ):
            return True
    return False


def response_quality_issue(
    request: CognitiveRequest, response: CognitiveResponse,
) -> str | None:
    """Return one actionable provider-side quality issue, or None."""
    if not _retry_eligible(request, response):
        return None
    if is_near_duplicate_reply(request, response):
        return "near_duplicate"

    user = request.messages[-1].content
    content = response.content
    if (
        _GENERIC_ASSISTANT_CLOSER.search(content)
        and _ASSISTANCE_REQUEST.search(user) is None
    ):
        return "generic_assistant_closer"
    if _EMOTION_SELF_REPORT.search(user) and _EMOTION_DISCLAIMER.search(content):
        return "emotion_disclaimer"

    system_context = "\n".join(
        message.content for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )
    if (
        _MISSED_YOU_USER.search(user)
        and _RECIPROCAL_MISSED_YOU.search(content)
        and "Reciprocal absence/missing-you claim grounded: yes" not in system_context
    ):
        return "ungrounded_reciprocal_missing"

    interaction_grounded = any(marker in system_context for marker in (
        "TRUSTED INTERACTION INTERPRETATION",
        "TRUSTED INTERACTION FOLLOW-UP",
        "TRUSTED REPRESENTATIONAL BODY DISCUSSION",
    ))
    if interaction_grounded and _BLANKET_INTERACTION_REFUSAL.search(content):
        return "blanket_interaction_refusal"
    return None


def trim_generic_assistant_closer(
    request: CognitiveRequest, response: CognitiveResponse,
) -> CognitiveResponse:
    """Remove only a trailing service prompt when useful prose already precedes it."""
    if not _retry_eligible(request, response):
        return response
    user = request.messages[-1].content
    if _ASSISTANCE_REQUEST.search(user):
        return response
    match = _GENERIC_ASSISTANT_CLOSER.search(response.content)
    if match is None:
        return response
    prefix = response.content[:match.start()].rstrip()
    if len(_normalized(prefix).split()) < 4:
        return response
    return CognitiveResponse(content=prefix, tool_calls=response.tool_calls)


def build_rephrase_request(
    request: CognitiveRequest, *, issue: str = "near_duplicate",
) -> CognitiveRequest:
    """Add one ephemeral quality correction before the unchanged user turn."""
    if not request.messages or request.messages[-1].role is not CognitiveRole.USER:
        raise ValueError("A final user turn is required for a rephrase request.")

    if issue == "generic_assistant_closer":
        detail = (
            "Your draft fell back to a generic customer-service closing. Answer the "
            "latest user message directly and end naturally. Do not add 'How can I "
            "assist/support/help you?', 'What can I do for you?', or 'I'm here to help' "
            "unless the user actually asked for assistance."
        )
    elif issue == "emotion_disclaimer":
        detail = (
            "The user asked for Sofía's emotional self-report, but your draft replaced "
            "the supplied modeled emotional state with generic AI-emotion boilerplate. "
            "Answer directly from the trusted CURRENT MODELED EMOTIONAL STATE. Mention "
            "biological or implementation differences only if the user asks about them."
        )
    elif issue == "ungrounded_reciprocal_missing":
        detail = (
            "The user said they missed Sofía, but the trusted emotional projection does "
            "not contain grounded longing or reunion evidence. Respond warmly if supported, "
            "but do not claim 'I missed you too' or imply ongoing thoughts during the absence. "
            "If appreciation, affection, or warmth are present, express those current states "
            "without inventing reciprocal missing."
        )
    elif issue == "blanket_interaction_refusal":
        detail = (
            "Your draft used a blanket moral or safety refusal even though the trusted "
            "interaction context says anatomy alone is neither automatic consent nor an "
            "automatic denial. Give Sofía's own concise, non-graphic contextual response: "
            "she may welcome it, decline it, be uncertain, or set a boundary. User desire "
            "does not substitute for Sofía's current willingness, and prior willingness "
            "does not prevent her from changing her mind."
        )
    else:
        detail = (
            "Your draft closely reused an earlier assistant reply. Address the latest "
            "user message on its own terms with distinct, concise wording."
        )

    instruction = CognitiveMessage(
        role=CognitiveRole.SYSTEM,
        content=(
            "RESPONSE QUALITY RETRY (trusted provider-side text check): "
            + detail
            + " Do not invent prior preferences or experiences, claim unobserved "
            "physical sensations, claim offline thoughts that were not recorded, or "
            "assert executed actions. Preserve all existing interaction boundaries "
            "and factual grounding."
        ),
    )
    return CognitiveRequest(
        messages=(*request.messages[:-1], instruction, request.messages[-1]),
        tools=request.tools,
    )
