from datetime import datetime, timedelta, timezone
import sqlite3

import sofia.application.act_service as act_service
from sofia.act.delivery import ActOutbox, DeliveryOutcome, SendResult
from sofia.application.act_service import SofiaActService
from sofia.act.outreach import Policy
from sofia.social.principals import SPARKS_PRINCIPAL_ID


NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def test_production_act_delivery_defaults_enabled_when_transport_is_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("SOFIA_ACT_DELIVERY_ENABLED", raising=False)
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_URL", "http://ha.local")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("SOFIA_NOTIFICATION_HA_SERVICE", "mobile_app_sparks")

    service = SofiaActService(tmp_path / "state.db")

    assert act_service.configure_act_delivery_from_environment(service) is True
    assert service.delivery_enabled is True


def test_default_outreach_without_transport_keeps_runtime_available(tmp_path, monkeypatch):
    for name in (
        "SOFIA_ACT_DELIVERY_ENABLED",
        "SOFIA_HOME_ASSISTANT_URL",
        "SOFIA_HOME_ASSISTANT_TOKEN",
        "SOFIA_NOTIFICATION_HA_SERVICE",
    ):
        monkeypatch.delenv(name, raising=False)
    state_path = tmp_path / "state.db"
    state_path.touch()
    service = SofiaActService(state_path)

    assert act_service.configure_act_delivery_from_environment(service) is False
    assert service.delivery_enabled is False


def test_explicit_outreach_opt_out_wins_over_configured_transport(tmp_path, monkeypatch):
    monkeypatch.setenv("SOFIA_ACT_DELIVERY_ENABLED", "0")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_URL", "http://ha.local")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("SOFIA_NOTIFICATION_HA_SERVICE", "mobile_app_sparks")
    service = SofiaActService(tmp_path / "state.db")

    assert act_service.configure_act_delivery_from_environment(service) is False
    assert service.delivery_enabled is False


def test_production_act_delivery_uses_pinned_home_assistant_destination_and_timezone(
    tmp_path,
    monkeypatch,
):
    calls = []

    class FakeHomeAssistantAdapter:
        def __init__(self, url, token):
            calls.append(("init", url, token))

        def call_service(self, domain, service, data):
            calls.append(("call", domain, service, data))

    monkeypatch.setattr(
        act_service,
        "HomeAssistantAdapter",
        FakeHomeAssistantAdapter,
    )
    monkeypatch.setenv("SOFIA_ACT_DELIVERY_ENABLED", "1")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_URL", "http://ha.local")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("SOFIA_NOTIFICATION_HA_SERVICE", "mobile_app_sparks")
    monkeypatch.setenv("SOFIA_ACT_QUIET_START_LOCAL", "22")
    monkeypatch.setenv("SOFIA_ACT_QUIET_END_LOCAL", "8")
    monkeypatch.setenv("SOFIA_ACT_MAX_DAILY", "2")

    state_path = tmp_path / "state.db"
    state_path.touch()
    service = SofiaActService(state_path)
    assert act_service.configure_act_delivery_from_environment(service) is True
    assert service.delivery_enabled is True

    service.set_local_timezone("America/Chicago")
    assert service.policy is not None
    assert service.policy.timezone_name == "America/Chicago"

    service.queue_system_notice(
        notice_id="production-act-test",
        recipient_id=SPARKS_PRINCIPAL_ID,
        channel="home_assistant",
        destination="mobile_app_sparks",
        evidence_id="test:evidence",
        content="Production wiring test.",
        created_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )
    result = service.deliver_one(now=NOW)

    assert result is not None
    assert result.outcome is DeliveryOutcome.DELIVERED
    assert calls == [
        ("init", "http://ha.local", "secret"),
        (
            "call",
            "notify",
            "mobile_app_sparks",
            {"message": "Production wiring test."},
        ),
    ]



def test_application_act_skips_blocked_message_and_delivers_later_eligible_one(
    tmp_path,
):
    state_path = tmp_path / "state.db"
    with sqlite3.connect(state_path) as db:
        db.execute(
            """
            CREATE TABLE conversation_messages (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE interact_queued_messages (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        for message_id, minute in (("blocked", 0), ("eligible", 1)):
            db.execute(
                "INSERT INTO interact_queued_messages VALUES (?,?,?,?,?,?)",
                (
                    message_id,
                    "goal-1",
                    f"evidence-{message_id}",
                    f"message {message_id}",
                    (NOW - timedelta(minutes=10 - minute)).isoformat(),
                    "queued",
                ),
            )

    outbox = ActOutbox(state_path)
    outbox.bind(
        message_id="blocked",
        recipient_id="person:other",
        channel="home_assistant",
        destination="mobile_app_sparks",
        expires_at=NOW + timedelta(hours=1),
        at=NOW - timedelta(minutes=2),
    )
    outbox.bind(
        message_id="eligible",
        recipient_id=SPARKS_PRINCIPAL_ID,
        channel="home_assistant",
        destination="mobile_app_sparks",
        expires_at=NOW + timedelta(hours=1),
        at=NOW - timedelta(minutes=1),
    )

    sent = []
    service = SofiaActService(state_path)
    service.configure_delivery(
        sender=lambda payload: (
            sent.append(payload.message_id)
            or SendResult(
                DeliveryOutcome.DELIVERED,
                receipt_id=f"receipt:{payload.message_id}",
            )
        ),
        policy=Policy(
            recipient_id=SPARKS_PRINCIPAL_ID,
            enabled=True,
            min_interval=timedelta(0),
            max_daily=10,
            social_min_interval=timedelta(0),
            social_max_daily=10,
        ),
        channel="home_assistant",
        destination="mobile_app_sparks",
    )

    result = service.deliver_one(now=NOW)

    assert result is not None
    assert sent == ["eligible"]
