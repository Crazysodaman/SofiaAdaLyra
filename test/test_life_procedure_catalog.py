"""Real canonical LIFE/RUN proof required for repeatable skill history.

Authored for the final user-run test campaign. No synthetic tool result is
allowed to promote a procedure or create new SAFE/RUN authority.
"""
from datetime import timedelta
import json
import sqlite3

import pytest

from sofia.creative import ArtifactKind
from sofia.life import (
    PersonalJudgment, ProjectIdea, ProjectScope, ProjectStatus,
    TechnicalOutcome,
)
from sofia.life.procedures import LifeProcedureCatalog
from sofia.run.work import WorkStatus
from test.test_life_project_forge import (
    active_project, infrastructure, wait_for_job,
)


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run]


def _original_authorized_completion(life, project, evidence_ref, now):
    job = life.schedule_artifact(
        project.project_id, artifact_kind=ArtifactKind.TEXT,
        title="Original repeatable Foxfire note",
        specification={
            "content": (
                "Foxfire illuminated this original story, and its independently "
                "checkable project objective appears in the stored bytes."
            ),
        },
        evidence_ref=evidence_ref, now=now + timedelta(seconds=3),
    )
    life.manager.tick(now=now + timedelta(seconds=4))
    complete_job = wait_for_job(life, job.job_id)
    assert complete_job.status is WorkStatus.COMPLETED
    assert isinstance(complete_job.result, dict)
    artifact = str(complete_job.result["artifact_id"])
    revision = complete_job.result["revision"]
    receipt = str(complete_job.result["evidence_ref"])
    source_path, _media = life.creative_explorer.verified_preview(
        artifact, owner_principal_id="sofia", audience_id=project.audience_id,
    )
    source_text = source_path.read_text(encoding="utf-8")
    objective_results = {}
    for objective in project.brief.objectives:
        kind, separator, expected = objective.partition(":")
        assert kind == "text_contains" and separator and expected
        objective_results[objective] = expected in source_text
    assert objective_results and all(objective_results.values())
    evaluation = life.evaluate_artifact(
        project.project_id, artifact_id=artifact,
        technical_outcome=TechnicalOutcome.VALID,
        personal_judgment=PersonalJudgment.UNKNOWN,
        objective_results=objective_results,
        reason="Independently inspected original text source.",
        evidence_refs=(receipt,), preserve_for_research=False,
        now=now + timedelta(seconds=5),
    )
    assert evaluation.artifact_revision == revision
    assert life.complete(
        project.project_id,
        reason="Original text predicate passed on source bytes.",
        now=now + timedelta(seconds=6),
    ).status is ProjectStatus.COMPLETED
    return complete_job, receipt


def _second_same_capability_project(life, first, now):
    observation = life.record_observation(
        kind="independent-reproducibility",
        source="test:second-original-project",
        assertion="A distinct independent Foxfire writing experiment is selected.",
        now=now,
    )
    idea = ProjectIdea(
        f"idea:repeatable-foxfire-{now:%Y%m%d%H%M%S%f}",
        f"Second Independent Foxfire Note {now:%Y%m%d%H%M%S%f}",
        "Reproduce the typed check with an independently authored second artifact.",
        first.originating_interest,
        ("text_contains:Foxfire",), (),
        "text", (observation,), 0.89, 0.87, now,
    )
    project = life.invent_project(
        idea, scope=ProjectScope.PERSONAL_PRIVATE,
    )
    project = life.propose_project(
        project.project_id, reason="A fresh original source experiment.",
        evidence_refs=(observation,), now=now + timedelta(seconds=1),
    )
    project = life.activate_project(
        project.project_id, reason="An independent source-verifiable reproduction.",
        evidence_refs=(observation,), now=now + timedelta(seconds=2),
    )
    return project, observation


