from datetime import datetime, timedelta, timezone

import pytest

from sofia.act.delivery import DeliveryOutcome, SendResult
from sofia.act.diagnostics import OutreachTraceStore
from sofia.act.outreach import Importance, OutreachCategory, Policy
from sofia.application.act_service import SofiaActService
from sofia.application.presence import (
    InitiativeEvent,
    PresenceInitiativeEngine,
    WorldAvailability,
    WorldEpistemicState,
    WorldObservation,
)
from sofia.safe.operator_stop import OperatorStopStore


NOW = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    import sqlite3
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE conversation_messages(id TEXT PRIMARY KEY, role TEXT)"
        )
    return path


def policy(**changes):
    values = dict(
        recipient_id="sparks", enabled=True,
        min_interval=timedelta(0), max_daily=10,
        social_min_interval=timedelta(0),
        operational_min_interval=timedelta(0),
        social_max_daily=10, operational_max_daily=10,
    )
    values.update(changes)
    return Policy(**values)


def event(event_id="event-1", *, recipient="sparks"):
    observation = WorldObservation(
        observation_id=f"observation:{event_id}",
        subject_id="service:docker",
        predicate="service.repeated_failure",
        source_id="ops:health",
        observed_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        confidence=1.0,
        epistemic_state=WorldEpistemicState.OBSERVED,
        availability=WorldAvailability.DEGRADED,
        value={"failures": 3},
        audience_id="sparks",
    )
    return InitiativeEvent(
        event_id=event_id,
        trigger_kind="operational_alert",
        observation=observation,
        content="Docker has failed repeatedly; I can investigate the logs.",
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        category=OutreachCategory.OPERATIONAL,
        importance=Importance.IMPORTANT,
        salience=0.8,
        recipient_id=recipient,
    )


def configured(state, sent, *, outreach_policy=None):
    service = SofiaActService(state)
    service.configure_delivery(
        sender=lambda payload: (
            sent.append(payload)
            or SendResult(DeliveryOutcome.DELIVERED, receipt_id="receipt-1")
        ),
        policy=outreach_policy or policy(),
        channel="test",
        destination="sparks-test",
    )
    return service


def test_evidence_backed_event_delivers_without_user_message_and_traces(state):
    sent = []
    service = configured(state, sent)
    engine = PresenceInitiativeEngine(state_path=state, act_service=service)

    decision = engine.consider(event())
    result = service.deliver_one(now=NOW)

    assert decision.status == "queued"
    assert result.outcome is DeliveryOutcome.DELIVERED
    assert len(sent) == 1
    trace = OutreachTraceStore(state).history(notice_id=decision.notice_id)
    assert [row.stage for row in trace] == [
        "queued", "eligible", "transport_attempt", "transport_accepted",
    ]
    assert trace[-1].recipient_confirmed is False
    restarted = PresenceInitiativeEngine(state_path=state, act_service=service)
    assert restarted.consider(event()) == decision
    assert service.deliver_one(now=NOW + timedelta(minutes=1)) is None
    assert len(sent) == 1


@pytest.mark.parametrize(
    ("event_recipient", "policy_changes", "busy", "reason"),
    [
        ("sparks", {"quiet_start_local": 14, "quiet_end_local": 16}, False, "quiet_hours"),
        ("sparks", {}, True, "busy"),
        ("someone-else", {}, False, "wrong_recipient"),
    ],
)
def test_policy_blocks_are_durable(
    state, event_recipient, policy_changes, busy, reason,
):
    service = configured(state, [], outreach_policy=policy(**policy_changes))
    decision = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    ).consider(event(recipient=event_recipient))

    assert service.deliver_one(now=NOW, busy=busy) is None
    assert reason in {
        row.reason for row in OutreachTraceStore(state).history(
            notice_id=decision.notice_id,
        )
    }


