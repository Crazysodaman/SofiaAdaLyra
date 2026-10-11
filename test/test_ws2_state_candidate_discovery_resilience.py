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