def test_two_distinct_real_checked_projects_promote_nonexecutable_procedure(
    tmp_path,
):
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, first_receipt = _original_authorized_completion(
            life, first, evidence, now,
        )
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=7),
        ) == 1
        first_proof = life.procedures.has_source_project(first.project_id)
        assert first_proof
        assert life.procedures.available_for_project(first) == ()
        with sqlite3.connect(life.path) as db:
            assert db.execute(
                "SELECT status FROM life_procedure_catalog",
            ).fetchone()[0] == "candidate"
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=8),
        ) == 0

        second_start = now + timedelta(minutes=1)
        second, other_evidence = _second_same_capability_project(
            life, first, second_start,
        )
        second_job, second_receipt = _original_authorized_completion(
            life, second, other_evidence, second_start,
        )
        assert first_job.job_id != second_job.job_id
        assert first_receipt != second_receipt
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=7),
        ) == 1

        available = life.procedures.available_for_project(second)
        assert len(available) == 1
        procedure = available[0]
        assert procedure.status == "verified"
        assert procedure.verified_projects == 2
        assert procedure.version == 1
        assert procedure.exact_capabilities == second.brief.permission_requirements
        assert procedure.source_objectives == ("text_contains:Foxfire",)
        assert first_receipt in procedure.provenance_refs
        assert second_receipt in procedure.provenance_refs
        assert "no_remote_replay_authorized" in procedure.preconditions
        view = life.goal_dependency_view(
            now=second_start + timedelta(seconds=8),
        )
        assert {row["project_id"] for row in view} == {
            first.project_id, second.project_id,
        }
        assert all(
            procedure.procedure_id in row["verified_procedures"]
            for row in view
        )
        # Neither recording nor retrieval ever submits another RUN job.
        assert life.store.jobs(first.project_id) == (first_job.job_id,)
        assert life.store.jobs(second.project_id) == (second_job.job_id,)
        assert life.procedures.available_for_project(first) == available
        life.procedures.quarantine(
            procedure.procedure_id,
            reason="A human operator flagged incompatible source assumptions.",
            now=second_start + timedelta(seconds=9),
        )
        assert life.procedures.available_for_project(first) == ()
        assert life.procedures.available_for_project(second) == ()
    finally:
        life.close()


def _independent_post_quarantine_project(life, original, now, suffix):
    """A separately originated private work item, never historical replay."""
    observation = life.record_observation(
        kind="independent-skill-recovery",
        source=f"test:independent-recovery-{suffix}",
        assertion=f"Distinct genuine creative trial {suffix} was observed.",
        now=now,
    )
    idea = ProjectIdea(
        f"idea:verified-creative-recovery-{suffix}",
        f"New Foxfire Recovery Trial {suffix}",
        "Independently author and verify a new bounded creative artifact.",
        original.originating_interest,
        ("text_contains:Foxfire",), (),
        "text", (observation,), 0.85, 0.89, now,
    )
    project = life.invent_project(
        idea, scope=ProjectScope.PERSONAL_PRIVATE,
    )
    project = life.propose_project(
        project.project_id, reason="New post-quarantine independent trial.",
        evidence_refs=(observation,), now=now + timedelta(seconds=1),
    )
    project = life.activate_project(
        project.project_id,
        reason="Independent original governed creative trial.",
        evidence_refs=(observation,), now=now + timedelta(seconds=2),
    )
    return project, observation


