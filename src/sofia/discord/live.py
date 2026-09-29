"""Production composition for Sofía's live Discord DM channel.

The module supports both the standalone supervised Discord entrypoint and the
desktop-owned production path. Desktop startup may attach Discord only when it
is explicitly provisioned, using an audience-scoped conversation on the same
canonical Sofía runtime. The standalone path remains available for supervised
transport testing and dedicated deployments.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import logging
from pathlib import Path
import sys
from threading import Event, Thread
from typing import Callable, Protocol

from sofia.application import SofiaApplication
from sofia.config import (
    SofiaConfiguration,
    create_production_configuration,
)
from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.bridge import DiscordConversationBridge
from sofia.discord.delivery import DiscordDeliveryStore, DiscordSafeSender
from sofia.discord.discordpy import (
    DiscordLiveRuntime,
    create_discordpy_client,
    run_discordpy_client,
)
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
class ComposedDiscordChannel:
    """Live Discord transport bound to an already-started conversation."""

    runtime: DiscordLiveRuntime
    inbox: DiscordInboxStore
    bindings: DiscordBindingStore
    deliveries: DiscordDeliveryStore
    state_path: Path | str
    recovered_generation_claims: int
    recovered_delivery_claims: int


def _validated_existing_binding(
    provisioning: DiscordProvisioning,
    *,
    configuration: SofiaConfiguration,
):
    discord_config = provisioning.require_config()
    bindings = DiscordBindingStore(configuration.state_path)
    existing = (
        bindings.get(
            bot_user_id=discord_config.bot_user_id,
            channel_id=discord_config.dm_channel_id,
        )
        if discord_config.dm_channel_id is not None
        else bindings.find_for_owner(
            bot_user_id=discord_config.bot_user_id,
            owner_user_id=discord_config.owner_user_id,
        )
    )
    if existing is None:
        return None
    if existing.owner_user_id != discord_config.owner_user_id:
        raise RuntimeError(
            "configured Discord owner does not match durable channel binding"
        )
    if existing.state is BindingState.REVOKED:
        raise RuntimeError(
            "Discord channel binding is revoked; supervised re-enrollment is required"
        )
    return existing


def _persist_verified_dm_channel(
    configuration: SofiaConfiguration,
    channel_id: int,
) -> None:
    """Cache the authenticated owner DM channel in durable user settings."""
    store = RuntimeUserSettingsStore(configuration.state_path)
    settings = store.load()
    if (
        not settings.discord_enabled
        or settings.discord_dm_channel_id == channel_id
    ):
        return
    store.save(
        replace(
            settings,
            discord_dm_channel_id=channel_id,
        )
    )


def discord_bound_session_id(
    provisioning: DiscordProvisioning,
    *,
    configuration: SofiaConfiguration,
) -> str | None:
    """Return the durable Discord session that production startup must resume."""

    if not isinstance(provisioning, DiscordProvisioning):
        raise TypeError("provisioning must be DiscordProvisioning")
    if not provisioning.enabled:
        return None
    existing = _validated_existing_binding(
        provisioning,
        configuration=configuration,
    )
    return None if existing is None else existing.session_id


def compose_live_discord_for_conversation(
    provisioning: DiscordProvisioning,
    *,
    conversation,
    configuration: SofiaConfiguration | None = None,
) -> ComposedDiscordChannel:
    """Bind Discord to one already-started canonical conversation/runtime."""

    if not isinstance(provisioning, DiscordProvisioning):
        raise TypeError("provisioning must be DiscordProvisioning")
    discord_config = provisioning.require_config()
    config = configuration or create_production_configuration()

    active_session = getattr(conversation, "session_id", None)
    if not isinstance(active_session, str) or not active_session.strip():
        raise RuntimeError(
            "live Discord requires an already-started Sofía conversation"
        )

    inbox = DiscordInboxStore(config.state_path)
    bindings = DiscordBindingStore(config.state_path)
    deliveries = DiscordDeliveryStore(config.state_path)

    existing = _validated_existing_binding(
        provisioning,
        configuration=config,
    )
    if existing is not None and active_session != existing.session_id:
        raise RuntimeError(
            "active Sofía conversation does not match Discord binding"
        )

    recovered_generation = inbox.recover_interrupted_processing()
    recovered_delivery = deliveries.recover_interrupted()
    if recovered_generation or recovered_delivery:
        _log.warning(
            "Discord restart quarantined %d generation claim(s) and %d "
            "delivery claim(s) with unknown outcome.",
            recovered_generation,
            recovered_delivery,
        )

    ingress = DiscordIngress(
        config=discord_config,
        inbox=inbox,
    )
    bridge = DiscordConversationBridge(
        store=inbox,
        bindings=bindings,
        conversation=conversation,
    )
    gate = DiscordOutboundGate(
        config=discord_config,
        bindings=bindings,
    )
    sender = DiscordSafeSender(
        gate=gate,
        deliveries=deliveries,
    )
    runtime = DiscordLiveRuntime(
        config=discord_config,
        ingress=ingress,
        bridge=bridge,
        sender=sender,
        store=inbox,
        bindings=bindings,
        session_id=active_session,
        deliveries=deliveries,
        on_verified_channel=(
            lambda channel_id: _persist_verified_dm_channel(
                config,
                channel_id,
            )
        ),
    )
    return ComposedDiscordChannel(
        runtime=runtime,
        inbox=inbox,
        bindings=bindings,
        deliveries=deliveries,
        state_path=config.state_path,
        recovered_generation_claims=recovered_generation,
        recovered_delivery_claims=recovered_delivery,
    )


class DiscordBackgroundService:
    """Run discord.py beside a canonical application without creating another one."""

    def __init__(
        self,
        provisioning: DiscordProvisioning,
        channel: ComposedDiscordChannel,
        *,
        client_factory=create_discordpy_client,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        if not isinstance(provisioning, DiscordProvisioning):
            raise TypeError("provisioning must be DiscordProvisioning")
        if not isinstance(channel, ComposedDiscordChannel):
            raise TypeError("channel must be ComposedDiscordChannel")
        if not callable(client_factory):
            raise TypeError("client_factory must be callable")
        if on_error is not None and not callable(on_error):
            raise TypeError("on_error must be callable or None")
        self._provisioning = provisioning
        self._channel = channel
        self._client_factory = client_factory
        self._on_error = on_error
        self._client = None
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = Event()
        self._stop_requested = Event()
        self._error: Exception | None = None
        self._process_lock = DiscordProcessLock(channel.state_path)

    @property
    def error(self) -> Exception | None:
        return self._error

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("Discord background service already started")
        token = self._provisioning.require_token()
        self._process_lock.acquire()
        try:
            self._client = self._client_factory(self._channel.runtime)
            self._thread = Thread(
                target=self._run,
                args=(token,),
                name="sofia-discord",
                daemon=True,
            )
            self._thread.start()
            if not self._loop_ready.wait(timeout=5.0):
                raise RuntimeError(
                    "Discord background event loop did not start"
                )
            if self._error is not None:
                raise RuntimeError(
                    f"Discord background startup failed: {self._error}"
                ) from self._error
        except Exception:
            self._process_lock.release()
            self._thread = None
            self._client = None
            raise

    def _run(self, token: str) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._loop_ready.set()
        try:
            loop.run_until_complete(self._client.start(token))
            startup_error = getattr(
                self._client,
                "_sofia_startup_error",
                None,
            )
            if startup_error is not None and not self._stop_requested.is_set():
                raise RuntimeError(
                    f"Discord startup failed: {startup_error}"
                ) from startup_error
            ready = bool(
                getattr(self._client, "_sofia_ready", False)
            )
            if not ready and not self._stop_requested.is_set():
                raise RuntimeError(
                    "Discord client exited before authenticated readiness"
                )
        except Exception as exc:
            self._error = exc
            if self._on_error is not None:
                self._on_error(exc)
        finally:
            try:
                close = getattr(self._client, "close", None)
                if callable(close):
                    loop.run_until_complete(close())
            except Exception:
                pass
            self._loop = None
            loop.close()

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._stop_requested.set()
        self._loop_ready.wait(timeout=5.0)
        loop = self._loop
        client = self._client
        if loop is not None and loop.is_running() and client is not None:
            future = asyncio.run_coroutine_threadsafe(
                client.close(),
                loop,
            )
            try:
                future.result(timeout=10.0)
            except Exception:
                pass
        thread.join(timeout=10.0)
        if thread.is_alive():
            raise RuntimeError(
                "Discord background service did not stop safely"
            )
        self._thread = None
        self._client = None
        self._process_lock.release()


@dataclass(slots=True)
class ComposedDiscordApplication:
    application: _ApplicationLike
    runtime: DiscordLiveRuntime
    inbox: DiscordInboxStore
    bindings: DiscordBindingStore
    deliveries: DiscordDeliveryStore
    recovered_generation_claims: int
    recovered_delivery_claims: int

    def shutdown(self) -> None:
        self.application.shutdown()


def compose_live_discord(
    provisioning: DiscordProvisioning,
    *,
    configuration: SofiaConfiguration | None = None,
    application_factory: Callable[[SofiaConfiguration], _ApplicationLike] = SofiaApplication,
) -> ComposedDiscordApplication:
    """Compose one explicitly enabled live Discord process without connecting."""
    if not isinstance(provisioning, DiscordProvisioning):
        raise TypeError("provisioning must be DiscordProvisioning")
    discord_config = provisioning.require_config()
    config = configuration or create_production_configuration()

    inbox = DiscordInboxStore(config.state_path)
    bindings = DiscordBindingStore(config.state_path)
    deliveries = DiscordDeliveryStore(config.state_path)

    existing = (
        bindings.get(
            bot_user_id=discord_config.bot_user_id,
            channel_id=discord_config.dm_channel_id,
        )
        if discord_config.dm_channel_id is not None
        else bindings.find_for_owner(
            bot_user_id=discord_config.bot_user_id,
            owner_user_id=discord_config.owner_user_id,
        )
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
        if recovered_generation or recovered_delivery:
            _log.warning(
                "Discord restart quarantined %d generation claim(s) and %d "
                "delivery claim(s) with unknown outcome.",
                recovered_generation,
                recovered_delivery,
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
        runtime = DiscordLiveRuntime(
            config=discord_config,
            ingress=ingress,
            bridge=bridge,
            sender=sender,
            store=inbox,
            bindings=bindings,
            session_id=active_session,
        )
        return ComposedDiscordApplication(
            application=application,
            runtime=runtime,
            inbox=inbox,
            bindings=bindings,
            deliveries=deliveries,
            recovered_generation_claims=recovered_generation,
            recovered_delivery_claims=recovered_delivery,
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
) -> None:
    """Run the explicitly enabled Discord channel in the foreground."""
    config = configuration or create_production_configuration()
    with DiscordProcessLock(config.state_path):
        composed = compose_live_discord(
            provisioning,
            configuration=config,
            application_factory=application_factory,
        )
        try:
            runner(provisioning.require_token(), composed.runtime)
        finally:
            composed.shutdown()


def main() -> int:
    try:
        configuration = create_production_configuration()
        provisioning = DiscordProvisioning.from_runtime(
            configuration
        )
        if not provisioning.enabled:
            raise RuntimeError(
                "Discord transport is disabled; enable it in Sofía Settings "
                "or use an explicit supervised environment override"
            )
        run_live_discord(
            provisioning,
            configuration=configuration,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        print(f"Sofía Discord startup refused: {exc}", file=sys.stderr)
        return 2
    return 0
