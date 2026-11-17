"""Per-Core inference binding over the shared Platform inference coordinator.

This module is a thin, authority-aware projection over
:mod:`sofia.platform.inference`.  It adds exact per-Core conversation binding,
independent prompt assembly, per-Core model selection and restart-aware
evidence.  It never installs a model, downloads remote bytes, substitutes a
different model, or falls back to a cloud provider.

Platform/Fleet admission remains the external authority.  Constructing a
binding grants no permission to generate text; every submission is still
admitted by the injected Platform/Fleet authority and by the optional
SAFE/STOP gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import BoundedSemaphore, RLock
from time import monotonic
from typing import Callable, Iterable, Mapping, Protocol
from uuid import UUID

from sofia.platform.inference import (
    AdmissionAuthority,
    BudgetLedger,
    CancellationResult,
    CapacityDecision,
    CapacitySource,
    ConversationContextStore,
    ConversationKey,
    CoreIdentity as InferenceCoreIdentity,
    FairInferenceScheduler,
    GamingPolicy,
    InferenceBackend,
    InferenceResult,
    JobState,
    ModelFootprint,
    ModelIdentity,
    ProviderPolicy,
    PromptMessage,
    SchedulerLimits,
    SharedInferenceAdapter,
    SubmitDecision,
    WorkloadClass,
)


class CoreInferenceError(RuntimeError):
    """Base class for per-Core inference binding failures."""


class CoreInferenceDenied(PermissionError):
    """A SAFE boundary denied inference for this Core or conversation."""


class OperatorStopActive(CoreInferenceDenied):
    """The Platform operator STOP boundary is active."""


class CoreBindingError(CoreInferenceError):
    """A Core binding is missing, stale or conflicting."""


class UnknownCoreBinding(CoreBindingError):
    """No registration or conversation binding exists for the request."""


class StaleCoreGeneration(CoreBindingError):
    """A superseded Core generation cannot read or submit inference."""


class CoreInferenceConflict(CoreBindingError):
    """A registration, request or conversation binding conflicts."""


class CrossCoreContextError(CoreInferenceError):
    """A caller attempted to reuse another Core's conversation or job."""


class UnsupportedCoreModel(CoreInferenceError):
    """The selected model is not configured; no fallback is attempted."""


class UnknownInferenceJob(CoreInferenceError):
    """A job identifier is not known to this coordinator."""


class InferenceSafety(Protocol):
    """Optional SAFE boundary; absent means no additional local denial."""

    def is_operator_stopped(self) -> bool:
        ...

    def permits_inference(self, *, core_id: UUID, conversation_id: str) -> bool:
        ...


@dataclass(frozen=True, slots=True)
class CoreInferenceProfile:
    """Exact independently selected inference model for one Core generation."""

    core_id: UUID
    platform_id: str
    generation: int
    display_name: str
    model: ModelIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        # CoreIdentity validates UUID, platform, generation and display bounds.
        _ = self.identity

    @property
    def identity(self) -> InferenceCoreIdentity:
        return InferenceCoreIdentity(
            self.core_id,
            self.platform_id,
            self.generation,
            self.display_name,
        )


@dataclass(frozen=True, slots=True)
class CoreInferenceBinding:
    """Exact ``(Core, Platform, generation, conversation)`` inference binding."""

    profile: CoreInferenceProfile
    conversation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.profile, CoreInferenceProfile):
            raise TypeError("profile must be CoreInferenceProfile")
        # ConversationKey validates the exact bounded conversation identifier.
        _ = self.key

    @property
    def key(self) -> ConversationKey:
        return self.profile.identity.conversation_key(self.conversation_id)

    @property
    def core_id(self) -> UUID:
        return self.profile.core_id

    @property
    def platform_id(self) -> str:
        return self.profile.platform_id

    @property
    def generation(self) -> int:
        return self.profile.generation

    @property
    def model(self) -> ModelIdentity:
        return self.profile.model


@dataclass(frozen=True, slots=True)
class InferenceProvenance:
    """Explicit identity, provider/model and evidence for one result."""

    request_id: str
    core_id: UUID
    platform_id: str
    core_generation: int
    conversation_id: str
    provider: str
    model: str
    model_digest: str
    evidence_level: str
    simulated: bool
    output_sha256: str

    @property
    def model_label(self) -> str:
        return f"{self.provider}:{self.model}@{self.model_digest}"