def test_missing_transport_and_restart_are_idempotent(state):
    service = SofiaActService(state)
    first = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    ).consider(event())
    second = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    ).consider(event())

    assert first == second
    assert first.status == "suppressed"
    assert first.reason == "missing_transport"


def test_operator_stop_suppresses_existing_notice(state):
    service = configured(state, [])
    decision = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    ).consider(event())
    OperatorStopStore(state).set(
        active=True, updated_by="Sparks", reason="test stop", at=NOW,
    )

    assert service.deliver_one(now=NOW) is None
    assert "stopped" in {
        row.reason for row in OutreachTraceStore(state).history(
            notice_id=decision.notice_id,
        )
    }


def test_world_state_preserves_unknown_offline_and_unavailable(state):
    engine = PresenceInitiativeEngine(
        state_path=state, act_service=SofiaActService(state),
    )
    for index, availability in enumerate((
        WorldAvailability.UNKNOWN,
        WorldAvailability.OFFLINE,
        WorldAvailability.UNAVAILABLE,
    )):
        engine.record_state(
            observation_id=f"world:{index}", subject_id="service:x",
            predicate="service.availability", source_id="ops:test",
            observed_at=NOW + timedelta(seconds=index), freshness=None,
            confidence=1.0, epistemic_state=WorldEpistemicState.OBSERVED,
            availability=availability, value={"state": availability.value},
        )

    import sqlite3
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT availability FROM presence_world_observation ORDER BY observation_id"
        ).fetchall() == [("unknown",), ("offline",), ("unavailable",)]


@pytest.mark.parametrize(
    ("audience", "expected"),
    [
        ("discord:dm:34567", "incompatible_observation_audience"),
        ("private:another-device", "incompatible_observation_audience"),
    ],
)
def test_presence_refuses_foreign_private_audience_outreach(
    state, audience, expected,
):
    """An unrelated private audience cannot be republished to local ACT."""
    from dataclasses import replace

    sent = []
    engine = PresenceInitiativeEngine(
        state_path=state, act_service=configured(state, sent),
    )
    original = event("foreign-audience")
    changed = replace(
        original, observation=replace(
            original.observation, audience_id=audience,
        ),
    )
    result = engine.consider(changed)
    assert result.status == "suppressed"
    assert result.reason == expected
    assert result.notice_id is None
    assert engine.consider(changed) == result
    assert sent == []


@pytest.mark.parametrize("timing", ["expired", "future"])
def test_presence_refuses_stale_or_future_outreach_evidence(
    state, timing,
):
    """Observed evidence must exist and remain fresh when ACT is proposed."""
    from dataclasses import replace

    sent = []
    engine = PresenceInitiativeEngine(
        state_path=state, act_service=configured(state, sent),
    )
    original = event("stale-evidence")
    observation = (
        replace(
            original.observation,
            observed_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(hours=1),
        )
        if timing == "expired"
        else replace(
            original.observation,
            observed_at=NOW + timedelta(minutes=4),
            expires_at=NOW + timedelta(minutes=10),
        )
    )
    result = engine.consider(replace(original, observation=observation))
    assert result.status == "suppressed"
    assert result.reason == "stale_or_future_observation"
    assert result.notice_id is None
    assert sent == []


def test_presence_notice_expires_with_original_observation(state):
    """ACT cannot deliver a source-dependent notice after evidence expiration."""
    from dataclasses import replace

    sent = []
    service = configured(state, sent)
    engine = PresenceInitiativeEngine(state_path=state, act_service=service)
    original = event("short-lived-evidence")
    observation = replace(
        original.observation,
        expires_at=NOW + timedelta(minutes=2),
    )
    result = engine.consider(replace(original, observation=observation))
    assert result.status == "queued"
    assert result.notice_id is not None
    assert service.deliver_one(now=NOW + timedelta(minutes=3)) is None
    assert sent == []


