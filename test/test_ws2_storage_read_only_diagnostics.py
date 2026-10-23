"""Deferred read-only Settings > Storage database diagnostics contracts.

Synthetic canonical SQLite fixtures only. No tests/CI or live settings run.
"""
import sqlite3

import pytest

from sofia.platform.state.canonical_sqlite import (
    CanonicalStateUnavailable, bootstrap_canonical_sqlite,
)
from sofia.ui import settings_service


def test_storage_diagnostics_opens_only_existing_pinned_read_only_sqlite(
    tmp_path, monkeypatch,
):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    original_connect = sqlite3.connect
    observed = []

    def inspect_connect(database, *args, **kwargs):
        observed.append((database, kwargs))
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(settings_service.sqlite3, "connect", inspect_connect)
    rendered = settings_service.database_diagnostics(state)
    assert observed
    assert all(
        str(database).endswith("?mode=ro") and kwargs.get("uri") is True
        for database, kwargs in observed
    )
    assert str(state) in rendered
    assert "Integrity:" in rendered
    assert state.is_file()


def test_missing_canonical_state_diagnostics_never_creates_empty_identity(tmp_path):
    state = tmp_path / "missing" / "sofia.db"
    with pytest.raises((CanonicalStateUnavailable, FileNotFoundError)):
        settings_service.database_diagnostics(state)
    assert not state.exists()
