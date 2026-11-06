"""Production LIFE background follow-through: real work, evidence, revision.

Tests are deliberately authored but NOT run until the final user-authorized
verification campaign. No simulated receipt may count as project success.
"""
from datetime import datetime, timedelta, timezone
import json

import pytest
from zoneinfo import ZoneInfo

from sofia.core.cognition.model import CognitiveResponse
from sofia.core.life import (
    PersonalJudgment, ProjectIdea, ProjectScope, ProjectStatus,
    TechnicalOutcome,
)
from sofia.platform.run.work import WorkStatus
from test.test_life_project_forge import (
    infrastructure, active_project, wait_for_job,
)


class LifeTestClock:
    """One host clock for scheduling, actual capability effects and RUN receipts."""

    def __init__(self, value=None):
        self.value = value or datetime(2026, 9, 29, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def at(self, value):
        assert value.tzinfo is not None and value.utcoffset() is not None
        self.value = value.astimezone(timezone.utc)
        return self.value


@pytest.fixture
def life_clock():
    return LifeTestClock()


def typed_active_project(life, now, *, objectives, name="A Checkable Foxfire Note"):
    observation = life.record_observation(
        kind="curiosity", source="test:typed-objective",
        assertion="A source-backed interest in original experimental stories.",
        now=now,
    )
    # Real LIFE admission requires an active, original-evidence-linked interest.
    # An arbitrary text label is not a canonical originating interest ID.
    interest = life.revise_interest(
        name="foxfire-notes", context="creative", strength=0.82,
        confidence=0.90, reason="Reviewed original creative curiosity.",
        evidence_refs=(observation,), now=now,
    )
    idea = ProjectIdea(
        "idea:checkable-foxfire", name,
        "Make a small original foxfire note with independently checkable text.",
        interest.interest_id, objectives, (), "text", (observation,),
        0.92, 0.90, now,
    )
    project = life.invent_project(
        idea, scope=ProjectScope.PERSONAL_PRIVATE,
    )
    project = life.propose_project(
        project.project_id,
        reason="An independently checkable creative experiment is feasible.",
        evidence_refs=(observation,), now=now + timedelta(seconds=1),
    )
    project = life.activate_project(
        project.project_id,
        reason="Choose a bounded personal experiment without promising success.",
        evidence_refs=(observation,), now=now + timedelta(seconds=2),
    )
    return project


def _draft(text):
    return CognitiveResponse(content=json.dumps({"content": text}))


def test_life_auto_reviews_and_completes_only_independently_verified_artifact(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        created = life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire gathered above the ancient orchard, lighting a "
                "very small and original fictional map."
            ),
        )
        assert created["scheduled"] == 1
        first = life.store.jobs(project.project_id)[0]
        assert wait_for_job(life, first).status is WorkStatus.COMPLETED
        completed = life.tick(now=now + timedelta(minutes=5))
        assert completed["follow_through"] == "independently_completed"
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
        evaluation = life.store.evaluations(project.project_id)[0]
        assert evaluation.technical_outcome is TechnicalOutcome.VALID
        assert evaluation.personal_judgment is PersonalJudgment.UNKNOWN
        assert evaluation.objective_results["text_contains:Foxfire"] is True

        # Completion remains idempotent, with no new creative job or judgment.
        life.tick(now=now + timedelta(seconds=9))
        assert len(life.store.jobs(project.project_id)) == 1
        assert len(life.store.evaluations(project.project_id)) == 1
    finally:
        life.close()


