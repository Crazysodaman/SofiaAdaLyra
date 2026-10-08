"""Deterministic first-pass turn classification for matrix shadow mode."""
from __future__ import annotations

import re

from .multi_question import merge_question_turns, split_multi_question
from .visibility import asks_about_machine_visibility
from .model import (
    DomainContribution,
    HistoryPolicy,
    MatrixConfidence,
    MatrixDomain,
    MatrixIntent,
    MatrixRelevance,
    ResponseStrategy,
    TurnEnvelope,
    TurnMatrix,
)


_SOCIAL = re.compile(
    r"^\s*(?:hru|how\s+(?:are|r)\s+(?:you|u)|how(?:'|’)re\s+you)"
    r"\s*[?!.]*\s*$",
    re.IGNORECASE,
)
_GENERIC_FOLLOWUP = re.compile(
    r"^\s*(?:tell\s+me\s+(?:the\s+)?why|why|how\s+so|"
    r"why\s+(?:did\s+)?you\s+(?:pick|choose)\s+(?:that|it)|"
    r"why\s+(?:that|this)\s+(?:one|outfit|choice)|"
    r"why\s+are\s+you\s+wearing\s+(?:that|it)|"
    r"what\s+do\s+you\s+mean|explain\s+that|tell\s+me\s+more|"
    r"(?:what|which)\s+(?:old\s+)?reflectio(?:n)?(?:\s+do\s+you\s+mean)?|"
    r"what\s+oops\b.*|"
    r"give\s+me\s+(?:the\s+)?(?:figures|stats|numbers|readout)|"
    r"(?:the\s+)?(?:figures|stats|numbers|readout)|well|"
    r"is\s+that\s+all|that's\s+all|that\s+all)\s*[?!.]*\s*$",
    re.IGNORECASE,
)

_PERCEIVED_SELF_STATE = re.compile(
    r"^\s*(?:you|u)\s+(?:seem|sound)\s+(?:kinda\s+|kind\s+of\s+|"
    r"a\s+little\s+|pretty\s+|really\s+)?"
    r"(?:quiet|grumpy|happy|sad|upset|angry|mad|excited|energetic|"
    r"tired|sleepy|distant|soft|calm|tense|playful|serious)"
    r"(?:\s+today|\s+tonight|\s+right\s+now)?\s*[?!.]*\s*$",
    re.IGNORECASE,
)

