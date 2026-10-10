from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from threading import Barrier, Event
import subprocess
import sqlite3

import pytest

from sofia.application.act_service import SofiaActService
from sofia.application.autonomous_work import AutonomousWorkCoordinator, ImprovementDiagnostic
from sofia.application.evolution import SofiaEvolutionService
from sofia.application.presence import PresenceInitiativeEngine
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.dev.capability import DevToolService
from sofia.dev.opencode import (
    EngineeringExecutionResult, EngineeringExecutionRequest, OpenCodeAdapter,
    OpenCodeConfigurationError, OpenCodeMissingExecutableError,
    engineering_worker_environment,
)
from sofia.evolve.lifecycle import EvolutionProposalStatus
from sofia.evolve.orchestrator import CodeEvolutionOrchestrator
from sofia.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkOverloadError,
    WorkResult, WorkStatus,
)
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.safe.dev_approval import DevApprovalVerifier


NOW = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)


def state(tmp_path):
    path = tmp_path / "sofia.db"
    path.touch()
    return path


def enqueue(manager, fingerprint, *, deadline=None, kind="read"):
    return manager.submit(
        kind=kind, fingerprint=fingerprint, payload={"key": fingerprint},
        priority=50, resource_cost=5, risk="read_only",
        completion_condition="The deterministic read returns a result.",
        now=NOW, deadline=deadline or NOW + timedelta(minutes=5),
    )


def test_multiple_read_only_jobs_run_concurrently(tmp_path):
    store = DurableWorkStore(state(tmp_path))
    barrier = Barrier(2)
    entered = []

    def handler(job, cancel):
        entered.append(job.job_id)
        barrier.wait(timeout=3)
        return WorkResult(WorkStatus.COMPLETED, {"ok": True}, "read_complete")

    manager = TaskExecutionManager(store, {"read": handler}, max_workers=2)
    first, second = enqueue(manager, "one"), enqueue(manager, "two")
    assert manager.tick(now=NOW) == 2
    manager.close(wait=True)

    assert len(entered) == 2
    assert store.get(first.job_id).status is WorkStatus.COMPLETED
    assert store.get(second.job_id).status is WorkStatus.COMPLETED


def test_cancellation_timeout_overload_and_restart_are_deterministic(tmp_path):
    path = state(tmp_path)
    store = DurableWorkStore(path)
    release = Event()

    def waiting(job, cancel):
        cancel.wait(timeout=3)
        release.set()
        return WorkResult(WorkStatus.FAILED, {}, "worker_cancelled")

    manager = TaskExecutionManager(store, {"read": waiting}, max_workers=1, max_queued=1)
    job = enqueue(manager, "bounded", deadline=NOW + timedelta(seconds=1))
    with pytest.raises(WorkOverloadError):
        enqueue(manager, "overload")
    manager.tick(now=NOW)
    manager.poll(now=NOW + timedelta(seconds=2))
    assert store.get(job.job_id).status is WorkStatus.UNCERTAIN
    assert release.wait(timeout=3)
    manager.close(wait=True)

    queued_manager = TaskExecutionManager(store, {"read": waiting}, max_workers=1)
    queued = enqueue(queued_manager, "restart-pending")
    duplicate = enqueue(queued_manager, "restart-pending")
    assert duplicate.job_id == queued.job_id
    queued_manager.close()
    assert DurableWorkStore(path).get(queued.job_id).status is WorkStatus.QUEUED


def test_plan_dependencies_keep_later_steps_from_running_early(tmp_path):
    store = DurableWorkStore(state(tmp_path))
    order = []

    def handler(job, cancel):
        order.append(job.payload["key"])
        return WorkResult(WorkStatus.COMPLETED, {"ok": True}, "done")

    manager = TaskExecutionManager(store, {"read": handler}, max_workers=2)
    first = enqueue(manager, "plan-first")
    second = enqueue(manager, "plan-second")
    plan = store.create_plan(
        fingerprint="ordered-plan", title="Ordered diagnostic",
        evidence_ref="fixture:ordered", now=NOW,
    )
    store.attach_step(plan_id=plan, job_id=first.job_id, step_order=0)
    store.attach_step(
        plan_id=plan, job_id=second.job_id, step_order=1,
        depends_on_job_id=first.job_id,
    )
    assert manager.tick(now=NOW) == 1
    manager.close(wait=True)
    assert order == ["plan-first"]
    assert store.get(second.job_id).status is WorkStatus.QUEUED


class FakeDevService(DevToolService):
    def __init__(self):
        self.calls = []

    def build(self, parameters):
        self.calls.append(parameters)
        return {
            "proposal_id": parameters["proposal_id"],
            "base_sha": parameters["base_sha"],
            "changed_paths": ("src/problem.py",),
            "allowed_paths": tuple(parameters["allowed_paths"]),
            "tests_passed": True,
            "iterations": 1,
            "tests": tuple(parameters["tests"]),
            "verification_output_sha256": "a" * 64,
            "patch": "diff --git a/src/problem.py b/src/problem.py\n",
        }


