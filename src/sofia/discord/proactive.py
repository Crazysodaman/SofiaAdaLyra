"""Exact-owner Discord DM sender for policy-approved proactive ACT messages."""
from __future__ import annotations

from sofia.discord.access import SingleUserDiscordConfig, _snowflake
from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.integrations.http import JsonHttpClient


class DiscordProactiveSender:
    """Recheck the pinned owner binding immediately before Discord REST send."""

    def __init__(
        self,
        *,
        config: SingleUserDiscordConfig,
        bindings: DiscordBindingStore,
        token: str,
        http=None,
    ) -> None:
        if not isinstance(config, SingleUserDiscordConfig) or not config.enabled:
            raise ValueError("enabled Discord configuration required")
        if config.dm_channel_id is None:
            raise ValueError("pinned Discord owner DM channel required")
        if not isinstance(bindings, DiscordBindingStore):
            raise TypeError("bindings must be DiscordBindingStore")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Discord bot token required")
        self.config = config
        self.bindings = bindings
        self.http = http or JsonHttpClient(
            "https://discord.com/api/v10",
            headers={
                "Authorization": f"Bot {token.strip()}",
                "User-Agent": "SofiaAdaLyra/1.0 proactive-outreach",
            },
            timeout=15.0,
        )

    def send(self, content: str) -> int:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Discord outreach content must be nonempty")
        if len(content) > 2000:
            raise ValueError("Discord outreach content exceeds message limit")
        channel_id = self.config.dm_channel_id
        assert channel_id is not None
        binding = self.bindings.get(
            bot_user_id=self.config.bot_user_id,
            channel_id=channel_id,
        )
        if binding is None:
            raise PermissionError("Discord owner DM is not durably bound")
        if binding.state is not BindingState.ACTIVE:
            raise PermissionError("Discord owner DM binding is not active")
        if binding.owner_user_id != self.config.owner_user_id:
            raise PermissionError("Discord DM binding belongs to another owner")

        response = self.http.request(
            "POST",
            f"/channels/{channel_id}/messages",
            payload={
                "content": content.strip(),
                "allowed_mentions": {"parse": []},
            },
        )
        if not isinstance(response, dict):
            raise RuntimeError("Discord returned an invalid send receipt")
        raw_message_id = response.get("id")
        raw_channel_id = response.get("channel_id")
        try:
            message_id = int(raw_message_id)
            receipt_channel = int(raw_channel_id)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Discord send receipt lacks numeric identity") from exc
        if not _snowflake(message_id) or receipt_channel != channel_id:
            raise RuntimeError("Discord send receipt does not match pinned DM")
        return message_id
