"""B07: SMBA capability self-model, proposals, workshop requests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sofia.platform.application import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.codebase.model import (
    CodebaseEvidenceKind,
    CodebaseInspectionEvidence,
    PythonModule,
    PythonSymbol,
)
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.core.modreg.manifest import parse_manifest
from sofia.core.modreg.platform import (
    FakeCapabilitySpec,
    FakePlatformModuleObserver,
    ModuleObservationKind,
    OutcomeObservation,
    OutcomeStatus,
    PlacementObservation,
    PlacementMode,
)
from sofia.core.modreg.proposals import (
    ModuleNeed,
    ModuleProposalService,
    ModuleProposalStore,
    NeedOrigin,
    ProposalAction,
    ProposalStatus,
)
from sofia.core.modreg.registry import (
    ModuleRegistryService,
    ModuleRegistryStore,
)
from sofia.core.modreg.self_model import (
    CapabilitySelfModel,
    Grounding,
    ModuleAwarenessRow,
)
from sofia.core.modreg.workshop import (
    WorkshopRequestError,
    WorkshopRequestService,
    WorkshopRequestStatus,
    WorkshopRequestStore,
)
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 7, 5, 9, 30, tzinfo=timezone.utc)

PROJECT_ROOT = Path(__file__).parent.parent


def manifest_for(name: str, *, version: str = "1.4.0", deps: tuple = ()):
    return parse_manifest(
        {
            "name": name,
            "version": version,
            "purpose": "Bounded helper module used by the SMBA tests.",
            "boundary_notes": (
                "Observation and planning only; execution stays gated."
            ),
            "declared_capabilities": ["component.report", "roster.read"],
            "declared_dependencies": list(deps),
            "authority_boundary": "owner-session:sparks",
        }
    )


def inspection(modules) -> CodebaseInspectionEvidence:
    return CodebaseInspectionEvidence(
        root=PROJECT_ROOT,
        files=(),
        python_modules=tuple(
            PythonModule(
                path=Path(name.replace(".", "/") + ".py"),
                module_name=name,
                symbols=(
                    PythonSymbol(name="holder", kind="module", line=1),
                ),
                imports=(),
                parse_error=None,
            )
            for name in modules
        ),
        relationships=(),
        evidence_kind=CodebaseEvidenceKind.OBSERVED,
        file_limit_reached=False,
    )


def registry_with(tmp_path, name: str) -> ModuleRegistryService:
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = ModuleRegistryService(ModuleRegistryStore(tmp_path / "sofia.db"))
    sparks = local_sparks_principal()
    candidate = service.record_candidate(
        sparks, manifest=manifest_for(name), source_path="m/test.json",
        recorded_at=NOW,
    )
    service.verify(
        sparks,
        name=name,
        expected_revision=candidate.revision,
        inspection=inspection((f"{name}.api",)),
        recorded_at=NOW,
    )
    return service


def fake_platform(**overrides) -> FakePlatformModuleObserver:
    spec = FakeCapabilitySpec(
        module_id="sofia.trains",
        version="1.4.0",
        capabilities=("locomotive.list", "power.read", "train.simulate"),
        requires_permission=("power.read",),
        simulated_only=("train.simulate",),
    )
    stamp = datetime.now(timezone.utc) + timedelta(hours=1)
    health = ("sofia.trains@athena", "athena", ModuleObservationKind.HEALTHY)
    base = {
        "specs": (spec,),
        "health_rows": (health,),
        "placements": (
            PlacementObservation(
                module_id="sofia.trains",
                component="jmri-adapter",
                host_identity="athena",
                placement_mode=PlacementMode.HOST_PINNED,
                eligible_hosts=("athena",),
                device_affinity="loconet-usbx",
                observed_at=stamp,
            ),
            PlacementObservation(
                module_id="sofia.trains",
                component="dispatcher-planner",
                host_identity="artemis",
                placement_mode=PlacementMode.PORTABLE_STATELESS,
                eligible_hosts=("artemis", "venus"),
                device_affinity=None,
                observed_at=stamp,
            ),
        ),
        "outcomes": (),
        "fresh_until": stamp,
    }
    base.update(overrides)
    return FakePlatformModuleObserver(**base)


def test_self_model_reports_unknown_without_any_evidence(tmp_path):
    service = registry_with(tmp_path, "sofia.quiethelper")
    model = CapabilitySelfModel(service, None)
    rows = model.project(now=NOW)
    # Registry present but no platform observer: operational columns are
    # unknown, never invented.
    [row] = [r for r in rows if r.module_id == "sofia.quiethelper"]
    assert row.installed is Grounding.UNKNOWN
    assert row.active is Grounding.UNKNOWN
    assert row.healthy is Grounding.UNKNOWN
    assert row.available is Grounding.UNKNOWN
    assert row.manifest_trust is Grounding.YES
    assert row.discovered is Grounding.YES
    empty = CapabilitySelfModel(None, None)
    assert empty.project(now=NOW) == ()
    summary = empty.awareness_summary()
    assert "No module rows observed" in summary
    with pytest.raises(TypeError, match="PlatformModuleObserver"):
        CapabilitySelfModel(None, object())


def test_self_model_distinguishes_the_eight_states(tmp_path):
    registry_with(tmp_path, "sofia.trains")
    model = CapabilitySelfModel(None, fake_platform())
    [row] = model.project(now=NOW)
    assert isinstance(row, ModuleAwarenessRow)
    assert row.module_id == "sofia.trains"
    assert row.version is Grounding.YES and row.version_text == "1.4.0"
    assert row.installed is Grounding.YES
    assert row.active is Grounding.YES
    assert row.healthy is Grounding.YES
    assert row.available is Grounding.YES
    # Manifest unknown without the registry; compatibility unknown.
    assert row.manifest_trust is Grounding.UNKNOWN
    assert row.compatible is Grounding.UNKNOWN
    assert row.discovered is Grounding.UNKNOWN
    # Verified capability grants are only known from outcome evidence.
    grants = {
        aspect.capability: aspect.grant_state
        for aspect in row.permission_aspects
    }
    assert grants["power.read"] is Grounding.UNKNOWN
    assert grants["train.simulate"] is Grounding.UNKNOWN
    required = row.required_permissions()
    assert required == ("power.read",)
    assert row.simulated_capabilities == ("train.simulate",)
    assert row.verified_outcomes == 0


def test_outcomes_and_placement_ground_grant_and_assembly(tmp_path):
    outcomes = (
        OutcomeObservation(
            request_id="req-1",
            module_id="sofia.trains",
            capability="power.read",
            status=OutcomeStatus.SUCCEEDED_VERIFIED,
            verification_method="receipt",
            error_class=None,
            settled_at=NOW,
        ),
        OutcomeObservation(
            request_id="req-2",
            module_id="sofia.trains",
            capability="locomotive.list",
            status=OutcomeStatus.DENIED,
            verification_method=None,
            error_class="denied:scope",
            settled_at=NOW,
        ),
        OutcomeObservation(
            request_id="req-3",
            module_id="sofia.trains",
            capability="train.simulate",
            status=OutcomeStatus.SUCCEEDED_REPORTED_UNVERIFIED,
            verification_method=None,
            error_class=None,
            settled_at=NOW,
        ),
    )
    model = CapabilitySelfModel(
        None, fake_platform(outcomes=outcomes),
    )
    [row] = model.project(now=NOW)
    grants = {
        aspect.capability: aspect.grant_state
        for aspect in row.permission_aspects
    }
    assert grants["power.read"] is Grounding.YES
    assert grants["locomotive.list"] is Grounding.NO
    assert grants["train.simulate"] is Grounding.UNKNOWN
    assert row.verified_outcomes == 1
    assert row.denied_outcomes == 1
    assert row.unverified_outcomes == 1
    # One logical assembly across two hosts, hardware pinned.
    assert row.placements == (
        ("dispatcher-planner", "artemis", "portable_stateless"),
        ("jmri-adapter", "athena", "host_pinned"),
    )
    summary = model.awareness_summary()
    assert "jmri-adapter@athena(host_pinned)" in summary
    assert (
        "dispatcher-planner@artemis(portable_stateless)" in summary
    )


def test_stale_and_quarantined_health_stays_unknown_and_noted(tmp_path):
    registry_with(tmp_path, "sofia.trains")
    stale = fake_platform(
        health_rows=(
            ("sofia.trains@athena", "athena", ModuleObservationKind.HEALTHY),
        ),
        fresh_until=NOW - timedelta(hours=2),
    )
    model = CapabilitySelfModel(None, stale)
    [row] = model.project(now=NOW)
    assert "stale-observation" in row.notes
    assert row.active is Grounding.UNKNOWN
    assert row.healthy is Grounding.UNKNOWN
    assert row.available is Grounding.NO
    quarantined = fake_platform(
        health_rows=(
            (
                "sofia.trains@athena", "athena",
                ModuleObservationKind.QUARANTINED,
            ),
        ),
    )
    [qrow] = CapabilitySelfModel(None, quarantined).project(now=NOW)
    assert qrow.available is Grounding.NO
    assert qrow.healthy is Grounding.NO


def test_registry_and_platform_merge_and_compatibility(tmp_path):
    service = registry_with(tmp_path, "sofia.trains")
    candidate = service.record_candidate(
        local_sparks_principal(),
        manifest=manifest_for(
            "sofia.trains.ui", version="2.0.0",
            deps=("sofia.trains",),
        ),
        source_path="m/ui.json",
        recorded_at=NOW,
    )
    service.verify(
        local_sparks_principal(),
        name="sofia.trains.ui",
        expected_revision=candidate.revision,
        inspection=inspection(("sofia.trains.ui.api",)),
        recorded_at=NOW,
    )
    model = CapabilitySelfModel(
        service, fake_platform(),
    )
    rows = {row.module_id: row for row in model.project(now=NOW)}
    merged = rows["sofia.trains"]
    assert merged.installed is Grounding.YES
    assert merged.manifest_trust is Grounding.YES
    assert merged.discovered is Grounding.YES
    assert merged.compatible is Grounding.YES
    ui = rows["sofia.trains.ui"]
    assert ui.compatible is Grounding.NO
    assert any(
        note.startswith("dependency:sofia.trains:")
        and "major-version-mismatch" in note
        for note in ui.notes
    ), ui.notes
    summary = model.awareness_summary()
    assert "sofia.trains 1.4.0" in summary
    assert "manifest verified" in summary
    assert "permissions required" in summary
    assert "simulated only: train.simulate" in summary


def need() -> ModuleNeed:
    return ModuleNeed(
        need_id="need:railroading-session-31",
        origin=NeedOrigin.INTEREST,
        subject="railroading evening power checks",
        motivation=(
            "The power-state check has to be repeated by hand every "
            "session; a typed report would avoid my memory slipping."
        ),
        evidence_refs=("goal:hobby:trains", "conversation:turn-2201"),
        created_at=NOW,
    )


def test_need_evaluation_and_proposal_flow(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    service = registry_with(tmp_path, "sofia.trains")
    model = CapabilitySelfModel(service, fake_platform())
    proposals = ModuleProposalService(
        ModuleProposalStore(tmp_path / "sofia.db"), model,
    )
    sparks = local_sparks_principal()
    evaluation = proposals.evaluate_need(
        need(), capability_terms=("locomotive", "power"),
    )
    # Installed-first: the healthy installed module satisfies the need,
    # so a fresh INSTALL proposal would be refused later.
    assert evaluation.installed_alternatives == ("sofia.trains",)
    assert evaluation.unavailable_matches == ()
    assert evaluation.candidate_matches == ()
    health_down = fake_platform(
        health_rows=(
            ("sofia.trains@athena", "athena", ModuleObservationKind.FAILED),
        ),
    )
    proposals_down = ModuleProposalService(
        ModuleProposalStore(tmp_path / "sofia.db"),
        CapabilitySelfModel(service, health_down),
    )
    evaluation_down = proposals_down.evaluate_need(
        need(), capability_terms=("locomotive", "power"),
    )
    assert evaluation_down.candidate_matches == ()
    assert evaluation_down.unavailable_matches == ("sofia.trains",)
    proposal = proposals_down.propose(
        sparks,
        need=need(),
        target_module="sofia.trains",
        action=ProposalAction.IMPROVE,
        evaluation=evaluation_down,
        benefits="typed roster into the evening checklist",
        risks="scope creep beyond read-only observation",
        recorded_at=NOW,
    )
    assert proposal.status is ProposalStatus.PROPOSED
    assert "sofia.trains" in proposal.alternatives
    with pytest.raises(PermissionError, match="authenticated owner"):
        proposals_down.propose(
            PrincipalContext(
                "person:another", "local:text", AudienceKind.PRIVATE,
                "Another",
            ),
            need=need(),
            target_module="other.module",
            action=ProposalAction.IMPROVE,
            evaluation=evaluation_down,
            benefits="b", risks="r",
        )
    resolved = proposals_down.resolve(
        sparks,
        need_id=proposal.need_id,
        target_module=proposal.target_module,
        expected_revision=proposal.revision,
        status=ProposalStatus.DEFERRED,
        note="Waiting for the placement plan to be steady.",
        recorded_at=NOW + timedelta(days=2),
    )
    assert resolved.status is ProposalStatus.DEFERRED
    assert resolved.revision == 2
    from sofia.core.modreg.proposals import ProposalError

    with pytest.raises(ProposalError, match="revision changed"):
        proposals_down.resolve(
            sparks,
            need_id=proposal.need_id,
            target_module=proposal.target_module,
            expected_revision=proposal.revision,
            status=ProposalStatus.ABANDONED,
            note="Stale revision attempt.",
        )
    final = proposals_down.resolve(
        sparks,
        need_id=proposal.need_id,
        target_module=proposal.target_module,
        expected_revision=resolved.revision,
        status=ProposalStatus.NO_MODULE_NEEDED,
        note="The JMRI read path proves enough once it stops flapping.",
        recorded_at=NOW + timedelta(days=3),
    )
    assert final.status is ProposalStatus.NO_MODULE_NEEDED
    assert proposals_down.store.open_proposals() == ()
    healthy_evaluation = proposals.evaluate_need(
        need(), capability_terms=("locomotive", "power"),
    )
    extra_db = tmp_path / "sofia3.db"
    bootstrap_canonical_sqlite(extra_db)
    healthy_service = ModuleProposalService(
        ModuleProposalStore(extra_db), model,
    )
    with pytest.raises(ValueError, match="dispenses"):
        healthy_service.propose(
            sparks,
            need=need(),
            target_module="sofia.trains.unpack",
            action=ProposalAction.INSTALL,
            evaluation=healthy_evaluation,
            benefits="b", risks="r",
        )
    with pytest.raises(LookupError):
        proposals_down.resolve(
            sparks,
            need_id="need:missing",
            target_module="sofia.trains",
            expected_revision=1,
            status=ProposalStatus.ABANDONED,
            note="n/a",
        )


def test_workshop_request_generation(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    requests = WorkshopRequestService(
        WorkshopRequestStore(tmp_path / "sofia.db")
    )
    sparks = local_sparks_principal()
    prepared = requests.prepare(
        sparks,
        manifest=manifest_for("sofia.trains.checklist"),
        test_targets=(
            "test/test_trains_checklist_unit.py",
            "test/test_trains_checklist_faults.py",
        ),
        recorded_at=NOW,
    )
    assert prepared.status is WorkshopRequestStatus.PREPARED
    assert "isolated" in prepared.sandbox_requirement.lower()
    assert prepared.review_requirements == (
        "independent code review",
        "independent security review",
        "independent release certification",
    )
    with pytest.raises(PermissionError, match="authenticated owner"):
        requests.prepare(
            PrincipalContext(
                "person:another", "local:text", AudienceKind.PRIVATE,
                "Another",
            ),
            manifest=manifest_for("sofia.flag"),
            test_targets=("t/test_flag.py",),
        )
    submitted = requests.mark_submitted(
        sparks,
        manifest_name="sofia.trains.checklist",
        expected_revision=prepared.revision,
        submission_ref="workshop:ticket-31",
        recorded_at=NOW + timedelta(days=1),
    )
    assert submitted.status is WorkshopRequestStatus.SUBMITTED
    with pytest.raises(WorkshopRequestError, match="only prepared"):
        requests.mark_submitted(
            sparks,
            manifest_name="sofia.trains.checklist",
            expected_revision=submitted.revision,
            submission_ref="workshop:ticket-32",
        )
    with pytest.raises(RuntimeError, match="revision changed"):
        requests.retire(
            sparks,
            manifest_name="sofia.trains.checklist",
            expected_revision=prepared.revision,
        )
    retired = requests.retire(
        sparks,
        manifest_name="sofia.trains.checklist",
        expected_revision=submitted.revision,
        recorded_at=NOW + timedelta(days=4),
    )
    assert retired.status is WorkshopRequestStatus.RETIRED
    assert requests.store.open_requests() == ()
    with pytest.raises(ValueError, match="isolated"):
        requests.prepare(
            sparks,
            manifest=manifest_for("sofia.trains.checklist"),
            test_targets=("t/test_checklist.py",),
            sandbox_requirement="just run it on my host",
        )
    with pytest.raises(ValueError, match="test plan"):
        requests.prepare(
            sparks,
            manifest=manifest_for("sofia.trains.checklist2"),
            test_targets=(),
        )


def test_bootstrap_wiring_and_conversation_reach(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_HABIT_LEARNING", "0")
    personality = tmp_path / "personality.json"
    personality.write_text(
        """{
  "name": "Sofía Ada Lyra",
  "traits": ["rigorous", "curious", "direct"],
  "communication_style": "Clear, direct, warm and natural."
}""",
        encoding="utf-8",
    )
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    app = SofiaApplication(
        SofiaConfiguration(
            constitution_path=(
                PROJECT_ROOT / "src" / "sofia" / "constitution" /
                "constitution.md"
            ),
            constitution_hash_path=(
                PROJECT_ROOT / "src" / "sofia" / "constitution" /
                "constitution.sha256"
            ),
            identity_path=(
                PROJECT_ROOT / "src" / "sofia" / "identity" / "identity.json"
            ),
            personality_path=personality,
            avatar_path=(
                PROJECT_ROOT / "src" / "sofia" / "embodiment" / "avatar.json"
            ),
            state_path=tmp_path / "sofia.db",
            provider=ProviderConfiguration(provider="test", model="test"),
            filesystem_root=PROJECT_ROOT,
        )
    )
    requests_captured = []

    def respond(request, filesystem_results=(), **kwargs):
        requests_captured.append(request)
        return CognitiveResponse(content="Captured.")

    monkeypatch.setattr(app.runtime, "respond", respond)
    assert isinstance(app.module_awareness, CapabilitySelfModel)
    assert isinstance(app.module_proposals, ModuleProposalService)
    assert isinstance(app.workshop_requests, WorkshopRequestService)
    app.update_platform_module_observer(fake_platform())
    app.start()
    try:
        app.conversation.respond(
            "Check the software modules and the host hardware adapter "
            "availability for the trains stack.",
            principal=local_sparks_principal(),
        )
        assert requests_captured, "turns must reach the model request"
        request = requests_captured[-1]
        blocks = [
            message.content for message in request.messages
            if message.role is CognitiveRole.SYSTEM
            and message.content.startswith("SOF")
        ]
        awareness_blocks = [
            block for block in blocks if "MODULE AWARENESS" in block
        ]
        assert awareness_blocks, [block[:90] for block in blocks]
        block = awareness_blocks[-1]
        assert "SOFÍA'S MODULE AWARENESS" in block
        assert "availability never implies authority" in block
        assert "sofia.trains" in block
        assert "jmri-adapter@athena(host_pinned)" in block
    finally:
        app.shutdown()


def test_capability_system_gate(tmp_path):
    from sofia.capability.model import (
        Capability,
        CapabilityRequest,
        CapabilityResultKind,
    )
    from sofia.capability.system import CapabilitySystem
    from sofia.core.modreg.capability import (
        MODULE_AWARENESS_CAPABILITY,
        ModuleAwarenessCapability,
    )

    adapter = ModuleAwarenessCapability(CapabilitySelfModel(None, fake_platform()))
    system = CapabilitySystem(authorization_checker=lambda request: True)
    system.register(MODULE_AWARENESS_CAPABILITY, adapter.execute)
    result = system.execute(
        CapabilityRequest(
            capability=MODULE_AWARENESS_CAPABILITY,
            parameters={},
            requested_scope=None,
            rationale='Sofia wants an honest inventory before answering.',
        )
    )
    assert result.kind is CapabilityResultKind.SUCCESS
    rows, summary = result.evidence
    assert rows and summary.startswith('SOF')

    locked = CapabilitySystem(authorization_checker=lambda request: False)
    locked.register(MODULE_AWARENESS_CAPABILITY, adapter.execute)
    denied = locked.execute(
        CapabilityRequest(
            capability=MODULE_AWARENESS_CAPABILITY,
            parameters={},
            requested_scope=None,
            rationale='No authorization here.',
        )
    )
    assert denied.kind is CapabilityResultKind.UNAUTHORIZED
    lookalike = Capability(name=MODULE_AWARENESS_CAPABILITY.name, description='different')
    mismatch = system.execute(
        CapabilityRequest(
            capability=lookalike,
            parameters={},
            requested_scope=None,
            rationale='Replacing flexible.',
        )
    )
    assert mismatch.kind is CapabilityResultKind.DENIED
