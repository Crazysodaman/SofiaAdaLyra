"""Deferred Phase 06 source-audience guard for the SQL recall fallback.

The optional FTS index may be offline, corrupt or unavailable. The ordinary
fallback must never downgrade to an unrestricted session-ID source read.
Only synthetic SQLite fixtures are used; tests are authored but not run.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore


def _scoped_sources(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    original = ConversationStore(path)
    social = SocialSessionStore(path)
    session = original.create_session()
    owner = PrincipalContext(
        principal_id="person:test-owner", audience_id="private:original",
        audience_kind=AudienceKind.PRIVATE,
    )
    other = PrincipalContext(
        principal_id="person:other-owner", audience_id="private:other",
        audience_kind=AudienceKind.PRIVATE,
    )
    social.bind(session_id=session.id, principal=owner)
    original.save(ConversationMessage(
        id="original-source-one", session_id=session.id,
        role=ConversationRole.USER,
        content="The original synthetic HO model train roster lives here",
        created_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
    ))
    return path, original, session, owner, other


def _search(source, session_id, principal):
    return source.search_messages(
        session_id, terms=("train",),
        authorized_principal=principal, user_only=True, limit=6,
    )


def test_sql_fallback_returns_only_current_authenticated_audience(tmp_path):
    _path, source, session, owner, other = _scoped_sources(tmp_path)
    try:
        assert [msg.id for msg in _search(source, session.id, owner)] == [
            "original-source-one",
        ]
        assert _search(source, session.id, other) == ()
        with pytest.raises(PermissionError, match="authenticated"):
            _search(source, session.id, None)
    finally:
        source.close()


def test_sql_fallback_fails_closed_when_original_session_binding_changes(
    tmp_path,
):
    path, source, session, owner, other = _scoped_sources(tmp_path)
    try:
        # Simulate an independent privileged repair/rebinding between
        # initial conversation authentication and deferred source lookup.
        with sqlite3.connect(path) as db:
            db.execute(
                "UPDATE social_session_principal SET principal_id=?, "
                "audience_id=? WHERE session_id=?",
                (other.principal_id, other.audience_id, session.id),
            )
        assert _search(source, session.id, owner) == ()
        assert [msg.id for msg in _search(source, session.id, other)] == [
            "original-source-one",
        ]
    finally:
        source.close()


def test_sql_fallback_does_not_search_other_original_sessions(tmp_path):
    _path, source, session, owner, other = _scoped_sources(tmp_path)
    try:
        another = source.create_session()
        SocialSessionStore(source.database_path).bind(
            session_id=another.id, principal=other,
        )
        source.save(ConversationMessage(
            id="foreign-original", session_id=another.id,
            role=ConversationRole.USER, content="Another train roster",
            created_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
        ))
        assert [msg.id for msg in _search(source, session.id, owner)] == [
            "original-source-one",
        ]
        assert _search(source, another.id, owner) == ()
    finally:
        source.close()
