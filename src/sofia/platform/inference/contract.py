"""Provider-neutral request/result contract for shared inference.

The contract is deliberately smaller than Core cognition.  It keeps exact
provider/model identity, per-request message snapshots and explicit output
provenance so a shared scheduler can never blend one Core's context into
another's answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re
from uuid import UUID

from .identity import CoreIdentity

_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,199}$")
_REQUEST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MAX_MESSAGE_BYTES = 1_400_000
MAX_SINGLE_MESSAGE_BYTES = 256 * 1024


class SharedInferenceError(RuntimeError):
    """Base class for shared inference failures."""


class InferenceDenied(PermissionError):
    """A request is not authorized by explicit provider/model policy."""


class DuplicateInferenceRequest(SharedInferenceError):
    """A request identifier was reused with different semantics."""


class QueuePressureError(SharedInferenceError):
    """Per-Core or per-conversation queue pressure limit was reached."""


class BudgetExceeded(InferenceDenied):
    """A per-Core or per-conversation inference budget was exhausted."""


class CapacityDenied(SharedInferenceError):
    """Current capacity or telemetry cannot admit the operation."""


class ModelNotInstalled(InferenceDenied):
    """The exact pinned model is not installed; no download is authorized."""


class ModelResidencyError(SharedInferenceError):
    """A loaded model cannot be changed without violating residency rules."""


class ModelSubstitutionError(SharedInferenceError):
    """The backend answered with a different provider/model identity."""


class InvalidBackendOutput(SharedInferenceError):
    """A backend result is structurally unusable or claims no generation."""


class WorkloadClass(str, Enum):
    """Neutral priority classes; no Core-specific policy is encoded here."""

    FOREGROUND_OWNER = "foreground_owner"
    CORE_SOCIAL = "core_social"
    BENCHMARK = "benchmark"

    @property
    def priority(self) -> int:
        return {
            WorkloadClass.FOREGROUND_OWNER: 0,
            WorkloadClass.CORE_SOCIAL: 1,
            WorkloadClass.BENCHMARK: 2,
        }[self]

    @property
    def autonomous_background(self) -> bool:
        return self in {WorkloadClass.CORE_SOCIAL, WorkloadClass.BENCHMARK}


class EvidenceLevel(str, Enum):
    SIMULATED = "simulated"
    OBSERVED = "observed"


class PromptRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Exact provider, model and digest; never a family or alias."""

    provider: str
    model: str
    digest: str

    def __post_init__(self) -> None:
        if type(self.provider) is not str or _PROVIDER.fullmatch(self.provider) is None:
            raise ValueError("provider must be a bounded lowercase identifier")
        if type(self.model) is not str or _MODEL.fullmatch(self.model) is None:
            raise ValueError("model must be an exact bounded model identifier")
        if type(self.digest) is not str or _DIGEST.fullmatch(self.digest) is None:
            raise ValueError("model digest must be lowercase SHA-256")

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}@{self.digest}"


