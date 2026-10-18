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


def ordinary_event(event_id: str, *, trigger_kind: str = "reflection"):
    from sofia.social.principals import SPARKS_PRINCIPAL_ID
    observation = WorldObservation(
        observation_id=f"observation:{event_id}",
        subject_id="sofia:ordinary-update",
        predicate="presence.ordinary_update",
        source_id="presence:reflection",
        observed_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        confidence=1.0,
        epistemic_state=WorldEpistemicState.KNOWN,
        availability=WorldAvailability.NOT_APPLICABLE,
        value={"event_id": event_id},
        audience_id="local:text",
    )
    return InitiativeEvent(
        event_id=event_id, trigger_kind=trigger_kind,
        observation=observation,
        content="I found a small idea you might enjoy.",
        created_at=NOW, expires_at=NOW + timedelta(hours=1),
        category=OutreachCategory.SOCIAL,
        importance=Importance.ROUTINE, salience=0.6,
        recipient_id=SPARKS_PRINCIPAL_ID,
    )


def test_owner_ordinary_update_feedback_is_explicit_reversible_and_restart_safe(state):
    from sofia.social.principals import local_sparks_principal
    import sqlite3

    sent = []
    service = configured(state, sent)
    presence = PresenceInitiativeEngine(state_path=state, act_service=service)
    owner = local_sparks_principal()
    first = ordinary_event("ordinary-feedback:first")
    assert presence.consider(first).status == "queued"
    assert presence.owner_update_feedback(
        trigger_kind="reflection", principal=owner,
    ) == {"usefulness": None, "interruptiveness": None}

    presence.record_owner_update_feedback(
        principal=owner, original_event_id=first.event_id,
        dimension="usefulness", value="useful", at=NOW,
    )
    presence.record_owner_update_feedback(
        principal=owner, original_event_id=first.event_id,
        dimension="interruptiveness", value="too_interruptive", at=NOW,
    )
    restarted = PresenceInitiativeEngine(state_path=state, act_service=service)
    assert restarted.owner_update_feedback(
        trigger_kind="reflection", principal=owner,
    ) == {"usefulness": "useful", "interruptiveness": "too_interruptive"}
    blocked = restarted.consider(ordinary_event("ordinary-feedback:blocked"))
    assert (blocked.status, blocked.reason) == (
        "suppressed", "owner_marked_too_interruptive",
    )

    # A critical operational alert is outside the ordinary-feedback surface.
    critical = ordinary_event(
        "critical-feedback", trigger_kind="operational_alert",
    )
    assert restarted.consider(critical).status == "queued"
    with pytest.raises(PermissionError, match="ordinary update"):
        restarted.record_owner_update_feedback(
            principal=owner, original_event_id=critical.event_id,
            dimension="interruptiveness", value="too_interruptive", at=NOW,
        )

    restarted.record_owner_update_feedback(
        principal=owner, original_event_id=first.event_id,
        dimension="interruptiveness", value="acceptable", at=NOW + timedelta(seconds=1),
    )
    assert restarted.consider(
        ordinary_event("ordinary-feedback:restored")
    ).status == "queued"
    restarted.record_owner_update_feedback(
        principal=owner, original_event_id=first.event_id,
        dimension="usefulness", value="unknown", at=NOW + timedelta(seconds=2),
    )
    restarted.record_owner_update_feedback(
        principal=owner, original_event_id=first.event_id,
        dimension="interruptiveness", value="unknown", at=NOW + timedelta(seconds=3),
    )
    assert restarted.owner_update_feedback(
        trigger_kind="reflection", principal=owner,
    ) == {"usefulness": None, "interruptiveness": None}
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM presence_update_feedback_event"
        ).fetchone()[0] == 5