def test_hybrid_quarantine_requires_new_nonexecutable_verified_generation(
    tmp_path,
):
    """Quarantined v1 never revives; two fresh source projects earn v2."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        original, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, first_receipt = _original_authorized_completion(
            life, original, evidence, now,
        )
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=7),
        ) == 1
        other_at = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, original, other_at,
        )
        second_job, second_receipt = _original_authorized_completion(
            life, second, second_evidence, other_at,
        )
        assert life._reconcile_procedure_catalog(
            now=other_at + timedelta(seconds=7),
        ) == 1
        old = life.procedures.available_for_project(original)[0]
        assert old.version == 1
        quarantined_at = now + timedelta(minutes=2)
        assert life.procedures.quarantine(
            old.procedure_id, reason="The original version needs fresh proof.",
            now=quarantined_at,
        )
        assert life.procedures.available_for_project(original) == ()

        # An old proof may not be laundered into the fresh generation,
        # even if its original bytes and RUN receipt still validate.
        with pytest.raises(ValueError, match="post-quarantine"):
            life.procedures.record_verified_attempt(
                project=life._project(second.project_id),
                job_id=second_job.job_id,
                original_run_evidence_ref=second_receipt,
                now=quarantined_at + timedelta(seconds=1),
            )
        third_at = now + timedelta(minutes=3)
        third, third_evidence = _independent_post_quarantine_project(
            life, original, third_at, "third",
        )
        _original_authorized_completion(life, third, third_evidence, third_at)
        assert life._reconcile_procedure_catalog(
            now=third_at + timedelta(seconds=7),
        ) == 1
        assert life.procedures.available_for_project(original) == ()
        fourth_at = now + timedelta(minutes=4)
        fourth, fourth_evidence = _independent_post_quarantine_project(
            life, original, fourth_at, "fourth",
        )
        _original_authorized_completion(life, fourth, fourth_evidence, fourth_at)
        assert life._reconcile_procedure_catalog(
            now=fourth_at + timedelta(seconds=7),
        ) == 1

        replacement = life.procedures.available_for_project(original)
        assert len(replacement) == 1
        assert replacement[0].version == 2
        assert replacement[0].procedure_id != old.procedure_id
        assert replacement[0].verified_projects == 2
        assert life._verified_procedure_origins_current(
            (third.project_id, fourth.project_id),
            procedure_id=replacement[0].procedure_id,
            now=fourth_at + timedelta(seconds=8),
        )
        with sqlite3.connect(life.path) as db:
            recorded = db.execute(
                "SELECT status,version,quarantine_reason "
                "FROM life_procedure_catalog WHERE procedure_id=?",
                (old.procedure_id,),
            ).fetchone()
            assert recorded[0] == "quarantined"
            assert recorded[1] == 1
            assert recorded[2] == "The original version needs fresh proof."
            successor = db.execute(
                "SELECT quarantined_predecessor_id,disposition "
                "FROM life_procedure_replacement WHERE successor_id=?",
                (replacement[0].procedure_id,),
            ).fetchone()
            assert successor == (
                old.procedure_id, "auto_nonexecutable_creative_knowledge",
            )
            assert db.execute(
                "SELECT COUNT(*) FROM life_procedure_proof "
                "WHERE procedure_id=? AND project_id IN (?,?)",
                (
                    replacement[0].procedure_id,
                    original.project_id, second.project_id,
                ),
            ).fetchone()[0] == 0
        assert first_job.job_id != second_job.job_id
        assert first_receipt != second_receipt
    finally:
        life.close()


@pytest.mark.parametrize("blocked", ["remote_tool", "new_capability", "new_audience"])
def test_hybrid_automatic_recovery_excludes_remote_and_powerful_skills(
    tmp_path, blocked,
):
    """Non-creative/remote/cross-audience skills cannot auto-recover."""
    from dataclasses import replace

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(life, now)
        assert LifeProcedureCatalog._auto_recovery_eligible(project)
        if blocked == "remote_tool":
            changed = replace(
                project, brief=replace(
                    project.brief,
                    required_tools=project.brief.required_tools + ("fleet:remote",),
                ),
            )
        elif blocked == "new_capability":
            changed = replace(
                project, brief=replace(
                    project.brief,
                    permission_requirements=(
                        "creative.artifact.create", "fleet.remote.execute",
                    ),
                ),
            )
        else:
            changed = replace(project, audience_id="other:private")
        assert not LifeProcedureCatalog._auto_recovery_eligible(changed)
    finally:
        life.close()


def test_procedure_catalog_refuses_fabricated_job_and_source_receipt(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        job, receipt = _original_authorized_completion(
            life, project, evidence, now,
        )
        # Prove invalid RUN evidence against the current completed project,
        # rather than failing earlier on an obsolete ACTIVE project snapshot.
        project = life.store.get(
            project.project_id,
            owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        )
        assert project.status is ProjectStatus.COMPLETED
        catalog = LifeProcedureCatalog(life.path)
        with pytest.raises(ValueError, match="real original scoped RUN"):
            catalog.record_verified_attempt(
                project=project, job_id=job.job_id,
                original_run_evidence_ref="goal-evidence:imaginary",
                now=now + timedelta(seconds=7),
            )
        assert catalog.has_source_project(project.project_id) is False
        with pytest.raises(ValueError, match="real original scoped RUN"):
            catalog.record_verified_attempt(
                project=project, job_id="job:imaginary",
                original_run_evidence_ref=receipt,
                now=now + timedelta(seconds=7),
            )
        assert catalog.available_for_project(project) == ()
    finally:
        life.close()


def test_verified_procedure_quarantined_when_original_bytes_change(tmp_path):
    """A past pair of successes cannot mask current loss of source evidence."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, first_evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, _receipt = _original_authorized_completion(
            life, first, first_evidence, now,
        )
        second_start = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, second_start,
        )
        second_job, _receipt = _original_authorized_completion(
            life, second, second_evidence, second_start,
        )
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=7),
        ) == 2
        assert len(life.procedures.available_for_project(first)) == 1
        original = life.goal_dependency_view(
            now=second_start + timedelta(seconds=8),
        )
        assert all(item["verified_procedures"] for item in original)
        artifact_id = str(first_job.result["artifact_id"])
        original_path, _media = life.creative_explorer.verified_preview(
            artifact_id,
            owner_principal_id="sofia",
            audience_id="local:text",
        )
        original_path.write_text(
            "These bytes are not the original independently verified work.",
            encoding="utf-8",
        )
        # Diagnostics should fail closed even before the mutation-free audit
        # gets a chance to record its quarantine decision.
        after = life.goal_dependency_view(
            now=second_start + timedelta(seconds=9),
        )
        assert not any(row["verified_procedures"] for row in after)
        assert life._audit_procedure_sources(
            now=second_start + timedelta(seconds=10),
        ) == 1
        assert life._audit_procedure_sources(
            now=second_start + timedelta(seconds=11),
        ) == 0
        assert life.procedures.available_for_project(second) == ()
        assert life.work_store.get(first_job.job_id).status is WorkStatus.COMPLETED
        assert life.work_store.get(second_job.job_id).status is WorkStatus.COMPLETED
        # Quarantine changes only the reliability of remembered procedure
        # knowledge, not historic LIFE/GOALS/RUN or file contents.
        assert life._project(first.project_id).status is ProjectStatus.COMPLETED
        assert life._project(second.project_id).status is ProjectStatus.COMPLETED
    finally:
        life.close()


