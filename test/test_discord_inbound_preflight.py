"""Offline ingress screening tests."""

from dataclasses import replace

import pytest

from sofia.discord.access import Denial, DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.inbound import DiscordTextEvent, InboundDenial, screen_text_dm

OWNER = 123456789012345678
BOT = 987654321098765432
CHANNEL = 2002


def config(
    enabled: bool = True,
    *,
    dm_channel_id: int | None = None,
) -> SingleUserDiscordConfig:
    return SingleUserDiscordConfig(
        OWNER,
        BOT,
        enabled,
        dm_channel_id=dm_channel_id,
    )


def event(**changes: object) -> DiscordTextEvent:
    original = DiscordTextEvent(
        message_id=1001,
        channel_id=CHANNEL,
        content="Hi Sofía 🦊",
        facts=DiscordInboundFacts(OWNER, BOT, "dm", None, False, None, True),
    )
    return replace(original, **changes)


def test_accepts_exact_owner_text_without_changing_content() -> None:
    source = event()
    result = screen_text_dm(config(), source)
    assert result.accepted and result.event is source and result.denial is None


def test_bound_dm_channel_is_enforced() -> None:
    assert screen_text_dm(
        config(dm_channel_id=CHANNEL),
        event(),
    ).accepted
    denied = screen_text_dm(
        config(dm_channel_id=CHANNEL),
        event(channel_id=3003),
    )
    assert denied.denial is InboundDenial.WRONG_CHANNEL


@pytest.mark.parametrize(
    ("changes", "denial"),
    [
        ({"message_id": 0}, InboundDenial.MALFORMED_EVENT),
        ({"message_id": True}, InboundDenial.MALFORMED_EVENT),
        ({"message_id": "1001"}, InboundDenial.MALFORMED_EVENT),
        ({"channel_id": None}, InboundDenial.MALFORMED_EVENT),
        ({"attachment_count": 1}, InboundDenial.UNSUPPORTED_CONTENT),
        ({"content": ""}, InboundDenial.EMPTY_CONTENT),
        ({"content": "  \n  "}, InboundDenial.EMPTY_CONTENT),
        ({"content": "x\x00y"}, InboundDenial.UNSUPPORTED_CONTENT),
        ({"content": "x" * 4001}, InboundDenial.CONTENT_TOO_LONG),
        ({"content": "\ud800"}, InboundDenial.MALFORMED_EVENT),
    ],
)
def test_malformed_or_unsupported(changes: dict, denial: InboundDenial) -> None:
    result = screen_text_dm(config(), event(**changes))
    assert not result.accepted
    assert result.denial is denial


def test_access_policy_runs_before_content_screen() -> None:
    facts = replace(event().facts, author_user_id=77)
    result = screen_text_dm(config(), event(content="", facts=facts))
    assert result.denial is Denial.NOT_OWNER