@dataclass(frozen=True, slots=True)
class PromptMessage:
    role: PromptRole
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, PromptRole):
            raise TypeError("role must be PromptRole")
        if type(self.content) is not str:
            raise TypeError("message content must be text")
        try:
            encoded = self.content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("message content must be valid UTF-8") from exc
        if len(encoded) > MAX_SINGLE_MESSAGE_BYTES:
            raise ValueError("message content exceeds the bounded transport limit")


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """One Core's independently assembled generation request."""

    request_id: str
    core: CoreIdentity
    conversation_id: str
    workload_class: WorkloadClass
    messages: tuple[PromptMessage, ...]
    model: ModelIdentity
    context_tokens: int
    max_output_tokens: int
    timeout_seconds: float
    keep_alive: str | None = None

    def __post_init__(self) -> None:
        if type(self.request_id) is not str or _REQUEST.fullmatch(self.request_id) is None:
            raise ValueError("request_id must be a bounded identifier")
        if not isinstance(self.core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        if type(self.conversation_id) is not str or _REQUEST.fullmatch(
            self.conversation_id
        ) is None:
            raise ValueError("conversation_id must be a bounded identifier")
        if not isinstance(self.workload_class, WorkloadClass):
            raise TypeError("workload_class must be WorkloadClass")
        if not isinstance(self.model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        if type(self.messages) is not tuple or not self.messages or any(
            not isinstance(message, PromptMessage) for message in self.messages
        ):
            raise ValueError("messages must be a nonempty tuple of PromptMessage")
        encoded = 0
        for message in self.messages:
            encoded += len(message.content.encode("utf-8"))
            if _CONTROL.search(message.content) is not None:
                raise ValueError("messages must not contain control characters")
        if encoded > MAX_MESSAGE_BYTES:
            raise ValueError("assembled prompt exceeds the bounded transport limit")
        if type(self.context_tokens) is not int or not 1 <= self.context_tokens <= 1_048_576:
            raise ValueError("context_tokens must be in 1..1048576")
        if type(self.max_output_tokens) is not int or not (
            1 <= self.max_output_tokens <= 131_072
        ):
            raise ValueError("max_output_tokens must be in 1..131072")
        if type(self.timeout_seconds) not in (int, float) or not (
            0.1 <= float(self.timeout_seconds) <= 600.0
        ):
            raise ValueError("timeout_seconds must be in 0.1..600")
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        if self.keep_alive is not None and (
            type(self.keep_alive) is not str
            or not self.keep_alive.strip()
            or len(self.keep_alive) > 64
        ):
            raise ValueError("keep_alive must be a bounded nonempty string or None")

    @property
    def conversation_key(self):
        return self.core.conversation_key(self.conversation_id)


@dataclass(frozen=True, slots=True)
class ProviderPolicy:
    """Explicit local provider authorization; there is no fallback list."""

    authorized_models: tuple[ModelIdentity, ...]
    allow_cloud_fallback: bool = False
    allow_cpu_fallback: bool = False
    allow_downloads: bool = False

    def __post_init__(self) -> None:
        if type(self.authorized_models) is not tuple or not self.authorized_models or any(
            not isinstance(model, ModelIdentity) for model in self.authorized_models
        ):
            raise ValueError("authorized_models must be a nonempty tuple")
        if len(set(self.authorized_models)) != len(self.authorized_models):
            raise ValueError("authorized_models must be unique")
        for value in (
            self.allow_cloud_fallback, self.allow_cpu_fallback, self.allow_downloads,
        ):
            if type(value) is not bool:
                raise TypeError("provider policy flags must be booleans")

    @classmethod
    def local_only(cls, models: tuple[ModelIdentity, ...]) -> "ProviderPolicy":
        return cls(models)

    def allows(self, model: ModelIdentity) -> bool:
        if not isinstance(model, ModelIdentity):
            return False
        return model in self.authorized_models

    @property
    def providers(self) -> frozenset[str]:
        return frozenset(model.provider for model in self.authorized_models)


@dataclass(frozen=True, slots=True)
class GenerationCall:
    """Bounded backend work item; messages are an immutable snapshot."""

    job_id: str
    request: InferenceRequest
    model: ModelIdentity
    messages: tuple[PromptMessage, ...]
    context_tokens: int
    max_output_tokens: int
    keep_alive: str | None
    deadline_at: float

    def __post_init__(self) -> None:
        if self.model != self.request.model:
            raise ValueError("generation model must match the request")
        if self.messages != self.request.messages:
            raise ValueError("generation messages must be the request snapshot")
        if self.context_tokens != self.request.context_tokens:
            raise ValueError("generation context must match the request")
        if self.max_output_tokens != self.request.max_output_tokens:
            raise ValueError("generation output budget must match the request")


@dataclass(frozen=True, slots=True)
class BackendOutput:
    """Opaque backend result that must echo the exact admitted identity."""

    model: ModelIdentity
    text: str
    prompt_tokens: int
    generated_tokens: int
    time_to_first_token_ms: float
    total_duration_ms: float
    load_duration_ms: float = 0.0
    simulated: bool = False
    finish_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        if type(self.text) is not str:
            raise TypeError("text must be a string")
        try:
            self.text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("text must be valid UTF-8") from exc
        for label, value in (
            ("prompt_tokens", self.prompt_tokens),
            ("generated_tokens", self.generated_tokens),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        for label, value in (
            ("time_to_first_token_ms", self.time_to_first_token_ms),
            ("total_duration_ms", self.total_duration_ms),
            ("load_duration_ms", self.load_duration_ms),
        ):
            if type(value) not in (int, float) or float(value) < 0:
                raise ValueError(f"{label} must be non-negative")
        if float(self.total_duration_ms) < float(self.time_to_first_token_ms):
            raise ValueError("total duration cannot precede first token")
        if type(self.simulated) is not bool:
            raise TypeError("simulated must be bool")
        if self.finish_reason is not None and (
            type(self.finish_reason) is not str or len(self.finish_reason) > 64
        ):
            raise ValueError("finish_reason must be bounded text or None")

    @property
    def tokens_per_second(self) -> float:
        if self.total_duration_ms <= 0 or self.generated_tokens <= 0:
            return 0.0
        return self.generated_tokens / (self.total_duration_ms / 1000.0)


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Completed output with explicit provider/model and evidence provenance."""

    request_id: str
    core_id: UUID
    platform_id: str
    core_generation: int
    conversation_id: str
    workload_class: WorkloadClass
    model: ModelIdentity
    text: str
    output_sha256: str
    prompt_tokens: int
    generated_tokens: int
    time_to_first_token_ms: float
    total_duration_ms: float
    evidence_level: EvidenceLevel
    simulated: bool
    cloud_fallback: bool = False
    cpu_fallback: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        if not isinstance(self.evidence_level, EvidenceLevel):
            raise TypeError("evidence_level must be EvidenceLevel")
        if type(self.cloud_fallback) is not bool or type(self.cpu_fallback) is not bool:
            raise TypeError("fallback flags must be booleans")
        if self.cloud_fallback or self.cpu_fallback:
            raise ValueError("shared inference never reports an unauthorized fallback")
        if type(self.output_sha256) is not str or _DIGEST.fullmatch(
            self.output_sha256
        ) is None:
            raise ValueError("output_sha256 must be lowercase SHA-256")

    @classmethod
    def build(
        cls, request: InferenceRequest, output: BackendOutput,
    ) -> "InferenceResult":
        if not isinstance(request, InferenceRequest):
            raise TypeError("request must be InferenceRequest")
        if not isinstance(output, BackendOutput):
            raise TypeError("output must be BackendOutput")
        if output.model != request.model:
            raise ModelSubstitutionError(
                "backend returned a different provider/model/digest than admitted"
            )
        if output.generated_tokens < 1 or not output.text.strip():
            raise InvalidBackendOutput("backend returned no generated text")
        return cls(
            request_id=request.request_id,
            core_id=request.core.core_id,
            platform_id=request.core.platform_id,
            core_generation=request.core.generation,
            conversation_id=request.conversation_id,
            workload_class=request.workload_class,
            model=request.model,
            text=output.text,
            output_sha256=sha256(output.text.encode("utf-8")).hexdigest(),
            prompt_tokens=output.prompt_tokens,
            generated_tokens=output.generated_tokens,
            time_to_first_token_ms=float(output.time_to_first_token_ms),
            total_duration_ms=float(output.total_duration_ms),
            evidence_level=(
                EvidenceLevel.SIMULATED if output.simulated
                else EvidenceLevel.OBSERVED
            ),
            simulated=output.simulated,
        )
