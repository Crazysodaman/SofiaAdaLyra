"""HNF-05/06 durable, idle-gated benchmark regressions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic, sleep

from sofia.platform.resources import CapabilityFact, EvidenceClass, HardwareInventoryStore
from sofia.platform.resources.benchmark import (
    BenchmarkCoordinator, BenchmarkKind, IdleAdmission, VerifiedIdleObserver,
    read_benchmark_scores, resolve_source_revision,
)
from sofia.platform.run.work import DurableWorkStore, TaskExecutionManager, WorkStatus
from sofia.platform.ops.activity import ActivityMode, HostActivityObservation, HostActivityStore
from sofia.platform.resources import HardwareTelemetryStore


SHA = "a" * 40


@dataclass
class AdmissionProbe:
    eligible: bool = False
    reason: str = "foreground_activity"

    def __call__(self, host_id, resource_id, kind, now):
        assert host_id == "node:eligible"
        assert resource_id.startswith("host:")
        assert isinstance(kind, BenchmarkKind)
        return IdleAdmission(
            self.eligible,
            () if self.eligible else (self.reason,),
            ("activity:verified-idle",) if self.eligible else ("activity:foreground",),
            now,
        )


def enrolled_inventory(path, now):
    store = HardwareInventoryStore(
        path,
        enrollment_verifier=lambda host, reference, at: (
            host == "node:eligible" and reference == "enrollment:eligible"
        ),
    )
    fact = CapabilityFact(
        "cpu.arch", "x86_64", None, "node:eligible", "host:node-eligible",
        EvidenceClass.OBSERVED, "agent:eligible", now, None, True,
    )
    return store, store.record(
        host_id="node:eligible", display_name="Renameable Worker", facts=(fact,),
        observed_at=now, enrolled=True, trusted=True,
        enrollment_ref="enrollment:eligible",
    )


def coordinator(path, inventory, admission, *, freshness=timedelta(days=30)):
    work = DurableWorkStore(path)
    manager = TaskExecutionManager(work, {}, max_workers=2)
    service = BenchmarkCoordinator(
        state_path=path, inventory=inventory, work_store=work, manager=manager,
        idle_observer=admission, source_revision=SHA,
        scratch_root=path.parent / "scratch", result_freshness=freshness,
    )
    return service, work, manager


def wait_for_terminal(work, *, expected, timeout=5.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        jobs = work.list()
        if len(jobs) == expected and all(job.status in {
            WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.CANCELLED,
            WorkStatus.UNCERTAIN,
        } for job in jobs):
            return jobs
        sleep(0.01)
    raise AssertionError(f"RUN jobs did not settle: {work.list()!r}")


def test_discovery_queues_but_unverified_idle_cannot_start(canonical_state_path) -> None:
    now = datetime.now(timezone.utc)
    inventory, record = enrolled_inventory(canonical_state_path, now)
    admission = AdmissionProbe()
    service, work, manager = coordinator(canonical_state_path, inventory, admission)
    try:
        assert service.queue_inventory(record, now=now) == 2
        assert service.queue_inventory(record, now=now) == 0
        assert service.schedule(now=now) == 0
        assert work.list() == ()
        assert {plan["last_reason"] for plan in service.plans()} == {"foreground_activity"}
    finally:
        manager.close(wait=True)


def test_idle_benchmarks_execute_through_canonical_run_and_survive_restart(
    canonical_state_path,
) -> None:
    now = datetime.now(timezone.utc)
    inventory, _ = enrolled_inventory(canonical_state_path, now)
    admission = AdmissionProbe(eligible=True)
    service, work, manager = coordinator(canonical_state_path, inventory, admission)
    assert service.schedule(now=now) == 2
    assert manager.tick(now=now) == 2
    jobs = wait_for_terminal(work, expected=2)
    assert all(job.status is WorkStatus.COMPLETED for job in jobs)
    results = service.results(host_id="node:eligible")
    assert len(results) == 2
    assert {result["source_revision"] for result in results} == {SHA}
    assert all(result["status"] == "completed" for result in results)
    manager.close(wait=True)

    restarted_work = DurableWorkStore(canonical_state_path)
    assert restarted_work.recover(now=now + timedelta(minutes=1)) == 0
    restarted_manager = TaskExecutionManager(restarted_work, {}, max_workers=1)
    restarted = BenchmarkCoordinator(
        state_path=canonical_state_path, inventory=inventory,
        work_store=restarted_work, manager=restarted_manager,
        idle_observer=admission, source_revision=SHA,
        scratch_root=canonical_state_path.parent / "scratch",
    )
    try:
        assert len(restarted.results(host_id="node:eligible")) == 2
        assert restarted.schedule(now=now + timedelta(minutes=1)) == 0
    finally:
        restarted_manager.close(wait=True)


def test_stale_results_create_a_new_attempt_not_replay_old_run(canonical_state_path) -> None:
    now = datetime.now(timezone.utc)
    inventory, _ = enrolled_inventory(canonical_state_path, now)
    admission = AdmissionProbe(eligible=True)
    service, work, manager = coordinator(
        canonical_state_path, inventory, admission, freshness=timedelta(minutes=1),
    )
    try:
        assert service.schedule(now=now) == 2
        manager.tick(now=now)
        wait_for_terminal(work, expected=2)
        score = read_benchmark_scores(
            canonical_state_path, host_ids=("node:eligible",),
            metric="integer_iterations_per_second", now=datetime.now(timezone.utc),
        )
        assert score["node:eligible"] > 0
        later = datetime.now(timezone.utc) + timedelta(minutes=2)
        assert read_benchmark_scores(
            canonical_state_path, host_ids=("node:eligible",),
            metric="integer_iterations_per_second", now=later,
        ) == {}
        assert service.schedule(now=later) == 2
        assert {plan["attempt"] for plan in service.plans()} == {2}
        assert len({job.fingerprint for job in work.list()}) == 4
    finally:
        manager.close(wait=True)


def test_restart_reconciles_uncertain_attempt_without_reusing_it(canonical_state_path) -> None:
    now = datetime.now(timezone.utc)
    inventory, _ = enrolled_inventory(canonical_state_path, now)
    admission = AdmissionProbe(eligible=True)
    service, work, manager = coordinator(canonical_state_path, inventory, admission)
    assert service.schedule(now=now, limit=1) == 1
    job = work.list()[0]
    work.transition(
        job.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.RUNNING,
        reason="simulated_claim", now=now,
    )
    assert work.recover(now=now + timedelta(seconds=1)) == 1
    manager.close(wait=True)

    work2 = DurableWorkStore(canonical_state_path)
    manager2 = TaskExecutionManager(work2, {}, max_workers=1)
    restarted = BenchmarkCoordinator(
        state_path=canonical_state_path, inventory=inventory,
        work_store=work2, manager=manager2, idle_observer=admission,
        source_revision=SHA, scratch_root=canonical_state_path.parent / "scratch",
    )
    try:
        plan = next(item for item in restarted.plans() if item["job_id"] is None)
        assert plan["status"] == "pending"
        assert "uncertain" in plan["last_reason"]
        assert restarted.schedule(now=now + timedelta(minutes=6), limit=1) == 1
        assert len({job.fingerprint for job in work2.list()}) == 2
    finally:
        manager2.close(wait=True)


def test_activity_change_preempts_before_measurement(canonical_state_path) -> None:
    now = datetime.now(timezone.utc)
    inventory, _ = enrolled_inventory(canonical_state_path, now)
    admission = AdmissionProbe(eligible=True)
    service, work, manager = coordinator(canonical_state_path, inventory, admission)
    try:
        assert service.schedule(now=now, limit=1) == 1
        admission.eligible = False
        admission.reason = "gaming_started"
        manager.tick(now=now)
        jobs = wait_for_terminal(work, expected=1)
        assert jobs[0].status is WorkStatus.FAILED
        assert service.results()[0]["status"] == "cancelled"
        assert service.results()[0]["failure_reason"] == "InterruptedError"
        plan = service.plans()[0]
        assert plan["status"] == "pending"
        assert "gaming_started" in plan["last_reason"]
    finally:
        manager.close(wait=True)


def test_production_idle_observer_requires_complete_fresh_host_evidence(
    canonical_state_path,
) -> None:
    now = datetime.now(timezone.utc)
    DurableWorkStore(canonical_state_path)
    activity = HostActivityStore(canonical_state_path)
    activity.record(HostActivityObservation(
        "node:eligible", ActivityMode.IDLE, now, "authenticated-agent",
    ))
    telemetry = HardwareTelemetryStore(canonical_state_path)

    def observed(key, value, unit=None, *, at=now):
        return CapabilityFact(
            key, value, unit, "node:eligible", "host:node-eligible",
            EvidenceClass.OBSERVED, "agent:eligible", at,
            at + timedelta(minutes=2), True,
        )

    facts = (
        observed("cpu.utilization_percent", 5.0, "percent"),
        observed("memory.allocatable_bytes", 2 * 1024 ** 3, "bytes"),
        observed("health.temperature_c", 45.0, "celsius"),
        observed("health.throttled", False),
    )
    telemetry.record(
        host_id="node:eligible", facts=facts, source_ref="agent:eligible",
        observed_at=now,
    )
    observer = VerifiedIdleObserver(
        state_path=canonical_state_path, telemetry=telemetry,
    )
    missing_power = observer(
        "node:eligible", "host:node-eligible", BenchmarkKind.CPU_SINGLE, now,
    )
    assert missing_power.eligible is False
    assert "power_headroom_unverified" in missing_power.reasons

    later = now + timedelta(seconds=1)
    refreshed = tuple(
        observed(fact.key, fact.value, fact.unit, at=later) for fact in facts
    )
    telemetry.record(
        host_id="node:eligible",
        facts=refreshed + (observed("health.power_limited", False, at=later),),
        source_ref="agent:eligible", observed_at=later,
    )
    admitted = observer(
        "node:eligible", "host:node-eligible", BenchmarkKind.CPU_SINGLE,
        later,
    )
    assert admitted.eligible is True
    assert "agent:eligible" in admitted.evidence_refs


def test_source_revision_environment_is_exact_and_invalid_value_disables(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SOFIA_SOURCE_REVISION", SHA)
    assert resolve_source_revision(tmp_path) == SHA
    monkeypatch.setenv("SOFIA_SOURCE_REVISION", "main")
    assert resolve_source_revision(tmp_path) is None
