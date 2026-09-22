"""Offline D1 ingress tests. NOT live gateway, durability, or delivery proof."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from sofia.discord.access import Denial, DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.inbound import (
    DiscordTextEvent,
    InboundDenial,
    InMemoryReplayLedger,
    ReplayResult,
    screen_text_dm,
)

OWNER = 123456789012345678
BOT = 987654321098765432

def config(enabled: bool = True) -> SingleUserDiscordConfig:
    return SingleUserDiscordConfig(OWNER, BOT, enabled)

def event(**changes: object) -> DiscordTextEvent:
    original = DiscordTextEvent(
        message_id=1001,
        channel_id=2002,
        content="Hi Sofía 🦊",
        facts=DiscordInboundFacts(OWNER, BOT, "dm", None, False, None, True),
    )
    return replace(original, **changes)

def test_accepts_exact_owner_text_without_changing_content():
    source = event()
    result = screen_text_dm(config(), source)
    assert result.accepted and result.event is source and result.denial is None

@pytest.mark.parametrize("changes,denial", [
    ({"message_id": 0}, InboundDenial.MALFORMED_EVENT),
    ({"message_id": True}, InboundDenial.MALFORMED_EVENT),
    ({"message_id": "1001"}, InboundDenial.MALFORMED_EVENT),
    ({"channel_id": None}, InboundDenial.MALFORMED_EVENT),
    ({"channel_id": 1 << 64}, InboundDenial.MALFORMED_EVENT),
    ({"content": 42}, InboundDenial.MALFORMED_EVENT),
    ({"attachment_count": True}, InboundDenial.MALFORMED_EVENT),
    ({"attachment_count": -1}, InboundDenial.MALFORMED_EVENT),
    ({"attachment_count": 1}, InboundDenial.UNSUPPORTED_CONTENT),
    ({"content": ""}, InboundDenial.EMPTY_CONTENT),
    ({"content": "  \n  "}, InboundDenial.EMPTY_CONTENT),
    ({"content": "x\x00y"}, InboundDenial.UNSUPPORTED_CONTENT),
    ({"content": "x" * 4001}, InboundDenial.CONTENT_TOO_LONG),
    ({"content": "\ud800"}, InboundDenial.MALFORMED_EVENT),
])
def test_malformed_or_unsupported(changes, denial):
    result = screen_text_dm(config(), event(**changes))
    assert not result.accepted and result.event is None and result.denial is denial

@pytest.mark.parametrize("facts,denial", [
    (replace(event().facts, author_user_id=77), Denial.NOT_OWNER),
    (replace(event().facts, guild_id=88), Denial.NOT_DIRECT_MESSAGE),
    (replace(event().facts, channel_kind="group_dm"), Denial.NOT_DIRECT_MESSAGE),
    (replace(event().facts, author_is_bot=True), Denial.AUTOMATED_SENDER),
    (replace(event().facts, authenticated_source=False), Denial.UNVERIFIED_SOURCE),
])
def test_existing_access_policy_applies_first(facts, denial):
    result = screen_text_dm(config(), event(facts=facts))
    assert not result.accepted and result.denial is denial

def test_disabled_blocks_valid_message():
    assert screen_text_dm(config(False), event()).denial is Denial.DISABLED

@pytest.mark.parametrize("limit", [0, 4001, True, 1.5, "2000"])
def test_invalid_limit_is_rejected(limit):
    with pytest.raises(ValueError):
        screen_text_dm(config(), event(), max_chars=limit)

def test_configured_content_limit():
    assert screen_text_dm(config(), event(content="abc"), max_chars=2).denial is InboundDenial.CONTENT_TOO_LONG

def test_replay_ledger_detects_duplicate_and_mutated_content():
    ledger = InMemoryReplayLedger()
    first = screen_text_dm(config(), event())
    assert ledger.claim(first) is ReplayResult.CLAIMED
    assert ledger.claim(first) is ReplayResult.DUPLICATE
    assert ledger.claim(screen_text_dm(config(), event(content="different"))) is ReplayResult.CONFLICT
    assert ledger.claim(screen_text_dm(config(), event(message_id=1002))) is ReplayResult.CLAIMED

def test_full_ledger_still_recognizes_duplicates():
    ledger = InMemoryReplayLedger(capacity=1)
    first = screen_text_dm(config(), event())
    assert ledger.claim(first) is ReplayResult.CLAIMED
    assert ledger.claim(first) is ReplayResult.DUPLICATE
    assert ledger.claim(screen_text_dm(config(), event(message_id=1002))) is ReplayResult.FULL

def test_denied_events_cannot_be_claimed():
    with pytest.raises(ValueError):
        InMemoryReplayLedger().claim(screen_text_dm(config(False), event()))

@pytest.mark.parametrize("capacity", [0, -1, True, "100"])
def test_invalid_capacity(capacity):
    with pytest.raises(ValueError):
        InMemoryReplayLedger(capacity=capacity)

def test_claim_is_thread_safe_for_identical_event():
    ledger = InMemoryReplayLedger()
    screened = screen_text_dm(config(), event())
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(ledger.claim, [screened] * 40))
    assert results.count(ReplayResult.CLAIMED) == 1
    assert results.count(ReplayResult.DUPLICATE) == 39

def test_ledger_is_process_local_not_durable():
    screened = screen_text_dm(config(), event())
    assert InMemoryReplayLedger().claim(screened) is ReplayResult.CLAIMED
    assert InMemoryReplayLedger().claim(screened) is ReplayResult.CLAIMED

def test_requires_typed_event_and_screen():
    with pytest.raises(TypeError):
        screen_text_dm(config(), {"message_id": 1001})
    with pytest.raises(ValueError):
        InMemoryReplayLedger().claim({"accepted": True})