class FakeVerifier:
    def verify(self, *, expected_paths):
        return {"accepted": True, "phase": "candidate", "git_revision": "a" * 40}


class MissingOpenCodeDevService(FakeDevService):
    def build(self, parameters):
        raise OpenCodeMissingExecutableError("OpenCode executable was not found")


def config(tmp_path, workspace):
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=workspace,
    )


def git_workspace(tmp_path):
    workspace = tmp_path / "repo"
    (workspace / "src").mkdir(parents=True)
    (workspace / "test").mkdir()
    (workspace / "src" / "problem.py").write_text("BROKEN = True\n", encoding="utf-8")
    (workspace / "test" / "test_problem.py").write_text("def test_problem(): assert True\n", encoding="utf-8")
    subprocess.run(("git", "init"), cwd=workspace, check=True, capture_output=True)
    subprocess.run(("git", "config", "user.email", "test@example.invalid"), cwd=workspace, check=True)
    subprocess.run(("git", "config", "user.name", "Test"), cwd=workspace, check=True)
    subprocess.run(("git", "add", "."), cwd=workspace, check=True)
    subprocess.run(("git", "commit", "-m", "fixture"), cwd=workspace, check=True, capture_output=True)
    return workspace


def test_fixture_problem_reaches_review_without_changing_production(tmp_path):
    workspace = git_workspace(tmp_path)
    configuration = config(tmp_path, workspace)
    plane = SQLiteStatePlane(configuration.state_path)
    evolution = SofiaEvolutionService(configuration=configuration, state_plane=plane)
    dev = FakeDevService()
    orchestrator = CodeEvolutionOrchestrator(
        lifecycle=evolution.lifecycle, dev_service=dev, verifier=FakeVerifier(),
    )
    act = SofiaActService(Path(configuration.state_path))
    presence = PresenceInitiativeEngine(state_path=configuration.state_path, act_service=act)
    coordinator = AutonomousWorkCoordinator(
        state_path=configuration.state_path, workspace=workspace,
        evolution=evolution, code_orchestrator=orchestrator, presence=presence,
    )
    before = (workspace / "src" / "problem.py").read_bytes()
    assert coordinator.record_diagnostic(ImprovementDiagnostic(
        diagnostic_id="fixture-regression-1", source_ref="pytest:fixture-regression-1",
        summary="The fixture reports a reproducible defect in problem.py.",
        details={"test": "test/test_problem.py", "failure": "expected false"},
        allowed_paths=("src/problem.py",), tests=("test/test_problem.py",),
        success_metric="The focused regression test passes.", observed_at=NOW, severity=80,
    ))

    result = coordinator.tick(now=NOW + timedelta(minutes=1))
    assert result == {"failures_discovered": 0, "proposals_created": 1, "jobs_started": 1}
    coordinator.manager.close(wait=True)

    jobs = coordinator.work_store.list()
    assert len(jobs) == 1
    assert jobs[0].status is WorkStatus.WAITING_APPROVAL
    proposal_id = str(jobs[0].result["proposal_id"])
    assert evolution.proposal(proposal_id).status is EvolutionProposalStatus.CANDIDATE_BUILT
    assert dev.calls and dev.calls[0]["tests"] == ["test/test_problem.py"]
    assert (workspace / "src" / "problem.py").read_bytes() == before
    with sqlite3.connect(configuration.state_path) as db:
        assert db.execute(
            "SELECT reason FROM presence_initiative_opportunity WHERE trigger_kind='dev_finding'"
        ).fetchone()[0] == "missing_transport"