def test_ordinary_update_feedback_rejects_fabricated_and_cross_audience_events(state):
    from sofia.social.model import AudienceKind, PrincipalContext
    from sofia.social.principals import local_sparks_principal

    service = configured(state, [])
    presence = PresenceInitiativeEngine(state_path=state, act_service=service)
    owner = local_sparks_principal()
    with pytest.raises(PermissionError, match="authentic ordinary"):
        presence.record_owner_update_feedback(
            principal=owner, original_event_id="fabricated:update",
            dimension="usefulness", value="useful", at=NOW,
        )
    first = ordinary_event("ordinary-feedback:scope")
    assert presence.consider(first).status == "queued"
    foreign = PrincipalContext(
        owner.principal_id, "discord:dm:1", AudienceKind.PRIVATE, "Sparks",
    )
    with pytest.raises(PermissionError, match="authentic ordinary"):
        presence.record_owner_update_feedback(
            principal=foreign, original_event_id=first.event_id,
            dimension="usefulness", value="useful", at=NOW,
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


def test_concurrent_presence_clients_keep_one_original_decision(state):
    """Concurrent identical opportunities converge without a duplicate notice."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import sqlite3

    sent = []
    service = configured(state, sent)
    one = PresenceInitiativeEngine(state_path=state, act_service=service)
    two = PresenceInitiativeEngine(state_path=state, act_service=service)
    common = event("same-observation-concurrent")
    gate = Barrier(2)
    for instance in (one, two):
        original_observe = instance.observe

        def observe_then_sync(observation, *, _original=original_observe, **kw):
            result = _original(observation, **kw)
            gate.wait(timeout=10)
            return result

        instance.observe = observe_then_sync
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(one.consider, common)
        b = pool.submit(two.consider, common)
        decisions = (a.result(timeout=20), b.result(timeout=20))
    assert decisions[0] == decisions[1]
    assert decisions[0].status == "queued"
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM presence_initiative_opportunity WHERE event_id=?",
            (common.event_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM act_system_notice WHERE notice_id=?",
            (decisions[0].notice_id,),
        ).fetchone()[0] == 1
    assert sent == []


def test_replayed_presence_event_never_restores_deleted_original_observation(state):
    """An ACT candidate must not become grounded by replaying its old event."""
    import sqlite3

    sent = []
    service = configured(state, sent)
    presence = PresenceInitiativeEngine(state_path=state, act_service=service)
    original = event("source-revoked-and-replayed")
    first = presence.consider(original)
    assert first.status == "queued"
    with sqlite3.connect(state) as db:
        db.execute(
            "DELETE FROM presence_world_observation WHERE observation_id=?",
            (original.observation.observation_id,),
        )
    again = presence.consider(original)
    assert again == first
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT 1 FROM presence_world_observation WHERE observation_id=?",
            (original.observation.observation_id,),
        ).fetchone() is None
    assert service.deliver_one(now=NOW + timedelta(minutes=1)) is None
    assert sent == []


def test_presence_replay_rejects_changed_original_event_identity(state):
    """One event ID cannot be relabelled as another observation or recipient."""
    from dataclasses import replace
    import sqlite3

    sent = []
    service = configured(state, sent)
    presence = PresenceInitiativeEngine(state_path=state, act_service=service)
    original = event("single-original-opportunity")
    first = presence.consider(original)
    changed_source = replace(
        original,
        observation=replace(
            original.observation,
            observation_id="observation:substituted-source",
        ),
    )
    with pytest.raises(ValueError, match="event ID reused"):
        presence.consider(changed_source)
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT 1 FROM presence_world_observation WHERE observation_id=?",
            (changed_source.observation.observation_id,),
        ).fetchone() is None
        assert db.execute(
            "SELECT COUNT(*) FROM presence_initiative_opportunity WHERE event_id=?",
            (original.event_id,),
        ).fetchone()[0] == 1
    assert presence.consider(original) == first
    assert sent == []


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


def _choose_to_share(request):
    """The bounded cognition chooses, while Presence/ACT owns the facts."""
    from sofia.cognition.model import CognitiveResponse

    assert request.allow_tools is False
    assert request.route_hint == "standard"
    return CognitiveResponse(content=(
        '{"share_now":true,"tone":"playful",'
        '"reason":"A genuine creative milestone feels worth one update."}'
    ))


def _choose_silence(request):
    """The optional model may decline to talk after genuine verified work."""
    from sofia.cognition.model import CognitiveResponse

    assert request.allow_tools is False
    return CognitiveResponse(content=(
        '{"share_now":false,"tone":"warm",'
        '"reason":"This is a good time to enjoy the project privately."}'
    ))


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
            # These tests use current UTC for the LIFE receipt. Keep test
            # quiet hours twelve hours from that receipt so the permission
            # and source-revocation branches actually get exercised.
            quiet_start_local=(datetime.now(timezone.utc).hour + 12) % 24,
            quiet_end_local=(datetime.now(timezone.utc).hour + 13) % 24,
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
            now=now, busy=False, generate=_choose_to_share,
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
            generate=_choose_to_share,
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
            generate=_choose_to_share,
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
            now=now, busy=False, generate=_choose_to_share,
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
            now=now, busy=False, generate=_choose_to_share,
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
            now=now, busy=False, generate=_choose_to_share,
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
            now=now, busy=False, generate=_choose_to_share,
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
            now=later, busy=False, generate=_choose_to_share,
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
            now=stamp, busy=False, generate=_choose_to_share,
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
            now=stamp, busy=False, generate=_choose_to_share,
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
            now=now, busy=False, generate=_choose_to_share,
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
            now=now, busy=False, generate=_choose_to_share,
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


def test_life_chooses_silence_without_spawning_notice(tmp_path):
    """Independent creative success does not compel a notification."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    import sqlite3

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)
        assert life.voluntary_project_updates(now=now)[0]["project_id"] == project.project_id
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=_choose_silence,
        ) == 0
        with sqlite3.connect(life.path) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM presence_initiative_opportunity "
                "WHERE event_id LIKE 'life-update:%'",
            ).fetchone()[0] == 0
        assert sent == []
        assert service.has_pending() is False
    finally:
        life.close()