@dataclass(frozen=True, slots=True)
class CoreInferenceOutcome:
    """Completed text result bound to the exact Core conversation."""

    binding: CoreInferenceBinding
    result: InferenceResult

    def __post_init__(self) -> None:
        if not isinstance(self.binding, CoreInferenceBinding):
            raise TypeError("binding must be CoreInferenceBinding")
        if not isinstance(self.result, InferenceResult):
            raise TypeError("result must be InferenceResult")

    @property
    def provenance(self) -> InferenceProvenance:
        result = self.result
        return InferenceProvenance(
            request_id=result.request_id,
            core_id=result.core_id,
            platform_id=result.platform_id,
            core_generation=result.core_generation,
            conversation_id=result.conversation_id,
            provider=result.model.provider,
            model=result.model.model,
            model_digest=result.model.digest,
            evidence_level=result.evidence_level.value,
            simulated=result.simulated,
            output_sha256=result.output_sha256,
        )


@dataclass(frozen=True, slots=True)
class CoreInferenceFailure:
    """Truthful record of a failed, cancelled, expired or uncertain job."""

    binding: CoreInferenceBinding
    request_id: str
    job_id: str
    reason: str
    occurred_at: float
    uncertain: bool


@dataclass(frozen=True, slots=True)
class CoreInferencePending:
    """Accepted work whose outcome has not yet been journaled."""

    binding: CoreInferenceBinding
    request_id: str
    job_id: str
    submitted_at: float


@dataclass(frozen=True, slots=True)
class CoreInferenceSubmission:
    """Result of one submission attempt before any provider execution."""

    accepted: bool
    binding: CoreInferenceBinding
    job_id: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class CoreInferenceDispatch:
    """One dispatch step with exact Core provenance when text was produced."""

    binding: CoreInferenceBinding | None
    result: InferenceResult | None
    provenance: InferenceProvenance | None
    reason: str | None
    capacity: CapacityDecision | None = None
    evidence_level: str | None = None
    job_state: JobState | None = None


class CoreInferenceJournal(Protocol):
    """Durable-enough evidence seam for bindings, context and outcomes."""

    def latest_generation(self, core_id: UUID, platform_id: str) -> int | None:
        ...

    def record_registration(self, profile: CoreInferenceProfile) -> None:
        ...

    def registration(
        self, core_id: UUID, platform_id: str, generation: int,
    ) -> CoreInferenceProfile | None:
        ...

    def registrations(self) -> tuple[CoreInferenceProfile, ...]:
        ...

    def record_binding(self, binding: CoreInferenceBinding) -> None:
        ...

    def binding(
        self, core_id: UUID, platform_id: str, generation: int,
        conversation_id: str,
    ) -> CoreInferenceBinding | None:
        ...

    def bindings(self) -> tuple[CoreInferenceBinding, ...]:
        ...

    def record_context(
        self, binding: CoreInferenceBinding,
        messages: tuple[PromptMessage, ...],
    ) -> None:
        ...

    def context(
        self, binding: CoreInferenceBinding,
    ) -> tuple[PromptMessage, ...]:
        ...

    def record_pending(self, pending: CoreInferencePending) -> None:
        ...

    def pending(self) -> tuple[CoreInferencePending, ...]:
        ...

    def resolve_pending(self, job_id: str) -> None:
        ...

    def record_outcome(self, outcome: CoreInferenceOutcome) -> None:
        ...

    def outcomes(
        self, binding: CoreInferenceBinding,
    ) -> tuple[CoreInferenceOutcome, ...]:
        ...

    def record_failure(self, failure: CoreInferenceFailure) -> None:
        ...

    def failures(
        self, binding: CoreInferenceBinding,
    ) -> tuple[CoreInferenceFailure, ...]:
        ...


