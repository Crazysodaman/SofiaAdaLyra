"""Neutral shared-inference coordination for multiple Core identities.

Platform/Fleet remain the admission authority.  This package supplies the
social workload adapter, fair queue ordering, budgets, exact-model residency
and provenance for one already-authorized local backend.
"""
from .adapter import (
    AdapterTelemetry, AdmissionAuthority, CancellationResult, DispatchOutcome,
    InferenceBackend, PreloadDecision, SharedInferenceAdapter, SubmitDecision,
)
from .benchmark import (
    BenchmarkMeasurement, BenchmarkProfile, BenchmarkReport,
    RealBenchmarkApproval, SHARED_CONTEXT_TOKENS, SHARED_MODEL_FAMILY,
    SharedModelBenchmarkHarness,
)
from .budget import BudgetDecision, BudgetLedger, BudgetWindow, InferenceBudgetPolicy
from .context import (
    ContextIsolationError, ConversationContextStore, ConversationSnapshot,
)
from .contract import (
    BackendOutput, BudgetExceeded, CapacityDenied, DuplicateInferenceRequest,
    EvidenceLevel, GenerationCall, InferenceDenied, InferenceRequest,
    InferenceResult, InvalidBackendOutput, ModelIdentity, ModelNotInstalled,
    ModelResidencyError, ModelSubstitutionError, PromptMessage, PromptRole,
    ProviderPolicy, QueuePressureError, SharedInferenceError, WorkloadClass,
)
from .gaming import GamingDecision, GamingPolicy
from .identity import ConversationKey, CoreIdentity
from .residency import (
    ModelLoadDeferred, ModelResidencyTracker, ResidencyRecord, ResidencyTelemetry,
)
from .scheduler import (
    CancelOutcome, Claim, FairInferenceScheduler, JobState, JobView,
    SchedulerLimits, SchedulerSnapshot,
)
from .telemetry import (
    CapacityDecision, CapacitySource, HostCapacity, ModelFootprint,
    SequenceCapacitySource, StaticCapacitySource, admit_generation,
    effective_parallelism, verified_idle,
)

__all__ = [
    "AdapterTelemetry", "AdmissionAuthority", "BackendOutput", "BenchmarkMeasurement",
    "BenchmarkProfile", "BenchmarkReport", "BudgetDecision", "BudgetExceeded",
    "BudgetLedger", "BudgetWindow", "CancelOutcome", "CancellationResult",
    "CapacityDecision", "CapacityDenied", "CapacitySource", "Claim",
    "ContextIsolationError", "ConversationContextStore", "ConversationKey",
    "ConversationSnapshot", "CoreIdentity", "DispatchOutcome",
    "DuplicateInferenceRequest", "EvidenceLevel", "FairInferenceScheduler",
    "GamingDecision", "GamingPolicy", "GenerationCall", "HostCapacity",
    "InferenceBackend", "InferenceBudgetPolicy", "InferenceDenied",
    "InferenceRequest", "InferenceResult", "InvalidBackendOutput", "JobState",
    "JobView", "ModelFootprint", "ModelIdentity", "ModelLoadDeferred",
    "ModelNotInstalled", "ModelResidencyError", "ModelResidencyTracker",
    "ModelSubstitutionError", "PreloadDecision", "PromptMessage", "PromptRole",
    "ProviderPolicy", "QueuePressureError", "RealBenchmarkApproval",
    "ResidencyRecord", "ResidencyTelemetry", "SHARED_CONTEXT_TOKENS",
    "SHARED_MODEL_FAMILY", "SchedulerLimits", "SchedulerSnapshot", "SequenceCapacitySource",
    "SharedInferenceAdapter", "SharedInferenceError", "SharedModelBenchmarkHarness",
    "StaticCapacitySource", "SubmitDecision", "WorkloadClass",
    "admit_generation", "effective_parallelism", "verified_idle",
]
