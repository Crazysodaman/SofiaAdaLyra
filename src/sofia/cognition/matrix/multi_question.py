"""Shared multi-question parsing and matrix-plan merging."""
from __future__ import annotations

import re

from .model import (
    DomainContribution,
    HistoryPolicy,
    MatrixConfidence,
    MatrixIntent,
    MatrixRelevance,
    ResponseStrategy,
    TurnMatrix,
)


_QUESTION_START = (
    r"(?:(?:please\s+)?(?:what|what's|whats|which|where|when|why|how|who|whose|"
    r"can|could|would|will|should|do|does|did|is|are|am|have|has|"
    r"inspect|list|show|check|summarize|explain|describe|tell|"
    r"restart|reboot|start|stop|wear|change|remove|add|"
    r"discover|scan|find|design|generate|create|make))"
)
_BOUNDARY = re.compile(
    r"\s*(?:"
    r"\?+\s*(?:and\s+)?(?=" + _QUESTION_START + r"\b)|"
    r";+|"
    r",(?=\s*" + _QUESTION_START + r"\b)|"
    r"\band\b(?=\s*" + _QUESTION_START + r"\b)"
    r")\s*",
    re.IGNORECASE,
)


def split_multi_question(content: str) -> tuple[str, ...]:
    """Split only explicit question boundaries, preserving ordinary prose."""
    if not isinstance(content, str):
        raise TypeError("content must be str")
    stripped = content.strip()
    if not stripped:
        return ()
    parts = tuple(
        part.strip(" \t\r\n?!.")
        for part in _BOUNDARY.split(stripped)
        if part.strip(" \t\r\n?!.")
    )
    return parts if len(parts) > 1 else (stripped.rstrip("?!."),)


def merge_question_turns(turns: tuple[TurnMatrix, ...]) -> TurnMatrix:
    """Merge independently classified question clauses without losing domains."""
    if not isinstance(turns, tuple) or not turns:
        raise ValueError("turns must be a nonempty tuple")
    if any(not isinstance(turn, TurnMatrix) for turn in turns):
        raise TypeError("turns must contain TurnMatrix values")
    if len(turns) == 1:
        return turns[0]

    intents = tuple(turn.intent for turn in turns)
    if MatrixIntent.ACTION_REQUEST in intents:
        intent = MatrixIntent.ACTION_REQUEST
    elif MatrixIntent.GOAL_MANAGEMENT in intents:
        intent = MatrixIntent.GOAL_MANAGEMENT
    elif MatrixIntent.OPERATIONAL_QUERY in intents:
        intent = MatrixIntent.OPERATIONAL_QUERY
    elif all(item is intents[0] for item in intents):
        intent = intents[0]
    else:
        intent = MatrixIntent.GENERAL

    confidence = (
        MatrixConfidence.LOW
        if any(turn.confidence is MatrixConfidence.LOW for turn in turns)
        else (
            MatrixConfidence.MEDIUM
            if any(turn.confidence is MatrixConfidence.MEDIUM for turn in turns)
            else MatrixConfidence.HIGH
        )
    )

    strategy_order = {
        ResponseStrategy.DETERMINISTIC: 0,
        ResponseStrategy.GENERATIVE: 1,
        ResponseStrategy.HYBRID: 2,
        ResponseStrategy.CLARIFY: 3,
        ResponseStrategy.TOOL_ASSISTED: 4,
    }
    response_strategy = max(
        (turn.response_strategy for turn in turns),
        key=strategy_order.__getitem__,
    )

    policies = tuple(turn.history_policy for turn in turns)
    if all(policy is HistoryPolicy.NONE for policy in policies):
        history_policy = HistoryPolicy.NONE
    elif HistoryPolicy.RETRIEVE_SPECIFIC in policies:
        history_policy = HistoryPolicy.RETRIEVE_SPECIFIC
    elif HistoryPolicy.LAST_TURN in policies:
        history_policy = HistoryPolicy.BOUNDED_RECENT
    else:
        history_policy = max(
            policies,
            key=lambda policy: {
                HistoryPolicy.NONE: 0,
                HistoryPolicy.LAST_TURN: 1,
                HistoryPolicy.RETRIEVE_SPECIFIC: 2,
                HistoryPolicy.TOPIC_WINDOW: 3,
                HistoryPolicy.BOUNDED_RECENT: 4,
            }[policy],
        )

    contributions: dict[object, DomainContribution] = {}
    for turn in turns:
        for item in turn.domains:
            current = contributions.get(item.domain)
            if (
                current is None
                or item.relevance.value > current.relevance.value
            ):
                contributions[item.domain] = DomainContribution(
                    item.domain,
                    item.relevance,
                    "multi-question clause: " + item.reason,
                )

    return TurnMatrix(
        intent=intent,
        confidence=confidence,
        history_policy=history_policy,
        response_strategy=response_strategy,
        domains=tuple(
            contributions[key]
            for key in sorted(
                contributions,
                key=lambda domain: domain.value,
            )
        ),
        ambiguous=any(turn.ambiguous for turn in turns),
    )