class InMemoryCoreInferenceJournal:
    """Thread-safe in-process journal used by tests and disposable fixtures.

    It is intentionally not a production credential store.  Callers that need
    cross-process restart evidence can supply another object implementing
    :class:`CoreInferenceJournal`.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._latest: dict[tuple[UUID, str], int] = {}
        self._profiles: dict[
            tuple[UUID, str, int], CoreInferenceProfile
        ] = {}
        self._bindings: dict[
            tuple[UUID, str, int, str], CoreInferenceBinding
        ] = {}
        self._contexts: dict[ConversationKey, tuple[PromptMessage, ...]] = {}
        self._pending: dict[str, CoreInferencePending] = {}
        self._outcomes: dict[
            ConversationKey, list[CoreInferenceOutcome]
        ] = {}
        self._failures: dict[
            ConversationKey, list[CoreInferenceFailure]
        ] = {}

    def latest_generation(self, core_id: UUID, platform_id: str) -> int | None:
        with self._lock:
            return self._latest.get((core_id, platform_id))

    def record_registration(self, profile: CoreInferenceProfile) -> None:
        if not isinstance(profile, CoreInferenceProfile):
            raise TypeError("profile must be CoreInferenceProfile")
        with self._lock:
            key = (profile.core_id, profile.platform_id, profile.generation)
            existing = self._profiles.get(key)
            if existing is not None and existing != profile:
                raise CoreInferenceConflict(
                    "Core inference registration conflicts with existing evidence"
                )
            self._profiles[key] = profile
            identity = (profile.core_id, profile.platform_id)
            latest = self._latest.get(identity)
            self._latest[identity] = max(profile.generation, latest or 0)

    def registration(
        self, core_id: UUID, platform_id: str, generation: int,
    ) -> CoreInferenceProfile | None:
        with self._lock:
            return self._profiles.get((core_id, platform_id, generation))

    def registrations(self) -> tuple[CoreInferenceProfile, ...]:
        with self._lock:
            return tuple(
                self._profiles[key]
                for key in sorted(
                    self._profiles,
                    key=lambda item: (str(item[0]), item[1], item[2]),
                )
            )

    def record_binding(self, binding: CoreInferenceBinding) -> None:
        if not isinstance(binding, CoreInferenceBinding):
            raise TypeError("binding must be CoreInferenceBinding")
        with self._lock:
            key = (
                binding.core_id, binding.platform_id,
                binding.generation, binding.conversation_id,
            )
            existing = self._bindings.get(key)
            if existing is not None and existing != binding:
                raise CoreInferenceConflict(
                    "conversation inference binding conflicts with existing evidence"
                )
            self._bindings[key] = binding

    def binding(
        self, core_id: UUID, platform_id: str, generation: int,
        conversation_id: str,
    ) -> CoreInferenceBinding | None:
        with self._lock:
            return self._bindings.get(
                (core_id, platform_id, generation, conversation_id)
            )

    def bindings(self) -> tuple[CoreInferenceBinding, ...]:
        with self._lock:
            return tuple(
                self._bindings[key]
                for key in sorted(
                    self._bindings,
                    key=lambda item: (str(item[0]), item[1], item[2], item[3]),
                )
            )

    def record_context(
        self, binding: CoreInferenceBinding,
        messages: tuple[PromptMessage, ...],
    ) -> None:
        if not isinstance(binding, CoreInferenceBinding):
            raise TypeError("binding must be CoreInferenceBinding")
        prepared = tuple(messages)
        if any(not isinstance(message, PromptMessage) for message in prepared):
            raise TypeError("messages must contain PromptMessage values")
        with self._lock:
            self._contexts[binding.key] = prepared

    def context(
        self, binding: CoreInferenceBinding,
    ) -> tuple[PromptMessage, ...]:
        with self._lock:
            return self._contexts.get(binding.key, ())

    def record_pending(self, pending: CoreInferencePending) -> None:
        if not isinstance(pending, CoreInferencePending):
            raise TypeError("pending must be CoreInferencePending")
        with self._lock:
            if pending.job_id in self._pending:
                raise CoreInferenceConflict(
                    "inference job is already pending"
                )
            self._pending[pending.job_id] = pending

    def pending(self) -> tuple[CoreInferencePending, ...]:
        with self._lock:
            return tuple(
                self._pending[key]
                for key in sorted(
                    self._pending,
                    key=lambda item: (
                        self._pending[item].submitted_at, item,
                    ),
                )
            )

    def resolve_pending(self, job_id: str) -> None:
        with self._lock:
            self._pending.pop(job_id, None)

    def record_outcome(self, outcome: CoreInferenceOutcome) -> None:
        if not isinstance(outcome, CoreInferenceOutcome):
            raise TypeError("outcome must be CoreInferenceOutcome")
        with self._lock:
            self._outcomes.setdefault(outcome.binding.key, []).append(outcome)
            for job_id, pending in tuple(self._pending.items()):
                if pending.request_id == outcome.result.request_id:
                    self._pending.pop(job_id, None)

    def outcomes(
        self, binding: CoreInferenceBinding,
    ) -> tuple[CoreInferenceOutcome, ...]:
        with self._lock:
            return tuple(self._outcomes.get(binding.key, ()))

    def record_failure(self, failure: CoreInferenceFailure) -> None:
        if not isinstance(failure, CoreInferenceFailure):
            raise TypeError("failure must be CoreInferenceFailure")
        with self._lock:
            self._failures.setdefault(failure.binding.key, []).append(failure)

    def failures(
        self, binding: CoreInferenceBinding,
    ) -> tuple[CoreInferenceFailure, ...]:
        with self._lock:
            return tuple(self._failures.get(binding.key, ()))


def _rotated(items: tuple[SharedInferenceAdapter, ...], start: int):
    for offset in range(len(items)):
        yield items[(start + offset) % len(items)]


class MultiCoreInference:
    """Shared local provider with exact per-Core bindings and model selection.

    ``models`` must be an explicit, bounded mapping of already-authorized local
    exact models to measured footprints.  There is no default model, fallback
    list, download path or cloud routing.  One backend instance is shared by
    all model-specific adapters.
    """

    def __init__(
        self, *,
        backend: InferenceBackend,
        admission: AdmissionAuthority,
        models: Mapping[ModelIdentity, ModelFootprint] | Iterable[
            tuple[ModelIdentity, ModelFootprint]
        ],
        policy: ProviderPolicy,
        residency,
        capacity: CapacitySource,
        budgets: BudgetLedger,
        scheduler_limits: SchedulerLimits | None = None,
        gaming: GamingPolicy | None = None,
        clock: Callable[[], float] = monotonic,
        max_parallel: int = 1,
        keep_alive_seconds: float | None = None,
        journal: CoreInferenceJournal | None = None,
        safety: InferenceSafety | None = None,
    ) -> None:
        if not isinstance(policy, ProviderPolicy):
            raise TypeError("policy must be ProviderPolicy")
        if policy.allow_cloud_fallback:
            raise CoreInferenceDenied(
                "shared multi-Core inference never permits cloud fallback"
            )
        if gaming is not None and not isinstance(gaming, GamingPolicy):
            raise TypeError("gaming must be GamingPolicy")
        if gaming is not None and gaming.allow_cloud_fallback:
            raise CoreInferenceDenied(
                "gaming policy may not authorize a cloud fallback"
            )
        if type(max_parallel) is not int or not 1 <= max_parallel <= 8:
            raise ValueError("max_parallel must be in 1..8")
        if not callable(clock):
            raise TypeError("clock must be callable")
        if journal is not None and not isinstance(
            journal, InMemoryCoreInferenceJournal
        ) and not all(
            callable(getattr(journal, method, None))
            for method in (
                "latest_generation", "record_registration", "registration",
                "registrations", "record_binding", "binding", "bindings",
                "record_context", "context", "record_pending", "pending",
                "resolve_pending", "record_outcome", "outcomes",
                "record_failure", "failures",
            )
        ):
            raise TypeError("journal must implement CoreInferenceJournal")
        if safety is not None and not all(
            callable(getattr(safety, method, None))
            for method in ("is_operator_stopped", "permits_inference")
        ):
            raise TypeError("safety must expose STOP and inference permission")

        supplied = models.items() if isinstance(models, Mapping) else models
        resolved: dict[ModelIdentity, ModelFootprint] = {}
        for model, footprint in supplied:
            if not isinstance(model, ModelIdentity):
                raise TypeError("every configured model must be ModelIdentity")
            if not isinstance(footprint, ModelFootprint):
                raise TypeError("every model footprint must be ModelFootprint")
            if model in resolved:
                raise CoreInferenceConflict("duplicate configured model")
            if not policy.allows(model):
                raise UnsupportedCoreModel(
                    "every configured model must be explicitly authorized"
                )
            resolved[model] = footprint
        if not resolved:
            raise ValueError("at least one authorized local model is required")
        self._lock = RLock()
        self._backend = backend
        self._policy = policy
        self._max_parallel = max_parallel
        self._clock = clock
        self._journal = (
            journal if journal is not None else InMemoryCoreInferenceJournal()
        )
        self._safety = safety
        self._contexts = ConversationContextStore()
        self._limits = scheduler_limits or SchedulerLimits(
            max_active=max_parallel,
            max_queue_per_core=8,
            max_pending_per_conversation=4,
        )
        self._adapters: dict[ModelIdentity, SharedInferenceAdapter] = {
            model: SharedInferenceAdapter(
                backend=backend,
                admission=admission,
                model=model,
                footprint=footprint,
                policy=policy,
                residency=residency,
                capacity=capacity,
                budgets=budgets,
                scheduler=FairInferenceScheduler(self._limits),
                gaming=gaming,
                clock=clock,
                max_parallel=max_parallel,
                keep_alive_seconds=keep_alive_seconds,
            )
            for model, footprint in resolved.items()
        }
        self._models = tuple(self._adapters)
        self._slots = BoundedSemaphore(max_parallel)
        self._profiles: dict[
            tuple[UUID, str, int], CoreInferenceProfile
        ] = {}
        self._bindings: dict[
            tuple[UUID, str, int, str], CoreInferenceBinding
        ] = {}
        self._request_bindings: dict[str, CoreInferenceBinding] = {}
        self._jobs: dict[
            str, tuple[CoreInferenceBinding, SharedInferenceAdapter, str]
        ] = {}
        self._reported: set[str] = set()
        self._dispatch_turn = 0
        self._restore()

    def _now(self, now: float | None) -> float:
        moment = self._clock() if now is None else now
        if type(moment) not in (int, float):
            raise ValueError("now must be numeric")
        return float(moment)

    def _restore(self) -> None:
        for profile in self._journal.registrations():
            if profile.model not in self._adapters:
                continue
            key = (profile.core_id, profile.platform_id, profile.generation)
            self._profiles.setdefault(key, profile)
        restored_bindings: list[CoreInferenceBinding] = []
        for binding in self._journal.bindings():
            profile_key = (
                binding.core_id, binding.platform_id, binding.generation,
            )
            profile = self._profiles.get(profile_key)
            if profile is None or profile.model != binding.model:
                continue
            self._bindings[
                (*profile_key, binding.conversation_id)
            ] = binding
            restored_bindings.append(binding)
        # Older generations restore first so generation fencing remains exact.
        for binding in sorted(
            restored_bindings,
            key=lambda item: (
                item.platform_id, str(item.core_id),
                item.generation, item.conversation_id,
            ),
        ):
            messages = self._journal.context(binding)
            if messages:
                self._contexts.replace(
                    binding.profile.identity,
                    binding.conversation_id,
                    messages,
                )
        for pending in self._journal.pending():
            key = (
                pending.binding.core_id,
                pending.binding.platform_id,
                pending.binding.generation,
                pending.binding.conversation_id,
            )
            if key not in self._bindings:
                continue
            adapter = self._adapters[pending.binding.model]
            self._request_bindings[pending.request_id] = pending.binding
            self._jobs[pending.job_id] = (
                pending.binding, adapter, pending.request_id,
            )
        for binding in self._bindings.values():
            for outcome in self._journal.outcomes(binding):
                self._request_bindings[
                    outcome.result.request_id
                ] = outcome.binding

    def _latest_generation(self, core_id: UUID, platform_id: str) -> int | None:
        return self._journal.latest_generation(core_id, platform_id)

    def register_core(
        self, *,
        core_id: UUID,
        platform_id: str,
        generation: int,
        display_name: str,
        model: ModelIdentity,
    ) -> CoreInferenceProfile:
        """Register one exact Core generation with its explicit local model."""
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        profile = CoreInferenceProfile(
            core_id, platform_id, generation, display_name, model,
        )
        if model not in self._adapters:
            raise UnsupportedCoreModel(
                "selected model is not configured; no substitution is permitted"
            )
        with self._lock:
            latest = self._latest_generation(core_id, platform_id)
            if latest is not None and generation < latest:
                raise StaleCoreGeneration(
                    "a newer Core generation is already recorded"
                )
            key = (core_id, platform_id, generation)
            existing = self._profiles.get(key)
            if existing is not None and existing != profile:
                raise CoreInferenceConflict(
                    "Core generation already has a different inference model"
                )
            self._journal.record_registration(profile)
            self._profiles[key] = profile
            return profile

    def registration(
        self, core_id: UUID, platform_id: str, generation: int,
    ) -> CoreInferenceProfile | None:
        with self._lock:
            return self._profiles.get((core_id, platform_id, generation))

    def open_conversation(
        self, *, core_id: UUID, platform_id: str, generation: int,
        conversation_id: str,
    ) -> CoreInferenceBinding:
        """Bind the exact Core/platform/generation/conversation tuple."""
        with self._lock:
            profile = self._profiles.get((core_id, platform_id, generation))
            if profile is None:
                raise UnknownCoreBinding("Core generation is not registered")
            latest = self._latest_generation(core_id, platform_id)
            if latest is not None and generation < latest:
                raise StaleCoreGeneration(
                    "a stale Core generation cannot open a conversation"
                )
            binding = CoreInferenceBinding(profile, conversation_id)
            existing = self._journal.binding(
                core_id, platform_id, generation, conversation_id,
            )
            if existing is not None:
                if existing != binding:
                    raise CrossCoreContextError(
                        "conversation is already bound to another Core identity"
                    )
                self._bindings[(*(
                    core_id, platform_id, generation,
                ), conversation_id)] = existing
                return existing
            self._journal.record_binding(binding)
            self._bindings[
                (core_id, platform_id, generation, conversation_id)
            ] = binding
            return binding

    def _validate(self, binding: CoreInferenceBinding) -> None:
        if not isinstance(binding, CoreInferenceBinding):
            raise TypeError("binding must be CoreInferenceBinding")
        key = (
            binding.core_id, binding.platform_id,
            binding.generation, binding.conversation_id,
        )
        with self._lock:
            known = self._bindings.get(key)
            if known is None:
                raise UnknownCoreBinding(
                    "conversation binding is not open for this Core generation"
                )
            if known != binding:
                raise CrossCoreContextError("conversation binding differs")
            latest = self._latest_generation(
                binding.core_id, binding.platform_id,
            )
            if latest is not None and binding.generation < latest:
                raise StaleCoreGeneration(
                    "a stale Core generation cannot use conversation inference"
                )

    def _check_safety(
        self, binding: CoreInferenceBinding | None = None,
    ) -> None:
        safety = self._safety
        if safety is None:
            return
        if safety.is_operator_stopped() is True:
            raise OperatorStopActive("operator STOP is active")
        if binding is not None and safety.permits_inference(
            core_id=binding.core_id,
            conversation_id=binding.conversation_id,
        ) is not True:
            raise CoreInferenceDenied(
                "SAFE policy does not permit inference for this conversation"
            )

    @staticmethod
    def _text_messages(messages) -> tuple[PromptMessage, ...]:
        prepared = tuple(messages)
        for message in prepared:
            if not isinstance(message, PromptMessage):
                raise TypeError(
                    "multi-Core inference accepts PromptMessage text only"
                )
            if type(message.content) is not str:
                raise TypeError(
                    "multi-Core inference is text-only; non-text content is denied"
                )
        return prepared

    def append_context(
        self, binding: CoreInferenceBinding, messages,
    ) -> tuple[PromptMessage, ...]:
        """Append text to exactly one Core generation's conversation."""
        self._validate(binding)
        prepared = self._text_messages(messages)
        snapshot = self._contexts.append(
            binding.profile.identity,
            binding.conversation_id,
            prepared,
        )
        self._journal.record_context(binding, snapshot.messages)
        return snapshot.messages

    def assemble_prompt(
        self, binding: CoreInferenceBinding, messages=(),
        *, include_history: bool = True,
    ) -> tuple[PromptMessage, ...]:
        """Independently assemble this Core's prompt with no shared state."""
        self._validate(binding)
        prepared = self._text_messages(messages)
        history = (
            self._contexts.snapshot(
                binding.profile.identity, binding.conversation_id,
            ).messages
            if include_history else ()
        )
        return tuple(history) + prepared

    def submit(
        self, binding: CoreInferenceBinding, *,
        request_id: str,
        messages=(),
        workload_class: WorkloadClass = WorkloadClass.CORE_SOCIAL,
        max_output_tokens: int,
        context_tokens: int = 4096,
        timeout_seconds: float = 120.0,
        include_history: bool = True,
        now: float | None = None,
    ) -> CoreInferenceSubmission:
        """Assemble, admit and queue one text-only generation request."""
        self._validate(binding)
        self._check_safety(binding)
        moment = self._now(now)
        prompt = self.assemble_prompt(
            binding, messages, include_history=include_history,
        )
        if not prompt:
            raise ValueError("a text prompt is required")
        with self._lock:
            if request_id in self._request_bindings:
                raise CoreInferenceConflict(
                    "request identifier is already bound to another submission"
                )
        adapter = self._adapters[binding.model]
        decision: SubmitDecision = adapter.submit(
            request_id=request_id,
            core=binding.profile.identity,
            conversation_id=binding.conversation_id,
            workload_class=workload_class,
            messages=prompt,
            max_output_tokens=max_output_tokens,
            context_tokens=context_tokens,
            timeout_seconds=timeout_seconds,
            now=moment,
        )
        if not decision.accepted or decision.job is None:
            return CoreInferenceSubmission(
                False, binding, None, decision.reason,
            )
        job_id = decision.job.job_id
        pending = CoreInferencePending(
            binding, request_id, job_id, moment,
        )
        with self._lock:
            self._request_bindings[request_id] = binding
            self._jobs[job_id] = (binding, adapter, request_id)
            self._journal.record_pending(pending)
        return CoreInferenceSubmission(True, binding, job_id, None)

    def _collect_terminal(
        self, adapter: SharedInferenceAdapter, now: float,
    ) -> None:
        with self._lock:
            known = tuple(self._jobs.items())
        for job_id, (binding, owner, request_id) in known:
            if owner is not adapter or job_id in self._reported:
                continue
            view = adapter.scheduler.status(job_id)
            if view is None:
                continue
            state = view.state
            if state is JobState.COMPLETED:
                continue
            if state is JobState.FAILED:
                reason, uncertain = (
                    view.reason or "backend generation failed", False,
                )
            elif state is JobState.EXPIRED:
                reason, uncertain = (
                    view.reason or "queued request deadline expired", False,
                )
            elif state is JobState.CANCELLED:
                reason, uncertain = (
                    view.reason or "inference request cancelled", False,
                )
            elif state is JobState.TIMED_OUT:
                reason, uncertain = (
                    view.reason or "in-flight request deadline expired", True,
                )
            elif state is JobState.OUTCOME_UNCERTAIN:
                reason, uncertain = (
                    view.reason or "backend outcome is uncertain", True,
                )
            else:
                continue
            failure = CoreInferenceFailure(
                binding, request_id, job_id, reason, now, uncertain,
            )
            self._journal.record_failure(failure)
            if not uncertain:
                self._journal.resolve_pending(job_id)
            self._reported.add(job_id)

    def _result_binding(self, result: InferenceResult) -> CoreInferenceBinding:
        binding = self._request_bindings.get(result.request_id)
        if binding is None:
            raise CoreInferenceError(
                "backend result has no bound Core conversation"
            )
        if (
            result.core_id != binding.core_id
            or result.platform_id != binding.platform_id
            or result.core_generation != binding.generation
            or result.conversation_id != binding.conversation_id
            or result.model != binding.model
        ):
            raise CrossCoreContextError(
                "backend result identity does not match the admitted binding"
            )
        return binding

    def _record_result(
        self, result: InferenceResult,
    ) -> CoreInferenceOutcome:
        binding = self._result_binding(result)
        outcome = CoreInferenceOutcome(binding, result)
        with self._lock:
            self._journal.record_outcome(outcome)
            for job_id, (owner, _, request_id) in tuple(self._jobs.items()):
                if request_id == result.request_id and owner.key == binding.key:
                    self._journal.resolve_pending(job_id)
                    self._reported.discard(job_id)
                    break
        return outcome

    def dispatch_next(self, now: float | None = None) -> CoreInferenceDispatch:
        """Run at most one queued generation under global bounded concurrency."""
        self._check_safety()
        moment = self._now(now)
        if not self._slots.acquire(blocking=False):
            return CoreInferenceDispatch(
                None, None, None,
                "global bounded concurrency saturated",
            )
        try:
            with self._lock:
                start = self._dispatch_turn
                self._dispatch_turn = (self._dispatch_turn + 1) % len(
                    self._models
                )
            first_reason: CoreInferenceDispatch | None = None
            for adapter in _rotated(
                tuple(self._adapters[model] for model in self._models), start,
            ):
                try:
                    outcome = adapter.dispatch_next(now=moment)
                except Exception:
                    self._collect_terminal(adapter, moment)
                    raise
                self._collect_terminal(adapter, moment)
                if outcome.result is not None:
                    completed = self._record_result(outcome.result)
                    return CoreInferenceDispatch(
                        completed.binding,
                        completed.result,
                        completed.provenance,
                        None,
                        outcome.capacity,
                        outcome.evidence_level,
                        outcome.job_state,
                    )
                if outcome.job_state is not None:
                    candidate = CoreInferenceDispatch(
                        None, None, None, outcome.reason, outcome.capacity,
                        outcome.evidence_level, outcome.job_state,
                    )
                    if outcome.job_state is JobState.DEFERRED:
                        first_reason = first_reason or candidate
                        continue
                    return candidate
                if outcome.reason != "no admissible inference request":
                    first_reason = first_reason or CoreInferenceDispatch(
                        None, None, None, outcome.reason, outcome.capacity,
                        outcome.evidence_level, None,
                    )
            return first_reason or CoreInferenceDispatch(
                None, None, None, "no admissible inference request",
            )
        finally:
            self._slots.release()

    def cancel(
        self, binding: CoreInferenceBinding, job_id: str,
        now: float | None = None,
    ) -> CancellationResult:
        """Cancel only a job that belongs to the exact supplied binding."""
        self._validate(binding)
        moment = self._now(now)
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is None:
                raise UnknownInferenceJob("inference job is not known")
            owner, adapter, _ = entry
            if owner.key != binding.key:
                raise CrossCoreContextError(
                    "cannot cancel another Core's inference job"
                )
        result = adapter.cancel(job_id, now=moment)
        self._collect_terminal(adapter, moment)
        return result

    def timeouts(self, now: float | None = None) -> tuple[str, ...]:
        """Expire queued work and mark in-flight work timed out truthfully."""
        moment = self._now(now)
        changed: list[str] = []
        for adapter in self._adapters.values():
            changed.extend(adapter.timeouts(now=moment))
            self._collect_terminal(adapter, moment)
        return tuple(changed)

    def reconcile(
        self, binding: CoreInferenceBinding, job_id: str, *,
        completed: bool,
        output=None,
        now: float | None = None,
    ) -> InferenceResult | None:
        """Resolve an uncertain/timed-out job without automatic resubmission."""
        self._validate(binding)
        moment = self._now(now)
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry is None:
                raise UnknownInferenceJob("inference job is not known")
            owner, adapter, _ = entry
            if owner.key != binding.key:
                raise CrossCoreContextError(
                    "cannot reconcile another Core's inference job"
                )
        result = adapter.reconcile(
            job_id, completed=completed, output=output, now=moment,
        )
        self._collect_terminal(adapter, moment)
        if result is not None:
            self._record_result(result)
        return result

    def results(
        self, binding: CoreInferenceBinding,
    ) -> tuple[CoreInferenceOutcome, ...]:
        self._validate(binding)
        return self._journal.outcomes(binding)

    def failures(
        self, binding: CoreInferenceBinding,
    ) -> tuple[CoreInferenceFailure, ...]:
        self._validate(binding)
        return self._journal.failures(binding)

    def pending(self) -> tuple[CoreInferencePending, ...]:
        return self._journal.pending()

    def recover_after_restart(
        self, now: float | None = None,
    ) -> tuple[CoreInferenceFailure, ...]:
        """Report unfinished accepted work as unknown; never retry it."""
        moment = self._now(now)
        recovered: list[CoreInferenceFailure] = []
        for item in self._journal.pending():
            failure = CoreInferenceFailure(
                item.binding,
                item.request_id,
                item.job_id,
                "provider restarted before job completion; outcome unknown",
                moment,
                True,
            )
            self._journal.record_failure(failure)
            self._journal.resolve_pending(item.job_id)
            self._reported.add(item.job_id)
            recovered.append(failure)
        return tuple(recovered)

    def telemetry(self) -> tuple[dict[str, object], ...]:
        """Read-only aggregate; each entry retains its exact model identity."""
        rows = []
        for model in self._models:
            adapter = self._adapters[model]
            data = adapter.telemetry()
            rows.append({
                "model": model.label,
                "provider": model.provider,
                "model_name": model.model,
                "digest": model.digest,
                "backend_calls": data.backend_calls,
                "capacity_denials": data.capacity_denials,
                "scheduler": data.scheduler,
                "residency": data.residency,
            })
        return tuple(rows)
