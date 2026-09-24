"""Host-side controls for the supervised single-owner Discord channel.

These commands operate only on durable local state. They never connect to
Discord, never read the bot token, and never infer authority from chat text.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Callable

from sofia.config import SofiaConfiguration, create_default_configuration
from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.delivery import DiscordDeliveryStore
from sofia.discord.provisioning import DiscordIdentity
from sofia.discord.store import DiscordInboxStore


@dataclass(frozen=True, slots=True)
class DiscordOperatorStatus:
    state: BindingState
    session_id: str
    generation: int
    pending_outbox: int
    unknown_generation_outcomes: int
    unknown_delivery_outcomes: int


def inspect_discord_state(
    identity: DiscordIdentity,
    *,
    configuration: SofiaConfiguration | None = None,
) -> DiscordOperatorStatus:
    if not isinstance(identity, DiscordIdentity):
        raise TypeError("identity must be DiscordIdentity")
    config = configuration or create_default_configuration()

    bindings = DiscordBindingStore(config.state_path)
    binding = bindings.get(
        bot_user_id=identity.bot_user_id,
        channel_id=identity.dm_channel_id,
    )
    if binding is None:
        raise RuntimeError("Discord channel has not been enrolled")
    if binding.owner_user_id != identity.owner_user_id:
        raise RuntimeError("configured Discord owner does not match durable binding")

    inbox = DiscordInboxStore(config.state_path)
    deliveries = DiscordDeliveryStore(config.state_path)
    pending = inbox.list_outbox(
        bot_user_id=identity.bot_user_id,
        channel_id=identity.dm_channel_id,
        states=("prepared",),
    )
    return DiscordOperatorStatus(
        state=binding.state,
        session_id=binding.session_id,
        generation=binding.generation,
        pending_outbox=len(pending),
        unknown_generation_outcomes=inbox.count_outcome_unknown(),
        unknown_delivery_outcomes=deliveries.count_outcome_unknown(),
    )


def control_discord(
    action: str,
    identity: DiscordIdentity,
    *,
    configuration: SofiaConfiguration | None = None,
) -> DiscordOperatorStatus:
    if action not in {"status", "pause", "resume", "revoke"}:
        raise ValueError("Discord operator action must be status, pause, resume, or revoke")
    config = configuration or create_default_configuration()
    if action != "status":
        bindings = DiscordBindingStore(config.state_path)
        binding = bindings.get(
            bot_user_id=identity.bot_user_id,
            channel_id=identity.dm_channel_id,
        )
        if binding is None:
            raise RuntimeError("Discord channel has not been enrolled")
        if binding.owner_user_id != identity.owner_user_id:
            raise RuntimeError("configured Discord owner does not match durable binding")
        if action == "pause":
            bindings.pause(
                bot_user_id=identity.bot_user_id,
                channel_id=identity.dm_channel_id,
            )
        elif action == "resume":
            bindings.resume(
                bot_user_id=identity.bot_user_id,
                channel_id=identity.dm_channel_id,
            )
        else:
            bindings.revoke(
                bot_user_id=identity.bot_user_id,
                channel_id=identity.dm_channel_id,
            )
    return inspect_discord_state(identity, configuration=config)


def _render(status: DiscordOperatorStatus) -> str:
    return (
        f"Discord state={status.state.value} "
        f"session={status.session_id} generation={status.generation} "
        f"pending={status.pending_outbox} "
        f"unknown_generation={status.unknown_generation_outcomes} "
        f"unknown_delivery={status.unknown_delivery_outcomes}"
    )


def main(
    action: str,
    *,
    output: Callable[[str], None] = print,
    error_output: Callable[[str], None] | None = None,
) -> int:
    errors = error_output or (lambda text: print(text, file=sys.stderr))
    try:
        identity = DiscordIdentity.from_environment()
        status = control_discord(action, identity)
    except (RuntimeError, TypeError, ValueError) as exc:
        errors(f"Sofía Discord operator command refused: {exc}")
        return 2
    output(_render(status))
    return 0
