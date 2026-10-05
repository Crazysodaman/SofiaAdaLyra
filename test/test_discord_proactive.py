from sofia.discord.access import SingleUserDiscordConfig
from sofia.discord.binding import DiscordBindingStore
from sofia.discord.proactive import DiscordProactiveSender


OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 223456789012345678
MESSAGE = 323456789012345678


class FakeHTTP:
    def __init__(self):
        self.calls = []

    def request(self, method, path, *, payload):
        self.calls.append((method, path, payload))
        return {"id": str(MESSAGE), "channel_id": str(CHANNEL)}


def test_proactive_discord_send_rechecks_exact_active_owner_binding(tmp_path):
    path = tmp_path / "state.db"
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-1",
    )
    http = FakeHTTP()
    sender = DiscordProactiveSender(
        config=SingleUserDiscordConfig(
            owner_user_id=OWNER,
            bot_user_id=BOT,
            enabled=True,
            dm_channel_id=CHANNEL,
        ),
        bindings=bindings,
        token="protected-token",
        http=http,
    )

    assert sender.send("Hey, I had an idea.") == MESSAGE
    assert http.calls == [
        (
            "POST",
            f"/channels/{CHANNEL}/messages",
            {
                "content": "Hey, I had an idea.",
                "allowed_mentions": {"parse": []},
            },
        )
    ]


def test_paused_discord_binding_blocks_proactive_send(tmp_path):
    path = tmp_path / "state.db"
    bindings = DiscordBindingStore(path)
    bindings.bind(
        bot_user_id=BOT,
        owner_user_id=OWNER,
        channel_id=CHANNEL,
        session_id="session-1",
    )
    bindings.pause(bot_user_id=BOT, channel_id=CHANNEL)
    sender = DiscordProactiveSender(
        config=SingleUserDiscordConfig(
            owner_user_id=OWNER,
            bot_user_id=BOT,
            enabled=True,
            dm_channel_id=CHANNEL,
        ),
        bindings=bindings,
        token="protected-token",
        http=FakeHTTP(),
    )

    try:
        sender.send("This must not send.")
    except PermissionError as exc:
        assert "not active" in str(exc)
    else:
        raise AssertionError("paused binding unexpectedly allowed outreach")
