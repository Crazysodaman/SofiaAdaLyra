"""Offline contract tests; not Discord transport/integration evidence."""

from dataclasses import replace

import pytest

from sofia.discord.access import (
    Denial,
    DiscordInboundFacts,
    SingleUserDiscordConfig,
    authorize_private_dm,
)


OWNER = 123456789012345678
BOT = 987654321098765432


def owner_dm(**changes: object) -> DiscordInboundFacts:
    baseline = DiscordInboundFacts(
        author_user_id=OWNER,
        recipient_user_id=BOT,
        channel_kind="dm",
        guild_id=None,
        author_is_bot=False,
        webhook_id=None,
        authenticated_source=True,
    )
    return replace(baseline, **changes)


def enabled_config() -> SingleUserDiscordConfig:
    return SingleUserDiscordConfig(owner_user_id=OWNER, bot_user_id=BOT, enabled=True)


def test_disabled_by_default() -> None:
    config = SingleUserDiscordConfig(owner_user_id=OWNER, bot_user_id=BOT)
    assert authorize_private_dm(config, owner_dm()).reason is Denial.DISABLED


def test_authenticated_owner_dm_is_allowed() -> None:
    decision = authorize_private_dm(enabled_config(), owner_dm())
    assert decision.allowed is True
    assert decision.reason is None


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"authenticated_source": False}, Denial.UNVERIFIED_SOURCE),
        ({"authenticated_source": None}, Denial.UNVERIFIED_SOURCE),
        ({"author_user_id": 111}, Denial.NOT_OWNER),
        ({"recipient_user_id": 222}, Denial.WRONG_RECIPIENT),
        ({"channel_kind": "group_dm"}, Denial.NOT_DIRECT_MESSAGE),
        ({"channel_kind": "guild_text"}, Denial.NOT_DIRECT_MESSAGE),
        ({"guild_id": 333}, Denial.NOT_DIRECT_MESSAGE),
        ({"author_is_bot": True}, Denial.AUTOMATED_SENDER),
        ({"webhook_id": 444}, Denial.AUTOMATED_SENDER),
        ({"author_user_id": "123456789012345678"}, Denial.MALFORMED),
        ({"author_user_id": None}, Denial.MALFORMED),
        ({"recipient_user_id": True}, Denial.MALFORMED),
        ({"channel_kind": None}, Denial.MALFORMED),
        ({"author_is_bot": None}, Denial.MALFORMED),
        ({"guild_id": 0}, Denial.MALFORMED),
        ({"webhook_id": -1}, Denial.MALFORMED),
    ],
)
def test_untrusted_or_wrong_audience_is_denied(changes: dict, reason: Denial) -> None:
    decision = authorize_private_dm(enabled_config(), owner_dm(**changes))
    assert decision.allowed is False
    assert decision.reason is reason


@pytest.mark.parametrize(
    ("owner", "bot"),
    [(0, BOT), (-1, BOT), ("123", BOT), (True, BOT), (OWNER, OWNER), (OWNER, 1 << 64)],
)
def test_bad_config_rejected(owner: object, bot: object) -> None:
    with pytest.raises(ValueError):
        SingleUserDiscordConfig(owner_user_id=owner, bot_user_id=bot)


def test_non_boolean_enable_rejected() -> None:
    with pytest.raises(TypeError):
        SingleUserDiscordConfig(owner_user_id=OWNER, bot_user_id=BOT, enabled=1)


def test_requires_typed_trusted_facts() -> None:
    with pytest.raises(TypeError):
        authorize_private_dm(enabled_config(), {"author_user_id": OWNER})