def _verified_private_project_for_unprompted_sharing(
    tmp_path, *, name="A Foxfire Atlas",
):
    from test.test_life_project_forge import (
        infrastructure, active_project, authored_foxfire_text, wait_for_job,
    )
    from sofia.run.work import WorkStatus
    from sofia.life import ProjectStatus

    life, _goals, now = infrastructure(tmp_path)
    project, _evidence = active_project(
        life, now, name=name, objectives=("text_contains:Foxfire",),
    )
    initial = life.tick(
        now=now + timedelta(seconds=3), generate=authored_foxfire_text,
    )
    assert initial["scheduled"] == 1
    job = wait_for_job(life, life.store.jobs(project.project_id)[0])
    assert job.status is WorkStatus.COMPLETED
    finished = life.tick(now=now + timedelta(seconds=8))
    assert finished["follow_through"] == "independently_completed"
    assert life._project(project.project_id).status is ProjectStatus.COMPLETED
    return life, project, now + timedelta(seconds=8)


def _owner_only_outreach(life):
    from sofia.social.principals import SPARKS_PRINCIPAL_ID

    sent = []
    service = SofiaActService(life.path)
    service.configure_delivery(
        sender=lambda payload: (
            sent.append(payload)
            or SendResult(DeliveryOutcome.DELIVERED, receipt_id="test-ack")
        ),
        policy=policy(
            recipient_id=SPARKS_PRINCIPAL_ID,
            quiet_start_local=23, quiet_end_local=0,
            max_daily=1, social_max_daily=1,
        ),
        channel="desktop", destination="tray",
    )
    presence = PresenceInitiativeEngine(
        state_path=life.path, act_service=service,
    )
    return presence, service, sent


def test_verified_personal_life_work_can_start_owner_conversation(tmp_path):
    """A verified creative achievement may be mentioned without per-project approval."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)
        moments = life.voluntary_project_updates(now=now)
        assert len(moments) == 1
        assert moments[0]["project_id"] == project.project_id
        assert moments[0]["disclosure"] == (
            "owner_only_project_update_no_artifact_payload"
        )
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
        ) == 1
        assert presence.recent_life_project_outreach(now=now) is True
        assert service.has_pending()
        # Queued does not mean delivered, read, heard or acknowledged.
        assert sent == []
        import sqlite3
        with sqlite3.connect(life.path) as db:
            row = db.execute(
                "SELECT trigger_kind,recipient_id,notice_id,status "
                "FROM presence_initiative_opportunity "
                "WHERE event_id LIKE 'life-update:%'",
            ).fetchone()
        assert row is not None
        assert row[0] == "task_completed"
        assert row[1] == "person:sparks"
        assert row[2].startswith("presence:")
        assert row[3] == "queued"
        with sqlite3.connect(life.path) as db:
            notice = db.execute(
                "SELECT recipient_id,channel,destination,category,content "
                "FROM act_system_notice WHERE notice_id=?",
                (row[2],),
            ).fetchone()
        assert notice[:4] == (
            "person:sparks", "desktop", "tray", "social",
        )
        assert project.name in notice[4]
        assert "artifact:" not in notice[4]
        assert "private reflection" not in notice[4].lower()
        # A restart and another 5-minute background tick cannot create
        # another outreach message from the same (or any other) project.
        restarted = PresenceInitiativeEngine(
            state_path=life.path, act_service=service,
        )
        assert bridge_voluntary_life_outreach(
            life=life, presence=restarted, act_service=service,
            now=now + timedelta(minutes=5), busy=False,
        ) == 0
    finally:
        life.close()


@pytest.mark.parametrize("busy", [True, False])
def test_life_can_choose_silence_despite_verified_project(tmp_path, busy):
    """Foreground activity or voluntary quiet overrides an exciting project."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, _sent = _owner_only_outreach(life)
        if not busy:
            life.choose_inactivity(
                reason="I want some private creative downtime.",
                until=now + timedelta(hours=1), now=now,
            )
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now + timedelta(seconds=1), busy=busy,
        ) == 0
        assert service.has_pending() is False
    finally:
        life.close()


