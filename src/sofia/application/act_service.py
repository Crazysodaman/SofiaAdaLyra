from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
from sofia.act.diagnostics import OutreachTraceStore
from sofia.interaction.goal_journal import GoalJournal
from sofia.personality.influence import ContinuityInfluence, outreach_salience
from sofia.personality.reflection import ReflectionJournal
from sofia.social.model import ScopeKind, SocialScope
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.integrations.home_assistant import HomeAssistantAdapter
from sofia.ui.notifications import DesktopNotificationStore
from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.proactive import DiscordProactiveSender
from sofia.discord.provisioning import DiscordProvisioning
from sofia.safe.operator_stop import OperatorStopStore


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

    @property
    def delivery_route(self) -> tuple[str, str] | None:
        if self._default_channel is None or self._default_destination is None:
            return None
        return self._default_channel, self._default_destination

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
        category: OutreachCategory = OutreachCategory.OPERATIONAL,
        importance: Importance = Importance.ROUTINE,
        salience: float = 0.5,
    ):
        notice = SystemNoticeQueue(self.state_path).enqueue(
            notice_id=notice_id,
            recipient_id=recipient_id,
            channel=channel,
            destination=destination,
            evidence_id=evidence_id,
            content=content,
            created_at=created_at,
            expires_at=expires_at,
            category=category,
            importance=importance,
            salience=salience,
        )
        if not self.delivery_enabled:
            OutreachTraceStore(self.state_path).record(
                notice_id=notice.notice_id,
                stage="suppressed",
                reason="missing_transport",
                recorded_at=created_at,
                channel=channel,
                destination=destination,
            )
        return notice

    def has_pending(self) -> bool:
        """Return queue readiness without claiming or evaluating policy."""
        return SystemNoticeQueue(self.state_path).has_pending() or bool(
            GoalJournal(self.state_path).pending(limit=1)
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
        policy = self._policy
        if policy is None:
            return None
        if OperatorStopStore(self.state_path).current().active:
            policy = replace(policy, stop=True)
        notice_result = SystemNoticeQueue(self.state_path).deliver_one(
            sender=self._sender,
            policy=policy,
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
                policy=policy,
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


def _enabled(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if value == "":
        return default
    if value in ("0", "false", "off"):
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
    Configure the production ACT sender when its transport is ready.

    Outreach defaults to the durable local tray transport. An explicit
    preference may select Home Assistant instead; incomplete configuration
    fails closed without preventing the rest of Sofía's runtime from starting.
    """
    if not isinstance(service, SofiaActService):
        raise TypeError("service must be a SofiaActService")
    from sofia.config.user_settings import RuntimeUserSettingsStore
    from sofia.safe.secret_store import ProtectedSecretStore
    preferences = RuntimeUserSettingsStore(service.state_path).load()
    outreach = preferences.outreach
    if not (
        outreach.enabled
        if outreach is not None
        else _enabled("SOFIA_ACT_DELIVERY_ENABLED", default=True)
    ):
        service.disable_delivery()
        return False

    configured_channel = os.environ.get(
        "SOFIA_ACT_DELIVERY_CHANNEL", ""
    ).strip()
    channel = (
        outreach.delivery_channel
        if outreach is not None
        else configured_channel
        or (
            "home_assistant"
            if notification_destination_from_environment()
            else "desktop"
        )
    )
    policy = outreach.policy(SPARKS_PRINCIPAL_ID) if outreach is not None else Policy(
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
                os.environ.get("SOFIA_ACT_MIN_INTERVAL_MINUTES", "360")
            )
        ),
        max_daily=int(os.environ.get("SOFIA_ACT_MAX_DAILY", "1")),
    )

    if channel == "desktop":
        notifications = DesktopNotificationStore(service.state_path)

        def desktop_sender(payload: DeliveryPayload) -> SendResult:
            if not isinstance(payload, DeliveryPayload):
                raise TypeError("payload must be a DeliveryPayload")
            if payload.recipient_id != SPARKS_PRINCIPAL_ID:
                raise PermissionError(
                    "ACT desktop sender is currently bound only to Sparks"
                )
            if payload.channel != "desktop" or payload.destination != "tray":
                raise PermissionError(
                    "ACT desktop destination does not match the local tray"
                )
            notifications.enqueue(
                notification_id=f"act:{payload.message_id}",
                title="Sofía",
                content=(
                    payload.content
                    if len(payload.content) <= 255
                    else payload.content[:252].rstrip() + "..."
                ),
                created_at=datetime.now(timezone.utc),
            )
            return SendResult(
                DeliveryOutcome.DELIVERED,
                receipt_id=f"desktop-queued:{payload.message_id}",
            )

        service.configure_delivery(
            sender=desktop_sender,
            channel="desktop",
            destination="tray",
            policy=policy,
        )
        return True

    if channel == "discord":
        if "SOFIA_DISCORD_ENABLED" in os.environ:
            provisioning = DiscordProvisioning.from_environment()
        else:
            provisioning = DiscordProvisioning(
                enabled=preferences.discord_enabled,
                owner_user_id=preferences.discord_owner_user_id,
                bot_user_id=preferences.discord_bot_user_id,
                dm_channel_id=preferences.discord_dm_channel_id,
                token=ProtectedSecretStore.for_state_path(
                    service.state_path
                ).get("discord-token"),
            )
        if not provisioning.enabled or provisioning.dm_channel_id is None:
            service.disable_delivery()
            return False
        config = provisioning.require_config()
        token = provisioning.require_token()
        bindings = DiscordBindingStore(service.state_path)
        binding = bindings.get(
            bot_user_id=config.bot_user_id,
            channel_id=config.dm_channel_id,
        )
        if (
            binding is None
            or binding.state is not BindingState.ACTIVE
            or binding.owner_user_id != config.owner_user_id
        ):
            service.disable_delivery()
            return False
        discord_sender = DiscordProactiveSender(
            config=config,
            bindings=bindings,
            token=token,
        )
        destination = str(config.dm_channel_id)

        def send_discord(payload: DeliveryPayload) -> SendResult:
            if not isinstance(payload, DeliveryPayload):
                raise TypeError("payload must be a DeliveryPayload")
            if payload.recipient_id != SPARKS_PRINCIPAL_ID:
                raise PermissionError(
                    "ACT Discord sender is currently bound only to Sparks"
                )
            if (
                payload.channel != "discord"
                or payload.destination != destination
            ):
                raise PermissionError(
                    "ACT Discord destination does not match the pinned owner DM"
                )
            message_id = discord_sender.send(payload.content)
            return SendResult(
                DeliveryOutcome.DELIVERED,
                receipt_id=f"discord-ack:{message_id}",
            )

        service.configure_delivery(
            sender=send_discord,
            channel="discord",
            destination=destination,
            policy=policy,
        )
        return True

    if channel == "mobile":
        from sofia.mobile.notifications import MobileNotificationStore
        from sofia.mobile.provisioning import mobile_companion_ready

        if not mobile_companion_ready(service.state_path):
            service.disable_delivery()
            return False
        notifications = MobileNotificationStore(service.state_path)

        def mobile_sender(payload: DeliveryPayload) -> SendResult:
            if not isinstance(payload, DeliveryPayload):
                raise TypeError("payload must be a DeliveryPayload")
            if payload.recipient_id != SPARKS_PRINCIPAL_ID:
                raise PermissionError(
                    "ACT mobile sender is currently bound only to Sparks"
                )
            if payload.channel != "mobile" or payload.destination != "paired-phone":
                raise PermissionError(
                    "ACT mobile destination does not match the paired phone"
                )
            notifications.enqueue(
                notification_id=f"act:{payload.message_id}",
                title="Sofía",
                content=payload.content,
                created_at=datetime.now(timezone.utc),
            )
            return SendResult(
                DeliveryOutcome.DELIVERED,
                receipt_id=f"mobile-queued:{payload.message_id}",
            )

        service.configure_delivery(
            sender=mobile_sender,
            channel="mobile",
            destination="paired-phone",
            policy=policy,
        )
        return True

    if channel != "home_assistant":
        raise ValueError(
            "SOFIA_ACT_DELIVERY_CHANNEL must be desktop, discord, mobile, or "
            "home_assistant"
        )

    url = os.environ.get("SOFIA_HOME_ASSISTANT_URL", "").strip()
    token = os.environ.get("SOFIA_HOME_ASSISTANT_TOKEN", "").strip()
    notify_service = outreach.notification_service if outreach is not None else notification_destination_from_environment()
    if outreach is not None:
        url = preferences.home_assistant_url or ""
        token = ProtectedSecretStore.for_state_path(service.state_path).get("home-assistant-token") or ""
    if not url or not token or not notify_service:
        # Outreach is on by default, but an unavailable transport must not
        # prevent Sofía from starting. Settings expose the missing pieces and
        # the next restart activates delivery once all three are present.
        service.disable_delivery()
        return False
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
        policy=policy,
    )
    return True


def notification_destination_from_environment(*, state_path: Path | None = None) -> str:
    """Read the saved notification service, falling back to host configuration.

    A configured destination permits queue wiring; delivery still requires
    explicit ACT policy authorization. An empty destination disables notices.
    """
    if state_path is not None:
        from sofia.config.user_settings import RuntimeUserSettingsStore
        settings = RuntimeUserSettingsStore(state_path).load()
        outreach = settings.outreach
        if outreach is not None:
            return outreach.notification_service
    destination = os.environ.get("SOFIA_NOTIFICATION_HA_SERVICE", "").strip()
    if destination and (
        "/" in destination
        or not destination.replace("_", "").replace("-", "").isalnum()
    ):
        raise ValueError(
            "SOFIA_NOTIFICATION_HA_SERVICE must be one notify service name"
        )
    return destination


def notification_route_from_environment(
    *,
    state_path: Path | None = None,
) -> tuple[str, str] | None:
    """Return the selected queue route without claiming transport readiness."""
    if state_path is not None:
        from sofia.config.user_settings import RuntimeUserSettingsStore

        settings = RuntimeUserSettingsStore(state_path).load()
        outreach = settings.outreach
        if outreach is not None:
            if not outreach.enabled:
                return None
            if outreach.delivery_channel == "desktop":
                return "desktop", "tray"
            if outreach.delivery_channel == "discord":
                return (
                    None
                    if (
                        not settings.discord_enabled
                        or settings.discord_dm_channel_id is None
                    )
                    else ("discord", str(settings.discord_dm_channel_id))
                )
            if outreach.delivery_channel == "mobile":
                from sofia.mobile.provisioning import mobile_companion_ready
                return (
                    ("mobile", "paired-phone")
                    if mobile_companion_ready(state_path)
                    else None
                )
            return (
                None
                if not outreach.notification_service
                else ("home_assistant", outreach.notification_service)
            )
    destination = notification_destination_from_environment()
    channel = os.environ.get("SOFIA_ACT_DELIVERY_CHANNEL", "").strip()
    if not channel:
        channel = "home_assistant" if destination else "desktop"
    if channel == "desktop":
        return "desktop", "tray"
    if channel == "mobile":
        enabled = _enabled("SOFIA_MOBILE_ENABLED")
        token = os.environ.get("SOFIA_MOBILE_TOKEN", "").strip()
        if enabled and 32 <= len(token) <= 512:
            return "mobile", "paired-phone"
        return None
    if channel == "home_assistant" and destination:
        return "home_assistant", destination
    return None
