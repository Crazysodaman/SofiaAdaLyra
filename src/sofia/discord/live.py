"""Supervised foreground composition for Sofía's live Discord DM channel.

This module is intentionally separate from the normal terminal application.
Nothing imports it to start networking automatically. The live process resumes
its durable Discord-bound conversation, quarantines interrupted work, and then
hands transport to discord.py.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import sys
from typing import Callable, Protocol

from sofia.application import SofiaApplication
from sofia.config import SofiaConfiguration, create_default_configuration
from sofia.discord.act_live import DiscordActTransportBridge
from sofia.discord.act_sender import DiscordActDeliveryStore, DiscordActSafeSender
from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.bridge import DiscordConversationBridge
from sofia.discord.delivery import DiscordDeliveryStore, DiscordSafeSender
from sofia.discord.discordpy import DiscordLiveRuntime, run_discordpy_client
from sofia.discord.ingress import DiscordIngress
from sofia.discord.outbound import DiscordOutboundGate
from sofia.discord.process_lock import DiscordProcessLock
from sofia.discord.provisioning import DiscordProvisioning
from sofia.discord.store import DiscordInboxStore


_log = logging.getLogger(__name__)


class _ApplicationLike(Protocol):
    @property
    def conversation(self): ...

    def start(self, session_id: str | None = None): ...

    def shutdown(self) -> None: ...


@dataclass(slots=True)
class ComposedDiscordApplication:
    application: _ApplicationLike
    runtime: DiscordLiveRuntime
    inbox: DiscordInboxStore
    bindings: DiscordBindingStore
    deliveries: DiscordDeliveryStore
    act_deliveries: DiscordActDeliveryStore
    act_transport: DiscordActTransportBridge
    recovered_generation_claims: int
    recovered_delivery_claims: int
    recovered_act_delivery_claims: int

    def shutdown(self) -> None:
        self.application.shutdown()


def compose_live_discord(
    provisioning: DiscordProvisioning,
    *,
    configuration: SofiaConfiguration | None = None,
    application_factory: Callable[[SofiaConfiguration], _ApplicationLike] = SofiaApplication,
    act_recipient_id: str | None = None,
) -> ComposedDiscordApplication:
    """Compose one explicitly enabled live Discord process without connecting."""
    if not isinstance(provisioning, DiscordProvisioning):
        raise TypeError("provisioning must be DiscordProvisioning")
    discord_config = provisioning.require_config()
    config = configuration or create_default_configuration()
    if act_recipient_id is not None:
        if (
            not isinstance(act_recipient_id, str)
            or not act_recipient_id.strip()
            or len(act_recipient_id.strip()) > 120
        ):
            raise ValueError("act_recipient_id must be a bounded identifier")
        act_recipient_id = act_recipient_id.strip()

    inbox = DiscordInboxStore(config.state_path)
    bindings = DiscordBindingStore(config.state_path)
    deliveries = DiscordDeliveryStore(config.state_path)
    act_deliveries = DiscordActDeliveryStore(config.state_path)
    act_transport = DiscordActTransportBridge(
        expected_channel_id=discord_config.dm_channel_id,
    )

    existing = bindings.get(
        bot_user_id=discord_config.bot_user_id,
        channel_id=discord_config.dm_channel_id,
    )
    if existing is not None:
        if existing.owner_user_id != discord_config.owner_user_id:
            raise RuntimeError(
                "configured Discord owner does not match durable channel binding"
            )
        if existing.state is BindingState.REVOKED:
            raise RuntimeError(
                "Discord channel binding is revoked; supervised re-enrollment is required"
            )
        session_id = existing.session_id
    else:
        session_id = None

    application = application_factory(config)
    started = False
    try:
        application.start(session_id=session_id)
        started = True
        active_session = application.conversation.session_id
        if not isinstance(active_session, str) or not active_session.strip():
            raise RuntimeError("live Discord requires an active Sofía conversation")

        if existing is not None and active_session != existing.session_id:
            raise RuntimeError(
                "resumed Sofía conversation does not match Discord binding"
            )

        recovered_generation = inbox.recover_interrupted_processing()
        recovered_delivery = deliveries.recover_interrupted()
        recovered_act_delivery = act_deliveries.recover_interrupted()
        if recovered_generation or recovered_delivery or recovered_act_delivery:
            _log.warning(
                "Discord restart quarantined %d generation claim(s), %d reply "
                "delivery claim(s), and %d proactive ACT transport claim(s) "
                "with unknown outcome.",
                recovered_generation,
                recovered_delivery,
                recovered_act_delivery,
            )

        ingress = DiscordIngress(
            config=discord_config,
            inbox=inbox,
        )
        bridge = DiscordConversationBridge(
            store=inbox,
            bindings=bindings,
            conversation=application.conversation,
        )
        gate = DiscordOutboundGate(
            config=discord_config,
            bindings=bindings,
        )
        sender = DiscordSafeSender(
            gate=gate,
            deliveries=deliveries,
        )
        act_sender = (
            DiscordActSafeSender(
                config=discord_config,
                bindings=bindings,
                deliveries=act_deliveries,
                session_id=active_session,
                recipient_id=act_recipient_id,
                send_chunk=act_transport.send_chunk,
            )
            if act_recipient_id is not None
            else None
        )
        runtime = DiscordLiveRuntime(
            config=discord_config,
            ingress=ingress,
            bridge=bridge,
            sender=sender,
            store=inbox,
            bindings=bindings,
            session_id=active_session,
            act_transport=act_transport,
            act_sender=act_sender,
        )
        return ComposedDiscordApplication(
            application=application,
            runtime=runtime,
            inbox=inbox,
            bindings=bindings,
            deliveries=deliveries,
            act_deliveries=act_deliveries,
            act_transport=act_transport,
            recovered_generation_claims=recovered_generation,
            recovered_delivery_claims=recovered_delivery,
            recovered_act_delivery_claims=recovered_act_delivery,
        )
    except Exception:
        if started:
            application.shutdown()
        raise


def run_live_discord(
    provisioning: DiscordProvisioning,
    *,
    configuration: SofiaConfiguration | None = None,
    application_factory: Callable[[SofiaConfiguration], _ApplicationLike] = SofiaApplication,
    runner=run_discordpy_client,
    act_recipient_id: str | None = None,
) -> None:
    """Run the explicitly enabled Discord channel in the foreground."""
    config = configuration or create_default_configuration()
    with DiscordProcessLock(config.state_path):
        composed = compose_live_discord(
            provisioning,
            configuration=config,
            application_factory=application_factory,
            act_recipient_id=act_recipient_id,
        )
        try:
            runner(provisioning.require_token(), composed.runtime)
        finally:
            composed.shutdown()


def main() -> int:
    try:
        provisioning = DiscordProvisioning.from_environment()
        if not provisioning.enabled:
            raise RuntimeError(
                "Discord transport is disabled; set SOFIA_DISCORD_ENABLED=1 "
                "only on the supervised host"
            )
        run_live_discord(provisioning)
    except (RuntimeError, TypeError, ValueError) as exc:
        print(f"Sofía Discord startup refused: {exc}", file=sys.stderr)
        return 2
    return 0
