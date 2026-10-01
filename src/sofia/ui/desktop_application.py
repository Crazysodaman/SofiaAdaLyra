"""Canonical desktop application composition.

The desktop always owns one local SofiaApplication backed by the configured
canonical state_path. Fleet may place cognition remotely, but desktop chat/state
authority does not move independently of the state plane.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sofia.config import SofiaConfiguration
from sofia.ui.control_center import (
    DesktopControlSettingsStore,
    RemoteChatMode,
)


def _ensure_state(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with sqlite3.connect(path):
            pass


def _enforce_single_database_mode(
    configuration: SofiaConfiguration,
) -> None:
    """Migrate legacy remote-chat UI settings back to canonical local state."""
    _ensure_state(configuration.state_path)
    store = DesktopControlSettingsStore(configuration.state_path)
    settings = store.load()
    if settings.remote_chat_mode is RemoteChatMode.LOCAL:
        return
    store.save(
        replace(
            settings,
            remote_chat_mode=RemoteChatMode.LOCAL,
            pinned_chat_endpoint=None,
        ),
        at=datetime.now(timezone.utc),
    )


def create_desktop_application(configuration: SofiaConfiguration):
    """Return the one canonical SofiaApplication for the desktop UI."""
    if not isinstance(configuration, SofiaConfiguration):
        raise TypeError("configuration must be a SofiaConfiguration")
    _enforce_single_database_mode(configuration)
    from sofia.application import SofiaApplication
    return SofiaApplication(configuration)
