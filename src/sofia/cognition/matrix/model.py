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
    REL = "rel"
    HABIT = "habit"
    DEV = "dev"
    KNOW = "know"
    INTEGRATE = "integrate"
    BODY = "body"
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


class MatrixRoute(str, Enum):
    AUTO = "auto"
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    VERIFY = "verify"


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

    def __post_init__(self) -> None:
        if not isinstance(self.requirements, tuple):
            raise TypeError("requirements must be a tuple")
        if not isinstance(self.records, tuple):
            raise TypeError("records must be a tuple")
        requirement_keys = set()
        for item in self.requirements:
            if not isinstance(item, EvidenceRequirement):
                raise TypeError(
                    "requirements must contain EvidenceRequirement"
                )
            if item.key in requirement_keys:
                raise ValueError("evidence requirements must be unique")
            requirement_keys.add(item.key)
        record_keys = set()
        for item in self.records:
            if not isinstance(item, EvidenceRecord):
                raise TypeError("records must contain EvidenceRecord")
            if item.key in record_keys:
                raise ValueError("evidence records must be unique")
            record_keys.add(item.key)

    def state_for(self, key: str) -> EvidenceState:
        for record in self.records:
            if record.key == key:
                return record.state
        return EvidenceState.UNKNOWN

    @property
    def missing_required(self) -> tuple[EvidenceRequirement, ...]:
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.required
            and self.state_for(requirement.key)
            in {
                EvidenceState.MISSING,
                EvidenceState.STALE,
                EvidenceState.UNKNOWN,
            }
        )


@dataclass(frozen=True, slots=True)
class ContextPlan:
    included_domains: tuple[MatrixDomain, ...]
    history_policy: HistoryPolicy
    excluded_domains: tuple[MatrixDomain, ...] = ()
    max_history_messages: int = 12

    def __post_init__(self) -> None:
        if not isinstance(self.included_domains, tuple):
            raise TypeError("included_domains must be a tuple")
        if not isinstance(self.excluded_domains, tuple):
            raise TypeError("excluded_domains must be a tuple")
        if not isinstance(self.history_policy, HistoryPolicy):
            raise TypeError("history_policy must be HistoryPolicy")
        if (
            type(self.max_history_messages) is not int
            or self.max_history_messages < 1
        ):
            raise ValueError("max_history_messages must be a positive int")
        included = set()
        for domain in self.included_domains:
            if not isinstance(domain, MatrixDomain):
                raise TypeError(
                    "included_domains must contain MatrixDomain values"
                )
            if domain in included:
                raise ValueError("included_domains must be unique")
            included.add(domain)
        excluded = set()
        for domain in self.excluded_domains:
            if not isinstance(domain, MatrixDomain):
                raise TypeError(
                    "excluded_domains must contain MatrixDomain values"
                )
            if domain in excluded:
                raise ValueError("excluded_domains must be unique")
            excluded.add(domain)
        if included & excluded:
            raise ValueError(
                "a matrix domain cannot be both included and excluded"
            )


@dataclass(frozen=True, slots=True)
class AuthorityPlan:
    decision: AuthorityDecision
    requested_action: str | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.decision, AuthorityDecision):
            raise TypeError("decision must be AuthorityDecision")
        if self.requested_action is not None and (
            not isinstance(self.requested_action, str)
            or not self.requested_action.strip()
        ):
            raise ValueError(
                "requested_action must be None or a nonempty string"
            )
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")


@dataclass(frozen=True, slots=True)
class PrivacyProjectionPlan:
    """Trusted principal/audience projection eligibility for one turn.

    This plan never creates identity, private grants, consent, or authority.
    It only narrows which already-scoped state may be considered.
    """

    principal_id: str | None
    audience_id: str | None
    audience_kind: str | None
    allow_relationship_scope: bool
    allow_audience_scope: bool
    allow_historical_private_scope: bool
    allow_private_presentation_candidate: bool
    reason: str

    def __post_init__(self) -> None:
        for name in (
            "allow_relationship_scope",
            "allow_audience_scope",
            "allow_historical_private_scope",
            "allow_private_presentation_candidate",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("privacy projection reason must be nonempty")

        if self.principal_id is None:
            if any(
                value is not None
                for value in (
                    self.audience_id,
                    self.audience_kind,
                )
            ):
                raise ValueError(
                    "unbound privacy projection cannot carry audience identity"
                )
            if any(
                (
                    self.allow_relationship_scope,
                    self.allow_audience_scope,
                    self.allow_historical_private_scope,
                    self.allow_private_presentation_candidate,
                )
            ):
                raise ValueError(
                    "unbound privacy projection cannot permit scoped state"
                )
            return

        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("principal_id must be None or nonempty")
        if not isinstance(self.audience_id, str) or not self.audience_id.strip():
            raise ValueError("bound privacy projection requires audience_id")
        if self.audience_kind not in {"private", "shared", "system"}:
            raise ValueError(
                "bound privacy projection requires a known audience_kind"
            )


@dataclass(frozen=True, slots=True)
class ToolExposurePlan:
    """Relevant capability exposure for one turn.

    This is a relevance decision only. It never grants capability authority.
    The CapabilityGateway remains the final execution boundary.
    """

    capabilities: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, tuple):
            raise TypeError("tool exposure capabilities must be a tuple")
        seen = set()
        for capability in self.capabilities:
            if not isinstance(capability, str) or not capability.strip():
                raise ValueError(
                    "tool exposure capabilities must contain nonempty strings"
                )
            if capability in seen:
                raise ValueError("tool exposure capabilities must be unique")
            seen.add(capability)
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("tool exposure reason must be nonempty")

    @property
    def allow_tools(self) -> bool:
        return bool(self.capabilities)


