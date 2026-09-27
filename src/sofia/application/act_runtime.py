from __future__ import annotations

from datetime import timedelta
import os
from uuid import uuid4

from sofia.act.delivery import DeliveryOutcome, DeliveryPayload, SendResult
from sofia.act.outreach import Policy
from sofia.application.act_service import SofiaActService
from sofia.integrations.home_assistant import HomeAssistantAdapter
from sofia.social.principals import SPARKS_PRINCIPAL_ID


def _enabled(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if value in ("", "0", "false", "off"):
        return False
    if value in ("1", "true", "on"):
        return True
    raise ValueError(
        f"{name} must be 1 or 0 (also accepts true/false)"
    )


def configure_act_delivery_from_environment(
    service: SofiaActService,
) -> bool:
    """
    Configure the production ACT sender only through explicit host opt-in.

    Home Assistant credentials alone never enable proactive delivery.
    """
    if not isinstance(service, SofiaActService):
        raise TypeError("service must be a SofiaActService")
    if not _enabled("SOFIA_ACT_DELIVERY_ENABLED"):
        service.disable_delivery()
        return False

    url = os.environ.get("SOFIA_HOME_ASSISTANT_URL", "").strip()
    token = os.environ.get("SOFIA_HOME_ASSISTANT_TOKEN", "").strip()
    notify_service = os.environ.get(
        "SOFIA_NOTIFICATION_HA_SERVICE",
        "",
    ).strip()
    if not url or not token or not notify_service:
        raise RuntimeError(
            "ACT delivery requires Home Assistant URL/token and "
            "SOFIA_NOTIFICATION_HA_SERVICE"
        )
    if (
        "/" in notify_service
        or not notify_service.replace("_", "").replace("-", "").isalnum()
    ):
        raise ValueError(
            "SOFIA_NOTIFICATION_HA_SERVICE must be one notify service name"
        )

    adapter = HomeAssistantAdapter(url, token)

    def sender(payload: DeliveryPayload) -> SendResult:
        if not isinstance(payload, DeliveryPayload):
            raise TypeError("payload must be a DeliveryPayload")
        if payload.recipient_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "ACT production sender is currently bound only to Sparks"
            )
        if payload.channel != "home_assistant":
            raise PermissionError(
                "ACT production sender accepts only home_assistant channel"
            )
        if payload.destination != notify_service:
            raise PermissionError(
                "ACT destination does not match configured notify service"
            )
        adapter.call_service(
            "notify",
            notify_service,
            {"message": payload.content},
        )
        return SendResult(
            DeliveryOutcome.DELIVERED,
            receipt_id=f"ha-ack:{uuid4()}",
        )

    service.configure_delivery(
        sender=sender,
        channel="home_assistant",
        destination=notify_service,
        policy=Policy(
            recipient_id=SPARKS_PRINCIPAL_ID,
            enabled=True,
            mute=False,
            stop=False,
            quiet_start_local=int(
                os.environ.get("SOFIA_ACT_QUIET_START_LOCAL", "22")
            ),
            quiet_end_local=int(
                os.environ.get("SOFIA_ACT_QUIET_END_LOCAL", "8")
            ),
            timezone_name="UTC",
            min_interval=timedelta(
                minutes=int(
                    os.environ.get(
                        "SOFIA_ACT_MIN_INTERVAL_MINUTES",
                        "360",
                    )
                )
            ),
            max_daily=int(
                os.environ.get("SOFIA_ACT_MAX_DAILY", "1")
            ),
        ),
    )
    return True
