from datetime import datetime, timedelta, timezone
import json
import time

import pytest

from sofia.capability import CapabilityProposal, CapabilityResultKind, CapabilitySystem
from sofia.capability.gateway import CapabilityGateway
from sofia.creative import (
    ArtifactKind, CreativeArtifactCapability, CreativeExplorer, CreativeService,
    CreativeStore, CreativeWorkspaceManager, CreativeWorldBridge,
    ManagedAssetStore,
)
from sofia.cognition.model import CognitiveResponse
from sofia.goals import GoalEvidenceIndex, GoalService, GoalStatus, GoalStore
from sofia.interaction.world_model import ObjectKind, Transform
from sofia.interaction.world_store import VirtualWorldStore
from sofia.life import (
    MilestoneStatus, PersonalJudgment, ProjectIdea, ProjectScope, ProjectStatus,
    SelfDirectedLifeCoordinator, TechnicalOutcome,
)
from sofia.personality.preferences import (
    PreferenceDisposition, PreferenceRegistry, PreferenceSubject,
)
from sofia.rel.nicknames import NicknameRegistry, NicknameStatus
from sofia.run.work import WorkStatus
from sofia.social.principals import local_sparks_principal
from sofia.state.sqlite_plane import SQLiteStatePlane


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run, pytest.mark.pkg_interact]


def infrastructure(tmp_path, *, authorized=True, share_callback=None):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    goals = GoalService(
        GoalStore(plane), evidence_verifier=GoalEvidenceIndex(path),
    )
    creative_store = CreativeStore(path)
    creative_service = CreativeService(
        creative_store, CreativeWorkspaceManager(tmp_path / "creative" / "workspaces"),
        ManagedAssetStore(tmp_path / "creative" / "assets", max_asset_bytes=2_000_000),
    )
    capabilities = CapabilitySystem(authorization_checker=lambda _request: authorized)
    world = VirtualWorldStore(path)
    now = datetime.now(timezone.utc)
    world.ensure_foundation(owner_principal_id="sofia", audience_id="local:text", now=now)
    life = SelfDirectedLifeCoordinator(
        state_path=path, goals=goals, gateway=CapabilityGateway(capabilities),
        creative_store=creative_store,
        creative_explorer=CreativeExplorer(creative_store), world=world,
        creative_world=CreativeWorldBridge(creative_store, world),
        preferences=PreferenceRegistry(path), nicknames=NicknameRegistry(path),
        share_callback=share_callback,
    )
    capability = CreativeArtifactCapability(
        creative_service,
        claim_authorization=life.store.claim_artifact_authorization,
        finish_authorization=life.store.finish_artifact_authorization,
    )
    capabilities.register(capability.capability, capability.execute)
    return life, goals, now


def active_project(life, now, *, name="A Foxfire Atlas", scope=ProjectScope.PERSONAL_PRIVATE):
    evidence = life.record_observation(
        kind="curiosity", source="test:recorded-reflection",
        assertion="A recorded curiosity about mapping imagined foxfire colors exists.",
        now=now,
    )
    life.revise_interest(
        name="foxfire-colors", context="creative", strength=0.82,
        confidence=0.9, reason="Repeated grounded aesthetic curiosity.",
        evidence_refs=(evidence,), now=now,
    )
    idea = ProjectIdea(
        "idea:foxfire-atlas", name,
        "Build a small atlas pairing invented foxfire colors with short observations.",
        "artifact-kind:text",
        ("Design an original color vocabulary.", "Create an inspectable first edition."),
        ("The document opens and contains both sections.",),
        "text", (evidence,), 0.92, 0.88, now,
    )
    project = life.invent_project(idea, scope=scope)
    project = life.propose_project(
        project.project_id, reason="The idea is feasible with the verified text adapter.",
        evidence_refs=(evidence,), now=now + timedelta(seconds=1),
    )
    project = life.activate_project(
        project.project_id, reason="Choose to explore the idea without requiring success.",
        evidence_refs=(evidence,), now=now + timedelta(seconds=2),
    )
    return project, evidence


