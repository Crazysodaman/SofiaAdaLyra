import pytest

from sofia.discord.process_lock import DiscordProcessLock
from sofia.ui.process_lock import TrayProcessLock


def test_discord_excludes_second_owner_and_releases_for_reacquisition(tmp_path):
    first = DiscordProcessLock(tmp_path / "sofia.db")
    second = DiscordProcessLock(tmp_path / "sofia.db")
    with first:
        with pytest.raises(RuntimeError, match="another live Sofía Discord process"):
            second.acquire()
        with pytest.raises(RuntimeError, match="already acquired"):
            first.acquire()
    with second:
        assert second.path.name.startswith("sofia-discord-")


def test_tray_and_discord_have_independent_lifetime_ownership(tmp_path):
    state = tmp_path / "sofia.db"
    with TrayProcessLock(state) as tray, DiscordProcessLock(state) as discord:
        assert tray.path != discord.path


def test_process_registry_blocks_windows_handle_reentry(tmp_path, monkeypatch):
    import os
    import sys
    from types import SimpleNamespace
    import sofia.run.process_lock as process_lock

    first = DiscordProcessLock(tmp_path / "sofia.db")
    second = DiscordProcessLock(tmp_path / "sofia.db")
    calls = []
    # Windows permits same-process byte-range reentry; simulate that OS behavior.
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace(
        LK_NBLCK=1, LK_UNLCK=2,
        locking=lambda descriptor, mode, count: calls.append((mode, count)),
    ))
    monkeypatch.setattr(process_lock, "os", SimpleNamespace(
        name="nt", path=os.path, fstat=os.fstat,
    ))
    with first:
        with pytest.raises(RuntimeError, match="another live Sofía Discord process"):
            second.acquire()
    assert calls == [(1, 1), (2, 1)]
    with second:
        pass
