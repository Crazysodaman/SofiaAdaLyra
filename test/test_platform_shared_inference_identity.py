"""Shared inference identity, context isolation and provenance regressions."""
from uuid import UUID

import pytest

from sofia.platform.inference import (
    ContextIsolationError, ConversationContextStore, EvidenceLevel,
    GamingPolicy, ModelSubstitutionError, ProviderPolicy, WorkloadClass,
)
from test._shared_inference_support import (
    MODEL, OTHER_MODEL, AdmissionStub, FakeBackend, build_adapter, core, user,
)


def test_context_is_isolated_per_core_and_returns_independent_copies() -> None:
    store = ConversationContextStore()
    first, second = core(1), core(2)
    initial = store.append(first, "conv:shared", (user("alpha"),))
    store.append(second, "conv:shared", (user("beta"),))

    assert [item.content for item in initial.messages] == ["alpha"]
    assert [
        item.content for item in store.snapshot(first, "conv:shared").messages
    ] == ["alpha"]
    assert [
        item.content for item in store.snapshot(second, "conv:shared").messages
    ] == ["beta"]

    store.append(first, "conv:shared", (user("alpha-two"),))
    assert [item.content for item in initial.messages] == ["alpha"]


def test_stale_core_generation_cannot_reuse_or_append_context() -> None:
    store = ConversationContextStore()
    newest = core(1, generation=2)
    stale = core(1, generation=1)
    store.append(newest, "conv", (user("new writer"),))
    with pytest.raises(ContextIsolationError, match="stale"):
        store.snapshot(stale, "conv")
    with pytest.raises(ContextIsolationError, match="stale"):
        store.append(stale, "conv", (user("old writer"),))


def test_adapter_returns_exact_provider_model_and_simulated_provenance() -> None:
    backend = FakeBackend()
    adapter = build_adapter(backend=backend)
    owner = core(7)
    submitted = adapter.submit(
        request_id="req:one", core=owner, conversation_id="conv:seven",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=64,
    )
    assert submitted.accepted and submitted.job is not None

    outcome = adapter.dispatch_next(now=1_000.0)
    result = outcome.result
    assert result is not None
    assert result.model == MODEL
    assert result.model.provider == "ollama"
    assert result.model.digest == MODEL.digest
    assert result.evidence_level is EvidenceLevel.SIMULATED
    assert result.simulated is True
    assert result.cloud_fallback is False
    assert result.cpu_fallback is False
    assert result.core_id == owner.core_id
    assert result.conversation_id == "conv:seven"
    assert len(result.output_sha256) == 64
    assert backend.calls[0].messages[0].content == "hello"


def test_backend_model_substitution_is_rejected_not_relabelled() -> None:
    backend = FakeBackend(answer_model=OTHER_MODEL)
    adapter = build_adapter(backend=backend)
    assert adapter.submit(
        request_id="req:sub", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=64,
    ).accepted

    with pytest.raises(ModelSubstitutionError):
        adapter.dispatch_next(now=1_000.0)

    telemetry = adapter.telemetry()
    assert telemetry.scheduler.failed == 1
    assert telemetry.backend_calls == 1


def test_uninstalled_exact_model_is_denied_without_download_or_cpu_fallback() -> None:
    backend = FakeBackend()
    adapter = build_adapter(backend=backend, installed=())
    decision = adapter.submit(
        request_id="req:cold", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=64,
    )
    assert decision.accepted is False
    assert "not installed" in (decision.reason or "")
    assert "CPU fallback" in (decision.reason or "")
    assert backend.calls == []
    assert adapter.telemetry().scheduler.queued == 0


def test_unauthorized_model_is_denied_without_cloud_fallback() -> None:
    backend = FakeBackend()
    adapter = build_adapter(
        backend=backend, policy=ProviderPolicy.local_only((OTHER_MODEL,)),
    )
    decision = adapter.submit(
        request_id="req:cloud", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.CORE_SOCIAL,
        messages=(user("hello"),), max_output_tokens=64,
    )
    assert decision.accepted is False
    assert "no cloud fallback" in (decision.reason or "")
    assert backend.calls == []


def test_platform_admission_denial_is_enforced_before_queueing() -> None:
    backend = FakeBackend()
    admission = AdmissionStub(allowed=False)
    adapter = build_adapter(backend=backend, admission=admission)
    decision = adapter.submit(
        request_id="req:denied", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=64,
    )
    assert decision.accepted is False
    assert "admission denied" in (decision.reason or "")
    assert admission.requests
    assert backend.calls == []


def test_request_messages_are_a_snapshot_not_a_live_context_alias() -> None:
    store = ConversationContextStore()
    owner = core(9)
    snapshot = store.append(owner, "conv:snapshot", (user("original"),))
    backend = FakeBackend()
    adapter = build_adapter(backend=backend)
    adapter.submit(
        request_id="req:snapshot", core=owner, conversation_id="conv:snapshot",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=snapshot.messages, max_output_tokens=64,
    )
    store.append(owner, "conv:snapshot", (user("later"),))
    outcome = adapter.dispatch_next(now=1_000.0)
    assert outcome.result is not None
    assert [
        item.content for item in backend.calls[0].messages
    ] == ["original"]
    assert [
        item.content for item in store.snapshot(owner, "conv:snapshot").messages
    ] == ["original", "later"]


def test_request_carries_core_uuid_and_platform_identity() -> None:
    adapter = build_adapter()
    owner = core(11)
    job = adapter.submit(
        request_id="req:identity", core=owner, conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=64,
    )
    assert job.job is not None
    request = job.job.request
    assert isinstance(request.core.core_id, UUID)
    assert request.core.platform_id == "platform:test"
    assert request.core.generation == 1

def test_one_backend_serves_two_cores_without_prompt_mixing() -> None:
    backend = FakeBackend(echo=True)
    adapter = build_adapter(
        backend=backend,
        gaming=GamingPolicy(allow_background_preload=True),
    )
    first, second = core(21), core(22)
    for owner, text, request_id in (
        (first, "only-alpha", "req:alpha"),
        (second, "only-beta", "req:beta"),
    ):
        assert adapter.submit(
            request_id=request_id, core=owner, conversation_id="conv:shared",
            workload_class=WorkloadClass.CORE_SOCIAL,
            messages=(user(text),), max_output_tokens=10,
        ).accepted

    alpha = adapter.dispatch_next(now=1_000.0)
    beta = adapter.dispatch_next(now=1_000.0)
    assert alpha.result is not None and beta.result is not None
    assert alpha.result.core_id == first.core_id
    assert beta.result.core_id == second.core_id
    assert alpha.result.text == "echo:only-alpha"
    assert beta.result.text == "echo:only-beta"
    assert backend.calls[0].messages[0].content == "only-alpha"
    assert backend.calls[1].messages[0].content == "only-beta"
