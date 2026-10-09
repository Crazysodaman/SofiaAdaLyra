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
