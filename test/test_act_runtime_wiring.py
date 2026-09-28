from datetime import datetime, timedelta, timezone

import sofia.application.act_runtime as act_runtime
from sofia.act.delivery import DeliveryOutcome
from sofia.application.act_service import SofiaActService
from sofia.social.principals import SPARKS_PRINCIPAL_ID


NOW = datetime(2026, 9, 28, 15, 0, tzinfo=timezone.utc)


def test_production_act_delivery_requires_explicit_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("SOFIA_ACT_DELIVERY_ENABLED", raising=False)
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_URL", "http://ha.local")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("SOFIA_NOTIFICATION_HA_SERVICE", "mobile_app_sparks")

    service = SofiaActService(tmp_path / "state.db")

    assert act_runtime.configure_act_delivery_from_environment(service) is False
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
        act_runtime,
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

    service = SofiaActService(tmp_path / "state.db")
    assert act_runtime.configure_act_delivery_from_environment(service) is True
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
