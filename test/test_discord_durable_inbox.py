"""Durable Discord inbox and ingress tests."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from sofia.discord.access import Denial, DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.inbound import DiscordTextEvent, screen_text_dm
from sofia.discord.ingress import DiscordIngress, IngressDisposition
from sofia.discord.store import DiscordInboxStore, InboxAcceptResult

OWNER = 123456789012345678
BOT = 987654321098765432


def config(enabled: bool = True) -> SingleUserDiscordConfig:
    return SingleUserDiscordConfig(OWNER, BOT, enabled)


def event(**changes: object) -> DiscordTextEvent:
    baseline = DiscordTextEvent(
        message_id=1001,
        channel_id=2002,
        content="Hello from Discord",
        facts=DiscordInboundFacts(OWNER, BOT, "dm", None, False, None, True),
    )
    return replace(baseline, **changes)


def accepted(source: DiscordTextEvent | None = None):
    return screen_text_dm(config(), source or event())


def test_record_survives_store_recreation(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    first = DiscordInboxStore(path)
    assert first.accept(accepted()) is InboxAcceptResult.INSERTED

    second = DiscordInboxStore(path)
    record = second.get(bot_user_id=BOT, channel_id=2002, message_id=1001)
    assert record is not None
    assert record.author_user_id == OWNER
    assert record.content == "Hello from Discord"
    assert record.state == "received"


def test_duplicate_after_restart_is_not_reinserted(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    assert DiscordInboxStore(path).accept(accepted()) is InboxAcceptResult.INSERTED
    assert DiscordInboxStore(path).accept(accepted()) is InboxAcceptResult.DUPLICATE
    assert DiscordInboxStore(path).count() == 1


def test_same_platform_identity_with_changed_content_is_conflict(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    assert store.accept(accepted()) is InboxAcceptResult.INSERTED
    changed = accepted(event(content="mutated payload"))
    assert store.accept(changed) is InboxAcceptResult.CONFLICT
    assert store.count() == 1


def test_same_message_id_in_different_dm_channel_is_distinct(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    assert store.accept(accepted()) is InboxAcceptResult.INSERTED
    assert store.accept(accepted(event(channel_id=3003))) is InboxAcceptResult.INSERTED
    assert store.count() == 2


def test_concurrent_duplicate_claims_insert_once(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    screened = accepted()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.accept(screened), range(24)))

    assert results.count(InboxAcceptResult.INSERTED) == 1
    assert results.count(InboxAcceptResult.DUPLICATE) == 23
    assert store.count() == 1


def test_ingress_denial_never_hits_durable_inbox(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    ingress = DiscordIngress(config=config(), inbox=store)
    denied_event = event(
        facts=replace(event().facts, author_user_id=77),
    )
    outcome = ingress.receive(denied_event)

    assert outcome.disposition is IngressDisposition.DENIED
    assert outcome.screen.denial is Denial.NOT_OWNER
    assert store.count() == 0


def test_ingress_reports_duplicate_and_conflict(tmp_path) -> None:
    store = DiscordInboxStore(tmp_path / "state.sqlite3")
    ingress = DiscordIngress(config=config(), inbox=store)

    assert ingress.receive(event()).disposition is IngressDisposition.ACCEPTED
    assert ingress.receive(event()).disposition is IngressDisposition.DUPLICATE
    assert (
        ingress.receive(event(content="changed")).disposition
        is IngressDisposition.CONFLICT
    )