def test_controlled_opencode_adapter_builds_real_detached_patch(tmp_path, monkeypatch):
    workspace = git_workspace(tmp_path)
    (workspace / "test" / "test_problem.py").write_text(
        "from pathlib import Path\n"
        "def test_problem():\n"
        "    scope = {}\n"
        "    exec(Path('src/problem.py').read_text(), scope)\n"
        "    assert scope['BROKEN'] is False\n",
        encoding="utf-8",
    )
    subprocess.run(("git", "add", "."), cwd=workspace, check=True)
    subprocess.run(("git", "commit", "-m", "real failing fixture"), cwd=workspace, check=True, capture_output=True)
    configuration = config(tmp_path, workspace)
    plane = SQLiteStatePlane(configuration.state_path)
    evolution = SofiaEvolutionService(configuration=configuration, state_plane=plane)
    dev = DevToolService(
        workspace, Path(configuration.state_path),
        approval_verifier=DevApprovalVerifier(configuration.state_path),
        state_plane=plane, executable="controlled-opencode",
    )
    orchestrator = CodeEvolutionOrchestrator(
        lifecycle=evolution.lifecycle, dev_service=dev, verifier=FakeVerifier(),
    )

    def controlled_execute(adapter, request):
        assert adapter.workspace != workspace
        (adapter.workspace / "src" / "problem.py").write_text(
            "BROKEN = False\n", encoding="utf-8",
        )
        return EngineeringExecutionResult(
            request.proposal_id, 0, "candidate written", "", request.base_sha,
            ("src/problem.py",), None, False,
        )

    monkeypatch.setattr(OpenCodeAdapter, "execute", controlled_execute)
    presence = PresenceInitiativeEngine(
        state_path=configuration.state_path,
        act_service=SofiaActService(Path(configuration.state_path)),
    )
    coordinator = AutonomousWorkCoordinator(
        state_path=configuration.state_path, workspace=workspace,
        evolution=evolution, code_orchestrator=orchestrator, presence=presence,
    )
    before = (workspace / "src" / "problem.py").read_text(encoding="utf-8")
    coordinator.record_diagnostic(ImprovementDiagnostic(
        diagnostic_id="real-adapter-regression", source_ref="pytest:test_problem",
        summary="BROKEN remains true and fails its focused regression test.",
        details={"test": "test/test_problem.py", "observed": "failed"},
        allowed_paths=("src/problem.py",), tests=("test/test_problem.py",),
        success_metric="test/test_problem.py passes", observed_at=NOW, severity=90,
    ))
    assert coordinator.tick(now=NOW + timedelta(minutes=1))["jobs_started"] == 1
    coordinator.manager.close(wait=True)

    job = coordinator.work_store.list()[0]
    candidate = dev.candidate(str(job.result["proposal_id"]))
    assert job.status is WorkStatus.WAITING_APPROVAL
    assert candidate["tests_passed"] is True
    assert "BROKEN = False" in candidate["patch"]
    assert (workspace / "src" / "problem.py").read_text(encoding="utf-8") == before


def test_missing_opencode_is_a_durable_failed_job_and_does_not_change_production(tmp_path):
    workspace = git_workspace(tmp_path)
    configuration = config(tmp_path, workspace)
    plane = SQLiteStatePlane(configuration.state_path)
    evolution = SofiaEvolutionService(configuration=configuration, state_plane=plane)
    orchestrator = CodeEvolutionOrchestrator(
        lifecycle=evolution.lifecycle,
        dev_service=MissingOpenCodeDevService(),
        verifier=FakeVerifier(),
    )
    presence = PresenceInitiativeEngine(
        state_path=configuration.state_path,
        act_service=SofiaActService(Path(configuration.state_path)),
    )
    coordinator = AutonomousWorkCoordinator(
        state_path=configuration.state_path, workspace=workspace,
        evolution=evolution, code_orchestrator=orchestrator, presence=presence,
    )
    before = (workspace / "src" / "problem.py").read_bytes()
    coordinator.record_diagnostic(ImprovementDiagnostic(
        diagnostic_id="missing-opencode", source_ref="pytest:missing-opencode",
        summary="A reviewed fixture requires an isolated engineering candidate.",
        details={"test": "test/test_problem.py"},
        allowed_paths=("src/problem.py",), tests=("test/test_problem.py",),
        success_metric="The focused test passes.", observed_at=NOW, severity=75,
    ))

    assert coordinator.tick(now=NOW + timedelta(minutes=1))["jobs_started"] == 1
    coordinator.manager.close(wait=True)

    job = coordinator.work_store.list()[0]
    assert job.status is WorkStatus.FAILED
    assert job.result["error_type"] == "OpenCodeMissingExecutableError"
    assert job.result["execution"]["resource_cost_admission"] == 60
    assert evolution.lifecycle.get_evidence("dev-build-failure:" + sha256(
        job.job_id.encode("utf-8")
    ).hexdigest()[:32]).kind == "engineering-failure"
    assert (workspace / "src" / "problem.py").read_bytes() == before


def test_opencode_configuration_and_worker_secret_isolation_are_explicit(tmp_path, monkeypatch):
    with pytest.raises(OpenCodeConfigurationError):
        OpenCodeAdapter(tmp_path, executable="")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-cross-boundary")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-cross-boundary")
    assert "GITHUB_TOKEN" not in engineering_worker_environment()
    assert "AWS_SECRET_ACCESS_KEY" not in engineering_worker_environment()

    adapter = OpenCodeAdapter(tmp_path, executable="missing-opencode")
    request = EngineeringExecutionRequest(
        proposal_id="p1", base_sha="a" * 40, prompt="fix fixture",
        allowed_paths=("src",), authorized=True,
    )
    monkeypatch.setattr("sofia.dev.opencode.shutil.which", lambda value: None)
    with pytest.raises(OpenCodeMissingExecutableError):
        adapter.command(request)
