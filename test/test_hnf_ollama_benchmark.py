"""HNF-06 exact-installed-model Ollama benchmark regressions."""
from datetime import datetime, timedelta, timezone
from threading import Event
from time import monotonic, sleep

import pytest

from sofia.modules.inference.benchmark import OllamaBenchmarkAdapter
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.resources import (
    BenchmarkCoordinator, CapabilityFact, EvidenceClass, HardwareInventoryStore,
    HardwareTelemetryStore, IdleAdmission, ResourceSupply,
)
from sofia.platform.run.work import DurableWorkStore, TaskExecutionManager, WorkStatus


DIGEST = "b" * 64
SHA = "c" * 40
NOW = datetime.now(timezone.utc)


class FakeOllama:
    def __init__(self):
        self.chat_calls = 0
        self.digest = DIGEST

    def list(self):
        return {"models": [{"model": "owner/exact:1", "digest": self.digest}]}

    def chat(self, **kwargs):
        self.chat_calls += 1
        assert kwargs["model"] == "owner/exact:1"
        assert kwargs["stream"] is True
        assert kwargs["tools"] is None
        assert kwargs["messages"][0]["content"] == OllamaBenchmarkAdapter.SYNTHETIC_PROMPT
        yield {"message": {"content": "bench"}}
        yield {
            "message": {"content": "mark"},
            "prompt_eval_count": 20,
            "eval_count": 2,
            "prompt_eval_duration": 2_000_000_000,
            "eval_duration": 500_000_000,
            "load_duration": 100_000_000,
            "total_duration": 2_700_000_000,
        }


def adapter(client=None):
    return OllamaBenchmarkAdapter(
        ProviderConfiguration(
            provider="ollama", model="owner/exact:1", context_size=4096,
            seed=7,
        ),
        client=client or FakeOllama(),
    )


def test_exact_installed_model_metrics_are_measured_without_prompt_content() -> None:
    observed = adapter().run(expected_digest=DIGEST, cancel=Event())
    assert observed.model_id == "owner/exact:1"
    assert observed.model_digest == DIGEST
    assert observed.prompt_tokens_per_second == 10.0
    assert observed.generated_tokens_per_second == 4.0
    assert observed.load_duration_ms == 100.0
    assert observed.total_duration_ms == 2700.0
    assert len(observed.response_sha256) == 64
    assert "benchmark" not in repr(observed)


def test_wrong_or_changed_digest_fails_without_claiming_success() -> None:
    client = FakeOllama()
    with pytest.raises(PermissionError, match="differs"):
        adapter(client).run(expected_digest="d" * 64, cancel=Event())
    assert client.chat_calls == 0

    class Changing(FakeOllama):
        def chat(self, **kwargs):
            yield from super().chat(**kwargs)
            self.digest = "e" * 64

    with pytest.raises(RuntimeError, match="changed"):
        adapter(Changing()).run(expected_digest=DIGEST, cancel=Event())


def test_cancellation_never_contacts_provider_when_already_set() -> None:
    cancel = Event(); cancel.set(); client = FakeOllama()
    with pytest.raises(InterruptedError, match="before"):
        adapter(client).run(expected_digest=DIGEST, cancel=cancel)
    assert client.chat_calls == 0


def test_llm_benchmark_runs_only_from_fresh_verified_inventory_via_run(
    canonical_state_path,
) -> None:
    inventory = HardwareInventoryStore(
        canonical_state_path,
        enrollment_verifier=lambda host, reference, at: reference == "enrollment:worker",
    )
    static = CapabilityFact(
        "cpu.arch", "x86_64", None, "node:worker", "host:node-worker",
        EvidenceClass.OBSERVED, "agent:worker", NOW, None, True,
    )
    record = inventory.record(
        host_id="node:worker", display_name="Renameable", facts=(static,),
        observed_at=NOW, enrolled=True, trusted=True,
        enrollment_ref="enrollment:worker",
    )
    telemetry = HardwareTelemetryStore(canonical_state_path)
    expires = NOW + timedelta(minutes=2)
    live = (
        CapabilityFact(
            "runtime.ollama.version", "0.12.4", None, "node:worker",
            "runtime:ollama", EvidenceClass.OBSERVED, "agent:worker", NOW,
            expires, True,
        ),
        CapabilityFact(
            "model[owner/exact:1].digest", DIGEST, None, "node:worker",
            "model:owner-exact-1", EvidenceClass.OBSERVED, "agent:worker", NOW,
            expires, True,
        ),
    )
    telemetry.record(
        host_id="node:worker", facts=live, source_ref="agent:worker",
        observed_at=NOW,
    )

    def supply(host_id):
        return ResourceSupply(
            host_id, True, True, record.revision,
            record.facts + telemetry.latest(host_id),
        )

    work = DurableWorkStore(canonical_state_path)
    manager = TaskExecutionManager(work, {}, max_workers=4)
    coordinator = BenchmarkCoordinator(
        state_path=canonical_state_path, inventory=inventory,
        work_store=work, manager=manager,
        idle_observer=lambda host, resource, kind, now: IdleAdmission(
            True, (), ("idle:verified",), now,
        ),
        source_revision=SHA, supply_provider=supply,
    )
    coordinator.register_ollama_adapter(host_id="node:worker", adapter=adapter())
    try:
        assert coordinator.queue_inventory(record, now=NOW) == 3
        assert coordinator.schedule(now=NOW) == 3
        assert manager.tick(now=NOW) == 3
        deadline = monotonic() + 5
        while monotonic() < deadline and any(
            job.status not in {WorkStatus.COMPLETED, WorkStatus.FAILED}
            for job in work.list()
        ):
            sleep(0.01)
        manager.close(wait=True)
        jobs = work.list()
        assert all(job.status is WorkStatus.COMPLETED for job in jobs)
        result = next(item for item in coordinator.results() if item["kind"] == "llm")
        assert result["model_id"] == "owner/exact:1"
        assert result["model_digest"] == DIGEST
        assert "synthetic-fixed-v1" in result["configuration_json"]
        assert OllamaBenchmarkAdapter.SYNTHETIC_PROMPT not in repr(result)
    finally:
        # close() is idempotent for a manager with no remaining active work.
        try:
            manager.close(wait=True)
        except RuntimeError:
            pass