def test_life_revises_failed_original_text_after_daily_budget_reset(tmp_path, life_clock):
    life, _goals, now = infrastructure(tmp_path, clock=life_clock)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    attempts = []

    def generator(request):
        brief = request.messages[-1].content
        attempts.append(brief)
        if len(attempts) == 1:
            return _draft(
                "Moonlight collected above the imagined valley, with "
                "no named fire or special glowing phenomenon."
            )
        return _draft(
            "Foxfire returned to the imaginary valley on the second night, "
            "and the forest's maps glowed quietly at the water's edge."
        )

    try:
        life.tick(now=life_clock.at(now + timedelta(seconds=3)), generate=generator)
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED

        # Scheduling, capability execution and receipt recording share this
        # controlled host clock. This intentionally remains within one UTC day.
        inspected = life.tick(now=life_clock.at(now + timedelta(minutes=5)), generate=generator)
        assert inspected["follow_through"] == "deferred_daily_draft_limit"
        assert len(life.store.evaluations(project.project_id)) == 1
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE

        next_day = now + timedelta(days=1)
        revised = life.tick(now=life_clock.at(next_day), generate=generator)
        assert revised["follow_through"] == "revision_scheduled"
        assert revised["scheduled"] == 1
        assert "text_contains:Foxfire" in attempts[-1]
        jobs = life.store.jobs(project.project_id)
        assert len(jobs) == 2
        assert wait_for_job(life, jobs[-1]).status is WorkStatus.COMPLETED

        completed = life.tick(now=life_clock.at(next_day + timedelta(seconds=8)), generate=generator)
        assert completed["follow_through"] == "independently_completed"
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
        assert len(life.store.evaluations(project.project_id)) == 2
    finally:
        life.close()


def test_life_abstains_on_uncheckable_subjective_objectives(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project, _evidence = active_project(life, now)
    try:
        life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire blue shifts gently toward amber in the first "
                "movement of this small imaginary color atlas."
            ),
        )
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED
        # RUN receipts carry real wall-clock timestamps while this test's LIFE
        # ticks use a synthetic schedule; a margin smaller than execution drift
        # on a loaded runner makes a legitimate receipt future-dated, so the
        # settle budget is minutes-wide.
        result = life.tick(now=now + timedelta(minutes=5))
        assert result["follow_through"] == "needs_independent_objective_review"
        # The verified outcome is UNKNOWN, so pause future autonomous
        # spending rather than leave an uncheckable project ACTIVE forever.
        assert life._project(project.project_id).status is ProjectStatus.PAUSED
        assert len(life.store.jobs(project.project_id)) == 1
        evals = life.store.evaluations(project.project_id)
        assert len(evals) == 1
        assert evals[0].technical_outcome is TechnicalOutcome.INCONCLUSIVE
        assert all(value is None for value in evals[0].objective_results.values())
    finally:
        life.close()


def test_life_corrupt_artifact_does_not_revise_or_complete(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire drifted above the meadow, painting the mountains "
                "of a tiny imaginary world for the first edition."
            ),
        )
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED
        artifact_id, _revision = life.store.artifacts(project.project_id)[0]
        path, _media = life.creative_explorer.verified_preview(
            artifact_id, owner_principal_id="sofia", audience_id="local:text",
        )
        path.write_text("tampered", encoding="utf-8")
        # RUN receipts carry real wall-clock timestamps while this test's LIFE
        # ticks use a synthetic schedule; a margin smaller than execution drift
        # on a loaded runner makes a legitimate receipt future-dated, so the
        # settle budget is minutes-wide.
        result = life.tick(now=now + timedelta(minutes=5))
        assert result["follow_through"] == "artifact_integrity_review_required"
        assert life._project(project.project_id).status is ProjectStatus.ACTIVE
        assert len(life.store.jobs(project.project_id)) == 1
        assert len(life.store.evaluations(project.project_id)) == 0
        assert all(
            milestone.status.value == "planned"
            for milestone in life.store.milestones(project.project_id)
        )
        assert life._current_verified_objective_completion(
            life._project(project.project_id), now=now + timedelta(minutes=5),
        ) is False
    finally:
        life.close()


