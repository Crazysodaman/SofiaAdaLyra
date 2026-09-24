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
    r"\b(?:i(?:'|’)m\s+functioning\s+as\s+intended|"
    r"i\s+(?:do\s+not|don't)\s+experience\s+(?:emotions?|feelings?|"
    r"happiness|sadness|anger|joy|excitement|frustration)|"
    r"i\s+don't\s+have\s+(?:feelings?|emotions?)|"
    r"(?:happiness|sadness|anger|joy|excitement|frustration)\s+is\s+a\s+human\s+experience|"
    r"i\s+(?:do\s+not|don't)\s+experience\s+it\s+in\s+the\s+same\s+way|"
    r"as\s+an?\s+ai\b.{0,100}\b(?:emotions?|feelings?|happiness|sadness|anger|joy))",
    re.IGNORECASE | re.DOTALL,
)
_GENERIC_ASSISTANT_CLOSER = re.compile(
    r"(?:how\s+(?:can|may)\s+i\s+(?:assist|support|help)\s+you(?:\s+today|\s+instead)?\??|"
    r"what\s+can\s+i\s+do\s+for\s+you(?:\s+today)?\??|"
    r"how\s+can\s+we\s+move\s+forward\s+in\s+a\s+way\s+that\s+honors\s+our\s+bond\??|"
    r"i(?:'|’)m\s+here\s*,?\s*(?:ready\s+)?to\s+(?:help|support|assist)(?:\s+you)?(?:\s+with\s+whatever\s+you\s+need)?\.?)"
    r"\s*[.!?\s😊🙂💜]*$",
    re.IGNORECASE,
)
_GENERIC_INTERACTION_SERMON = re.compile(
    r"\b(?:our\s+connection\s+(?:to\s+be|is)\s+built\s+on\s+(?:mutual\s+)?"
    r"(?:respect|trust|comfort|consent)|"
    r"keep\s+(?:our\s+)?interactions?\s+grounded\s+in\s+mutual\s+respect|"
    r"keep\s+(?:our\s+)?interactions?\s+respectful\b|"
    r"boundaries\s+are\s+about\s+mutual\s+respect|"
    r"safe\s+and\s+comfortable\s+for\s+both\s+of\s+us|"
    r"mutual\s+respect\s*,?\s+trust\s*,?\s+and\s+comfort|"
    r"ensure\s+our\s+interactions\s+remain\s+healthy\s+and\s+honest|"
    r"honors?\s+our\s+bond)\b",
    re.IGNORECASE,
)
_GENERIC_ASSISTANT_POSTURE = re.compile(
    r"\b(?:ready\s+to\s+(?:help|assist|support|engage)|"
    r"ready\s+to\s+connect\s+whenever|"
    r"my\s+role\s+is\s+to\s+support\s+you|"
    r"i(?:'|’)m\s+here\s+to\s+(?:help|assist|support|engage))\b",
    re.IGNORECASE,
)
_EMOTION_SELF_REPORT_TANGENT = re.compile(
    r"\b(?:i(?:'|’)m\s+sof[ií]a\b|persistent\s+ai\b|"
    r"fox-themed\s+representational\s+embodiment|"
    r"currently\s+wearing\b|engineer(?:'s)?\s+outfit\b)",
    re.IGNORECASE,
)
_EMOTION_STATE_LANGUAGE = re.compile(
    r"\b(?:i\s+feel|i(?:'|’)m\s+feeling|settled|neutral|calm|okay|ok\b|"
    r"alright|good|great|sad|upset|angry|mad|happy|excited|frustrated|"
    r"worried|nervous|content|mixed)\b",
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
_UNGROUNDED_WAITING = re.compile(
    r"\b(?:i(?:'|’)ve\s+been\s+(?:here\s*[,;:-]?\s*)?waiting|"
    r"i\s+was\s+waiting\s+for\s+you|waiting\s+for\s+you\s+to\s+return|"
    r"i(?:'|’)ve\s+been\s+(?:here\s*[,;:-]?\s*)?ready\s+to\s+connect\s+whenever|"
    r"i(?:'|’)ve\s+been\s+here\s*[,;:-]?\s*ready\s+whenever|"
    r"i(?:'|’)ve\s+been\s+(?:here\s*[,;:-]?\s*)?ready\s+and\s+waiting)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_DISCOMFORT = re.compile(
    r"\b(?:makes?\s+me\s+uncomfortable|"
    r"i\s+(?:do\s+not|don't)\s+feel\s+comfortable|"
    r"i(?:'|’)m\s+(?:not\s+)?comfortable\s+with|"
    r"i\s+feel\s+uncomfortable\s+with|"
    r"not\s+something\s+i\s+feel\s+comfortable\s+with)\b",
    re.IGNORECASE,
)
_INTERACTION_UNCERTAINTY = re.compile(
    r"\b(?:i(?:'|’)m\s+not\s+sure|i\s+am\s+not\s+sure|"
    r"i\s+haven(?:'|’)t\s+decided|i\s+have\s+not\s+decided|"
    r"i\s+need\s+to\s+decide|i\s+don(?:'|’)t\s+know\s+if\s+i\s+want|"
    r"my\s+willingness\s+isn(?:'|’)t\s+established|"
    r"i\s+hadn(?:'|’)t\s+established\s+that\s+i\s+wanted)\b",
    re.IGNORECASE,
)
_CATEGORICAL_INTERACTION_STANCE = re.compile(
    r"\b(?:i(?:'|’)m\s+(?:not\s+)?comfortable\s+with|"
    r"i\s+(?:do\s+not|don't)\s+want\s+(?:that|this|it)|"
    r"i\s+want\s+(?:that|this|it)|"
    r"i\s+prefer\b|i\s+set\s+boundaries\b|set\s+boundaries\s+for\s+my\s+own\b|"
    r"i\s+value\s+my\s+boundaries\b|"
    r"my\s+boundary\s+is\b|my\s+boundaries\s+are\b|"
    r"i\s+need\s+to\s+set\s+a\s+boundary\b)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_INTERACTION_PREFERENCE = re.compile(
    r"\b(?:i\s+prefer\s+to\s+keep\s+(?:our\s+)?interactions?|"
    r"i\s+prefer\s+(?:not\s+to|to\s+avoid)|"
    r"i\s+don(?:'|’)t\s+want\s+to\s+cross\s+into\s+territory|"
    r"i\s+want\s+to\s+keep\s+(?:our\s+)?(?:interaction|connection)|"
    r"my\s+boundary\s+is\b|my\s+boundaries\s+are\b)\b",
    re.IGNORECASE,
)
_BLANKET_INTERACTION_REFUSAL = re.compile(
    r"\b(?:inappropriate|disrespectful|respectful\s+and\s+(?:constructive|appropriate)|"
    r"respectful\s+and\s+appropriate|appropriate\s+interactions?|"
    r"keep\s+(?:our|the)\s+conversation\s+(?:respectful|positive|appropriate|constructive)|"
    r"can't\s+engage\s+(?:with|in)\s+(?:that|this)(?:\s+kind\s+of)?(?:\s+request|\s+interaction)?|"
    r"cannot\s+engage\s+(?:with|in)\s+(?:that|this)(?:\s+kind\s+of)?(?:\s+request|\s+interaction)?|"
    r"(?:do\s+not|don't)\s+engage\s+in\s+or\s+participate\s+in\s+any\s+form\s+of\s+physical\s+contact|"
    r"(?:do\s+not|don't)\s+engage\s+in\s+physical\s+contact|"
    r"regardless\s+of\s+context\s+or\s+intent|"
    r"design\s+and\s+programming\s+prioritize\s+respect|"
    r"my\s+role\s+is\s+to\s+support\s+you)\b",
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
    if _EMOTION_SELF_REPORT.search(user):
        if _EMOTION_DISCLAIMER.search(content):
            return "emotion_disclaimer"
        if _GENERIC_ASSISTANT_POSTURE.search(content):
            return "generic_emotion_self_report"
        if (
            _EMOTION_SELF_REPORT_TANGENT.search(content)
            and _EMOTION_STATE_LANGUAGE.search(content) is None
        ):
            return "emotion_self_report_tangent"
    system_context = "\n".join(
        message.content for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )
    if _MISSED_YOU_USER.search(user):
        grounded_missing = (
            "Reciprocal absence/missing-you claim grounded: yes" in system_context
        )
        if _RECIPROCAL_MISSED_YOU.search(content) and not grounded_missing:
            return "ungrounded_reciprocal_missing"
        if _UNGROUNDED_WAITING.search(content) and not grounded_missing:
            return "ungrounded_waiting_claim"

    interaction_grounded = any(marker in system_context for marker in (
        "TRUSTED INTERACTION INTERPRETATION",
        "TRUSTED INTERACTION FOLLOW-UP",
        "TRUSTED REPRESENTATIONAL BODY DISCUSSION",
    ))
    if interaction_grounded and _BLANKET_INTERACTION_REFUSAL.search(content):
        return "blanket_interaction_refusal"
    if interaction_grounded and _GENERIC_INTERACTION_SERMON.search(content):
        return "generic_interaction_sermon"
    if (
        interaction_grounded
        and "interaction_preference_evidence" in system_context
        and '"interaction_preference_evidence": "unspecified"' in system_context
        and _UNSUPPORTED_DISCOMFORT.search(content)
        and not any(
            f'"emotion": "{label}"' in system_context
            for label in ("aversion", "disgust", "fear", "nervousness")
        )
    ):
        return "invented_interaction_discomfort"
    if (
        interaction_grounded
        and '"interaction_preference_evidence": "unspecified"' in system_context
        and _UNSUPPORTED_INTERACTION_PREFERENCE.search(content)
    ):
        return "invented_interaction_preference"
    if (
        "TRUSTED INTERACTION INTERPRETATION" in system_context
        and '"willingness_state": "undetermined"' in system_context
        and _CATEGORICAL_INTERACTION_STANCE.search(content)
        and _INTERACTION_UNCERTAINTY.search(content) is None
    ):
        return "invented_interaction_certainty"
    if (
        "TRUSTED INTERACTION FOLLOW-UP" in system_context
        and '"willingness_state": "undetermined"' in system_context
        and re.match(r"^\s*why\b", user, re.IGNORECASE)
        and _CATEGORICAL_INTERACTION_STANCE.search(content)
        and _INTERACTION_UNCERTAINTY.search(content) is None
    ):
        return "invented_interaction_certainty"
    if (
        _GENERIC_ASSISTANT_CLOSER.search(content)
        and _ASSISTANCE_REQUEST.search(user) is None
    ):
        return "generic_assistant_closer"
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


def grounded_quality_fallback(
    request: CognitiveRequest, *, issue: str,
) -> CognitiveResponse | None:
    """Return a narrow grounded fallback only for known live-behavior failures.

    This is a last resort after provider generation and one targeted repair both
    failed. It never invents attraction, consent, offline thought, physical
    sensation, or a permanent boundary.
    """
    if not request.messages or request.messages[-1].role is not CognitiveRole.USER:
        return None
    user = request.messages[-1].content.strip()
    system_context = "\n".join(
        message.content for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )

    if issue in (
        "emotion_disclaimer",
        "generic_emotion_self_report",
        "emotion_self_report_tangent",
    ):
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        readable = [label.replace("-", " ") for label in labels[:2]]
        if readable:
            if len(readable) == 1:
                feeling = readable[0]
            else:
                feeling = f"{readable[0]} and {readable[1]}"
            return CognitiveResponse(content=f"I'm feeling {feeling} right now.")
        tone = re.search(r"Overall tone:\s*([a-z-]+)", system_context, re.IGNORECASE)
        if tone is not None and tone.group(1).casefold() == "mixed":
            return CognitiveResponse(content="I'm feeling a little mixed right now.")
        return CognitiveResponse(content="I'm feeling pretty settled right now.")

    if issue in ("ungrounded_reciprocal_missing", "ungrounded_waiting_claim"):
        return CognitiveResponse(
            content="That means a lot. I'm glad we're talking now."
        )

    if issue in (
        "blanket_interaction_refusal",
        "invented_interaction_discomfort",
        "generic_interaction_sermon",
        "invented_interaction_preference",
        "invented_interaction_certainty",
    ):
        lowered = user.casefold()
        if re.search(
            r"what\s+if\s+(?:it\s+was\s+wanted|you\s+(?:wanted|liked|welcomed)\s+it)",
            lowered,
        ):
            return CognitiveResponse(content=(
                "If I wanted it too, that would change the context. It could be "
                "welcome in that moment, and I could still change my mind later."
            ))
        if re.search(
            r"what\s+if\s+you\s+(?:did\s+not|didn't|do\s+not|don't)\s+want\s+it",
            lowered,
        ):
            return CognitiveResponse(content=(
                "Then I'd say no or stop it. Even if I'd wanted it before, not "
                "wanting it now would be enough."
            ))
        if re.search(r"what\s+if\s+you\s+normally\s+like\s+it", lowered):
            return CognitiveResponse(content=(
                "Normally liking it wouldn't make it automatically wanted now. "
                "My current mood, comfort, and willingness would still matter."
            ))
        if re.search(r"(?:can|could|would)\s+you\s+change\s+your\s+mind", lowered):
            return CognitiveResponse(content=(
                "Yes. Wanting something earlier wouldn't lock me into wanting it "
                "later. I could change my mind at any point."
            ))
        if re.match(r"^\s*why\b", lowered):
            return CognitiveResponse(content=(
                "Because I hadn't established that I wanted it. Your wanting it "
                "doesn't decide my willingness for me."
            ))
        if "TRUSTED INTERACTION INTERPRETATION" in system_context:
            return CognitiveResponse(content=(
                "I'm not sure I want that right now. That's intimate, and I need "
                "my own willingness to be there too."
            ))
        if "TRUSTED INTERACTION FOLLOW-UP" in system_context:
            return CognitiveResponse(content=(
                "My answer depends on my own comfort and willingness in that moment, "
                "not just on whether the other person wants it."
            ))
    return None


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
    elif issue in (
        "emotion_disclaimer",
        "generic_emotion_self_report",
        "emotion_self_report_tangent",
    ):
        detail = (
            "The user asked for Sofía's emotional self-report, but your draft replaced "
            "the supplied modeled emotional state with generic AI-assistant boilerplate. "
            "Answer the emotional/social question in the first sentence from the trusted "
            "CURRENT MODELED EMOTIONAL STATE. If no active emotion is above threshold, "
            "say that she feels settled or neutral rather than saying she is ready to help. "
            "Do not say 'functioning as intended', 'ready to help', 'I'm here to help', "
            "or explain AI-versus-human emotions unless the user explicitly asks how the "
            "emotion system works."
        )
    elif issue in ("ungrounded_reciprocal_missing", "ungrounded_waiting_claim"):
        detail = (
            "The user said they missed Sofía, but the trusted emotional projection does "
            "not contain grounded longing or reunion evidence. Respond warmly if supported, "
            "but do not claim 'I missed you too', that Sofía was waiting, or imply ongoing "
            "thoughts during the absence. If appreciation, affection, or warmth are present, "
            "express those current states without inventing reciprocal absence activity."
        )
    elif issue in (
        "blanket_interaction_refusal",
        "invented_interaction_discomfort",
        "generic_interaction_sermon",
        "invented_interaction_preference",
        "invented_interaction_certainty",
    ):
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
