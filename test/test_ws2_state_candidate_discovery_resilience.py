"""Deferred Phase 03 bounded and failure-isolated state-home discovery.

All paths and SQLite databases are synthetic. No tests or live recovery run.
"""
import sqlite3

from sofia.ops.state_mobility import discover_local_state_candidates


def _db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(
            "CREATE TABLE conversation_sessions(id TEXT PRIMARY KEY);"
            "CREATE TABLE conversation_messages(id TEXT PRIMARY KEY);"
            "CREATE TABLE social_session_principal(session_id TEXT PRIMARY KEY);"
        )


def test_oversized_protected_identity_is_untrusted_and_scan_continues(tmp_path):
    known = tmp_path / "configured"
    backup = tmp_path / "recovery"
    _db(known / "sofia.db")
    _db(backup / "sofia.db")
    (known / "protected").mkdir()
    (backup / "protected").mkdir()
    (known / "protected" / "identity.json").write_bytes(b"X" * (64 * 1024 + 1))
    (backup / "protected" / "identity.json").write_bytes(b'{"test":"identity"}')
    records = discover_local_state_candidates(
        configured_path=known / "sofia.db", extra_roots=(backup,),
    )
    match = {record.state_path: record for record in records}
    assert match[known / "sofia.db"].protected_identity_present is False
    assert match[backup / "sofia.db"].protected_identity_present is True
    assert match[backup / "sofia.db"].identity_matches_configured_home is None
    assert all(record.expected_schema_present for record in match.values())


def test_unreadable_one_candidate_does_not_exclude_other_known_candidates(
    tmp_path, monkeypatch,
):
    known = tmp_path / "configured"
    other = tmp_path / "recovery"
    _db(known / "sofia.db")
    _db(other / "sofia.db")
    from pathlib import Path
    original_open = Path.open

    def deny_one_database(self, *args, **kwargs):
        if self == known / "sofia.db":
            raise PermissionError("synthetically locked original")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_one_database)
    found = discover_local_state_candidates(
        configured_path=known / "sofia.db", extra_roots=(other,),
    )
    assert [record.state_path for record in found] == [other / "sofia.db"]
    assert found[0].sqlite_header_valid is True


def test_redirected_identity_path_cannot_claim_matching_lineage(tmp_path):
    known = tmp_path / "configured"
    other = tmp_path / "recovery"
    _db(known / "sofia.db")
    _db(other / "sofia.db")
    (known / "protected").mkdir()
    (other / "protected").mkdir()
    (known / "protected" / "identity.json").write_bytes(b"synthetic-only")
    outside = tmp_path / "elsewhere"
    outside.write_bytes(b"synthetic-only")
    alias = other / "protected" / "identity.json"
    try:
        alias.symlink_to(outside)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("symlinks unavailable on test host")
    found = discover_local_state_candidates(
        configured_path=known / "sofia.db", extra_roots=(other,),
    )
    matches = {record.state_path: record for record in found}
    assert matches[other / "sofia.db"].protected_identity_present is False
    assert matches[other / "sofia.db"].identity_matches_configured_home is None


def test_explicit_owner_roots_come_before_guessed_paths_under_small_cap(tmp_path):
    configured = tmp_path / "configured"
    approved = tmp_path / "explicit-approved-root"
    _db(configured / "sofia.db")
    _db(approved / "sofia.db")
    discovered = discover_local_state_candidates(
        configured_path=configured / "sofia.db",
        extra_roots=(approved,), max_roots=2,
    )
    assert [candidate.state_path for candidate in discovered] == [
        configured / "sofia.db",
        approved / "sofia.db",
    ]


def test_duplicate_owner_roots_do_not_use_up_distinct_scan_slots(tmp_path):
    configured = tmp_path / "configured"
    approved = tmp_path / "second-root"
    _db(configured / "sofia.db")
    _db(approved / "sofia.db")
    found = discover_local_state_candidates(
        configured_path=configured / "sofia.db",
        extra_roots=(configured, approved), max_roots=2,
    )
    assert [candidate.state_path for candidate in found] == [
        configured / "sofia.db", approved / "sofia.db",
    ]


def test_candidate_identity_reads_are_bounded_even_if_stat_is_stale(
    tmp_path, monkeypatch,
):
    """A stale 1-byte stat cannot turn discovery into an unbounded read."""
    from pathlib import Path
    from types import SimpleNamespace

    configured = tmp_path / "configured"
    approved = tmp_path / "recovery"
    _db(configured / "sofia.db")
    _db(approved / "sofia.db")
    for directory in (configured, approved):
        (directory / "protected").mkdir()
    (configured / "protected" / "identity.json").write_bytes(
        b"known-identity",
    )
    oversized = approved / "protected" / "identity.json"
    oversized.write_bytes(b"X" * (64 * 1024 + 4096))
    original_stat = Path.stat

    def stale_stat(self, *args, **kwargs):
        if self == oversized:
            return SimpleNamespace(st_size=1)
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stale_stat)
    found = discover_local_state_candidates(
        configured_path=configured / "sofia.db",
        extra_roots=(approved,),
        max_roots=2,
    )
    by_path = {candidate.state_path: candidate for candidate in found}
    assert by_path[configured / "sofia.db"].protected_identity_present is True
    assert by_path[approved / "sofia.db"].protected_identity_present is False
    assert (
        by_path[approved / "sofia.db"].identity_matches_configured_home
        is None
    )


def test_recovery_discovery_never_uses_unbounded_path_read_bytes(
    tmp_path, monkeypatch,
):
    """Both configured and recovery identities must use capped streaming."""
    from pathlib import Path

    configured = tmp_path / "configured"
    approved = tmp_path / "recovery"
    _db(configured / "sofia.db")
    _db(approved / "sofia.db")
    for directory in (configured, approved):
        (directory / "protected").mkdir()
        (directory / "protected" / "identity.json").write_bytes(
            b'{"test": "same-identity"}',
        )

    original_read_bytes = Path.read_bytes

    def deny_unbounded_identity_read(self):
        if self.name == "identity.json":
            raise AssertionError("identity discovery used unbounded read_bytes")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", deny_unbounded_identity_read)
    found = discover_local_state_candidates(
        configured_path=configured / "sofia.db",
        extra_roots=(approved,), max_roots=2,
    )
    by_path = {candidate.state_path: candidate for candidate in found}
    assert by_path[approved / "sofia.db"].identity_matches_configured_home is True
