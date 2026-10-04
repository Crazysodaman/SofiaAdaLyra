from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import os
from pathlib import Path
from typing import Callable
from uuid import uuid4

from sofia.act.delivery import (
    ActDeliveryRunner,
    ActOutbox,
    DeliveryOutcome,
    DeliveryPayload,
    DeliveryRunResult,
    SendResult,
)
from sofia.act.outreach import Importance, OutreachCategory, Policy
from sofia.act.system_notice import SystemNoticeQueue
from sofia.interaction.goal_journal import GoalJournal
from sofia.personality.influence import ContinuityInfluence, outreach_salience
from sofia.personality.reflection import ReflectionJournal
from sofia.social.model import ScopeKind, SocialScope
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.integrations.home_assistant import HomeAssistantAdapter


class SofiaActService:
    """Application-owned ACT delivery facade over durable INTERACT queue state."""

    def __init__(self, state_path: Path) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be a Path")
        self.state_path = state_path
        self._sender: Callable[[DeliveryPayload], SendResult] | None = None
        self._policy: Policy | None = None
        self._default_channel: str | None = None
        self._default_destination: str | None = None

    def configure_delivery(
        self,
        *,
        sender: Callable[[DeliveryPayload], SendResult],
        policy: Policy,
        channel: str | None = None,
        destination: str | None = None,
    ) -> None:
        if not callable(sender):
            raise TypeError("sender must be callable")
        if not isinstance(policy, Policy):
            raise TypeError("policy must be a Policy")
        if (channel is None) != (destination is None):
            raise ValueError("channel and destination must be configured together")
        if channel is not None and (
            not isinstance(channel, str) or not channel.strip()
        ):
            raise ValueError("channel must be nonempty")
        if destination is not None and (
            not isinstance(destination, str) or not destination.strip()
        ):
            raise ValueError("destination must be nonempty")
        self._sender = sender
        self._policy = policy
        self._default_channel = channel.strip() if channel else None
        self._default_destination = destination.strip() if destination else None

    def disable_delivery(self) -> None:
        self._sender = None
        self._policy = None
        self._default_channel = None
        self._default_destination = None

    @property
    def delivery_enabled(self) -> bool:
        return self._sender is not None and self._policy is not None

    @property
    def policy(self) -> Policy | None:
        return self._policy

    def set_local_timezone(self, timezone_name: str) -> None:
        """Update outreach quiet-hour evaluation from trusted ENVIRONMENT."""
        if self._policy is None:
            return
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise ValueError("timezone_name must be nonempty")
        self._policy = replace(
            self._policy,
            timezone_name=timezone_name.strip(),
        )

    def queue_system_notice(
        self,
        *,
        notice_id: str,
        recipient_id: str,
        channel: str,
        destination: str,
        evidence_id: str,
        content: str,
        created_at: datetime,
        expires_at: datetime,
    ):
        return SystemNoticeQueue(self.state_path).enqueue(
            notice_id=notice_id,
            recipient_id=recipient_id,
            channel=channel,
            destination=destination,
            evidence_id=evidence_id,
            content=content,
            created_at=created_at,
            expires_at=expires_at,
        )

    def bridge_reflection_outbox(
        self,
        *,
        reflections: ReflectionJournal,
        scope: SocialScope,
        now: datetime,
        influence: ContinuityInfluence,
    ) -> int:
        """Turn explicit share-now reflections into scoped social ACT candidates."""
        if not isinstance(reflections, ReflectionJournal):
            raise TypeError("reflections must be ReflectionJournal")
        if not isinstance(scope, SocialScope):
            raise TypeError("scope must be SocialScope")
        if scope.kind not in (ScopeKind.RELATIONSHIP, ScopeKind.AUDIENCE):
            return 0
        if (
            not self.delivery_enabled
            or self._default_channel is None
            or self._default_destination is None
        ):
            return 0

        principal_id = scope.principal_id
        if principal_id is None:
            return 0

        bridged = 0
        queue = SystemNoticeQueue(self.state_path)
        for entry in reflections.pending(limit=10, scope=scope):
            base = {
                "routine": 0.35,
                "excited": 0.60,
                "urgent": 0.90,
            }[entry.urgency]
            salience = outreach_salience(
                base_importance=base,
                influence=influence,
            )
            importance = (
                Importance.IMPORTANT
                if salience >= 0.72
                else Importance.ROUTINE
            )
            queue.enqueue(
                notice_id=f"reflection:{entry.message_id}",
                recipient_id=principal_id,
                channel=self._default_channel,
                destination=self._default_destination,
                evidence_id=entry.evidence_ref,
                content=entry.content,
                created_at=entry.queued_at,
                expires_at=entry.queued_at + (
                    timedelta(hours=6)
                    if importance is Importance.IMPORTANT
                    else timedelta(days=1)
                ),
                category=OutreachCategory.SOCIAL,
                importance=importance,
                salience=salience,
            )
            reflections.mark_outbox_bridged(
                message_id=entry.message_id,
            )
            bridged += 1
        return bridged

    def deliver_one(
        self,
        *,
        now: datetime,
        busy: bool = False,
    ) -> DeliveryRunResult | SendResult | None:
        if not self.delivery_enabled:
            return None
        notice_result = SystemNoticeQueue(self.state_path).deliver_one(
            sender=self._sender,
            policy=self._policy,
            now=now,
            busy=busy,
        )
        if notice_result is not None:
            return notice_result

        journal = GoalJournal(self.state_path)
        outbox = ActOutbox(self.state_path)
        runner = ActDeliveryRunner(
            outbox,
            self._sender,
        )
        for message in journal.pending(limit=10):
            if outbox.bound(message.id) is None:
                continue
            result = runner.deliver(
                message_id=message.id,
                attempt_id=str(uuid4()),
                policy=self._policy,
                now=now,
                busy=busy,
            )
            if result.claim_result.status not in (
                "not_queued",
                "not_bound",
                "retry_wait",
                "attempt_limit",
                "outcome_unknown",
                "policy_blocked",
            ):
                return result
        return None


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
    notify_service = notification_destination_from_environment()
    if not url or not token or not notify_service:
        raise RuntimeError(
            "ACT delivery requires Home Assistant URL/token and "
            "SOFIA_NOTIFICATION_HA_SERVICE"
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


def notification_destination_from_environment() -> str:
    """Read one validated Home Assistant notification service, without opt-in.

    A configured destination permits queue wiring; delivery still requires
    explicit ACT policy authorization. An empty destination disables notices.
    """
    destination = os.environ.get("SOFIA_NOTIFICATION_HA_SERVICE", "").strip()
    if destination and (
        "/" in destination
        or not destination.replace("_", "").replace("-", "").isalnum()
    ):
        raise ValueError(
            "SOFIA_NOTIFICATION_HA_SERVICE must be one notify service name"
        )
    return destination
