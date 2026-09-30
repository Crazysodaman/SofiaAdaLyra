"""Typed contracts for Sofía's message-matrix architecture.

The matrix layer coordinates relevance. It does not become a new source of
truth, authority, memory, emotion, environment, or Fleet state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


MATRIX_SCHEMA_VERSION = 1


class MatrixIntent(str, Enum):
    GENERAL = "general"
    SOCIAL_CHECKIN = "social_checkin"
    ENVIRONMENT_QUERY = "environment_query"
    AVATAR_QUERY = "avatar_query"
    INTERACTION_FOLLOWUP = "interaction_followup"
    MEMORY_QUERY = "memory_query"
    OPERATIONAL_QUERY = "operational_query"
    ACTION_REQUEST = "action_request"
    AMBIGUOUS = "ambiguous"


class MatrixDomain(str, Enum):
    SOCIAL = "social"
    EMOTION = "emotion"
    ENVIRONMENT = "environment"
    AVATAR = "avatar"
    INTERACTION = "interaction"
    MEMORY = "memory"
    COGNITION = "cognition"
    MACHINE = "machine"
    OPS = "ops"
    AUTHORITY = "authority"
    CONTINUITY = "continuity"


class MatrixRelevance(int, Enum):
    NONE = 0
    CONTEXTUAL = 1
    RELEVANT = 2
    REQUIRED = 3


class MatrixConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HistoryPolicy(str, Enum):
    NONE = "none"
    LAST_TURN = "last_turn"
    TOPIC_WINDOW = "topic_window"
    BOUNDED_RECENT = "bounded_recent"
    RETRIEVE_SPECIFIC = "retrieve_specific"


class ResponseStrategy(str, Enum):
    DETERMINISTIC = "deterministic"
    GENERATIVE = "generative"
    HYBRID = "hybrid"
    TOOL_ASSISTED = "tool_assisted"
    CLARIFY = "clarify"


class EvidenceKind(str, Enum):
    CANONICAL = "canonical"
    CURRENT = "current"
    MEASURED = "measured"
    REMEMBERED = "remembered"
    EXECUTION_RECEIPT = "execution_receipt"


class EvidenceState(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    STALE = "stale"
    UNKNOWN = "unknown"


class AuthorityDecision(str, Enum):
    NOT_REQUIRED = "not_required"
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"
    CLARIFY = "clarify"


class ResponseValidationDisposition(str, Enum):
    PASS = "pass"
    RETRY = "retry"
    FALLBACK = "fallback"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class TurnEnvelope:
    message_id: str
    session_id: str
    content: str
    created_at: datetime
    principal_id: str | None = None
    channel: str = "conversation"

    def __post_init__(self) -> None:
        for name in ("message_id", "session_id", "content", "channel"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if self.principal_id is not None and (
            not isinstance(self.principal_id, str)
            or not self.principal_id.strip()
        ):
            raise ValueError("principal_id must be None or nonempty")


@dataclass(frozen=True, slots=True)
class DomainContribution:
    domain: MatrixDomain
    relevance: MatrixRelevance
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.domain, MatrixDomain):
            raise TypeError("domain must be MatrixDomain")
        if not isinstance(self.relevance, MatrixRelevance):
            raise TypeError("relevance must be MatrixRelevance")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be nonempty")


@dataclass(frozen=True, slots=True)
class TurnMatrix:
    intent: MatrixIntent
    confidence: MatrixConfidence
    history_policy: HistoryPolicy
    response_strategy: ResponseStrategy
    domains: tuple[DomainContribution, ...]
    ambiguous: bool = False
    schema_version: int = MATRIX_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.intent, MatrixIntent):
            raise TypeError("intent must be MatrixIntent")
        if not isinstance(self.confidence, MatrixConfidence):
            raise TypeError("confidence must be MatrixConfidence")
        if not isinstance(self.history_policy, HistoryPolicy):
            raise TypeError("history_policy must be HistoryPolicy")
        if not isinstance(self.response_strategy, ResponseStrategy):
            raise TypeError("response_strategy must be ResponseStrategy")
        if type(self.ambiguous) is not bool:
            raise TypeError("ambiguous must be bool")
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValueError("schema_version must be a positive int")
        if not isinstance(self.domains, tuple):
            raise TypeError("domains must be a tuple")
        seen = set()
        for contribution in self.domains:
            if not isinstance(contribution, DomainContribution):
                raise TypeError("domains must contain DomainContribution")
            if contribution.domain in seen:
                raise ValueError("TurnMatrix domains must be unique")
            seen.add(contribution.domain)

    def relevance_for(self, domain: MatrixDomain) -> MatrixRelevance:
        for contribution in self.domains:
            if contribution.domain is domain:
                return contribution.relevance
        return MatrixRelevance.NONE


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    key: str
    kind: EvidenceKind
    required: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("evidence key must be nonempty")
        if not isinstance(self.kind, EvidenceKind):
            raise TypeError("kind must be EvidenceKind")
        if type(self.required) is not bool:
            raise TypeError("required must be bool")


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    key: str
    state: EvidenceState
    source_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("evidence key must be nonempty")
        if not isinstance(self.state, EvidenceState):
            raise TypeError("state must be EvidenceState")
        if self.source_ref is not None and (
            not isinstance(self.source_ref, str) or not self.source_ref.strip()
        ):
            raise ValueError("source_ref must be None or nonempty")


@dataclass(frozen=True, slots=True)
class EvidenceMatrix:
    requirements: tuple[EvidenceRequirement, ...] = ()
    records: tuple[EvidenceRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextPlan:
    included_domains: tuple[MatrixDomain, ...]
    history_policy: HistoryPolicy
    excluded_domains: tuple[MatrixDomain, ...] = ()


@dataclass(frozen=True, slots=True)
class AuthorityPlan:
    decision: AuthorityDecision
    requested_action: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ResponseContract:
    require_grounded_claims: bool = True
    prohibited_claims: tuple[str, ...] = ()
    requires_execution_receipt: bool = False


@dataclass(frozen=True, slots=True)
class ResponseValidation:
    disposition: ResponseValidationDisposition
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MatrixTrace:
    envelope: TurnEnvelope
    turn: TurnMatrix
    created_at: datetime
    shadow: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope")
        if not isinstance(self.turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if type(self.shadow) is not bool:
            raise TypeError("shadow must be bool")