def test_life_project_outreach_never_uses_unverified_or_nonprivate_work(tmp_path):
    """Even a high-curiosity project cannot claim success without source proof."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from test.test_life_project_forge import infrastructure, active_project
    from sofia.life import ProjectScope

    life, _goals, now = infrastructure(tmp_path)
    try:
        active_project(life, now, objectives=("text_contains:Foxfire",))
        presence, service, _sent = _owner_only_outreach(life)
        assert life.voluntary_project_updates(now=now) == ()
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
        ) == 0
        assert service.has_pending() is False
    finally:
        life.close()


@pytest.mark.parametrize("route", ["home_assistant", "mobile"])
def test_life_personal_story_cannot_escape_pinned_owner_routes(tmp_path, route):
    """No LIFE-private update goes to unverified shared or alternate routes."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)
        service.configure_delivery(
            sender=lambda payload: (
                sent.append(payload)
                or SendResult(DeliveryOutcome.DELIVERED, receipt_id="test")
            ),
            policy=policy(recipient_id="person:sparks"),
            channel=route, destination="unreviewed-destination",
        )
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
        ) == 0
        assert sent == []
        assert service.has_pending() is False
    finally:
        life.close()


def test_life_unprompted_conversation_respects_owner_outreach_mute(tmp_path):
    from dataclasses import replace
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)
        service.configure_delivery(
            sender=lambda payload: (
                sent.append(payload)
                or SendResult(DeliveryOutcome.DELIVERED, receipt_id="test")
            ),
            policy=replace(service.policy, mute=True),
            channel="desktop", destination="tray",
        )
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
        ) == 0
        assert service.has_pending() is False
        assert sent == []
    finally:
        life.close()


def test_life_celebration_does_not_outlive_its_independent_proof(tmp_path):
    """A historical completed label must not trigger sharing after corruption."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        artifact_id, _revision = life.store.artifacts(project.project_id)[0]
        path, _media = life.creative_explorer.verified_preview(
            artifact_id, owner_principal_id="sofia", audience_id="local:text",
        )
        path.write_text(
            "The completed source bytes changed and are no longer verifiable.",
            encoding="utf-8",
        )
        presence, service, sent = _owner_only_outreach(life)
        assert life.voluntary_project_updates(now=now) == ()
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
        ) == 0
        assert service.has_pending() is False
        assert sent == []
    finally:
        life.close()


def test_life_celebration_expires_instead_of_announcing_old_work(tmp_path):
    """An older completion is history, not a reason to message days later."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        later = now + timedelta(days=4)
        presence, service, _sent = _owner_only_outreach(life)
        assert life.voluntary_project_updates(now=later) == ()
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=later, busy=False,
        ) == 0
        assert service.has_pending() is False
    finally:
        life.close()