_WEATHER = re.compile(
    r"\b(?:weather|temperature|forecast|humidity|outside)\b",
    re.IGNORECASE,
)
_WEATHER_EMOTION = re.compile(
    r"\b(?:weather|rain|snow|storm|sunny|cloudy|temperature)\b"
    r".{0,64}\b(?:make\s+you\s+feel|affect\s+(?:you|u|your\s+(?:mood|feelings?))|"
    r"how\s+do\s+you\s+feel)\b|"
    r"\bhow\s+does\s+(?:that\s+|the\s+)?weather\s+"
    r"(?:make\s+(?:you|u)\s+feel|affect\s+(?:you|u))\b",
    re.IGNORECASE,
)
_ENVIRONMENT_FEELING = re.compile(
    r"\b(?:weather|rain|storm|snow|temperature|season|daylight|"
    r"morning|afternoon|evening|night)\b.*"
    r"\b(?:make\s+you\s+feel|affect\s+your\s+(?:mood|feelings?)|"
    r"how\s+do\s+you\s+feel)\b"
    r"|\bhow\s+do\s+you\s+feel\b.*"
    r"\b(?:weather|rain|storm|snow|temperature|season|daylight)\b",
    re.IGNORECASE,
)
_TIME_LOCATION = re.compile(
    r"\b(?:what\s+time|time\s+is\s+it|what\s+(?:day|date)\s+is\s+it|"
    r"today(?:'s)?\s+date|where\s+am\s+i|location|timezone|season)\b",
    re.IGNORECASE,
)
_BARE_TIME = re.compile(
    r"^\s*time\s*[?!.]*\s*$",
    re.IGNORECASE,
)
_USER_REPORTED_LOCAL_TIME = re.compile(
    r"\b(?:it(?:'|’)s|it\s+is|its)\s+"
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)\s+"
    r"(?:for\s+me|my\s+time|locally)\b",
    re.IGNORECASE,
)
_AVATAR = re.compile(
    r"\b(?:wearing|outfit|clothes|clothing|panties|underwear|bra|lingerie|"
    r"hair|tail|ears|appearance|look\s+like|body|height|weight|lounge|loungewear|night\s*wear|nightwear|wear\b|socks?|boots?|shoes?|bare\s*foot|barefoot)\b",
    re.IGNORECASE,
)
_INTERACTION_FOLLOWUP = re.compile(
    r"^\s*how\s+did\s+(?:you|u)\s+feel(?:\s+about)?\s+"
    r"(?:doing\s+)?(?:it|that|this)\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_EXPRESSION_FOLLOWUP = re.compile(
    r"^\s*(?:so\s+)?(?:no\s+)?(?:"
    r"tail\s+(?:wag(?:s|ging)?|swish(?:es|ing)?|flick(?:s|ing)?|movement)|"
    r"ears?\s+(?:twitch(?:es|ing)?|perk(?:s|ing)?|flick(?:s|ing)?)|"
    r"smile|grin|blush|gesture|expression"
    r")(?:\s+or\s+anything)?\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_MEMORY = re.compile(
    r"\b(?:remember|remembered|memory|earlier|last\s+time|"
    r"what\s+did\s+i\s+say|what\s+did\s+we\s+talk)\b",
    re.IGNORECASE,
)
_MODEL_STATUS = re.compile(
    r"\b(?:what|which)\s+(?:llm|model)\b|\bmodel\s+status\b",
    re.IGNORECASE,
)
_GOAL_MANAGEMENT = re.compile(
    r"\b(?:goal|goals)\b.*\b(?:add|make|create|keep|finish|list|show|current|"
    r"pause|resume|cancel|approve|reject|blocking|blocked|important|why|status)\b|"
    r"\b(?:add|make|create|pause|resume|cancel|approve|reject|list|show)\b.{0,64}\bgoals?\b|"
    r"\bwhat\s+are\s+(?:my|your|the)\s+current\s+goals\b|"
    r"\bwhat\s+is\s+blocking\s+goal\b|\bwhy\s+is\s+goal\b.{0,64}\bimportant\b|"
    r"\b(?:i\s+want\s+you\s+to\s+keep\s+an\s+eye\s+on|your\s+goal\s+is)\b",
    re.IGNORECASE | re.DOTALL,
)
_WEB_RESEARCH = re.compile(
    r"\b(?:search|browse|look\s+up|find)\b.{0,48}\b(?:web|internet|online)\b"
    r"|\b(?:web|internet|online)\b.{0,48}\b(?:search|research|results?|answers?|ideas?)\b"
    r"|\b(?:open|fetch|read|inspect|summarize|check|browse)\b.{0,64}https://",
    re.IGNORECASE | re.DOTALL,
)
_OPS_STATUS = re.compile(
    r"\b(?:network|fleet|telemetry|cpu|gpu|ram|memory\s+usage|disk|"
    r"storage|service|services|process|processes|host|hosts|machine|machines|"
    r"computer|computers|device|devices|node|nodes|server|servers|ollama|"
    r"virtualization)\b",
    re.IGNORECASE,
)
_HOST_HARDWARE_BUNDLE = re.compile(
    r"\b(?:cpu|gpu|ram|hardware|virtualization|network\s+adapters?)\b",
    re.IGNORECASE,
)
_READ_ONLY_OPERATION = re.compile(
    r"^\s*(?:please\s+)?(?:inspect|list|show|check|summarize|discover|scan|find)\b",
    re.IGNORECASE,
)
_READ_ONLY_OPERATION_QUESTION = re.compile(
    r"^\s*(?:what|which|where|how\s+many|can\s+(?:you|u)|"
    r"do\s+(?:you|u)|are\s+there)\b",
    re.IGNORECASE,
)
_MIXED_ENVIRONMENT_OPERATIONAL = re.compile(
    r"(?=.*\b(?:time|day|date|weather|temperature|forecast|timezone|season)\b)"
    r"(?=.*\b(?:computer|computers|host|hosts|machine|machines|fleet|"
    r"device|devices|node|nodes|system)\b)",
    re.IGNORECASE | re.DOTALL,
)
_ACTION = re.compile(
    r"\b(?:restart|reboot|shutdown|start|stop|install|uninstall|remove|"
    r"delete|deploy|execute|migrate|move|update|upgrade|write|edit|change|control)\b",
    re.IGNORECASE,
)
_ELLIPTICAL_CHANGE_FOLLOWUP = re.compile(
    r"^\s*(?:(?:(?:do\s+)?you\s+)?want\s+to\s+change|wanna\s+change|"
    r"feel\s+like\s+changing)(?:\s+(?:outfits?|clothes?))?\s*[?!.]*\s*$",
    re.IGNORECASE,
)
_NOTIFICATION_ACTION = re.compile(
    r"\b(?:send|push|deliver|create)\b.{0,48}\bnotification\b"
    r"|\bnotify\s+(?:me|sparks|the\s+owner)\b",
    re.IGNORECASE,
)
_CLOTHING_ACTION = re.compile(
    r"^\s*(?:please\s+)?(?:wear|change\s+into|"
    r"change\s+(?:your\s+)?outfit\s+(?:to|into)|put\s+on|"
    r"take\s+off|take\s+.+?\s+off|remove|swap|switch|undress|"
    r"get\s+undressed)\b",
    re.IGNORECASE,
)
_CLOTHING_CONSTRAINED_ACTION = re.compile(
    r"\b(?:outfit|loungewear|night\s*wear|nightwear)\b.{0,96}"
    r"\b(?:without|no)\s+(?:a\s+)?(?:bra|bralette|panties|panty|"
    r"briefs|underwear)\b",
    re.IGNORECASE | re.DOTALL,
)
_WARDROBE_GENERATION_ACTION = re.compile(
    r"^\s*(?:please\s+)?(?:design|generate|create|make)\s+.*"
    r"\b(?:garment|clothing|shirt|tee|top|tank|hoodie|sweater|"
    r"pants|trousers|jeans|shorts|skirt|dress|jumpsuit|romper|"
    r"bodysuit|bra|bralette|briefs|panties|underwear|socks|"
    r"stockings|shoes|boots|sandals|slippers|jacket|coat|vest|"
    r"belt|gloves|bracelet|necklace|choker|collar|accessory)\b",
    re.IGNORECASE,
)
_ACTION_FOLLOWUP = re.compile(
    r"^\s*(?:do\s+it|go\s+ahead|yes[, ]+do\s+it|"
    r"please\s+do\s+it|ok(?:ay)?[, ]+do\s+it)\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_PRIMARY_ACTION = re.compile(
    r"\b(?:make|set|switch)\s+[A-Za-z0-9_.-]+\s+primary\b",
    re.IGNORECASE,
)
_INTERACTION_CONTROL = re.compile(
    r"^\s*(?:sof[ií]a,\s*)?(?:stop|pause|resume)\s+"
    r"(?:body\s+)?(?:interactions?|gestures?)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_SPECIALIZED_ACTION_DOMAIN = re.compile(
    r"\b(?:code|codebase|source\s+code|repository|repo|git|github|pytest|"
    r"documentation|docs|document|pdf|knowledge|manual|"
    r"home\s+assistant|jmri|portainer|docker|containers?|hyper[- ]?v|"
    r"virtual\s+machines?|\bvms?\b|voice|speech|microphone|\bmic\b|"
    r"audio|tts|stt|push[- ]?to[- ]?talk|gaia|hexapod|ssc[- ]?32|servos?|"
    r"gait|kinematics|physical\s+embodiment|hardware\s+e[- ]?stop)\b",
    re.IGNORECASE,
)
_SPECIALIZED_CONTROL_VERB = re.compile(
    r"\b(?:turn|set)\b",
    re.IGNORECASE,
)