def test_life_refuses_invalid_model_outreach_choice_without_sending(tmp_path):
    """Invalid model JSON is a failed optional choice, never assumed approval."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from sofia.cognition.model import CognitiveResponse

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False,
            generate=lambda request: CognitiveResponse(content="SHARE RIGHT NOW"),
        ) == 0
        assert sent == []
        assert service.has_pending() is False
    finally:
        life.close()


def test_life_quiet_and_busy_never_wake_outreach_model(tmp_path):
    """ACT restraint comes before optional cognitive work, not afterward."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, _sent = _owner_only_outreach(life)
        unexpected = []
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=True, generate=unexpected.append,
        ) == 0
        life.choose_inactivity(
            reason="A little private project downtime.",
            until=now + timedelta(hours=1), now=now,
        )
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now + timedelta(seconds=1),
            busy=False, generate=unexpected.append,
        ) == 0
        assert unexpected == []
    finally:
        life.close()


@pytest.mark.parametrize("changed", ["interest", "recipient_route"])
def test_life_outreach_rechecks_exact_source_and_route_after_model(
    tmp_path, changed,
):
    """A previously grounded model choice cannot queue a stale LIFE update."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)
        previous = life.voluntary_project_updates(now=now)
        assert len(previous) == 1

        def changed_while_model_thinking(request):
            reply = _choose_to_share(request)
            if changed == "interest":
                current = life.store.interest_by_id(
                    project.originating_interest, audience_id="local:text",
                )
                assert current is not None
                life.revise_interest(
                    name=current.name, context=current.context,
                    strength=min(1.0, current.strength + 0.1),
                    confidence=current.confidence,
                    reason="A new original review revised the project interest.",
                    evidence_refs=current.evidence_refs,
                    now=now,
                )
                recent = life.voluntary_project_updates(now=now)
                assert len(recent) == 1
                assert recent[0]["event_id"] == previous[0]["event_id"]
                assert recent[0]["salience"] != previous[0]["salience"]
            else:
                service.configure_delivery(
                    sender=lambda payload: (
                        sent.append(payload)
                        or SendResult(DeliveryOutcome.DELIVERED, receipt_id="wrong"),
                    ),
                    policy=service.policy, channel="desktop",
                    destination="unexpected-recipient",
                )
            return reply

        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=changed_while_model_thinking,
        ) == 0
        assert service.has_pending() is False
        assert sent == []
        assert presence.recent_life_project_outreach(now=now) is False
    finally:
        life.close()


def test_life_outreach_operator_stop_after_model_choice_is_honored(tmp_path):
    """A choice made before the user's stop cannot queue a later notice."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach

    life, _project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, sent = _owner_only_outreach(life)

        def model_then_owner_stops(request):
            result = _choose_to_share(request)
            OperatorStopStore(life.path).set(
                active=True,
                updated_by="Sparks",
                reason="Don't deliver personal updates now.",
                at=now,
            )
            return result

        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=model_then_owner_stops,
        ) == 0
        assert service.has_pending() is False
        assert sent == []
        assert presence.recent_life_project_outreach(now=now) is False
    finally:
        life.close()