@dataclass(frozen=True, slots=True)
class RoutingPlan:
    route: MatrixRoute
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.route, MatrixRoute):
            raise TypeError("route must be MatrixRoute")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("routing reason must be nonempty")


@dataclass(frozen=True, slots=True)
class ResponseContract:
    require_grounded_claims: bool = True
    prohibited_claims: tuple[str, ...] = ()
    requires_execution_receipt: bool = False
    authority_decision: AuthorityDecision = AuthorityDecision.NOT_REQUIRED

    def __post_init__(self) -> None:
        if type(self.require_grounded_claims) is not bool:
            raise TypeError("require_grounded_claims must be bool")
        if not isinstance(self.prohibited_claims, tuple):
            raise TypeError("prohibited_claims must be a tuple")
        for claim in self.prohibited_claims:
            if not isinstance(claim, str) or not claim.strip():
                raise ValueError(
                    "prohibited_claims must contain nonempty strings"
                )
        if type(self.requires_execution_receipt) is not bool:
            raise TypeError("requires_execution_receipt must be bool")
        if not isinstance(self.authority_decision, AuthorityDecision):
            raise TypeError("authority_decision must be AuthorityDecision")


@dataclass(frozen=True, slots=True)
class ResponseValidation:
    disposition: ResponseValidationDisposition
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CognitionExecutionStep:
    role: str
    model: str | None = None
    host: str | None = None
    succeeded: bool = True

    def __post_init__(self) -> None:
        if self.role not in {"primary", "secondary"}:
            raise ValueError("cognition execution role must be primary or secondary")
        for value, label in ((self.model, "model"), (self.host, "host")):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"cognition execution {label} must be None or nonempty")
        if type(self.succeeded) is not bool:
            raise TypeError("cognition execution succeeded must be bool")


@dataclass(frozen=True, slots=True)
class CognitionExecutionTrace:
    serial: int
    actual_route: str
    steps: tuple[CognitionExecutionStep, ...] = ()
    fallback_count: int = 0
    verification_passes: int = 0

    def __post_init__(self) -> None:
        if type(self.serial) is not int or self.serial < 1:
            raise ValueError("cognition execution serial must be positive")
        if self.actual_route not in {
            "fast",
            "standard",
            "deep",
            "open",
            "verify",
        }:
            raise ValueError("invalid cognition execution route")
        if not isinstance(self.steps, tuple):
            raise TypeError("cognition execution steps must be a tuple")
        if any(not isinstance(step, CognitionExecutionStep) for step in self.steps):
            raise TypeError("cognition execution steps are invalid")
        if type(self.fallback_count) is not int or self.fallback_count < 0:
            raise ValueError("fallback_count must be a nonnegative int")
        if type(self.verification_passes) is not int or self.verification_passes < 0:
            raise ValueError("verification_passes must be a nonnegative int")

    @property
    def successful_steps(self) -> tuple[CognitionExecutionStep, ...]:
        return tuple(step for step in self.steps if step.succeeded)

    @property
    def last_successful_step(self) -> CognitionExecutionStep | None:
        values = self.successful_steps
        return values[-1] if values else None


@dataclass(frozen=True, slots=True)
class MatrixTrace:
    envelope: TurnEnvelope
    turn: TurnMatrix
    created_at: datetime
    context: ContextPlan | None = None
    evidence: EvidenceMatrix | None = None
    authority: AuthorityPlan | None = None
    privacy: PrivacyProjectionPlan | None = None
    tool_exposure: ToolExposurePlan | None = None
    response_contract: ResponseContract | None = None
    response_validation: ResponseValidation | None = None
    routing: RoutingPlan | None = None
    cognition_execution: CognitionExecutionTrace | None = None
    shadow: bool = True
    context_active: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope")
        if not isinstance(self.turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")
        if self.context is not None and not isinstance(
            self.context, ContextPlan
        ):
            raise TypeError("context must be ContextPlan or None")
        if self.evidence is not None and not isinstance(
            self.evidence, EvidenceMatrix
        ):
            raise TypeError("evidence must be EvidenceMatrix or None")
        if self.authority is not None and not isinstance(
            self.authority, AuthorityPlan
        ):
            raise TypeError("authority must be AuthorityPlan or None")
        if self.privacy is not None and not isinstance(
            self.privacy, PrivacyProjectionPlan
        ):
            raise TypeError(
                "privacy must be PrivacyProjectionPlan or None"
            )
        if self.tool_exposure is not None and not isinstance(
            self.tool_exposure, ToolExposurePlan
        ):
            raise TypeError(
                "tool_exposure must be ToolExposurePlan or None"
            )
        if self.response_contract is not None and not isinstance(
            self.response_contract, ResponseContract
        ):
            raise TypeError(
                "response_contract must be ResponseContract or None"
            )
        if self.response_validation is not None and not isinstance(
            self.response_validation, ResponseValidation
        ):
            raise TypeError(
                "response_validation must be ResponseValidation or None"
            )
        if self.routing is not None and not isinstance(
            self.routing, RoutingPlan
        ):
            raise TypeError("routing must be RoutingPlan or None")
        if self.cognition_execution is not None and not isinstance(
            self.cognition_execution, CognitionExecutionTrace
        ):
            raise TypeError(
                "cognition_execution must be CognitionExecutionTrace or None"
            )
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if type(self.shadow) is not bool:
            raise TypeError("shadow must be bool")
        if type(self.context_active) is not bool:
            raise TypeError("context_active must be bool")