def test_original_life_draft_cites_only_current_twice_verified_procedure(
    tmp_path,
):
    """The third creative project sees source proof, never implicit tool rights."""
    from sofia.cognition.model import CognitiveResponse
    from sofia.life.draft_agent import ProjectDraftAgent

    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        second_start = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, second_start,
        )
        _original_authorized_completion(
            life, second, second_evidence, second_start,
        )
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=8),
        ) == 2
        third_start = now + timedelta(minutes=2)
        third, _source = _second_same_capability_project(
            life, first, third_start,
        )
        original = life._current_verified_procedures_for_draft(
            third, now=third_start + timedelta(seconds=3),
        )
        assert len(original) == 1
        assert original[0].verified_projects == 2
        captured = []
        def model(request):
            captured.append(request)
            return CognitiveResponse(content=json.dumps({
                "content": (
                    "Foxfire is a new original story authored with an explicit "
                    "creative objective; this is not a copied prior artifact."
                ),
            }))
        specification = ProjectDraftAgent(model).draft(
            third, ArtifactKind.TEXT, verified_precedents=original,
        )
        assert "Foxfire" in specification["content"]
        assert captured[0].allow_tools is False
        assert "verified_precedents_non_authoritative" in captured[0].messages[1].content
        assert original[0].procedure_id in captured[0].messages[1].content
        assert "reproduce_original_work" in captured[0].messages[1].content
        assert life.store.jobs(third.project_id) == ()
    finally:
        life.close()


def test_procedure_source_rot_is_not_reused_for_subsequent_life_draft(
    tmp_path,
):
    """Current source invalidation withdraws precedents before model use."""
    from sofia.life.draft_agent import ProjectDraftAgent

    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, _ = _original_authorized_completion(
            life, first, evidence, now,
        )
        second_start = now + timedelta(minutes=1)
        second, evidence2 = _second_same_capability_project(
            life, first, second_start,
        )
        _original_authorized_completion(life, second, evidence2, second_start)
        assert life._reconcile_procedure_catalog(
            now=second_start + timedelta(seconds=8),
        ) == 2
        third, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        first_path, _media = life.creative_explorer.verified_preview(
            str(first_job.result["artifact_id"]),
            owner_principal_id="sofia", audience_id="local:text",
        )
        first_path.write_text("Changed content invalidates the prior proof.")
        assert life._current_verified_procedures_for_draft(
            third, now=now + timedelta(minutes=2, seconds=4),
        ) == ()
        assert life.store.jobs(third.project_id) == ()
    finally:
        life.close()


@pytest.mark.parametrize("alter_original", ["revoke_receipt", "downgrade_run"])
def test_procedure_promotion_rechecks_original_source_under_writer_lock(
    tmp_path, monkeypatch, alter_original,
):
    """An original RUN proof changed after bytes-check cannot promote skill."""
    import sofia.life.procedures as procedures_module

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        job, receipt = _original_authorized_completion(
            life, project, evidence, now,
        )
        original_checker = procedures_module.inspect_objective_artifact
        altered = []

        def original_source_changes_after_byte_review(**kwargs):
            report = original_checker(**kwargs)
            # The catalog has already checked the old RUN/evidence identity.
            # Change canonical state just before its final writer transaction.
            with sqlite3.connect(life.path) as db:
                if alter_original == "revoke_receipt":
                    db.execute(
                        "DELETE FROM goal_evidence_record WHERE evidence_ref=?",
                        (receipt,),
                    )
                else:
                    db.execute(
                        "UPDATE autonomous_work_job SET status='uncertain' "
                        "WHERE job_id=?",
                        (job.job_id,),
                    )
            altered.append(True)
            return report

        monkeypatch.setattr(
            procedures_module, "inspect_objective_artifact",
            original_source_changes_after_byte_review,
        )
        with pytest.raises(
            ValueError, match="original LIFE/RUN/evaluation proof changed",
        ):
            life.procedures.record_verified_attempt(
                project=life._project(project.project_id),
                job_id=job.job_id, original_run_evidence_ref=receipt,
                now=now + timedelta(seconds=8),
            )
        assert altered == [True]
        assert life.procedures.has_source_project(project.project_id) is False
        with sqlite3.connect(life.path) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM life_procedure_catalog",
            ).fetchone()[0] == 0
            assert db.execute(
                "SELECT COUNT(*) FROM life_procedure_proof",
            ).fetchone()[0] == 0
    finally:
        life.close()


