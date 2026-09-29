from pathlib import Path
import subprocess
import sys

from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.ui import tray_launcher


def _configuration(tmp_path: Path) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
        filesystem_root=tmp_path,
    )


def test_non_windows_tray_launcher_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert tray_launcher.ensure_tray_agent(_configuration(tmp_path)) is False


def test_windows_tray_launcher_skips_existing_singleton(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        tray_launcher,
        "tray_agent_is_running",
        lambda configuration: True,
    )
    called = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: called.append((args, kwargs)),
    )

    assert tray_launcher.ensure_tray_agent(_configuration(tmp_path)) is False
    assert called == []


def test_windows_tray_launcher_starts_module_detached(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        tray_launcher,
        "tray_agent_is_running",
        lambda configuration: False,
    )
    monkeypatch.setattr(tray_launcher.time, "sleep", lambda seconds: None)

    class Process:
        def poll(self):
            return None

    calls = []

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return Process()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    assert tray_launcher.ensure_tray_agent(_configuration(tmp_path)) is True
    args, kwargs = calls[0]
    assert args[1:] == ("-m", "sofia.ui.tray_agent")
    assert kwargs["close_fds"] is True