def test_explicit_project_decline_prevents_future_model_wakeup(tmp_path, monkeypatch):
    """A user's reviewed no stops new outreach, but not the creative project."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from sofia.social.principals import local_sparks_principal

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, _sent = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=_choose_to_share,
        ) == 1
        from hashlib import sha256
        original_id = "life-update:" + sha256(
            life.voluntary_project_updates(now=now)[0]["event_id"].encode("utf-8")
        ).hexdigest()[:32]
        principal = local_sparks_principal()
        assert presence.owner_life_update_feedback(
            project_id=project.project_id, principal=principal,
        ) is None
        presence.record_owner_life_update_feedback(
            principal=principal, project_id=project.project_id,
            original_event_id=original_id, feedback="declined", at=now,
        )
        assert PresenceInitiativeEngine(
            state_path=life.path, act_service=service,
        ).owner_life_update_feedback(
            project_id=project.project_id, principal=principal,
        ) == "declined"
        # Isolate the explicit topic decline from the independent daily
        # anti-spam policy. A restart cannot wake the model for this topic.
        restarted = PresenceInitiativeEngine(
            state_path=life.path, act_service=service,
        )
        monkeypatch.setattr(
            restarted, "recent_life_project_outreach",
            lambda **_: False,
        )
        calls = []
        assert bridge_voluntary_life_outreach(
            life=life, presence=restarted, act_service=service,
            now=now + timedelta(seconds=30), busy=False,
            generate=calls.append,
        ) == 0
        assert calls == []
        assert life._project(project.project_id).status.value == "completed"
        assert len(life.store.jobs(project.project_id)) == 1
    finally:
        life.close()


def test_life_owner_feedback_rejects_cross_scope_and_fabricated_opportunities(
    tmp_path,
):
    """Neither foreign principals nor imagined notifications supply preferences."""
    from sofia.social.model import AudienceKind, PrincipalContext
    from sofia.social.principals import local_sparks_principal

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, _ = _owner_only_outreach(life)
        principal = local_sparks_principal()
        with pytest.raises(PermissionError, match="matching authentic"):
            presence.record_owner_life_update_feedback(
                principal=principal, project_id=project.project_id,
                original_event_id="life-update:synthetic-not-sent",
                feedback="declined", at=now,
            )
        foreign = PrincipalContext(
            "person:other", "private:other",
            AudienceKind.PRIVATE, "Other person",
        )
        with pytest.raises(PermissionError, match="owner-only"):
            presence.record_owner_life_update_feedback(
                principal=foreign, project_id=project.project_id,
                original_event_id="life-update:synthetic-not-sent",
                feedback="declined", at=now,
            )
        assert presence.owner_life_update_feedback(
            project_id=project.project_id, principal=principal,
        ) is None
        assert service.has_pending() is False
    finally:
        life.close()


def test_owner_life_decline_is_explicit_not_inferred_from_silence(tmp_path):
    """No recipient reply must never be recorded as dislike or rejection."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from sofia.social.principals import local_sparks_principal

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, _ = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=_choose_to_share,
        ) == 1
        assert presence.owner_life_update_feedback(
            project_id=project.project_id,
            principal=local_sparks_principal(),
        ) is None
        assert presence.recent_life_project_outreach(now=now) is True
    finally:
        life.close()