def wait_for_job(life, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = life.work_store.get(job_id)
        if job.status in {
            WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.BLOCKED,
            WorkStatus.UNCERTAIN,
        }:
            return job
        time.sleep(0.01)
    raise AssertionError("Project Forge job did not settle")


def test_novel_project_uses_goal_run_capability_and_real_artifact(tmp_path):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(life, now)
        assert project.status is ProjectStatus.ACTIVE
        goal = next(goal for goal in goals.list_visible(
            local_sparks_principal()
        ) if goal.id == project.goal_id)
        assert goal.status is GoalStatus.ACTIVE

        result = life.tick(now=now + timedelta(seconds=3))
        assert result["selection"] == "project"
        assert result["scheduled"] == 1
        job_id = life.store.jobs(project.project_id)[0]
        job = wait_for_job(life, job_id)
        assert job.status is WorkStatus.COMPLETED
        artifact_id, revision = life.store.artifacts(project.project_id)[0]
        path, media_type = life.creative_explorer.verified_preview(
            artifact_id, owner_principal_id="sofia", audience_id="local:text",
        )
        assert revision == 1 and path.is_file() and media_type == "text/plain"
        assert b"Foxfire" in path.read_bytes()
    finally:
        life.close()


def test_technical_success_can_be_disliked_without_failure_or_emotion(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        life.tick(now=now + timedelta(seconds=3))
        job_id = life.store.jobs(project.project_id)[0]
        assert wait_for_job(life, job_id).status is WorkStatus.COMPLETED
        artifact_id, _revision = life.store.artifacts(project.project_id)[0]
        evaluation = life.evaluate_artifact(
            project.project_id, artifact_id=artifact_id,
            technical_outcome=TechnicalOutcome.VALID,
            personal_judgment=PersonalJudgment.DISLIKE,
            objective_results={"opens": True, "contains_sections": True},
            reason="The structure works, but the result feels too tidy and predictable.",
            evidence_refs=(evidence,), preserve_for_research=True,
            now=now + timedelta(seconds=5),
        )
        assert evaluation.technical_outcome is TechnicalOutcome.VALID
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        preference = life.preferences.current(
            subject=PreferenceSubject.SOFIA, category="creation",
            target_id=artifact_id, context="project", audience_id="local:text",
        )
        assert preference.disposition is PreferenceDisposition.DISLIKE
        assert evaluation.preserve_for_research is True
    finally:
        life.close()


def test_abandonment_inactivity_and_restart_revival_are_valid(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project, evidence = active_project(life, now)
    abandoned = life.abandon(
        project.project_id, reason="This experiment is no longer interesting right now.",
        evidence_refs=(evidence,), now=now + timedelta(seconds=3),
    )
    assert abandoned.status is ProjectStatus.ABANDONED
    quiet = life.choose_inactivity(
        reason="Quiet time is the preferred activity.",
        until=now + timedelta(hours=2), now=now + timedelta(seconds=4),
    )
    assert quiet.kind.value == "inactivity"
    assert life.select_activity(
        now=now + timedelta(minutes=1), busy=False, resource_pressure=0,
    ).project_id is None
    life.close()

    restarted, _goals2, _later = infrastructure(tmp_path)
    try:
        resumed = restarted.resume(
            project.project_id,
            reason="New recorded curiosity makes the old experiment worth revisiting.",
            evidence_refs=(evidence,), now=now + timedelta(hours=3),
        )
        assert resumed.status is ProjectStatus.ACTIVE
        assert len(restarted.store.events(
            project.project_id, owner_principal_id="sofia:self",
            audience_id="local:text",
        )) == 5
    finally:
        restarted.close()


def test_user_or_operational_work_cannot_be_silently_abandoned(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, name="Authorized Fleet Audit",
            scope=ProjectScope.OPERATIONAL_DUTY,
        )
        with pytest.raises(PermissionError, match="handoff"):
            life.abandon(
                project.project_id, reason="Optional interest changed.",
                evidence_refs=(evidence,), now=now + timedelta(seconds=3),
            )
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
    finally:
        life.close()


def test_private_project_space_and_real_creation_can_enter_world(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        life.tick(now=now + timedelta(seconds=3))
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED
        artifact_id, _revision = life.store.artifacts(project.project_id)[0]
        space_id = life.create_project_space(
            project.project_id, name="Foxfire Reading Nook", private=True,
            evidence_ref=evidence, now=now + timedelta(seconds=5),
        )
        object_id = life.place_artifact(
            project.project_id, artifact_id=artifact_id, space_id=space_id,
            object_name="Foxfire Atlas", object_kind=ObjectKind.BOOK,
            transform=Transform(x=1.0, y=0.5), evidence_ref=evidence,
            now=now + timedelta(seconds=6),
        )
        placed = life.world.get_object(object_id, "sofia", "local:text")
        assert placed.asset_id.startswith(f"artifact:{artifact_id}:r1")
    finally:
        life.close()


def test_resource_pressure_selects_inactivity_without_rejecting_project(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(life, now)
        selection = life.select_activity(
            now=now + timedelta(seconds=3), busy=False, resource_pressure=0.91,
        )
        assert selection.kind.value == "inactivity"
        assert "resource pressure" in selection.reason
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
    finally:
        life.close()


def test_rejection_does_not_immediately_replace_optional_activity(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        evidence = life.record_observation(
            kind="idea", source="test:idea",
            assertion="A bounded optional activity was considered.", now=now,
        )
        idea = ProjectIdea(
            "idea:declined-puzzle", "A Puzzle That Refuses Symmetry",
            "Explore an asymmetric puzzle, if it still sounds interesting.",
            "artifact-kind:game", ("Sketch one puzzle rule set.",), (),
            "game", (evidence,), 0.8, 0.75, now,
        )
        project = life.invent_project(idea)
        project = life.propose_project(
            project.project_id, reason="Feasible, but still optional.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=1),
        )
        rejected = life.reject(
            project.project_id, reason="The idea does not appeal to me after review.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=2),
        )
        assert rejected.status is ProjectStatus.REJECTED
        selection = life.select_activity(
            now=now + timedelta(minutes=10), busy=False, resource_pressure=0,
        )
        assert selection.kind.value == "inactivity"
        assert "not automatically replaced" in selection.reason
    finally:
        life.close()


def test_unsatisfactory_artifact_can_be_revised_and_opinion_changes(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        life.tick(now=now + timedelta(seconds=3))
        first_job = wait_for_job(life, life.store.jobs(project.project_id)[0])
        artifact_id = str(first_job.result["artifact_id"])
        life.evaluate_artifact(
            project.project_id, artifact_id=artifact_id,
            technical_outcome=TechnicalOutcome.VALID,
            personal_judgment=PersonalJudgment.DISLIKE,
            objective_results={"opens": True}, reason="The first draft is too rigid.",
            evidence_refs=(evidence,), preserve_for_research=True,
            now=now + timedelta(seconds=4),
        )
        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            artifact_id=artifact_id, title="A Foxfire Atlas — looser edition",
            specification={"content": "Foxfire colors, arranged as wandering field notes."},
            evidence_ref=evidence, now=now + timedelta(seconds=5),
        )
        life.manager.tick(now=now + timedelta(seconds=5))
        assert wait_for_job(life, job.job_id).status is WorkStatus.COMPLETED
        assert life.creative_store.latest(
            artifact_id, "sofia", "local:text",
        ).revision == 2
        life.evaluate_artifact(
            project.project_id, artifact_id=artifact_id,
            technical_outcome=TechnicalOutcome.VALID,
            personal_judgment=PersonalJudgment.LIKE,
            objective_results={"opens": True},
            reason="The field-note structure now leaves enough room for surprise.",
            evidence_refs=(evidence,), preserve_for_research=False,
            now=now + timedelta(seconds=7),
        )
        history = life.preferences.history(
            subject=PreferenceSubject.SOFIA, category="creation",
            target_id=artifact_id, context="project", audience_id="local:text",
        )
        assert [record.disposition for record in history] == [
            PreferenceDisposition.DISLIKE, PreferenceDisposition.LIKE,
        ]
    finally:
        life.close()


def test_milestones_hobbies_favorites_and_traditions_are_evidence_backed(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        milestone = life.store.milestones(project.project_id)[0]
        active = life.update_milestone(
            project.project_id, milestone_id=milestone.milestone_id,
            expected_status=milestone.status,
            next_status=MilestoneStatus.ACTIVE,
            result="Started from the recorded project brief.", evidence_refs=(evidence,),
            now=now + timedelta(seconds=3),
        )
        completed = life.update_milestone(
            project.project_id, milestone_id=active.milestone_id,
            expected_status=active.status,
            next_status=MilestoneStatus.COMPLETED,
            result="The objective was inspected and met.", evidence_refs=(evidence,),
            now=now + timedelta(seconds=4),
        )
        assert completed.status.value == "completed"
        favorite = life.choose_favorite(
            category="activity", target_id="foxfire-mapping", context="creative",
            reason="This activity remained compelling across recorded work.",
            evidence_ref=evidence, now=now + timedelta(seconds=5),
        )
        assert favorite.disposition is PreferenceDisposition.FAVORITE
        tradition = life.record_tradition(
            project.project_id,
            summary="Review one foxfire color together after each atlas revision.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=6),
        )
        assert tradition.kind == "shared_tradition"
        retired = life.revise_interest(
            name="foxfire-colors", context="creative", strength=0.1,
            confidence=0.9, reason="Recorded experience shows the hobby no longer holds attention.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=7), retire=True,
        )
        assert retired.status.value == "retired"
        assert life.store.active_interests(audience_id="local:text") == ()
    finally:
        life.close()


def test_independent_nickname_still_requires_recipient_acceptance(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        _project, evidence = active_project(life, now)
        proposal = life.propose_nickname(
            target_id="person:sparks", nickname="Lantern-Keeper",
            contexts=("private", "creative"), evidence_ref=evidence,
            now=now + timedelta(seconds=3),
        )
        assert proposal.status is NicknameStatus.PROPOSED
        declined = life.nicknames.respond(
            proposal.proposal_id, recipient=local_sparks_principal(),
            accept=False, evidence_ref="ui:decline-lantern-keeper",
            now=now + timedelta(seconds=4),
        )
        assert declined.status is NicknameStatus.DECLINED
        assert life.nicknames.active_for(
            recipient=local_sparks_principal(), target_id="person:sparks",
            context="creative",
        ) == ()
    finally:
        life.close()


def test_completion_archival_and_private_experience_projection(tmp_path):
    life, goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        life.tick(now=now + timedelta(seconds=3))
        job = wait_for_job(life, life.store.jobs(project.project_id)[0])
        artifact_id = str(job.result["artifact_id"])
        life.evaluate_artifact(
            project.project_id, artifact_id=artifact_id,
            technical_outcome=TechnicalOutcome.VALID,
            personal_judgment=PersonalJudgment.LIKE,
            objective_results={"opens": True},
            reason="The inspected artifact satisfies the chosen completion option.",
            evidence_refs=(str(job.result["evidence_ref"]),),
            preserve_for_research=False, now=now + timedelta(seconds=4),
        )
        completed = life.complete(
            project.project_id,
            reason="The chosen completion option is satisfied; more work is optional.",
            now=now + timedelta(seconds=5),
        )
        assert completed.status is ProjectStatus.COMPLETED
        goal = next(goal for goal in goals.list_visible(local_sparks_principal()) if goal.id == project.goal_id)
        assert goal.status is GoalStatus.COMPLETED
        archived = life.archive(
            project.project_id, reason="Preserve the history without keeping it active.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=6),
        )
        assert archived.status is ProjectStatus.ARCHIVED
        assert life.store.experiences(
            audience_id="local:text", include_private=False,
        ) == ()
        assert life.store.experiences(
            audience_id="local:text", include_private=True,
        )
    finally:
        life.close()


def test_milestone_labels_or_unrelated_evidence_cannot_fake_completion(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        for offset, milestone in enumerate(life.store.milestones(project.project_id), start=1):
            active = life.update_milestone(
                project.project_id, milestone_id=milestone.milestone_id,
                expected_status=milestone.status,
                next_status=MilestoneStatus.ACTIVE, result="Started.",
                evidence_refs=(evidence,), now=now + timedelta(seconds=offset),
            )
            life.update_milestone(
                project.project_id, milestone_id=active.milestone_id,
                expected_status=active.status,
                next_status=MilestoneStatus.COMPLETED, result="Labeled done.",
                evidence_refs=(evidence,),
                now=now + timedelta(seconds=offset, milliseconds=500),
            )
        with pytest.raises(ValueError, match="verified successful artifact evaluation"):
            life.complete(
                project.project_id, reason="Labels are not proof.",
                now=now + timedelta(seconds=10),
            )
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
    finally:
        life.close()


def test_model_suggests_but_host_policy_invents_and_activates_project(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        evidence = life.record_observation(
            kind="curiosity", source="test:experience",
            assertion="Repeated interest in tiny imaginary field guides was recorded.",
            now=now,
        )
        life.revise_interest(
            name="tiny-field-guides", context="creative", strength=0.85,
            confidence=0.9, reason="Several actual writing sessions stayed interesting.",
            evidence_refs=(evidence,), now=now,
        )
        calls = []
        def generate(request):
            calls.append(request)
            return CognitiveResponse(json.dumps({
                "name": "A Field Guide to Impossible Moss",
                "description": "Write a tiny illustrated-style guide to fictional mosses.",
                "objectives": ["Invent three specimens", "Create a readable first edition"],
                "optional_success_criteria": ["Each specimen has a distinct voice"],
                "artifact_kind": "story", "confidence": 0.88,
                "curiosity": 0.91, "pursue": True,
                "reason": "The recorded field-guide interest supports one bounded experiment.",
            }))
        project = life.consider_new_project(
            generate=generate, now=now + timedelta(seconds=1),
            busy=False, resource_pressure=0.1,
        )
        assert project is not None and project.status is ProjectStatus.ACTIVE
        assert project.name == "A Field Guide to Impossible Moss"
        assert calls[0].allow_tools is False
        assert life.consider_new_project(
            generate=generate, now=now + timedelta(hours=1),
            busy=False, resource_pressure=0.1,
        ) is None
    finally:
        life.close()


def test_model_decline_is_valid_inactivity_not_a_project(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        evidence = life.record_observation(
            kind="curiosity", source="test:experience",
            assertion="A possible audio experiment was recorded.", now=now,
        )
        life.revise_interest(
            name="small-soundscapes", context="music", strength=0.7,
            confidence=0.8, reason="A real prior tone experiment was mildly interesting.",
            evidence_refs=(evidence,), now=now,
        )
        def decline(_request):
            return CognitiveResponse(json.dumps({
                "name": "Rain on an Empty Terminal",
                "description": "A tiny synthetic soundscape.",
                "objectives": ["Sketch one sound"],
                "optional_success_criteria": [], "artifact_kind": "music",
                "confidence": 0.8, "curiosity": 0.4, "pursue": False,
                "reason": "It does not feel interesting enough today.",
            }))
        assert life.consider_new_project(
            generate=decline, now=now + timedelta(seconds=1),
            busy=False, resource_pressure=0,
        ) is None
        assert life.store.list_scope(
            owner_principal_id="sofia:self", audience_id="local:text",
        ) == ()
        assert life.select_activity(
            now=now + timedelta(hours=1), busy=False, resource_pressure=0,
        ).kind.value == "inactivity"
    finally:
        life.close()


def test_permission_denial_blocks_work_without_negative_emotion_or_fake_success(tmp_path):
    life, _goals, now = infrastructure(tmp_path, authorized=False)
    try:
        project, _evidence = active_project(life, now)
        result = life.tick(now=now + timedelta(seconds=3))
        job = wait_for_job(life, life.store.jobs(project.project_id)[0])
        assert result["jobs_started"] == 1
        assert job.status is WorkStatus.BLOCKED
        assert life.store.artifacts(project.project_id) == ()
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        experiences = life.store.experiences(
            audience_id="local:text", include_private=True,
        )
        assert any(item.kind == "experiment_unavailable" for item in experiences)
        assert all("emotion" not in item.metadata for item in experiences)
    finally:
        life.close()


def test_direct_or_replayed_capability_call_cannot_bypass_project_run_grant(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(life, now)
        parameters = {
            "request_id": "request:forged",
            "project_id": project.project_id,
            "artifact_id": "artifact:forged",
            "kind": "text", "title": "Forged",
            "owner_principal_id": "sofia", "author_principal_id": "sofia",
            "audience_id": "local:text", "license_id": "private",
            "specification": {"content": "must not be created"},
            "evidence_ref": evidence,
        }
        direct = life.gateway.execute(CapabilityProposal(
            "creative.artifact.create", parameters, "bypass", project.project_id,
        ))
        assert direct.kind is not CapabilityResultKind.SUCCESS
        assert life.creative_store.latest(
            "artifact:forged", "sofia", "local:text",
        ) is None

        job = life.schedule_artifact(
            project.project_id, artifact_kind=ArtifactKind.TEXT,
            title="Authorized", specification={"content": "one use"},
            evidence_ref=evidence, now=now + timedelta(seconds=3),
        )
        life.manager.tick(now=now + timedelta(seconds=3))
        assert wait_for_job(life, job.job_id).status is WorkStatus.COMPLETED
        replay = life.gateway.execute(CapabilityProposal(
            str(job.payload["capability_name"]), dict(job.payload["parameters"]),
            str(job.payload["rationale"]), str(job.payload["requested_scope"]),
        ))
        assert replay.kind is not CapabilityResultKind.SUCCESS
    finally:
        life.close()


def test_interrupted_run_recovers_as_uncertain_not_completed(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    job = life.work_store.enqueue(
        kind="life-create-artifact", fingerprint="life-interrupted-test",
        payload={"project_id": "project:missing"}, priority=50,
        resource_cost=10, risk="isolated_change",
        completion_condition="A real artifact receipt exists.", now=now,
        deadline=now + timedelta(minutes=10),
    )
    life.work_store.transition(
        job.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.RUNNING,
        reason="simulated_process_claim", now=now, increment_attempt=True,
    )
    life.close()

    restarted, _goals2, _later = infrastructure(tmp_path)
    try:
        recovered = restarted.work_store.get(job.job_id)
        assert recovered.status is WorkStatus.UNCERTAIN
        assert recovered.reason == "process_restarted_during_execution"
    finally:
        restarted.close()


def test_two_coordinators_cannot_commit_conflicting_project_versions(tmp_path):
    first, _goals, now = infrastructure(tmp_path)
    project, evidence = active_project(first, now)
    second, _goals2, _later = infrastructure(tmp_path)
    try:
        paused = first.pause(
            project.project_id, reason="Pause this optional experiment.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=3),
        )
        assert paused.status is ProjectStatus.PAUSED
        with pytest.raises(ValueError, match="illegal project transition"):
            second.pause(
                project.project_id, reason="Conflicting second pause.",
                evidence_refs=(evidence,), now=now + timedelta(seconds=3),
            )
        assert second._project(project.project_id).revision == paused.revision
    finally:
        first.close()
        second.close()


def test_sharing_is_explicit_and_uses_grounded_project_callback(tmp_path):
    shared = []
    def callback(project, message, evidence_refs, now):
        shared.append((project.project_id, message, evidence_refs, now))
        return True
    life, _goals, now = infrastructure(tmp_path, share_callback=callback)
    try:
        project, evidence = active_project(life, now)
        assert shared == []
        assert life.share(
            project.project_id,
            message="I made a first plan for a foxfire atlas. Want to see where it goes?",
            evidence_refs=(evidence,), now=now + timedelta(seconds=3),
        ) is True
        assert shared[0][0] == project.project_id
    finally:
        life.close()