def test_catalog_writer_rejects_stale_bytes_even_when_original_run_was_completed(
    tmp_path,
):
    """A future direct caller cannot promote old success labels after corruption."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, observation = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        job, receipt = _original_authorized_completion(
            life, project, observation, now,
        )
        artifact = str(job.result["artifact_id"])
        original, _mime = life.creative_explorer.verified_preview(
            artifact, owner_principal_id="sofia", audience_id="local:text",
        )
        original.write_text(
            "The source bytes changed after the original RUN receipt.",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="current original creative bytes"):
            life.procedures.record_verified_attempt(
                project=life._project(project.project_id),
                job_id=job.job_id,
                original_run_evidence_ref=receipt,
                now=now + timedelta(seconds=8),
            )
        assert life.procedures.has_source_project(project.project_id) is False
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=9),
        ) == 0
    finally:
        life.close()


def test_procedure_recovery_rotates_past_invalid_source_after_restart(tmp_path):
    """A bad early completion cannot permanently starve later valid work."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, first_evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        first_job, _ = _original_authorized_completion(
            life, first, first_evidence, now,
        )
        later = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, later,
        )
        second_job, _ = _original_authorized_completion(
            life, second, second_evidence, later,
        )
        ordered = sorted(
            ((first, first_job), (second, second_job)),
            key=lambda item: item[0].project_id,
        )
        invalid_project, invalid_job = ordered[0]
        valid_project, _ = ordered[1]
        original, _mime = life.creative_explorer.verified_preview(
            str(invalid_job.result["artifact_id"]),
            owner_principal_id="sofia", audience_id="local:text",
        )
        original.write_text(
            "This is not the source independently validated by the RUN receipt.",
            encoding="utf-8",
        )

        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=8), limit=1,
        ) == 0
        assert life.procedures.has_source_project(invalid_project.project_id) is False

        # Recreate the catalog as on application restart: the scan checkpoint
        # belongs to canonical SQLite, not ephemeral coordinator memory.
        life.procedures = LifeProcedureCatalog(life.path)
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=9), limit=1,
        ) == 1
        assert life.procedures.has_source_project(valid_project.project_id)
        assert not life.procedures.has_source_project(invalid_project.project_id)
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=10), limit=1,
        ) == 0
        assert life.store.jobs(valid_project.project_id)
    finally:
        life.close()