def test_owner_can_change_project_feedback_with_audited_history(tmp_path):
    """Authenticated owner may reverse an old choice; model cannot do so."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from sofia.social.principals import local_sparks_principal
    import sqlite3

    life, project, now = _verified_private_project_for_unprompted_sharing(
        tmp_path,
    )
    try:
        presence, service, _ = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=_choose_to_share,
        ) == 1
        with sqlite3.connect(life.path) as db:
            original = db.execute(
                "SELECT event_id FROM presence_initiative_opportunity "
                "WHERE event_id LIKE 'life-update:%' AND status='queued'"
            ).fetchone()[0]
        owner = local_sparks_principal()
        for decision in ("welcomed", "declined", "welcomed"):
            presence.record_owner_life_update_feedback(
                principal=owner, project_id=project.project_id,
                original_event_id=original, feedback=decision,
                at=now + timedelta(seconds=5),
            )
            assert presence.owner_life_update_feedback(
                project_id=project.project_id, principal=owner,
            ) == decision
        with sqlite3.connect(life.path) as db:
            history = [
                row[0] for row in db.execute(
                    "SELECT feedback FROM presence_life_update_feedback_event "
                    "WHERE principal_id=? AND project_id=? "
                    "ORDER BY feedback_event_id",
                    (owner.principal_id, project.project_id),
                )
            ]
        assert history == ["welcomed", "declined", "welcomed"]
        presence.record_owner_life_update_feedback(
            principal=owner, project_id=project.project_id,
            original_event_id=original, feedback="welcomed",
            at=now + timedelta(seconds=8),
        )
        with sqlite3.connect(life.path) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM presence_life_update_feedback_event "
                "WHERE project_id=?", (project.project_id,),
            ).fetchone()[0] == 3
    finally:
        life.close()


def test_owner_decline_terminates_queued_update_before_sender(tmp_path):
    """An already queued project note cannot reach Desktop or Discord after no."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from sofia.social.principals import local_sparks_principal
    from sofia.act.diagnostics import OutreachTraceStore
    import sqlite3

    life, project, now = _verified_private_project_for_unprompted_sharing(tmp_path)
    try:
        presence, service, sent = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=_choose_to_share,
        ) == 1
        with sqlite3.connect(life.path) as db:
            original, notice = db.execute(
                "SELECT event_id, notice_id FROM presence_initiative_opportunity "
                "WHERE event_id LIKE 'life-update:%'"
            ).fetchone()
        presence.record_owner_life_update_feedback(
            principal=local_sparks_principal(),
            project_id=project.project_id,
            original_event_id=original,
            feedback="declined",
            at=now + timedelta(seconds=1),
        )
        # This call loads the real ACT candidate and reaches its pre-send
        # guard. No transport, UI popup, recipient ACK or fake success.
        assert service.deliver_one(now=now + timedelta(seconds=2)) is None
        assert sent == []
        assert service.has_pending() is False
        with sqlite3.connect(life.path) as db:
            status, attempts, reason = db.execute(
                "SELECT status,attempt_count,error_type FROM act_system_notice "
                "WHERE notice_id=?", (notice,),
            ).fetchone()
        assert (status, attempts, reason) == (
            "failed", 0, "OwnerDeclinedProject",
        )
        trace = OutreachTraceStore(life.path).history(notice_id=notice)
        assert any(
            row.stage == "suppressed" and row.reason == "user_declined"
            for row in trace
        )
        assert all(
            row.stage not in {
                "transport_attempt", "transport_accepted",
                "recipient_confirmed",
            }
            for row in trace
        )
        assert service.deliver_one(now=now + timedelta(minutes=1)) is None
        assert sent == []
    finally:
        life.close()



def test_owner_stop_during_project_check_vetoes_transport_at_final_global_gate(
    state, monkeypatch,
):
    """A project check cannot keep using a now-revoked global send grant."""
    from sofia.act.outreach import Decision

    sent = []
    service = configured(state, sent)
    queued = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    ).consider(event(event_id="between-final-checks"))
    assert queued.status == "queued"

    observed = []
    def stop_while_project_guard_runs(_payload):
        observed.append("project_guard")
        OperatorStopStore(state).set(
            active=True, updated_by="Sparks",
            reason="Stop outreach after first global check.", at=NOW,
        )
        return Decision.ELIGIBLE_FOR_AUTHORIZATION

    monkeypatch.setattr(
        service, "_fresh_life_project_pre_send_decision",
        stop_while_project_guard_runs,
    )
    assert service.deliver_one(now=NOW) is None
    assert observed == ["project_guard"]
    assert sent == []
    trace = OutreachTraceStore(state).history(notice_id=queued.notice_id)
    assert any(
        row.stage == "deferred" and row.reason == Decision.STOPPED.value
        for row in trace
    )
    assert not any(
        row.stage in {"transport_attempt", "transport_accepted"}
        for row in trace
    )


def test_missing_original_life_presence_observation_refuses_queued_transport(
    tmp_path,
):
    """Losing the original private event must not authorize an old ACT notice."""
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    from sofia.act.diagnostics import OutreachTraceStore
    import sqlite3

    life, project, now = _verified_private_project_for_unprompted_sharing(tmp_path)
    try:
        presence, service, sent = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=_choose_to_share,
        ) == 1
        with sqlite3.connect(life.path) as db:
            observation_id, notice_id = db.execute(
                "SELECT observation_id,notice_id FROM presence_initiative_opportunity "
                "WHERE event_id LIKE 'life-update:%' AND status='queued'",
            ).fetchone()
            db.execute(
                "DELETE FROM presence_world_observation WHERE observation_id=?",
                (observation_id,),
            )
        assert service.deliver_one(now=now + timedelta(seconds=2)) is None
        assert sent == []
        assert service.has_pending() is True
        traces = OutreachTraceStore(life.path).history(notice_id=notice_id)
        assert any(
            item.stage == "deferred" and
            item.reason == "authorization_unavailable"
            for item in traces
        )
        assert all(
            item.stage not in ("transport_attempt", "transport_accepted")
            for item in traces
        )
    finally:
        life.close()


