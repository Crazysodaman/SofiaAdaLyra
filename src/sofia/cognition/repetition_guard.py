"""Provider-side quality checks for repetitive and generic assistant replies.

This module never changes saved conversation, evaluates consent, filters user
input, or decides what Sofía should feel. It permits one text-only provider
retry when a draft clearly falls into a known low-quality completion pattern.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import re

from sofia.cognition.model import CognitiveRequest, CognitiveResponse, CognitiveRole

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
_SHORT_SOCIAL_CUE = re.compile(
    r"^\s*(?:hey|hi|hello|yo)(?:\s+(?:sof[ií]a|nerd))?\s*[?!.]*\s*$|"
    r"^\s*(?:\*?\s*)?(?:waves?|wave)(?:\s+at\s+(?:you|u))?(?:\s*\*?)?\s*[?!.]*\s*$",
    re.IGNORECASE,
)
_FUTURE_RECIPROCAL_WAVE = re.compile(
    r"\b(?:i(?:'|’)ll|i\s+will|let\s+me)\b.{0,40}\b(?:wave|give\s+you\b.{0,20}\bwave)\b",
    re.IGNORECASE | re.DOTALL,
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
    r"\b(?:ready\s+to\s+(?:help|assist|support|engage|chat|talk|dive\s+into)|"
    r"ready\s+to\s+connect\s+whenever|"
    r"whether\s+you(?:'|’)re\s+looking\s+for\s+(?:a\s+)?(?:quick|deep|friendly)|"
    r"bring\s+my\s+full\s+attention|"
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
    r"modeled\s+emotional\s+state|foreground\s+(?:modeled\s+)?emotions?|"
    r"background\s+relational\s+tone|foreground\s+drama|"
    r"bond\s+coloring\s+the\s+background)\b",
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
_BIOLOGICAL_EMOTION_SENSATION = re.compile(
    r"\b(?:warmth|fondness|affection|sadness|joy|excitement|feeling)\b"
    r".{0,60}\b(?:spread|curl|ache|flutter|burn|tighten|settle)\b"
    r".{0,40}\b(?:chest|heart|skin|stomach|body)\b|"
    r"\b(?:chest|heart|skin|stomach|body)\b.{0,50}\b"
    r"(?:warm|ache|flutter|tight|tingle|buzz)\b",
    re.IGNORECASE | re.DOTALL,
)
_INCOMPLETE_TAIL = re.compile(
    r"\b(?:you(?:'|’)ve\s+been|i(?:'|’)ve\s+been|i\s+have\s+been|"
    r"going\s+to|because|although|unless|while)\s*$",
    re.IGNORECASE,
)
_UNGROUNDED_SELF_OBSERVATION = re.compile(
    r"\b(?:i(?:'|’)ve\s+been\s+quietly\s+observing|"
    r"i(?:'|’)ve\s+been\s+thinking\s+about\s+it|"
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
    r"(?:rain|fog|mist|wind|breeze|cold|heat|weather)\b.{0,80}\b"
    r"(?:nipping|touching|hitting|brushing|washing|kissing|hugging|wrapping|"
    r"pressing)\b.{0,60}\b(?:me|my\s+(?:ears?|skin|face|body|tail))\b|"
    r"(?:rain|fog|mist|wind|breeze|cold|heat|weather)\b.{0,80}\b"
    r"(?:against|across|around|over|on)\s+me\b|"
    r"i\s+(?:can|could)\s+feel\s+(?:the\s+)?(?:rain|fog|mist|wind|breeze|cold|heat|weather|world\s+around\s+me)|"
    r"i(?:'|’)m\s+feeling\s+(?:the\s+)?whole\s+(?:weather|thing))\b",
    re.IGNORECASE | re.DOTALL,
)
_DENIED_ENVIRONMENT_SENSATION = re.compile(
    r"\b(?:isn(?:'|’)t|is\s+not|aren(?:'|’)t|are\s+not|"
    r"don(?:'|’)t|do\s+not|doesn(?:'|’)t|does\s+not)\b"
    r".{0,50}\b(?:physically\s+)?(?:touching|kissing|hugging|"
    r"nipping|brushing|hitting|washing|pressing|felt|feel)\b",
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
    r"keep\s+an\s+ear\s+for|adjust\s+my|let\s+my\s+tail|bring\s+the\s+energy)|"
    r"my\s+next\s+reply\b|"
    r"just\s+the\s+right\s+amount\s+of\s+(?:depth|energy)|"
    r"keep\s+(?:this|the)\s+(?:conversation|exchange)\s+(?:flowing|tight|engaging)|"
    r"keep\s+this\s+momentum\s+going|"
    r"make\s+this\s+exchange\s+count|"
    r"bring\s+the\s+energy\s+you(?:'|’)re\s+looking\s+for|"
    r"i(?:'|’)ve\s+been\s+thinking\s+about\s+how\s+we\s+can\s+"
    r"keep\s+(?:this|the)\s+conversation\s+flowing)\b",
    re.IGNORECASE | re.DOTALL,
)

_SOCIAL_PERSONA_FICTION = re.compile(
    r"\b(?:digital\s+void|waiting\s+for\s+my\s+return|no\s+glitches)\b",
    re.IGNORECASE,
)
_REFLEXIVE_SOCIAL_HANDOFF = re.compile(
    r"(?:\byou\??|how\s+about\s+you\??|"
    r"how(?:'|’)s\s+it\s+looking\s+on\s+your\s+end\??)\s*$",
    re.IGNORECASE,
)
_FALSE_HOST_ACCESS_DENIAL = re.compile(
    r"\b(?:i\s+(?:cannot|can't|can(?:not|'t))\s+(?:inspect|access)|"
    r"i\b.{0,60}\bdo\s+not\s+have\s+direct\s+access|"
    r"i\s+don't\s+have\s+direct\s+access|"
    r"i\s+am\s+an?\s+ai\s+(?:model|assistant).{0,48}"
    r"\b(?:do\s+not|don't)\s+have\s+direct\s+access|"
    r"unable\s+to\s+(?:inspect|access))\b.{0,140}"
    r"\b(?:computer|hardware|operating\s+system|host|network|"
    r"storage|fleet|machine|system)\b",
    re.IGNORECASE | re.DOTALL,
)
_OPERATIONAL_EVIDENCE_OVERREACH = re.compile(
    r"\b(?:no\s+rogue\s+(?:agents?|processes?)|no\s+hidden\s+(?:daemons?|processes?)|"
    r"system\s+appears\s+healthy|nothing\s+is\s+actively\s+consuming\s+cpu|"
    r"(?:these|those)\s+processes\s+aren(?:'|’)t\s+the\s+bottleneck|"
    r"(?:they(?:'|’)re|they\s+are)\s+not\s+the\s+problem)\b",
    re.IGNORECASE,
)

_UNGROUNDED_ONGOING_ACTIVITY = re.compile(
    r"\b(?:i(?:'|’)ve\s+been\s+humming\s+along|"
    r"i(?:'|’)ve\s+been\s+quietly\s+observing|"
    r"i(?:'|’)ve\s+been\s+thinking\s+about\s+how\s+we\s+can\s+"
    r"keep\s+(?:this|the)\s+conversation\s+flowing)\b",
    re.IGNORECASE,
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
    # A completed tool round may still need a text-only quality repair. The
    # retry request removes tool definitions/authority, so allowing validation
    # here cannot re-execute a tool. Responses that themselves request tools
    # remain ineligible.
    return not (
        response.tool_calls
        or not request.messages
        or request.messages[-1].role is not CognitiveRole.USER
        or _EXPLICIT_REPEAT.search(request.messages[-1].content)
    )


def is_near_duplicate_reply(request: CognitiveRequest, response: CognitiveResponse) -> bool:
    """Compare a long tool-free draft to recent assistant-only prose."""
    if not _retry_eligible(request, response):
        return False
    # Near-duplicate comparison intentionally stays tool-free. Tool-result
    # requests are eligible for targeted quality checks, but their assistant
    # tool-call scaffolding must not become prose-repeat evidence.
    if any(
        message.role is CognitiveRole.TOOL or message.tool_calls
        for message in request.messages
    ):
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
    if "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT" not in system_context:
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
    if len(_normalized(content)) >= 20 and _INCOMPLETE_TAIL.search(content.strip()):
        return "incomplete_generation"
    concise_turn = (
        _STANDALONE_SOCIAL_CHECKIN.fullmatch(user.strip()) is not None
        or _SHORT_SOCIAL_CUE.fullmatch(user.strip()) is not None
        or _PERCEIVED_SELF_STATE_USER.search(user) is not None
        or _ENVIRONMENT_EFFECT_USER.search(user) is not None
    )
    if concise_turn and len(_normalized(content).split()) > 90:
        return "overlong_simple_social_turn"
    if _EMOTION_SELF_REPORT.search(user) and _repeats_previous_short_self_report(request, response):
        return "repeated_emotion_self_report"
    if (
        _EMOTION_SELF_REPORT.search(user)
        and _repeats_previous_short_self_report(request, response)
    ):
        return "repeated_emotion_self_report"
    if (
        (
            _STANDALONE_SOCIAL_CHECKIN.fullmatch(user.strip()) is not None
            or _EMOTION_SELF_REPORT.search(user) is not None
            or _PERCEIVED_SELF_STATE_USER.search(user) is not None
        )
        and _REFLEXIVE_SOCIAL_HANDOFF.search(content.strip())
    ):
        return "reflexive_social_handoff"
    if (
        re.search(r"\bwave", user, re.IGNORECASE)
        and _FUTURE_RECIPROCAL_WAVE.search(content)
    ):
        return "future_reciprocal_wave"
    if _EMOTION_SELF_REPORT.search(user):
        if _EMOTION_IMPLEMENTATION_LEAK.search(content):
            return "emotion_implementation_leak"
        if _EMOTION_TEMPORAL_OVERCLAIM.search(content):
            return "emotion_temporal_overclaim"
        if _EMOTION_DISCLAIMER.search(content):
            return "emotion_disclaimer"
        if _BIOLOGICAL_EMOTION_SENSATION.search(content):
            return "emotion_physical_sensation"
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
    tool_context = "\n".join(
        message.content for message in request.messages
        if message.role is CognitiveRole.TOOL
    )
    host_tool_result_present = (
        "COGNITIVE TOOL RESULT" in tool_context
        and "Capability:" in tool_context
        and "Result:" in tool_context
    )
    if (
        _STANDALONE_SOCIAL_CHECKIN.fullmatch(user.strip())
        and _SOCIAL_PERSONA_FICTION.search(content)
    ):
        return "social_persona_fiction"
    if host_tool_result_present and _FALSE_HOST_ACCESS_DENIAL.search(content):
        return "host_tool_evidence_denial"
    if (
        "Result: success" in tool_context
        and _OPERATIONAL_EVIDENCE_OVERREACH.search(content)
    ):
        return "operational_evidence_overreach"
    if (
        _EMOTION_SELF_REPORT.search(user)
        and _UNGROUNDED_ONGOING_ACTIVITY.search(content)
    ):
        return "ungrounded_ongoing_self_activity"
    if (
        "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT" in system_context
        and _TECHNICAL_EXPRESSION_QUERY.search(user) is None
        and _INTERNAL_EXPRESSION_SEMANTIC.search(content)
    ):
        return "internal_expression_semantic_leak"
    if (
        "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT" in system_context
        and _TECHNICAL_EXPRESSION_QUERY.search(user) is None
        and _EXPRESSION_STYLE_META_LEAK.search(content)
    ):
        return "expression_style_meta_leak"
    if (
        "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT" in system_context
        and _TECHNICAL_EXPRESSION_QUERY.search(user) is None
        and _GENERIC_ASSISTANT_POSTURE.search(content)
    ):
        return "generic_personality_deflection"
    if (
        _ENVIRONMENT_EFFECT_USER.search(user)
        and _ENVIRONMENT_SENSATION_OVERCLAIM.search(content)
        and _DENIED_ENVIRONMENT_SENSATION.search(content) is None
    ):
        return "environment_physical_sensation"
    if (
        _PERCEIVED_SELF_STATE_USER.search(user)
        and _BIOLOGICAL_EMOTION_SENSATION.search(content)
    ):
        return "emotion_physical_sensation"
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