def test_life_reviewed_draft_can_be_shared_without_claiming_objective_success(
    tmp_path,
):
    """Sofía can mention an actual draft before calling the project successful."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from test.test_life_project_forge import (
        infrastructure, active_project, authored_foxfire_text, wait_for_job,
    )
    from sofia.run.work import WorkStatus
    from sofia.life import ProjectStatus

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(
            life, now,
            objectives=("Create a personally moving original story.",),
        )
        first = life.tick(
            now=now + timedelta(seconds=3),
            generate=authored_foxfire_text,
        )
        assert first["scheduled"] == 1
        job = wait_for_job(life, life.store.jobs(project.project_id)[0])
        assert job.status is WorkStatus.COMPLETED
        reviewed = life.tick(now=now + timedelta(seconds=8))
        assert reviewed["follow_through"] == "needs_independent_objective_review"
        assert life._project(project.project_id).status is ProjectStatus.PAUSED
        stamp = now + timedelta(seconds=8)
        candidates = life.voluntary_project_updates(now=stamp)
        assert len(candidates) == 1
        assert candidates[0]["moment_kind"] == "reviewed_draft"
        presence, service, _sent = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=stamp, busy=False,
        ) == 1
        import sqlite3
        with sqlite3.connect(life.path) as db:
            row = db.execute(
                "SELECT predicate,value_json FROM presence_world_observation "
                "WHERE observation_id LIKE 'life-observed:%'",
            ).fetchone()
            message = db.execute(
                "SELECT content FROM act_system_notice "
                "WHERE notice_id LIKE 'presence:%'",
            ).fetchone()[0]
        assert row is not None
        assert row[0] == "original_project.verified_draft"
        import json
        assert json.loads(row[1])["independent_objectives_verified"] is False
        assert "draft" in message.lower()
        assert "checks passed" not in message.lower()
        assert "finished and verified" not in message.lower()
        assert "artifact:" not in message
        assert service.has_pending()
    finally:
        life.close()


def test_life_reviewed_draft_wont_share_corrupt_bytes(tmp_path):
    """An original completed RUN is not enough after creative bytes are altered."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from test.test_life_project_forge import (
        infrastructure, active_project, authored_foxfire_text, wait_for_job,
    )

    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _evidence = active_project(
            life, now, objectives=("Write a personally enjoyable story.",),
        )
        life.tick(
            now=now + timedelta(seconds=3), generate=authored_foxfire_text,
        )
        job = wait_for_job(life, life.store.jobs(project.project_id)[0])
        life.tick(now=now + timedelta(seconds=8))
        artifact_id = str(job.result["artifact_id"])
        path, _media = life.creative_explorer.verified_preview(
            artifact_id, owner_principal_id="sofia", audience_id="local:text",
        )
        path.write_text("An edited file with no original digest match.")
        presence, service, _sent = _owner_only_outreach(life)
        stamp = now + timedelta(seconds=9)
        assert life.voluntary_project_updates(now=stamp) == ()
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=stamp, busy=False,
        ) == 0
        assert not service.has_pending()
    finally:
        life.close()


def test_life_outreach_does_not_pass_through_untrusted_project_mentions(tmp_path):
    """A model-authored title cannot become Discord mentions or rich markup."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    import sqlite3

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path, name="@everyone <@123456> `Foxfire` Project",
    )
    try:
        presence, service, _sent = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
        ) == 1
        with sqlite3.connect(life.path) as db:
            content = db.execute(
                "SELECT content FROM act_system_notice "
                "WHERE notice_id LIKE 'presence:%'",
            ).fetchone()[0]
        assert "Foxfire" in content
        assert "@everyone" not in content
        assert "<@123456>" not in content
        assert chr(96) not in content
        assert "\n" not in content
    finally:
        life.close()


def test_life_social_update_uses_owner_bound_discord_route(tmp_path):
    """A production-configured owner DM route retains private Sparks scope."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from sofia.social.principals import SPARKS_PRINCIPAL_ID
    import sqlite3

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)
        # The live ACT factory separately verifies the pinned Discord binding;
        # this fixture verifies the resulting scoped delivery queue only.
        service.configure_delivery(
            sender=lambda payload: (
                sent.append(payload)
                or SendResult(DeliveryOutcome.DELIVERED, receipt_id="fixture")
            ),
            policy=policy(recipient_id=SPARKS_PRINCIPAL_ID),
            channel="discord", destination="987654321",
        )
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
        ) == 1
        with sqlite3.connect(life.path) as db:
            notice = db.execute(
                "SELECT recipient_id,channel,destination,category,content "
                "FROM act_system_notice WHERE notice_id LIKE 'presence:%'",
            ).fetchone()
        assert notice[:4] == (
            SPARKS_PRINCIPAL_ID, "discord", "987654321", "social",
        )
        assert project.name in notice[4]
        assert sent == []
    finally:
        life.close()