def test_presence_notice_with_changed_evidence_identity_fails_closed(tmp_path):
    from sofia.application.background_runtime import bridge_voluntary_life_outreach
    import sqlite3

    life, project, now = _verified_private_project_for_unprompted_sharing(tmp_path)
    try:
        presence, service, sent = _owner_only_outreach(life)
        assert bridge_voluntary_life_outreach(
            life=life, presence=presence, act_service=service,
            now=now, busy=False, generate=_choose_to_share,
        ) == 1
        with sqlite3.connect(life.path) as db:
            notice_id = db.execute(
                "SELECT notice_id FROM presence_initiative_opportunity "
                "WHERE event_id LIKE 'life-update:%'",
            ).fetchone()[0]
            db.execute(
                "UPDATE act_system_notice SET evidence_id=? WHERE notice_id=?",
                ("presence-evidence:unrelated-source", notice_id),
            )
        assert service.deliver_one(now=now + timedelta(seconds=2)) is None
        assert sent == []
    finally:
        life.close()


def test_presence_source_audience_revocation_blocks_already_queued_notice(
    state,
):
    """A changed original private audience cannot rebroadcast to Desktop."""
    import sqlite3

    sent = []
    service = configured(state, sent)
    engine = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    )
    queued = engine.consider(event(event_id="audience-revocation"))
    assert queued.status == "queued"
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE presence_world_observation SET audience_id=? "
            "WHERE observation_id=?",
            ("discord:unreviewed-private", "observation:audience-revocation"),
        )
    assert service.deliver_one(now=NOW) is None
    assert sent == []
    trace = OutreachTraceStore(state).history(notice_id=queued.notice_id)
    assert all(row.stage != "transport_attempt" for row in trace)
    assert any(
        row.stage == "deferred" and row.reason == "authorization_unavailable"
        for row in trace
    )


def test_presence_notice_rejects_altered_original_event_identity(state):
    """A substituted source event does not inherit a queued notice grant."""
    import sqlite3

    sent = []
    service = configured(state, sent)
    engine = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    )
    queued = engine.consider(event(event_id="original-id-A"))
    assert queued.status == "queued"
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE presence_initiative_opportunity SET event_id=? "
            "WHERE notice_id=?",
            ("original-id-B", queued.notice_id),
        )
    assert service.deliver_one(now=NOW) is None
    assert sent == []
    assert all(
        row.stage != "transport_attempt"
        for row in OutreachTraceStore(state).history(notice_id=queued.notice_id)
    )



@pytest.mark.parametrize(
    ("column", "changed_value"),
    (
        ("confidence", 0.35),
        ("epistemic_state", "inferred"),
        ("expires_at", (NOW + timedelta(minutes=1)).isoformat()),
        ("observed_at", (NOW + timedelta(minutes=1)).isoformat()),
        ("observed_at", "malformed-source-time"),
        ("expires_at", "malformed-expiry"),
    ),
)
def test_presence_delivery_refuses_source_grounding_change_after_queue(
    state, column, changed_value,
):
    """ACT must not inherit an old eligibility decision after source decay."""
    import sqlite3

    sent = []
    service = configured(state, sent)
    presence = PresenceInitiativeEngine(
        state_path=state, act_service=service,
    )
    original = event(event_id="source-downgraded-after-queue")
    decision = presence.consider(original)
    assert decision.status == "queued"
    assert column in {
        "confidence", "epistemic_state", "expires_at", "observed_at",
    }
    with sqlite3.connect(state) as db:
        db.execute(
            f"UPDATE presence_world_observation SET {column}=? "
            "WHERE observation_id=?",
            (changed_value, original.observation.observation_id),
        )
    result = service.deliver_one(now=NOW + timedelta(minutes=2))
    assert result is None
    assert sent == []
    traces = OutreachTraceStore(state).history(notice_id=decision.notice_id)
    assert any(
        trace.stage == "deferred"
        and trace.reason == "authorization_unavailable"
        for trace in traces
    )
    assert all(
        trace.stage not in {"transport_attempt", "transport_accepted"}
        for trace in traces
    )
