"""Deterministic fakes shared by the shared-inference test modules."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sofia.platform.inference import (
    BackendOutput, BudgetLedger, BudgetWindow, CoreIdentity,
    FairInferenceScheduler, GamingPolicy, InferenceBudgetPolicy, InferenceRequest,
    ModelFootprint, ModelIdentity, ModelResidencyTracker, PromptMessage,
    PromptRole, ProviderPolicy, SchedulerLimits, SharedInferenceAdapter,
    StaticCapacitySource, WorkloadClass,
)
from sofia.platform.ops.activity import ActivityMode
from sofia.platform.inference.telemetry import HostCapacity

DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64
MODEL = ModelIdentity("ollama", "qwen3.5:9b", DIGEST)
OTHER_MODEL = ModelIdentity("ollama", "other:7b", OTHER_DIGEST)
CLOUD_MODEL = ModelIdentity("cloud", "remote:70b", "c" * 64)


def core(number: int, generation: int = 1) -> CoreIdentity:
    return CoreIdentity(UUID(int=number), "platform:test", generation, f"Core {number}")


def user(text: str) -> PromptMessage:
    return PromptMessage(PromptRole.USER, text)


def footprint(
    *, weights: int = 4_000, kv: int = 1_000, runtime: int = 500,
    headroom: int = 500, simulated: bool = True, measured: bool = True,
) -> ModelFootprint:
    return ModelFootprint(weights, kv, runtime, headroom, simulated, measured)


def capacity(
    *, now: float = 1_000.0, ttl: float = 120.0,
    vram_total: int = 16_000, vram_free: int = 12_000,
    activity: ActivityMode = ActivityMode.IDLE,
    simulated: bool = True, measured: bool = True,
    host: str = "host:test",
) -> HostCapacity:
    return HostCapacity(
        host_id=host, observed_at=now, expires_at=now + ttl,
        vram_total_bytes=vram_total, vram_free_bytes=vram_free,
        ram_total_bytes=32_000, ram_free_bytes=24_000,
        gpu_utilization_percent=2.0, activity=activity, source="sim:test",
        simulated=simulated, measured=measured,
    )


def budgets(
    *, core_requests: int = 20, conversation_requests: int = 20,
    core_tokens: int = 100_000, conversation_tokens: int = 100_000,
) -> BudgetLedger:
    return BudgetLedger(InferenceBudgetPolicy(
        BudgetWindow(core_requests, core_tokens, 60.0),
        BudgetWindow(conversation_requests, conversation_tokens, 60.0),
    ))


def request(
    *, request_id: str, owner=None, conversation_id: str = "conv:one",
    workload: WorkloadClass = WorkloadClass.FOREGROUND_OWNER,
    timeout: float = 120.0,
) -> InferenceRequest:
    return InferenceRequest(
        request_id=request_id,
        core=owner or core(1),
        conversation_id=conversation_id,
        workload_class=workload,
        messages=(user("hello"),),
        model=MODEL,
        context_tokens=4096,
        max_output_tokens=64,
        timeout_seconds=timeout,
    )


@dataclass
class FakeBackend:
    answer_model: ModelIdentity = MODEL
    simulated: bool = True
    text: str = "answer"
    fail: bool = False
    cancel_confirmed: bool = True
    echo: bool = False

    def __post_init__(self) -> None:
        self.calls = []
        self.cancelled = []

    def generate(self, call):
        self.calls.append(call)
        if self.fail:
            raise RuntimeError("simulated backend failure")
        text = (
            f"echo:{call.messages[-1].content}" if self.echo else self.text
        )
        return BackendOutput(
            model=self.answer_model,
            text=text,
            prompt_tokens=12,
            generated_tokens=3,
            time_to_first_token_ms=10.0,
            total_duration_ms=40.0,
            load_duration_ms=5.0,
            simulated=self.simulated,
            finish_reason="stop",
        )

    def cancel(self, job_id: str) -> bool:
        self.cancelled.append(job_id)
        return self.cancel_confirmed


@dataclass
class AdmissionStub:
    allowed: bool = True

    def __post_init__(self) -> None:
        self.requests = []

    def admit(self, request, now: float) -> bool:
        self.requests.append((request.request_id, now))
        return self.allowed


def build_adapter(
    *, backend=None, installed=(MODEL,), admission=None,
    source=None, activity: ActivityMode = ActivityMode.IDLE,
    max_parallel: int = 1, limits: SchedulerLimits | None = None,
    gaming: GamingPolicy | None = None, policy: ProviderPolicy | None = None,
    ledger=None, keep_alive_seconds: float | None = None,
    model: ModelIdentity = MODEL,
    model_footprint: ModelFootprint | None = None,
) -> SharedInferenceAdapter:
    resolved_footprint = model_footprint or footprint()
    snapshot = source if source is not None else StaticCapacitySource(
        capacity(activity=activity)
    )
    return SharedInferenceAdapter(
        backend=backend if backend is not None else FakeBackend(),
        admission=admission if admission is not None else AdmissionStub(),
        model=model,
        footprint=resolved_footprint,
        policy=policy if policy is not None else ProviderPolicy.local_only(
            (MODEL, OTHER_MODEL, CLOUD_MODEL)
        ),
        residency=ModelResidencyTracker(installed),
        capacity=snapshot,
        budgets=ledger if ledger is not None else budgets(),
        scheduler=FairInferenceScheduler(
            limits if limits is not None else SchedulerLimits(
                max_active=1, max_queue_per_core=20,
                max_pending_per_conversation=20,
            )
        ),
        gaming=gaming if gaming is not None else GamingPolicy(),
        clock=lambda: 1_000.0,
        max_parallel=max_parallel,
        keep_alive_seconds=keep_alive_seconds,
    )
