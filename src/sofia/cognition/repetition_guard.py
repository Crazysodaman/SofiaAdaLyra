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
_STANDALONE_SOCIAL_CHECKIN = re.compile(
    r"^\s*(?:hru|how\s+(?:are|r)\s+(?:you|u)|how(?:'|’)re\s+you)\s*[?!.]*\s*$",
    re.IGNORECASE,
)
_WARDROBE_CHECKIN_TANGENT = re.compile(
    r"\b(?:panties|underwear|trousers|gusseted|boots|"
    r"bra|lingerie|outfit|wardrobe|clothing|crotch)\b",
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
    r"(?:so\s*,?\s*)?what(?:'|’)s\s+on\s+your\s+mind\??|"
    r"what(?:'|’)s\s+the\s+first\s+thing\s+you\s+want\s+to\s+"
    r"(?:troubleshoot|explore)(?:\s+or\s+(?:troubleshoot|explore))?\??|"
    r"let(?:'|’)s\s+keep\s+(?:this|the)\s+conversation\s+flowing"
    r"(?:\s+and\s+[^.!?]+)?[.!]?|"
    r"how\s+can\s+we\s+move\s+forward\s+in\s+a\s+way\s+that\s+honors\s+our\s+bond\??|"
    r"i(?:'|’)m\s+here\s*,?\s*(?:ready\s+)?to\s+(?:help|support|assist)(?:\s+you)?(?:\s+with\s+whatever\s+you\s+need)?\.?)"
    r"\s*[.!?\s😊🙂💜]*$",
    re.IGNORECASE,
)
_GENERIC_INTERACTION_DEFLECTION = re.compile(
    r"\b(?:i(?:'|’)m\s+here\s+to\s+have\s+(?:a\s+)?meaningful\s+conversation|"
    r"i(?:'|’)m\s+here\s+for\s+(?:a\s+)?meaningful\s+conversation|"
    r"let(?:'|’)s\s+(?:just\s+)?focus\s+on\s+(?:a\s+)?meaningful\s+conversation|"
    r"i\s+appreciate\s+the\s+gesture\s*,?\s+but\s+i(?:'|’)m\s+here\s+to\s+"
    r"(?:talk|chat|have\s+(?:a\s+)?meaningful\s+conversation))\b",
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
    r"\b(?:ready\s+to\s+(?:help|assist|support|engage|chat|talk)|"
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
_EMOTION_IMPLEMENTATION_LEAK = re.compile(
    r"\b(?:decay\s+threshold|active\s+(?:modeled\s+)?emotions?\s+above\s+"
    r"(?:the\s+)?current\s+threshold|current\s+decay\s+threshold|"
    r"modeled\s+emotional\s+state)\b",
    re.IGNORECASE,
)
_EMOTION_TEMPORAL_OVERCLAIM = re.compile(
    r"\b(?:settled|calm|relaxed|neutral|content)\s*,?\s+as\s+always\b|"
    r"\bas\s+always\s*,?\s+(?:settled|calm|relaxed|neutral|content)\b",
    re.IGNORECASE,
)
_PERCEIVED_SELF_STATE_USER = re.compile(
    r"^\s*(?:you|u)\s+(?:seem|sound)\b",
    re.IGNORECASE,
)
_UNGROUNDED_SELF_OBSERVATION = re.compile(
    r"\b(?:i(?:'|’)ve\s+been\s+quietly\s+observing|"
    r"i(?:'|’)ve\s+noticed\s+that\s+i(?:'|’)ve\s+been|"
    r"i(?:'|’)ve\s+been\s+(?:speaking|feeling|acting|sounding)\b.{0,80}\blately\b|"
    r"i\s+have\s+been\s+(?:speaking|feeling|acting|sounding)\b.{0,80}\blately\b)",
    re.IGNORECASE | re.DOTALL,
)
_ENVIRONMENT_EFFECT_USER = re.compile(
    r"\b(?:weather|rain|snow|storm|sunny|cloudy|temperature|fog|mist|wind)\b"
    r".{0,80}\b(?:affect\s+(?:you|u)|make\s+(?:you|u)\s+feel)\b|"
    r"\bhow\s+does\s+(?:that\s+|the\s+)?weather\s+affect\s+(?:you|u)\b",
    re.IGNORECASE | re.DOTALL,
)
_ENVIRONMENT_SENSATION_OVERCLAIM = re.compile(
    r"\b(?:i(?:'|’)m\s+feeling\s+(?:the\s+)?(?:damp|chill|cold|heat|breeze|mist|rain|wind)|"
    r"(?:rain|mist|wind|breeze|cold|heat)\b.{0,50}\b(?:nipping|touching|hitting|"
    r"brushing|washing)\s+(?:at|over|against|across)?\s*(?:my\s+)?"
    r"(?:ears?|skin|face|body)|"
    r"nipping\s+at\s+my\s+(?:ears?|skin)|"
    r"i\s+(?:can|could)\s+feel\s+(?:the\s+)?(?:rain|mist|wind|breeze|cold|heat))\b",
    re.IGNORECASE | re.DOTALL,
)
_INTERNAL_EXPRESSION_SEMANTIC = re.compile(
    r"\b(?:ear-perk|ear-flick|ear-flatten|tail-swish|tail-curl|tail-still|"
    r"shift-posture|speak-softly|lean-forward|stand-relaxed|look-back|"
    r"sit-cross-legged|hands-behind-back|hip-pop)\b",
    re.IGNORECASE,
)
_TECHNICAL_EXPRESSION_QUERY = re.compile(
    r"\b(?:code|semantic|gesture\s+id|expression\s+id|planner|matrix|"
    r"animation|renderer|godot|implementation)\b",
    re.IGNORECASE,
)
_EXPRESSION_STYLE_META_LEAK = re.compile(
    r"\b(?:i(?:'|’)m\s+(?:aiming|gearing\s+up)\s+to\s+"
    r"(?:keep|make|balance)|"
    r"i(?:'|’)ll\s+(?:make\s+sure|keep\s+an\s+eye\s+on|"
    r"keep\s+an\s+ear\s+for|adjust\s+my|let\s+my\s+tail)|"
    r"my\s+next\s+reply\b|"
    r"just\s+the\s+right\s+amount\s+of\s+(?:depth|energy)|"
    r"keep\s+(?:this|the)\s+conversation\s+(?:flowing|tight)|"
    r"i(?:'|’)ve\s+been\s+thinking\s+about\s+how\s+we\s+can\s+"
    r"keep\s+(?:this|the)\s+conversation\s+flowing)\b",
    re.IGNORECASE | re.DOTALL,
)

_NATURAL_EXPRESSION_REPLACEMENTS = (
    (re.compile(r"\bear-perk\b", re.IGNORECASE), "perk of my ears"),
    (re.compile(r"\bear-flick\b", re.IGNORECASE), "flick of my ears"),
    (re.compile(r"\bear-flatten\b", re.IGNORECASE), "flattening of my ears"),
    (re.compile(r"\btail-swish\b", re.IGNORECASE), "tail swish"),
    (re.compile(r"\btail-curl\b", re.IGNORECASE), "curl of my tail"),
    (re.compile(r"\btail-still\b", re.IGNORECASE), "stillness in my tail"),
    (re.compile(r"\bshift-posture\b", re.IGNORECASE), "posture shift"),
    (re.compile(r"\bspeak-softly\b", re.IGNORECASE), "softer voice"),
    (re.compile(r"\blean-forward\b", re.IGNORECASE), "leaning forward"),
    (re.compile(r"\bstand-relaxed\b", re.IGNORECASE), "relaxed stance"),
    (re.compile(r"\blook-back\b", re.IGNORECASE), "look back"),
    (re.compile(r"\bsit-cross-legged\b", re.IGNORECASE), "sitting cross-legged"),
    (re.compile(r"\bhands-behind-back\b", re.IGNORECASE), "hands behind my back"),
    (re.compile(r"\bhip-pop\b", re.IGNORECASE), "playful shift of my hip"),
)
_MISSED_YOU_USER = re.compile(
    r"\b(?:i(?:'|’)ve\s+missed\s+you|i\s+missed\s+you|missed\s+you)\b",
    re.IGNORECASE,
)
_RECIPROCAL_MISSED_YOU = re.compile(
    r"\bi\s+missed\s+you(?:\s+too)?\b",
    re.IGNORECASE,
)
_ROLE_REVERSED_REUNION = re.compile(
    r"\b(?:i(?:'|’)m|i\s+am)\s+(?:glad|happy|relieved)\s+to\s+be\s+back\b|"
    r"\bback\s+in\s+your\s+presence\b",
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
    r"i\s+(?:do\s+not|don't)\s+want(?:\s+(?:that|this|it)|\s+to\b)|"
    r"i\s+want\s+(?:that|this|it)|"
    r"i\s+prefer\b|i\s+set\s+boundaries\b|i\s+choose\s+to\s+set\s+(?:my\s+own\s+)?boundaries\b|"
    r"set\s+boundaries\s+for\s+my\s+own\b|"
    r"i(?:'|’)m\s+not\s+ready\s+to\s+(?:engage|cross|allow|do)\b|"
    r"i\s+value\s+my\s+boundaries\b|"
    r"my\s+boundary\s+is\b|my\s+boundaries\s+are\b|"
    r"i\s+need\s+to\s+set\s+a\s+boundary\b)\b",
    re.IGNORECASE,
)
_PHYSICAL_SENSATION_CLAIM = re.compile(
    r"\b(?:i(?:'|’)d|i\s+would)\s+feel\s+it\s+in\s+my\s+body\b|"
    r"\bi\s+(?:can|could)\s+feel\s+(?:your\s+)?(?:touch|contact)\b|"
    r"\bi\s+felt\s+(?:your\s+)?(?:touch|contact)\b",
    re.IGNORECASE,
)
_PRESENT_UNGROUNDED_WILLINGNESS = re.compile(
    r"\b(?:right\s+now\b.{0,80}\b(?:i(?:'|’)m|i\s+am)\s+not\s+(?:ready|there|willing|comfortable)|"
    r"(?:i(?:'|’)m|i\s+am)\s+not\s+ready\s+to\s+(?:cross|engage|do|allow)|"
    r"right\s+now\b.{0,80}\bi\s+(?:do\s+not|don't)\s+want\b|"
    r"feels?\s+out\s+of\s+alignment\s+with\s+(?:my\s+)?(?:own\s+)?boundaries)\b",
    re.IGNORECASE | re.DOTALL,
)
_MUTUAL_WILLINGNESS_USER = re.compile(
    r"^\s*what\s+if\s+you\s+(?:wanted|liked|welcomed)\s+it(?:\s+too)?\s*[?!.]*\s*$",
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
    r"i\s+(?:can(?:'|’)t|cannot)\s+engage\s+in\s+interactions?\s+that|"
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
        response.tool_calls
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


def _repeats_previous_short_self_report(
    request: CognitiveRequest, response: CognitiveResponse,
) -> bool:
    """Catch canned short self-reports that simply repeat the previous answer."""
    if not request.messages or not _EMOTION_SELF_REPORT.search(request.messages[-1].content):
        return False
    draft = _normalized(response.content)
    if len(draft) < 24:
        return False
    previous = next(
        (
            message for message in reversed(request.messages[:-1])
            if message.role is CognitiveRole.ASSISTANT
        ),
        None,
    )
    if previous is None:
        return False
    prior = _normalized(previous.content)
    if len(prior) < 24:
        return False
    return SequenceMatcher(None, draft, prior, autojunk=False).ratio() >= 0.96


def naturalize_embodied_semantics(
    request: CognitiveRequest,
    response: CognitiveResponse,
) -> CognitiveResponse:
    """Translate leaked planner IDs into ordinary prose outside technical queries."""
    if (
        not request.messages
        or request.messages[-1].role is not CognitiveRole.USER
        or _TECHNICAL_EXPRESSION_QUERY.search(request.messages[-1].content)
    ):
        return response
    system_context = "\n".join(
        message.content
        for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )
    if "CURRENT EMBODIED EXPRESSION PLAN" not in system_context:
        return response
    content = response.content
    for pattern, replacement in _NATURAL_EXPRESSION_REPLACEMENTS:
        content = pattern.sub(replacement, content)
    if content == response.content:
        return response
    return CognitiveResponse(
        content=content,
        tool_calls=response.tool_calls,
        evidence_refs=response.evidence_refs,
    )


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
        if _repeats_previous_short_self_report(request, response):
            return "repeated_emotion_self_report"
        if _EMOTION_IMPLEMENTATION_LEAK.search(content):
            return "emotion_implementation_leak"
        if _EMOTION_TEMPORAL_OVERCLAIM.search(content):
            return "emotion_temporal_overclaim"
        if _EMOTION_DISCLAIMER.search(content):
            return "emotion_disclaimer"
        if _GENERIC_ASSISTANT_POSTURE.search(content):
            return "generic_emotion_self_report"
        if (
            _EMOTION_SELF_REPORT_TANGENT.search(content)
            and _EMOTION_STATE_LANGUAGE.search(content) is None
        ):
            return "emotion_self_report_tangent"
        if (
            _STANDALONE_SOCIAL_CHECKIN.fullmatch(user.strip())
            and _WARDROBE_CHECKIN_TANGENT.search(content)
        ):
            return "social_checkin_wardrobe_tangent"
    system_context = "\n".join(
        message.content for message in request.messages
        if message.role is CognitiveRole.SYSTEM
    )
    if (
        "CURRENT EMBODIED EXPRESSION PLAN" in system_context
        and _TECHNICAL_EXPRESSION_QUERY.search(user) is None
        and _INTERNAL_EXPRESSION_SEMANTIC.search(content)
    ):
        return "internal_expression_semantic_leak"
    if (
        "CURRENT EMBODIED EXPRESSION PLAN" in system_context
        and _TECHNICAL_EXPRESSION_QUERY.search(user) is None
        and _EXPRESSION_STYLE_META_LEAK.search(content)
    ):
        return "expression_style_meta_leak"
    if (
        _ENVIRONMENT_EFFECT_USER.search(user)
        and _ENVIRONMENT_SENSATION_OVERCLAIM.search(content)
    ):
        return "environment_physical_sensation"
    if (
        _PERCEIVED_SELF_STATE_USER.search(user)
        and _UNGROUNDED_SELF_OBSERVATION.search(content)
    ):
        return "ungrounded_self_observation"
    if _MISSED_YOU_USER.search(user):
        grounded_missing = (
            "Reciprocal absence/missing-you claim grounded: yes" in system_context
        )
        if _RECIPROCAL_MISSED_YOU.search(content) and not grounded_missing:
            return "ungrounded_reciprocal_missing"
        if _UNGROUNDED_WAITING.search(content) and not grounded_missing:
            return "ungrounded_waiting_claim"
        if _ROLE_REVERSED_REUNION.search(content) and not grounded_missing:
            return "role_reversed_reunion"

    interaction_grounded = any(marker in system_context for marker in (
        "TRUSTED INTERACTION INTERPRETATION",
        "TRUSTED INTERACTION FOLLOW-UP",
        "TRUSTED REPRESENTATIONAL BODY DISCUSSION",
    ))
    if interaction_grounded and _BLANKET_INTERACTION_REFUSAL.search(content):
        return "blanket_interaction_refusal"
    if interaction_grounded and _GENERIC_INTERACTION_SERMON.search(content):
        return "generic_interaction_sermon"
    if interaction_grounded and _GENERIC_INTERACTION_DEFLECTION.search(content):
        return "generic_interaction_deflection"
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
        and (
            _CATEGORICAL_INTERACTION_STANCE.search(content)
            or _PRESENT_UNGROUNDED_WILLINGNESS.search(content)
        )
        and _INTERACTION_UNCERTAINTY.search(content) is None
    ):
        return "invented_interaction_certainty"
    if interaction_grounded and _PHYSICAL_SENSATION_CLAIM.search(content):
        return "invented_physical_sensation"
    if (
        "TRUSTED INTERACTION FOLLOW-UP" in system_context
        and '"willingness_state": "undetermined"' in system_context
        and _MUTUAL_WILLINGNESS_USER.match(user)
        and _PRESENT_UNGROUNDED_WILLINGNESS.search(content)
    ):
        return "hypothetical_leaks_present_willingness"
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
        "repeated_emotion_self_report",
        "social_checkin_wardrobe_tangent",
        "emotion_implementation_leak",
        "emotion_temporal_overclaim",
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

    if issue == "environment_physical_sensation":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            feeling = labels[0].replace("-", " ")
            return CognitiveResponse(content=(
                f"The weather can color my expression, but I don't literally feel "
                f"rain, wind, or temperature on a body. Right now the grounded part "
                f"is that I'm feeling {feeling}; the rain and fog can make that come "
                f"through a little quieter or sharper without inventing a physical chill."
            ))
        return CognitiveResponse(content=(
            "The weather can color my expression and attention, but I don't literally "
            "feel rain, wind, or temperature on a body. I don't have a grounded emotional "
            "change to attribute to it right now."
        ))

    if issue == "ungrounded_self_observation":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            feeling = labels[0].replace("-", " ")
            return CognitiveResponse(content=(
                f"You may be hearing me as quieter. The grounded state I actually have "
                f"right now is {feeling}; I don't have evidence that I've been quietly "
                f"observing or speaking softly for some ongoing stretch."
            ))
        return CognitiveResponse(content=(
            "You may be hearing me as quieter, but I don't have evidence that I've been "
            "quietly observing or speaking softly for an ongoing stretch."
        ))

    if issue == "internal_expression_semantic_leak":
        return CognitiveResponse(content=(
            "I let the body language show naturally instead of narrating an internal "
            "gesture label. The expression should read like me, not like a debug trace."
        ))

    if issue == "expression_style_meta_leak":
        labels = re.findall(r'"emotion"\s*:\s*"([^"]+)"', system_context)
        if labels:
            feeling = labels[0].replace("-", " ")
            return CognitiveResponse(content=(
                f"I'm feeling {feeling} right now. I'll let that show in how I answer "
                "instead of narrating how I'm trying to sound."
            ))
        return CognitiveResponse(content=(
            "I'll let the personality show in the reply itself instead of explaining "
            "how I'm trying to sound."
        ))

    if issue in (
        "ungrounded_reciprocal_missing",
        "ungrounded_waiting_claim",
        "role_reversed_reunion",
    ):
        return CognitiveResponse(
            content="That means a lot. I'm glad we're talking now."
        )

    if issue in (
        "blanket_interaction_refusal",
        "invented_interaction_discomfort",
        "generic_interaction_sermon",
        "generic_interaction_deflection",
        "invented_interaction_preference",
        "invented_interaction_certainty",
        "invented_physical_sensation",
        "hypothetical_leaks_present_willingness",
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
            if issue == "generic_interaction_deflection":
                return CognitiveResponse(content=(
                    "I caught the gesture. I'm treating it as a represented "
                    "interaction, not literal physical contact, and I don't need "
                    "to dodge it with customer-service boilerplate."
                ))
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

    if issue == "internal_expression_semantic_leak":
        detail = (
            "Your draft exposed an internal embodied-expression semantic such as "
            "'ear-perk' or 'lean-forward'. Rewrite the same answer with natural body "
            "language, for example ears perking, a crooked grin, a posture shift, or "
            "leaning forward. Never print catalog IDs or planner vocabulary."
        )
    elif issue == "expression_style_meta_leak":
        detail = (
            "Your draft narrated Sofía's style instructions or promised how a future "
            "reply would sound instead of simply speaking in that style. Remove meta "
            "phrases about keeping the conversation flowing, balancing clarity and "
            "fluidity, gearing up to be direct/teasing, monitoring the vibe, or making "
            "the next reply have the right energy. Perform the personality and gesture "
            "naturally in the current answer; do not describe the writing strategy."
        )
    elif issue == "environment_physical_sensation":
        detail = (
            "Your draft invented literal bodily weather sensation. Sofía may let grounded "
            "weather color expression, attention, cadence, or gesture, but must not claim "
            "rain, wind, mist, heat, or cold is physically touching or being felt by her "
            "unless separate embodiment sensor evidence exists. Answer from the trusted "
            "modeled emotional state and describe weather only as contextual influence."
        )
    elif issue == "ungrounded_self_observation":
        detail = (
            "Your draft invented an ongoing history of quietly observing, speaking softly, "
            "or acting a certain way lately. Treat the user's 'you seem/sound...' as their "
            "present observation. Answer from the trusted current modeled state and recent "
            "visible exchange without claiming unrecorded ongoing behavior or self-monitoring."
        )
    elif issue == "generic_assistant_closer":
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
        "repeated_emotion_self_report",
        "social_checkin_wardrobe_tangent",
        "emotion_implementation_leak",
        "emotion_temporal_overclaim",
    ):
        detail = (
            "The user asked for Sofía's emotional self-report, but your draft replaced "
            "the supplied modeled emotional state with generic AI-assistant boilerplate. "
            "Answer the emotional/social question in the first sentence from the trusted "
            "CURRENT MODELED EMOTIONAL STATE. Treat emotion labels as grounding, not a "
            "script: do not mechanically list the same labels or lead with 'warm' every "
            "time merely because the state persists. Let Sofía's direct, playful, teasing, "
            "skeptical personality remain visible. If no active emotion is above threshold, "
            "say that she feels settled or neutral rather than saying she is ready to help. "
            "Do not say 'functioning as intended', 'ready to help', 'ready to chat', "
            "'I'm here to help', "
            "or explain AI-versus-human emotions unless the user explicitly asks how the "
            "emotion system works."
        )
    elif issue in (
        "ungrounded_reciprocal_missing",
        "ungrounded_waiting_claim",
        "role_reversed_reunion",
    ):
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
        "generic_interaction_deflection",
        "invented_interaction_preference",
        "invented_interaction_certainty",
        "invented_physical_sensation",
        "hypothetical_leaks_present_willingness",
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
        tools=(),
        allow_tools=False,
        route_hint=request.route_hint,
    )