def test_procedure_page_is_bounded_and_source_scoped(tmp_path):
    """No write of catalog proof or RUN action occurs from paging alone."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, project, evidence, now)
        catalog = life.procedures
        assert catalog.next_completed_source_page(
            owner_principal_id="sofia:self",
            audience_id="local:text", limit=1,
        ) == (project.project_id,)
        assert LifeProcedureCatalog(life.path).next_completed_source_page(
            owner_principal_id="some-other-principal",
            audience_id="local:text", limit=1,
        ) == ()
        assert LifeProcedureCatalog(life.path).next_completed_source_page(
            owner_principal_id="sofia:self",
            audience_id="another-audience", limit=1,
        ) == ()
        assert catalog.has_source_project(project.project_id) is False
        assert len(life.store.jobs(project.project_id)) == 1
        with pytest.raises(ValueError, match="scoped bounded"):
            catalog.next_completed_source_page(
                owner_principal_id="sofia:self",
                audience_id="local:text", limit=0,
            )
    finally:
        life.close()


def test_verified_procedure_audit_rotates_to_older_source_after_restart(
    tmp_path,
):
    """The periodic integrity audit must eventually check older proof too."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, first_evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, first_evidence, now)
        second_time = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, second_time,
        )
        _original_authorized_completion(
            life, second, second_evidence, second_time,
        )

        def original_project(objective, stamp, suffix):
            source = life.record_observation(
                kind="independent-reproducibility",
                source="test:second-compatible-procedure",
                assertion="Another separately authored creative criterion was chosen.",
                now=stamp,
            )
            idea = ProjectIdea(
                f"idea:procedure-audit-{suffix}",
                f"Independent creative audit {suffix}",
                "Test a different original, independently validated writing goal.",
                first.originating_interest, (objective,), (), "text",
                (source,), 0.89, 0.87, stamp,
            )
            project = life.invent_project(
                idea, scope=ProjectScope.PERSONAL_PRIVATE,
            )
            life.propose_project(
                project.project_id,
                reason="Distinct original creative objective is source-grounded.",
                evidence_refs=(source,), now=stamp + timedelta(seconds=1),
            )
            life.activate_project(
                project.project_id,
                reason="Begin separately validated repeatable original work.",
                evidence_refs=(source,), now=stamp + timedelta(seconds=2),
            )
            job, _receipt = _original_authorized_completion(
                life, project, source, stamp,
            )
            return project, job

        third, third_job = original_project(
            "text_contains:independently", now + timedelta(minutes=2), "third",
        )
        fourth, fourth_job = original_project(
            "text_contains:independently", now + timedelta(minutes=3), "fourth",
        )
        checked_at = now + timedelta(minutes=3, seconds=8)
        assert life._reconcile_procedure_catalog(
            now=checked_at, limit=4,
        ) == 4
        verified = life.procedures.verified_proof_projects()
        assert len(verified) == 2
        by_id = sorted(pair[0] for pair in verified)
        assert LifeProcedureCatalog(life.path).next_verified_proof_audit_page(
            limit=1,
        )[0][0] == by_id[0]
        assert LifeProcedureCatalog(life.path).next_verified_proof_audit_page(
            limit=1,
        )[0][0] == by_id[1]

        # Invalidate an actual original of the second catalog record, not
        # its SQL proof metadata; the independent byte check must catch it.
        procedure_for_third = life.procedures.available_for_project(
            life._project(third.project_id),
        )[0].procedure_id
        procedure_for_first = life.procedures.available_for_project(
            life._project(first.project_id),
        )[0].procedure_id
        if procedure_for_third == by_id[1]:
            corrupted_job = third_job
        else:
            assert procedure_for_first == by_id[1]
            # Retrieve the original RUN artifact linked to the Foxfire group.
            original_job_id = life.store.jobs(first.project_id)[0]
            corrupted_job = life.work_store.get(original_job_id)
        source_path, _mime = life.creative_explorer.verified_preview(
            str(corrupted_job.result["artifact_id"]),
            owner_principal_id="sofia", audience_id="local:text",
        )
        source_path.write_text(
            "The original proof is no longer independently valid.",
            encoding="utf-8",
        )
        # The cursor is already at the larger ID; first audit wraps to the
        # still-valid lower ID, second audit reaches the invalid older proof.
        assert life._audit_procedure_sources(
            now=checked_at + timedelta(seconds=1), limit=1,
        ) == 0
        life.procedures = LifeProcedureCatalog(life.path)
        assert life._audit_procedure_sources(
            now=checked_at + timedelta(seconds=2), limit=1,
        ) == 1
        assert by_id[1] not in dict(life.procedures.verified_proof_projects())
        assert by_id[0] in dict(life.procedures.verified_proof_projects())
        assert life.store.jobs(third.project_id) == (third_job.job_id,)
        assert life.store.jobs(fourth.project_id) == (fourth_job.job_id,)
    finally:
        life.close()


def test_exact_draft_source_lookup_is_not_global_recent_catalog_page(
    tmp_path, monkeypatch,
):
    """Older exactly compatible verified skill remains usable at draft time."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        later = now + timedelta(minutes=1)
        second, evidence2 = _second_same_capability_project(life, first, later)
        _original_authorized_completion(life, second, evidence2, later)
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=8),
        ) == 2
        third, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        precedent = life.procedures.available_for_project(third)[0]
        assert set(life.procedures.source_projects_for_compatible_precedent(
            procedure=precedent, project=third,
        )) == {first.project_id, second.project_id}
        def global_page_is_not_an_admission_gate(**_kwargs):
            raise AssertionError("global newest-N list cannot hide exact skill")
        monkeypatch.setattr(
            life.procedures, "verified_proof_projects",
            global_page_is_not_an_admission_gate,
        )
        assert life._current_verified_procedures_for_draft(
            third, now=now + timedelta(minutes=2, seconds=3),
        ) == (precedent,)
        with pytest.raises(ValueError, match="bounded original"):
            life.procedures.source_projects_for_compatible_precedent(
                procedure=precedent, project=third, limit=1,
            )
        life.procedures.quarantine(
            precedent.procedure_id, reason="operator revoked this source",
            now=now + timedelta(minutes=2, seconds=4),
        )
        assert life.procedures.source_projects_for_compatible_precedent(
            procedure=precedent, project=third,
        ) == ()
        assert life.store.jobs(third.project_id) == ()
    finally:
        life.close()


def test_catalog_writer_rejection_does_not_abort_other_completed_learning(
    tmp_path, monkeypatch,
):
    """A concurrent source invalidation cannot abort the entire LIFE cycle."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, first_evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, first_evidence, now)
        later = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, later,
        )
        _original_authorized_completion(life, second, second_evidence, later)
        original = life.procedures.record_verified_attempt
        seen = []
        def independently_reject_one_original(*, project, **kwargs):
            seen.append(project.project_id)
            if project.project_id == first.project_id:
                raise ValueError(
                    "independent original source changed after coordinator inspection"
                )
            return original(project=project, **kwargs)
        monkeypatch.setattr(
            life.procedures, "record_verified_attempt",
            independently_reject_one_original,
        )
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=8), limit=2,
        ) == 1
        assert set(seen) == {first.project_id, second.project_id}
        assert not life.procedures.has_source_project(first.project_id)
        assert life.procedures.has_source_project(second.project_id)
        monkeypatch.setattr(
            life.procedures, "record_verified_attempt", original,
        )
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=9), limit=2,
        ) == 1
        assert life.procedures.has_source_project(first.project_id)
        assert life.procedures.has_source_project(second.project_id)
        assert len(life.store.jobs(first.project_id)) == 1
        assert len(life.store.jobs(second.project_id)) == 1
    finally:
        life.close()



