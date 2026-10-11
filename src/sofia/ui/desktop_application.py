"""Canonical desktop application composition.

The desktop always owns one local SofiaApplication backed by the configured
canonical state_path. Fleet may place cognition remotely, but desktop chat/state
authority does not move independently of the state plane.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sofia.state.canonical_sqlite import require_existing_sqlite

from sofia.config import SofiaConfiguration
from sofia.ui.control_center import DesktopControlSettingsStore


def _ensure_state(path: Path) -> None:
    # Only explicit configuration bootstrap may create canonical state.
    # A detached desktop entrypoint is not a first-install database writer.
    require_existing_sqlite(path)


def _enforce_single_database_mode(
    configuration: SofiaConfiguration,
) -> None:
    """Migrate legacy remote-chat UI settings back to canonical local state."""
    _ensure_state(configuration.state_path)
    store = DesktopControlSettingsStore(configuration.state_path)
    store.enforce_canonical_local_chat(
        at=datetime.now(timezone.utc),
    )


def create_desktop_application(configuration: SofiaConfiguration):
    """Return the one canonical SofiaApplication for the desktop UI."""
    if not isinstance(configuration, SofiaConfiguration):
        raise TypeError("configuration must be a SofiaConfiguration")
    _enforce_single_database_mode(configuration)
    from sofia.application import SofiaApplication
    return SofiaApplication(configuration)