@pytest.mark.parametrize("start", [
    datetime(2026, 9, 29, 12, tzinfo=timezone.utc),
    datetime(2026, 9, 29, 23, 59, 55, tzinfo=timezone.utc),
])
def test_life_restart_recovers_completed_artifact_and_finishes_once(tmp_path, life_clock, start):
    life_clock.at(start)
    life, _goals, now = infrastructure(tmp_path, clock=life_clock)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        life.tick(
            now=life_clock.at(now + timedelta(seconds=3)),
            generate=lambda request: _draft(
                "Foxfire climbed the eastern hill, marking a tiny imaginary "
                "border in an original story about learning new places."
            ),
        )
        assert wait_for_job(life, life.store.jobs(project.project_id)[0]).status is WorkStatus.COMPLETED
    finally:
        life.close()

    life_clock.at(now + timedelta(minutes=1))
    restarted, _goals, _ = infrastructure(tmp_path, clock=life_clock)
    try:
        completed = restarted.tick(now=life_clock.at(now + timedelta(minutes=1)))
        assert completed["follow_through"] == "independently_completed"
        assert restarted._project(project.project_id).status is ProjectStatus.COMPLETED
        assert len(restarted.store.jobs(project.project_id)) == 1
        assert len(restarted.store.evaluations(project.project_id)) == 1
    finally:
        restarted.close()



def test_background_draft_does_not_schedule_after_goals_pause_during_model(
    tmp_path,
):
    """A model reply is not permission that survives a GOALS revocation."""
    from sofia.core.goals import GoalStatus, SOFIA_GOAL_OWNER_ID
    from sofia.core.social.principals import local_sparks_principal

    life, goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        def paused_during_draft(_request):
            goal = next(
                item for item in goals.list_visible(local_sparks_principal())
                if item.id == project.goal_id
            )
            goals.transition(
                goal_id=goal.id,
                principal_id=goal.scope_principal_id,
                audience=goal.scope_audience,
                expected_status=GoalStatus.ACTIVE,
                next_status=GoalStatus.PAUSED,
                actor_principal_id=SOFIA_GOAL_OWNER_ID,
                now=now + timedelta(seconds=4),
                evidence_refs=(),
            )
            return _draft(
                "Foxfire flows through the imagined hills of this original "
                "fictional landscape with independently readable colors."
            )

        result = life.tick(
            now=now + timedelta(seconds=5), generate=paused_during_draft,
        )
        assert result["scheduled"] == 0
        assert result["draft_status"] == "authority_changed_during_draft"
        assert life.store.jobs(project.project_id) == ()
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_background_draft_respects_operator_stop_during_model(tmp_path):
    """A late stop suppresses newly drafted optional work."""
    from sofia.platform.safe.operator_stop import OperatorStopStore

    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        def stop_during_draft(_request):
            OperatorStopStore(life.path).set(
                active=True, updated_by="Sparks",
                reason="Pause personal work before authoring dispatch.",
            )
            return _draft(
                "Foxfire collects around the winding path of an original "
                "landscape that is still only uncommitted text."
            )
        result = life.tick(
            now=now + timedelta(seconds=3), generate=stop_during_draft,
        )
        assert result["draft_status"] == "authority_changed_during_draft"
        assert result["scheduled"] == 0
        assert life.store.jobs(project.project_id) == ()
    finally:
        life.close()


def test_revision_abstains_if_goal_pauses_during_generator(tmp_path, life_clock):
    """The old completed artifact is retained; no new RUN effect is minted."""
    from sofia.core.goals import GoalStatus, SOFIA_GOAL_OWNER_ID
    from sofia.core.social.principals import local_sparks_principal

    life, goals, now = infrastructure(tmp_path, clock=life_clock)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        first = life.tick(
            now=life_clock.at(now + timedelta(seconds=3)),
            generate=lambda _request: _draft(
                "The ordinary moon illuminated a little imaginary valley "
                "without the required named experimental phenomenon."
            ),
        )
        assert first["scheduled"] == 1
        original_job = life.store.jobs(project.project_id)[0]
        assert wait_for_job(life, original_job).status is WorkStatus.COMPLETED
        # A new model candidate is available but the same-day draft budget
        # already belongs to the first attempt, so no generator may run.
        initial_review = life.tick(
            now=life_clock.at(now + timedelta(seconds=7)),
            generate=lambda _request: _draft("Unauthorized same-day second revision"),
        )
        assert initial_review["follow_through"] == "deferred_daily_draft_limit"

        next_day = now + timedelta(days=1)
        def pause_during_revision(_request):
            goal = next(
                item for item in goals.list_visible(local_sparks_principal())
                if item.id == project.goal_id
            )
            goals.transition(
                goal_id=goal.id,
                principal_id=goal.scope_principal_id,
                audience=goal.scope_audience,
                expected_status=GoalStatus.ACTIVE,
                next_status=GoalStatus.PAUSED,
                actor_principal_id=SOFIA_GOAL_OWNER_ID,
                now=next_day, evidence_refs=(),
            )
            return _draft(
                "Foxfire now finally appears in an otherwise original "
                "second creative story, but its grant was revoked."
            )

        result = life.tick(now=life_clock.at(next_day), generate=pause_during_revision)
        assert result["follow_through"] == "revision_authority_changed"
        assert result["scheduled"] == 0
        assert life.store.jobs(project.project_id) == (original_job,)
        assert len(life.store.artifacts(project.project_id)) == 1
        assert len(life.store.evaluations(project.project_id)) == 1
    finally:
        life.close()


