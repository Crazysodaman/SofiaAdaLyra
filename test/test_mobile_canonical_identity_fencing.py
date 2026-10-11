"""Regression contracts for canonical SQLite identity in mobile credential authority.

Deferred execution: tests and CI are intentionally not run during V18 coding.
"""
import os
import sqlite3

import pytest

from sofia.mobile.pairing import MobileDeviceCredentialStore
from sofia.state.canonical_sqlite import CanonicalStateUnavailable


def test_existing_pairing_owner_fails_closed_after_database_replacement(tmp_path):
    canonical = tmp_path / "sofia.db"
    canonical.touch()
    store = MobileDeviceCredentialStore(canonical)
    old_token = store.enroll("owner-phone")

    replacement = tmp_path / "replacement.db"
    with sqlite3.connect(replacement) as db:
        db.execute("PRAGMA user_version=1")
    os.replace(replacement, canonical)

    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.authenticate(old_token)
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.enroll("another-phone")
    with pytest.raises(CanonicalStateUnavailable, match="replaced"):
        store.list_devices()


def test_existing_pairing_owner_fails_closed_after_state_disappears(tmp_path):
    canonical = tmp_path / "sofia.db"
    canonical.touch()
    store = MobileDeviceCredentialStore(canonical)
    token = store.enroll("owner-phone")

    canonical.unlink()
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        store.authenticate(token)
    with pytest.raises(CanonicalStateUnavailable, match="unavailable"):
        store.active_generation("owner-phone")
