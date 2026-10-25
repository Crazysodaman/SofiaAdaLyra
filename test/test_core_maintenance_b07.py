from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.modreg.manifest import ModuleManifest
from sofia.core.modreg.platform import (
    FakeCapabilitySpec,
    FakePlatformModuleObserver,
    ModuleObservationKind,
    OutcomeObservation,
    OutcomeStatus,
)
from sofia.core.modreg.proposals import (
    ModuleProposalRecord,
    ProposalAction,
    ProposalStatus,
)
from sofia.core.social.principals import local_sparks_principal, sofia_core_principal
from sofia.platform.application import SofiaApplication
from sofia.platform.run.github_update_watch import UpdateObservation, VerifiedUpdate
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from test.test_application import create_configuration, personality_path
from test.test_platform_module_operations import finish, prepared


assert personality_path is not None  # imported pytest fixture


@pytest.fixture(autouse=True)
def _canonical_state(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")


NOW = datetime(2026, 10, 24, 14, tzinfo=timezone.utc)


def application(personality_path, tmp_path):
    app = SofiaApplication(
        create_configuration(personality_path, tmp_path / "sofia.db")
    )
    app.start()
    return app


def test_restart_request_is_durable_non_effect_and_reconciles_exact_outcome(
    personality_path, tmp_path,
):
    app = application(personality_path, tmp_path)
    try:
        request = app.core_maintenance.request_restart(
            sofia_core_principal(), subject="sofia.runtime",
            reason="A verified release requires supervised recomposition.",
            evidence_refs=("release:verified-1",), now=NOW,
        )
        duplicate = app.core_maintenance.request_restart(
            sofia_core_principal(), subject="sofia.runtime",
            reason="A verified release requires supervised recomposition.",
            evidence_refs=("release:verified-1",), now=NOW + timedelta(minutes=1),
        )
        assert duplicate.request_id == request.request_id
        assert request.status == "requested"
        # Recording the request itself never creates a RUN job or effect.
        assert not any(job.fingerprint == request.request_id for job in app.autonomous_work.work_store.list())

        settled = app.core_maintenance.reconcile_request(OutcomeObservation(
            request_id=request.request_id, module_id="sofia.runtime",
            capability="runtime.restart", status=OutcomeStatus.OUTCOME_UNKNOWN,
            verification_method=None, error_class="connection_lost",
            settled_at=NOW + timedelta(minutes=2),
        ))
        assert settled.status == "uncertain"
        assert app.core_maintenance.reconcile_request(OutcomeObservation(
            request_id=request.request_id, module_id="sofia.runtime",
            capability="runtime.restart", status=OutcomeStatus.SUCCEEDED_VERIFIED,
            verification_method="startup-reconciliation", error_class=None,
            settled_at=NOW + timedelta(minutes=3),
        )).status == "uncertain"
    finally:
        app.shutdown()


def test_only_signed_verified_update_becomes_core_request(personality_path, tmp_path):
    app = application(personality_path, tmp_path)
    try:
        observation = UpdateObservation(
            "a" * 40, "b" * 40, "signed_release_available",
            VerifiedUpdate("a" * 40, "release-2", "c" * 64), NOW,
        )
        request = app.core_maintenance.propose_verified_update(
            sofia_core_principal(), observation,
        )
        assert request.kind == "verified_update"
        assert request.status == "requested"
        with pytest.raises(ValueError, match="verified signed release"):
            app.core_maintenance.propose_verified_update(
                sofia_core_principal(),
                UpdateObservation("a" * 40, "b" * 40, "awaiting_signed_release", None, NOW),
            )
    finally:
        app.shutdown()


def test_verified_module_outcome_learning_is_idempotent_and_not_authority(
    personality_path, tmp_path,
):
    app = application(personality_path, tmp_path)
    outcome = OutcomeObservation(
        request_id="request:verified-lesson", module_id="sofia.lab",
        capability="lab.inspect", status=OutcomeStatus.SUCCEEDED_VERIFIED,
        verification_method="signed-receipt", error_class=None, settled_at=NOW,
    )
    app.update_platform_module_observer(FakePlatformModuleObserver(
        specs=(FakeCapabilitySpec("sofia.lab", "1.0.0", ("lab.inspect",), ("lab.inspect",)),),
        health_rows=(("sofia.lab", "host:test", ModuleObservationKind.HEALTHY),),
        outcomes=(outcome,), fresh_until=NOW + timedelta(minutes=5),
    ))
    try:
        assert app.core_maintenance.learn_verified_outcomes() == 1
        assert app.core_maintenance.learn_verified_outcomes() == 0
        context = app.core_maintenance.working_context()
        assert "verified successful outcome" in context
        [row] = app.module_awareness.project(now=NOW)
        assert row.permission_aspects[0].grant_state.value == "unknown"
    finally:
        app.shutdown()


def test_canonical_module_run_outcome_is_learned_once_across_app_restart(
    personality_path, tmp_path,
):
    state_path = tmp_path / "sofia.db"
    _lifecycle, coordinator, manager, store, _adapter, request, _ = prepared(
        state_path, tmp_path,
    )
    try:
        job = coordinator.submit(request, now=datetime.now(timezone.utc))
        assert finish(manager, store, job.job_id).status.value == "completed"
    finally:
        manager.close(wait=True)

    first = application(personality_path, tmp_path)
    try:
        assert first.core_maintenance.learn_verified_outcomes() == 1
        assert "verified successful outcome" in first.core_maintenance.working_context()
    finally:
        first.shutdown()

    restarted = application(personality_path, tmp_path)
    try:
        assert restarted.core_maintenance.learn_verified_outcomes() == 0
        assert "verified successful outcome" in restarted.core_maintenance.working_context()
    finally:
        restarted.shutdown()


def test_module_proposal_reaches_workshop_then_existing_evolve_pipeline_only_after_owner_submission(
    personality_path, tmp_path,
):
    app = application(personality_path, tmp_path)
    proposal = ModuleProposalRecord(
        proposal_id=f"moduleproposal:{uuid4()}", revision=1,
        need_id="need:lab-helper", target_module="sofia.labhelper",
        action=ProposalAction.DEVELOP, status=ProposalStatus.PROPOSED,
        motivation="Repeated diagnostics need a bounded parser.", alternatives=(),
        benefits="Fewer repeated manual parsing steps.",
        risks="A parser can misclassify unfamiliar logs.",
        permissions_needed=("filesystem.inspect",), resource_notes="low CPU",
        outcome_refs=(), proposer_principal_id="sofia", audience_id="system:core",
        recorded_at=NOW,
    )
    manifest = ModuleManifest(
        name="sofia.labhelper", version="1.0.0",
        purpose="Parse bounded diagnostic records.",
        boundary_notes="Never executes repair actions.",
        declared_capabilities=("labhelper.inspect",), declared_dependencies=(),
        authority_boundary="read-only diagnostic input",
    )
    try:
        request = app.core_maintenance.prepare_development_handoff(
            sofia_core_principal(), proposal=proposal, manifest=manifest,
            test_targets=("test/test_labhelper.py",), now=NOW,
        )
        assert request.status.value == "prepared"
        with pytest.raises(PermissionError, match="owner"):
            app.core_maintenance.submit_handoff_to_engineering(
                sofia_core_principal(), request=request,
                allowed_paths=("src/sofia/core/modreg",),
                success_metric="candidate tests pass", now=NOW,
            )
        submitted = app.core_maintenance.submit_handoff_to_engineering(
            local_sparks_principal(), request=request,
            allowed_paths=("src/sofia/core/modreg",),
            success_metric="candidate tests pass", now=NOW,
        )
        assert submitted.status.value == "submitted"
        assert "grants no authority" in app.core_maintenance.explain_proposal(proposal)
    finally:
        app.shutdown()