def test_life_completed_receipt_must_match_original_sha_and_size(tmp_path, monkeypatch):
    """A signed job status without matching creative source cannot authorize review."""
    from dataclasses import replace

    life, _goals, now = infrastructure(tmp_path)
    project = typed_active_project(
        life, now, objectives=("text_contains:Foxfire",),
    )
    try:
        created = life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: _draft(
                "Foxfire was documented in an independently testable note."
            ),
        )
        assert created["scheduled"] == 1
        job_id = life.store.jobs(project.project_id)[0]
        assert wait_for_job(life, job_id).status is WorkStatus.COMPLETED
        job = life.work_store.get(job_id)
        assert job.result is not None
        original = dict(job.result)
        evidence_ref = original["evidence_ref"]
        artifact_id = original["artifact_id"]
        revision = original["revision"]
        kwargs = dict(
            artifact_id=artifact_id, revision=revision,
            evidence_ref=evidence_ref, now=now + timedelta(minutes=1),
        )
        assert life._confirmed_artifact_run_receipt(project, **kwargs)

        real_get = life.work_store.get
        for changed in (
            {**original, "sha256": "0" * 64},
            {**original, "byte_size": int(original["byte_size"]) + 1},
            {key: val for key, val in original.items() if key != "sha256"},
        ):
            monkeypatch.setattr(
                life.work_store, "get",
                lambda key, data=changed: replace(job, result=data)
                if key == job_id else real_get(key),
            )
            assert not life._confirmed_artifact_run_receipt(project, **kwargs)
            monkeypatch.setattr(life.work_store, "get", real_get)

        original_latest = life.creative_store.history
        canonical = original_latest(
            artifact_id, "sofia", project.audience_id,
        )[0]
        assert canonical is not None
        monkeypatch.setattr(
            life.creative_store, "history",
            lambda *args, **kwargs: (replace(
                canonical, content_sha256="0" * 64,
            ),),
        )
        assert not life._confirmed_artifact_run_receipt(project, **kwargs)
        monkeypatch.setattr(life.creative_store, "history", original_latest)

        reviewed = life.tick(now=now + timedelta(minutes=2))
        assert reviewed["follow_through"] == "independently_completed"
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
    finally:
        life.close()


