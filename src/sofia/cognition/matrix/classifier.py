"""Deterministic first-pass turn classification for matrix shadow mode."""
from __future__ import annotations

import re

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
_WEATHER = re.compile(
    r"\b(?:weather|temperature|forecast|humidity|outside)\b",
    re.IGNORECASE,
)
_TIME_LOCATION = re.compile(
    r"\b(?:what\s+time|time\s+is\s+it|where\s+am\s+i|location|timezone|season)\b",
    re.IGNORECASE,
)
_AVATAR = re.compile(
    r"\b(?:wearing|outfit|clothes|clothing|panties|underwear|bra|lingerie|"
    r"hair|tail|ears|appearance|look\s+like|body|height|weight)\b",
    re.IGNORECASE,
)
_INTERACTION_FOLLOWUP = re.compile(
    r"^\s*how\s+did\s+(?:you|u)\s+feel(?:\s+about)?\s+"
    r"(?:doing\s+)?(?:it|that|this)\s*[?.!]*\s*$",
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
_OPS_STATUS = re.compile(
    r"\b(?:network|fleet|telemetry|cpu|gpu|ram|memory\s+usage|disk|"
    r"storage|service|process|host|machine|server|ollama)\b",
    re.IGNORECASE,
)
_ACTION = re.compile(
    r"\b(?:restart|reboot|shutdown|start|stop|install|uninstall|remove|"
    r"delete|deploy|migrate|move|update|upgrade|write|edit|change|control)\b",
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
                        MatrixRelevance.RELEVANT,
                        "current modeled emotion can inform the reply",
                    ),
                ),
            )

        if _ACTION.search(text):
            domains = [
                _contribution(
                    MatrixDomain.AUTHORITY,
                    MatrixRelevance.REQUIRED,
                    "message contains an operational action verb",
                ),
                _contribution(
                    MatrixDomain.OPS,
                    MatrixRelevance.RELEVANT,
                    "action may target operational state",
                ),
            ]
            if _AVATAR.search(text):
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

        if _WEATHER.search(text) or _TIME_LOCATION.search(text):
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

        if _OPS_STATUS.search(text):
            return TurnMatrix(
                intent=MatrixIntent.OPERATIONAL_QUERY,
                confidence=MatrixConfidence.MEDIUM,
                history_policy=HistoryPolicy.NONE,
                response_strategy=ResponseStrategy.HYBRID,
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
