from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.ui.process_lock import (
    DesktopAttentionMailbox,
    DesktopProcessAlreadyRunning,
    DesktopProcessLock,
    TrayProcessAlreadyRunning,
    TrayProcessLock,
    core_link_profile_anchor,
)
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration


def test_only_one_tray_agent_can_own_one_state_database(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()

    first = TrayProcessLock(state)
    second = TrayProcessLock(state)

    first.acquire()
    try:
        with pytest.raises(TrayProcessAlreadyRunning, match="another live Sofía tray agent"):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()


def test_same_lock_object_cannot_be_acquired_twice(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()
    lock = TrayProcessLock(state)
    lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="already acquired"):
            lock.acquire()
    finally:
        lock.release()


def test_desktop_and_tray_are_independent_singletons(tmp_path):
    anchor = tmp_path / "client-profile"
    with DesktopProcessLock(anchor), TrayProcessLock(anchor):
        with pytest.raises(DesktopProcessAlreadyRunning):
            DesktopProcessLock(anchor).acquire()
        with pytest.raises(TrayProcessAlreadyRunning):
            TrayProcessLock(anchor).acquire()


def test_core_link_profile_lock_does_not_need_canonical_database(tmp_path):
    store = (tmp_path / "local" / "core-links.json").resolve()
    anchor = core_link_profile_anchor(store, "binding:sofia")
    assert not store.exists() and anchor.suffix != ".db"
    with DesktopProcessLock(anchor), TrayProcessLock(anchor):
        assert not store.exists()


def test_attention_mailbox_is_bounded_single_use_and_rejects_stale(tmp_path):
    lock = DesktopProcessLock(tmp_path / "profile")
    mailbox = DesktopAttentionMailbox(lock)
    now = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)
    mailbox.request(at=now)
    assert mailbox.consume(now=now + timedelta(seconds=5)) is True
    assert mailbox.consume(now=now + timedelta(seconds=5)) is False
    mailbox.request(at=now)
    assert mailbox.consume(now=now + timedelta(minutes=2)) is False


def test_reopening_desktop_requests_attention_without_second_window(tmp_path):
    pytest.importorskip("tkinter")
    from sofia.modules.ui.desktop import run_desktop

    state = tmp_path / "sofia.db"
    state.touch()
    config = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=state,
        provider=ProviderConfiguration(provider="ollama", model="unused"),
        filesystem_root=tmp_path,
    )
    owner = DesktopProcessLock(state)
    owner.acquire()
    try:
        assert run_desktop(config) == 0
        mailbox = DesktopAttentionMailbox(DesktopProcessLock(state))
        assert mailbox.consume() is True
    finally:
        owner.release()