def _contribution(
    domain: MatrixDomain,
    relevance: MatrixRelevance,
    reason: str,
) -> DomainContribution:
    return DomainContribution(domain, relevance, reason)


class BaselineTurnClassifier:
    """Cheap deterministic classifier.

    It can request relevance, but it cannot create truth, authority, or execute
    an action. Ambiguous language will later be eligible for LLM assistance.
    """

    def classify(self, envelope: TurnEnvelope) -> TurnMatrix:
        if not isinstance(envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope")
        text = envelope.content.strip()

        parts = split_multi_question(text)
        if len(parts) > 1:
            subturns = []
            for index, part in enumerate(parts, start=1):
                subturns.append(
                    self.classify(
                        TurnEnvelope(
                            message_id=f"{envelope.message_id}:q{index}",
                            session_id=envelope.session_id,
                            content=part,
                            created_at=envelope.created_at,
                            principal_id=envelope.principal_id,
                            channel=envelope.channel,
                        )
                    )
                )
            return merge_question_turns(tuple(subturns))

        if _GOAL_MANAGEMENT.search(text):
            return TurnMatrix(
                intent=MatrixIntent.GOAL_MANAGEMENT,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.DETERMINISTIC,
                domains=(
                    _contribution(
                        MatrixDomain.GOALS,
                        MatrixRelevance.REQUIRED,
                        "explicit goal creation, query, or lifecycle request",
                    ),
                    _contribution(
                        MatrixDomain.AUTHORITY,
                        MatrixRelevance.RELEVANT,
                        "goal ownership and authenticated scope require host validation",
                    ),
                ),
            )

        if _INTERACTION_FOLLOWUP.fullmatch(text):
            return TurnMatrix(
                intent=MatrixIntent.INTERACTION_FOLLOWUP,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.LAST_TURN,
                response_strategy=ResponseStrategy.GENERATIVE,
                domains=(
                    _contribution(
                        MatrixDomain.INTERACTION,
                        MatrixRelevance.REQUIRED,
                        "explicit represented-experience follow-up",
                    ),
                    _contribution(
                        MatrixDomain.EMOTION,
                        MatrixRelevance.RELEVANT,
                        "user asks about modeled experience",
                    ),
                    _contribution(
                        MatrixDomain.AVATAR,
                        MatrixRelevance.CONTEXTUAL,
                        "prior represented action may involve avatar state",
                    ),
                ),
            )

        if _EXPRESSION_FOLLOWUP.fullmatch(text):
            return TurnMatrix(
                intent=MatrixIntent.GENERAL,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.LAST_TURN,
                response_strategy=ResponseStrategy.GENERATIVE,
                domains=(
                    _contribution(
                        MatrixDomain.AVATAR,
                        MatrixRelevance.REQUIRED,
                        "short represented-expression follow-up",
                    ),
                    _contribution(
                        MatrixDomain.EMOTION,
                        MatrixRelevance.RELEVANT,
                        "current modeled emotion can ground embodied expression",
                    ),
                    _contribution(
                        MatrixDomain.INTERACTION,
                        MatrixRelevance.CONTEXTUAL,
                        "represented expression may continue the prior exchange",
                    ),
                ),
            )

        if _PERCEIVED_SELF_STATE.fullmatch(text):
            return TurnMatrix(
                intent=MatrixIntent.SOCIAL_CHECKIN,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.LAST_TURN,
                response_strategy=ResponseStrategy.GENERATIVE,
                domains=(
                    _contribution(
                        MatrixDomain.SOCIAL,
                        MatrixRelevance.REQUIRED,
                        "user is commenting on Sofía's apparent conversational state",
                    ),
                    _contribution(
                        MatrixDomain.EMOTION,
                        MatrixRelevance.REQUIRED,
                        "current modeled emotion is required to ground the response",
                    ),
                ),
            )

        if _SOCIAL.fullmatch(text):
            return TurnMatrix(
                intent=MatrixIntent.SOCIAL_CHECKIN,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.GENERATIVE,
                domains=(
                    _contribution(
                        MatrixDomain.SOCIAL,
                        MatrixRelevance.REQUIRED,
                        "direct social check-in",
                    ),
                    _contribution(
                        MatrixDomain.EMOTION,
                        MatrixRelevance.REQUIRED,
                        "current modeled emotion is required to inform the reply",
                    ),
                ),
            )

        if _ACTION_FOLLOWUP.fullmatch(text):
            return TurnMatrix(
                intent=MatrixIntent.ACTION_REQUEST,
                confidence=MatrixConfidence.MEDIUM,
                history_policy=HistoryPolicy.LAST_TURN,
                response_strategy=ResponseStrategy.TOOL_ASSISTED,
                domains=(
                    _contribution(
                        MatrixDomain.AUTHORITY,
                        MatrixRelevance.REQUIRED,
                        "short action follow-up requires prior-turn authority context",
                    ),
                    _contribution(
                        MatrixDomain.AVATAR,
                        MatrixRelevance.CONTEXTUAL,
                        "prior action may target avatar presentation state",
                    ),
                ),
            )

        if (
            _GENERIC_FOLLOWUP.fullmatch(text)
            or _ELLIPTICAL_CHANGE_FOLLOWUP.fullmatch(text)
        ):
            return TurnMatrix(
                intent=MatrixIntent.GENERAL,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.LAST_TURN,
                response_strategy=ResponseStrategy.GENERATIVE,
                domains=(
                    _contribution(
                        MatrixDomain.SOCIAL,
                        MatrixRelevance.CONTEXTUAL,
                        "short follow-up should stay bound to the immediately prior turn",
                    ),
                    *(
                        (_contribution(
                            MatrixDomain.AVATAR,
                            MatrixRelevance.CONTEXTUAL,
                            "elliptical change question may inherit presentation context",
                        ),)
                        if _ELLIPTICAL_CHANGE_FOLLOWUP.fullmatch(text)
                        else ()
                    ),
                ),
            )

        if _WEATHER_EMOTION.search(text):
            return TurnMatrix(
                intent=MatrixIntent.GENERAL,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.GENERATIVE,
                domains=(
                    _contribution(
                        MatrixDomain.ENVIRONMENT,
                        MatrixRelevance.REQUIRED,
                        "current weather evidence grounds the environmental context",
                    ),
                    _contribution(
                        MatrixDomain.EMOTION,
                        MatrixRelevance.REQUIRED,
                        "weather asks for modeled emotional response",
                    ),
                ),
            )

        if (
            _CLOTHING_ACTION.search(text)
            or _CLOTHING_CONSTRAINED_ACTION.search(text)
            or _WARDROBE_GENERATION_ACTION.search(text)
            or _ACTION.search(text)
            or _NOTIFICATION_ACTION.search(text)
            or _PRIMARY_ACTION.search(text)
            or (
                _SPECIALIZED_ACTION_DOMAIN.search(text)
                and _SPECIALIZED_CONTROL_VERB.search(text)
            )
        ):
            domains = [
                _contribution(
                    MatrixDomain.AUTHORITY,
                    MatrixRelevance.REQUIRED,
                    "message requests a state-changing action",
                ),
            ]
            avatar_action = (
                _AVATAR.search(text) is not None
                or _CLOTHING_ACTION.search(text) is not None
                or _CLOTHING_CONSTRAINED_ACTION.search(text) is not None
                or _WARDROBE_GENERATION_ACTION.search(text) is not None
            )
            interaction_control = (
                _INTERACTION_CONTROL.fullmatch(text) is not None
            )
            specialized_action = (
                _SPECIALIZED_ACTION_DOMAIN.search(text) is not None
            )
            if (
                not avatar_action
                and not interaction_control
                and not specialized_action
            ):
                domains.append(
                    _contribution(
                        MatrixDomain.OPS,
                        MatrixRelevance.RELEVANT,
                        "action may target operational state",
                    )
                )
            if avatar_action:
                domains.append(
                    _contribution(
                        MatrixDomain.AVATAR,
                        MatrixRelevance.RELEVANT,
                        "action references avatar or presentation state",
                    )
                )
            if _MODEL_STATUS.search(text):
                domains.append(
                    _contribution(
                        MatrixDomain.COGNITION,
                        MatrixRelevance.RELEVANT,
                        "action references a cognitive model",
                    )
                )
            return TurnMatrix(
                intent=MatrixIntent.ACTION_REQUEST,
                confidence=MatrixConfidence.MEDIUM,
                history_policy=HistoryPolicy.BOUNDED_RECENT,
                response_strategy=ResponseStrategy.TOOL_ASSISTED,
                domains=tuple(domains),
            )

        if _ENVIRONMENT_FEELING.search(text):
            return TurnMatrix(
                intent=MatrixIntent.GENERAL,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.GENERATIVE,
                domains=(
                    _contribution(
                        MatrixDomain.ENVIRONMENT,
                        MatrixRelevance.REQUIRED,
                        "environment + modeled-emotion question",
                    ),
                    _contribution(
                        MatrixDomain.EMOTION,
                        MatrixRelevance.REQUIRED,
                        "answer must use current modeled emotional state",
                    ),
                ),
            )

        if _MIXED_ENVIRONMENT_OPERATIONAL.search(text):
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.TOOL_ASSISTED,
                domains=(
                    _contribution(
                        MatrixDomain.ENVIRONMENT,
                        MatrixRelevance.RELEVANT,
                        "mixed factual turn includes current calendar/environment facts",
                    ),
                    _contribution(
                        MatrixDomain.MACHINE,
                        MatrixRelevance.REQUIRED,
                        "mixed factual turn asks about local or known computers",
                    ),
                    _contribution(
                        MatrixDomain.OPS,
                        MatrixRelevance.RELEVANT,
                        "known Fleet/remote state may answer computer visibility",
                    ),
                ),
            )

        if (
            _WEATHER.search(text)
            or _TIME_LOCATION.search(text)
            or _BARE_TIME.fullmatch(text)
            or _USER_REPORTED_LOCAL_TIME.search(text)
        ):
            return TurnMatrix(
                intent=MatrixIntent.ENVIRONMENT_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.DETERMINISTIC,
                domains=(
                    _contribution(
                        MatrixDomain.ENVIRONMENT,
                        MatrixRelevance.REQUIRED,
                        "direct environment/time/location query",
                    ),
                ),
            )

        # Explicit read-only operational requests take precedence over
        # overloaded words such as "memory". "Inspect memory usage" means host
        # telemetry, not autobiographical recall.
        if _READ_ONLY_OPERATION.search(text) and _OPS_STATUS.search(text):
            machine_required = _HOST_HARDWARE_BUNDLE.search(text) is not None
            domains = [
                _contribution(
                    (
                        MatrixDomain.MACHINE
                        if machine_required
                        else MatrixDomain.OPS
                    ),
                    MatrixRelevance.REQUIRED,
                    (
                        "explicit host hardware/resource inspection requires "
                        "current machine evidence"
                        if machine_required
                        else "explicit operational inspection requires current host evidence"
                    ),
                ),
            ]
            if machine_required:
                domains.append(
                    _contribution(
                        MatrixDomain.OPS,
                        MatrixRelevance.RELEVANT,
                        "host operational state may contextualize hardware evidence",
                    )
                )
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.TOOL_ASSISTED,
                domains=tuple(domains),
            )

        # Host-resource language such as "CPU, GPU, memory, storage" is
        # operational even though the word "memory" also exists in the
        # autobiographical-memory vocabulary.
        if _HOST_HARDWARE_BUNDLE.search(text):
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=(
                    ResponseStrategy.TOOL_ASSISTED
                    if (
                        _READ_ONLY_OPERATION.search(text)
                        or _READ_ONLY_OPERATION_QUESTION.search(text)
                    )
                    else ResponseStrategy.HYBRID
                ),
                domains=(
                    _contribution(
                        MatrixDomain.MACHINE,
                        MatrixRelevance.REQUIRED,
                        "host hardware/resource inspection requires current machine evidence",
                    ),
                    _contribution(
                        MatrixDomain.OPS,
                        MatrixRelevance.RELEVANT,
                        "host operational state may contextualize hardware evidence",
                    ),
                ),
            )

        if _AVATAR.search(text):
            return TurnMatrix(
                intent=MatrixIntent.AVATAR_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.HYBRID,
                domains=(
                    _contribution(
                        MatrixDomain.AVATAR,
                        MatrixRelevance.REQUIRED,
                        "direct avatar or presentation query",
                    ),
                    _contribution(
                        MatrixDomain.INTERACTION,
                        MatrixRelevance.CONTEXTUAL,
                        "presentation requests may carry interaction constraints",
                    ),
                ),
            )

        if _MEMORY.search(text):
            return TurnMatrix(
                intent=MatrixIntent.MEMORY_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.RETRIEVE_SPECIFIC,
                response_strategy=ResponseStrategy.HYBRID,
                domains=(
                    _contribution(
                        MatrixDomain.MEMORY,
                        MatrixRelevance.REQUIRED,
                        "explicit prior-conversation or memory request",
                    ),
                ),
            )

        if _WEB_RESEARCH.search(text):
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.BOUNDED_RECENT,
                response_strategy=ResponseStrategy.TOOL_ASSISTED,
                domains=(
                    _contribution(
                        MatrixDomain.KNOW,
                        MatrixRelevance.REQUIRED,
                        "explicit public-web research requires current external evidence",
                    ),
                    _contribution(
                        MatrixDomain.INTEGRATE,
                        MatrixRelevance.RELEVANT,
                        "governed HTTPS/search adapter supplies external evidence",
                    ),
                ),
            )

        if _MODEL_STATUS.search(text):
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.HIGH,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.DETERMINISTIC,
                domains=(
                    _contribution(
                        MatrixDomain.COGNITION,
                        MatrixRelevance.REQUIRED,
                        "direct model/routing status question",
                    ),
                ),
            )

        if asks_about_machine_visibility(text):
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.MEDIUM,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.TOOL_ASSISTED,
                domains=(
                    _contribution(
                        MatrixDomain.OPS,
                        MatrixRelevance.REQUIRED,
                        "named-machine visibility requires current Fleet evidence",
                    ),
                    _contribution(
                        MatrixDomain.MACHINE,
                        MatrixRelevance.RELEVANT,
                        "local host facts do not establish remote host state",
                    ),
                ),
            )

        if _OPS_STATUS.search(text):
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.MEDIUM,
                history_policy=HistoryPolicy.NONE,
                response_strategy=(
                    ResponseStrategy.TOOL_ASSISTED
                    if (
                        _READ_ONLY_OPERATION.search(text)
                        or _READ_ONLY_OPERATION_QUESTION.search(text)
                    )
                    else ResponseStrategy.HYBRID
                ),
                domains=(
                    _contribution(
                        MatrixDomain.OPS,
                        MatrixRelevance.REQUIRED,
                        "direct machine/Fleet/operational status question",
                    ),
                    _contribution(
                        MatrixDomain.MACHINE,
                        MatrixRelevance.RELEVANT,
                        "host-local evidence may be required",
                    ),
                ),
            )

        return TurnMatrix(
            intent=MatrixIntent.GENERAL,
            confidence=MatrixConfidence.MEDIUM,
            history_policy=HistoryPolicy.BOUNDED_RECENT,
            response_strategy=ResponseStrategy.GENERATIVE,
            domains=(
                _contribution(
                    MatrixDomain.SOCIAL,
                    MatrixRelevance.CONTEXTUAL,
                    "ordinary conversation may need principal/social context",
                ),
            ),
        )