@pytest.mark.parametrize("before,after,new_day", [
    (
        datetime(2026, 9, 29, 23, 59, 59, tzinfo=timezone.utc),
        datetime(2026, 9, 30, 0, 0, 0, tzinfo=timezone.utc),
        True,
    ),
    # Same Chicago calendar date, but a new UTC quota day.
    (
        datetime(2026, 9, 29, 18, 59, 59, tzinfo=ZoneInfo("America/Chicago")),
        datetime(2026, 9, 29, 19, 0, 0, tzinfo=ZoneInfo("America/Chicago")),
        True,
    ),
    # A local midnight is not a reset when UTC is still on the same date.
    (
        datetime(2026, 9, 29, 23, 59, 59, tzinfo=ZoneInfo("America/Chicago")),
        datetime(2026, 9, 30, 0, 0, 0, tzinfo=ZoneInfo("America/Chicago")),
        False,
    ),
    # Spring-forward and repeated fall-back hours cannot mint another slot.
    (
        datetime(2026, 3, 8, 1, 59, 59, tzinfo=ZoneInfo("America/Chicago")),
        datetime(2026, 3, 8, 3, 0, 0, tzinfo=ZoneInfo("America/Chicago")),
        False,
    ),
    (
        datetime(2026, 11, 1, 1, 59, 59, tzinfo=ZoneInfo("America/Chicago"), fold=0),
        datetime(2026, 11, 1, 1, 0, 0, tzinfo=ZoneInfo("America/Chicago"), fold=1),
        False,
    ),
])
def test_daily_draft_admission_uses_utc_across_local_and_restart_boundaries(
    canonical_state_path, before, after, new_day,
):
    from sofia.core.life.store import LifeStore

    store = LifeStore(canonical_state_path)
    assert store.claim_daily_draft_attempt("project:clock-boundary", now=before)
    assert not store.claim_daily_draft_attempt("project:clock-boundary", now=before)
    # Reopening the canonical store must preserve the spent UTC-day slot.
    restarted = LifeStore(canonical_state_path)
    assert restarted.has_daily_draft_attempt("project:clock-boundary", now=after) is not new_day
    assert restarted.claim_daily_draft_attempt("project:clock-boundary", now=after) is new_day
    assert not restarted.claim_daily_draft_attempt("project:clock-boundary", now=after)
    # Re-expressing exactly the same instant in UTC must not change admission.
    assert restarted.has_daily_draft_attempt(
        "project:clock-boundary", now=after.astimezone(timezone.utc),
    )


def test_daily_draft_admission_rejects_host_local_naive_timestamps(canonical_state_path):
    from sofia.core.life.store import LifeStore

    store = LifeStore(canonical_state_path)
    for operation in (store.claim_daily_draft_attempt, store.has_daily_draft_attempt):
        with pytest.raises(ValueError, match="timezone-aware"):
            operation("project:clock-boundary", now=datetime(2026, 9, 29, 23, 59, 59))


def test_delayed_receipt_reconciliation_at_midnight_uses_next_utc_day(tmp_path, life_clock):
    life_clock.at(datetime(2026, 9, 29, 23, 59, 56, tzinfo=timezone.utc))
    life, _goals, now = infrastructure(tmp_path, clock=life_clock)
    project = typed_active_project(life, now, objectives=("text_contains:Foxfire",))
    attempts = []

    def generator(request):
        attempts.append(request)
        return _draft(
            "An original moonlit valley contains no required named phenomenon."
            if len(attempts) == 1 else
            "Foxfire outlines a second original map of the imaginary valley."
        )

    try:
        started = life.tick(now=life_clock.at(now + timedelta(seconds=3)), generate=generator)
        assert started["scheduled"] == 1
        first = wait_for_job(life, life.store.jobs(project.project_id)[0])
        assert first.status is WorkStatus.COMPLETED
        receipt = life.evidence_index.lookup(first.result["evidence_ref"])
        assert receipt is not None and receipt.successful is True
        assert receipt.observed_at == datetime(2026, 9, 29, 23, 59, 59, tzinfo=timezone.utc)
        # The durable one-use authorization and independent effect receipt
        # must share the same host execution clock, not mix in wall time.
        from contextlib import closing
        import sqlite3
        with closing(sqlite3.connect(life.path)) as db:
            finished = db.execute(
                "SELECT finished_at FROM life_artifact_authorization WHERE status='completed'"
            ).fetchone()
        assert finished is not None
        assert datetime.fromisoformat(finished[0]) == receipt.observed_at
        # Real capability bytes already exist; delayed reconciliation happens
        # at exactly midnight, so the new UTC-day revision is now eligible.
        reviewed = life.tick(now=life_clock.at(now + timedelta(seconds=4)), generate=generator)
        assert reviewed["follow_through"] == "revision_scheduled"
        assert reviewed["scheduled"] == 1
        assert len(life.store.jobs(project.project_id)) == 2
        second = wait_for_job(life, life.store.jobs(project.project_id)[-1])
        assert second.status is WorkStatus.COMPLETED
        completed = life.tick(now=life_clock.at(now + timedelta(seconds=5)), generate=generator)
        assert completed["follow_through"] == "independently_completed"
        assert life._project(project.project_id).status is ProjectStatus.COMPLETED
        assert len(attempts) == 2
    finally:
        life.close()