def test_procedure_precedent_rejects_tampered_original_job_receipt(tmp_path):
    """A different valid original artifact cannot launder a forged proof row."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        later = now + timedelta(minutes=1)
        second, source = _second_same_capability_project(life, first, later)
        _original_authorized_completion(life, second, source, later)
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=8),
        ) == 2
        future, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        found = life._current_verified_procedures_for_draft(
            future, now=now + timedelta(minutes=2, seconds=4),
        )
        assert len(found) == 1
        procedure_id = found[0].procedure_id
        real = life.procedures.proof_receipts_for_procedure(procedure_id)
        assert len(real) == 2
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE life_procedure_proof SET evidence_ref=? "
                "WHERE procedure_id=? AND project_id=?",
                ("goal-evidence:forged-elsewhere", procedure_id, first.project_id),
            )
        assert life._current_verified_procedures_for_draft(
            future, now=now + timedelta(minutes=2, seconds=5),
        ) == ()
        assert life._audit_procedure_sources(
            now=now + timedelta(minutes=2, seconds=6),
        ) == 1
        assert life.procedures.available_for_project(future) == ()
        assert life.store.jobs(future.project_id) == ()
        assert life.work_store.get(
            life.store.jobs(second.project_id)[0],
        ).status is WorkStatus.COMPLETED
    finally:
        life.close()


def test_procedure_proof_check_rejects_original_job_mismatch(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        later = now + timedelta(minutes=1)
        second, source = _second_same_capability_project(life, first, later)
        _original_authorized_completion(life, second, source, later)
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=8),
        ) == 2
        third, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        procedure_id = life.procedures.available_for_project(third)[0].procedure_id
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE life_procedure_proof SET job_id=? "
                "WHERE procedure_id=? AND project_id=?",
                ("job:unrelated", procedure_id, first.project_id),
            )
        assert life._current_verified_procedures_for_draft(
            third, now=now + timedelta(minutes=2, seconds=8),
        ) == ()
    finally:
        life.close()


def test_goal_dependency_view_keeps_exact_provenance_without_global_newest_page(
    tmp_path, monkeypatch,
):
    """Operator diagnostic agrees with safe LIFE drafting after catalog grows."""
    import sqlite3

    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        second_now = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, second_now,
        )
        _original_authorized_completion(
            life, second, second_evidence, second_now,
        )
        assert life._reconcile_procedure_catalog(
            now=second_now + timedelta(seconds=8),
        ) == 2
        future, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        record = life.procedures.available_for_project(future)[0]
        def no_global_report(**_kwargs):
            raise AssertionError("global newest-N procedure list cannot gate diagnostic")
        monkeypatch.setattr(
            life.procedures, "verified_proof_projects", no_global_report,
        )
        view = life.goal_dependency_view(
            now=now + timedelta(minutes=2, seconds=4),
        )
        future_row = next(
            row for row in view if row["project_id"] == future.project_id
        )
        assert future_row["verified_procedures"] == (record.procedure_id,)
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE life_procedure_proof SET evidence_ref=? "
                "WHERE procedure_id=? AND project_id=?",
                ("source-ref:revoked", record.procedure_id, first.project_id),
            )
        # The cache lives only for one view call; a future operator read
        # must see the current revoked source and never a stale VERIFIED tag.
        after = life.goal_dependency_view(
            now=now + timedelta(minutes=2, seconds=5),
        )
        future_row = next(
            row for row in after if row["project_id"] == future.project_id
        )
        assert future_row["verified_procedures"] == ()
        assert life.store.jobs(future.project_id) == ()
    finally:
        life.close()


def test_verified_skill_refuses_stale_native_tool_version_and_quarantines(
    tmp_path,
):
    """Two authentic prior successes are not permission to assume new tools."""
    from sofia.creative import NativeCreativeAdapter

    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        second_at = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, second_at,
        )
        _original_authorized_completion(
            life, second, second_evidence, second_at,
        )
        assert life._reconcile_procedure_catalog(
            now=second_at + timedelta(seconds=8),
        ) == 2
        third, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        assert len(life._current_verified_procedures_for_draft(
            third, now=now + timedelta(minutes=2, seconds=3),
        )) == 1
        source_job = life.work_store.get(life.store.jobs(first.project_id)[0])
        original_artifact = source_job.result["artifact_id"]
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE creative_artifact_revision SET tool_version=? "
                "WHERE artifact_id=? AND revision=?",
                ("obsolete-native-version", original_artifact,
                 source_job.result["revision"]),
            )
        assert life._current_verified_procedures_for_draft(
            third, now=now + timedelta(minutes=2, seconds=4),
        ) == ()
        assert life._audit_procedure_sources(
            now=now + timedelta(minutes=2, seconds=5),
        ) == 1
        assert life.procedures.available_for_project(third) == ()
        assert life.store.jobs(third.project_id) == ()
    finally:
        life.close()


def test_procedure_promotion_requires_original_current_native_tool_version(
    tmp_path,
):
    """Actual source output metadata cannot claim a stale or missing adapter."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        job, receipt = _original_authorized_completion(
            life, project, evidence, now,
        )
        with sqlite3.connect(life.path) as db:
            db.execute(
                "UPDATE creative_artifact_revision SET tool_id=? "
                "WHERE artifact_id=? AND revision=?",
                ("creative.unverified-other-host",
                 job.result["artifact_id"], job.result["revision"]),
            )
        with pytest.raises(ValueError, match="tool ID/version"):
            life.procedures.record_verified_attempt(
                project=life._project(project.project_id),
                job_id=job.job_id, original_run_evidence_ref=receipt,
                now=now + timedelta(seconds=9),
            )
        assert not life.procedures.has_source_project(project.project_id)
    finally:
        life.close()



def test_quarantine_preserves_first_original_reason_and_timestamp(tmp_path):
    """A restarted or competing audit cannot overwrite an existing decision."""
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        later = now + timedelta(minutes=1)
        second, second_evidence = _second_same_capability_project(
            life, first, later,
        )
        _original_authorized_completion(
            life, second, second_evidence, later,
        )
        assert life._reconcile_procedure_catalog(
            now=later + timedelta(seconds=8),
        ) == 2
        third, _ = _second_same_capability_project(
            life, first, now + timedelta(minutes=2),
        )
        procedure_id = life.procedures.available_for_project(
            third,
        )[0].procedure_id
        first_time = now + timedelta(minutes=2, seconds=3)
        assert life.procedures.quarantine(
            procedure_id,
            reason="Original artifact digest no longer matches.",
            now=first_time,
        ) is True
        assert life.procedures.quarantine(
            procedure_id, reason="Later diagnostic must not replace first.",
            now=first_time + timedelta(minutes=1),
        ) is False
        with sqlite3.connect(life.path) as db:
            state = db.execute(
                "SELECT status,quarantine_reason,updated_at "
                "FROM life_procedure_catalog WHERE procedure_id=?",
                (procedure_id,),
            ).fetchone()
        assert state == (
            "quarantined",
            "Original artifact digest no longer matches.",
            first_time.isoformat(),
        )
        assert life.procedures.available_for_project(third) == ()
        assert life._audit_procedure_sources(
            now=first_time + timedelta(minutes=2),
        ) == 0
        assert life.store.jobs(third.project_id) == ()
    finally:
        life.close()


def test_quarantine_rejects_candidate_or_unknown_procedure(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        first, evidence = active_project(
            life, now, objectives=("text_contains:Foxfire",),
        )
        _original_authorized_completion(life, first, evidence, now)
        assert life._reconcile_procedure_catalog(
            now=now + timedelta(seconds=8),
        ) == 1
        with sqlite3.connect(life.path) as db:
            candidate = db.execute(
                "SELECT procedure_id FROM life_procedure_catalog "
                "WHERE status='candidate'",
            ).fetchone()
        assert candidate is not None
        with pytest.raises(ValueError, match="only verified"):
            life.procedures.quarantine(
                candidate[0], reason="Candidate has not been promoted.",
                now=now + timedelta(seconds=9),
            )
        with pytest.raises(LookupError, match="does not exist"):
            life.procedures.quarantine(
                "life-procedure:absent-from-original-catalog",
                reason="No source exists",
                now=now + timedelta(seconds=9),
            )
    finally:
        life.close()
