"""Deferred full-text source retrieval and principal/audience security tests.

FTS5 is explicitly rebuilt only inside a synthetic, isolated fixture.
No real state is indexed or tests run during the coding workstream.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.conversation.fulltext_search import (
    ConversationFullTextSearch, OfflineIndexAuthorization,
)
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.social.principals import local_sparks_principal, discord_sparks_principal
from sofia.social.store import SocialSessionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def test_fulltext_original_search_checks_exact_authenticated_audience(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    source = ConversationStore(path)
    social = SocialSessionStore(path)
    local = local_sparks_principal()
    discord = discord_sparks_principal(123456789012345678)
    first = source.create_session()
    second = source.create_session()
    try:
        social.bind(session_id=first.id, principal=local)
        social.bind(session_id=second.id, principal=discord)
        for session, phrase in (
            (first, "violet local only source"),
            (second, "violet Discord only source"),
        ):
            source.save(ConversationMessage(
                id=str(uuid4()), session_id=session.id,
                role=ConversationRole.USER, content=phrase,
                created_at=datetime.now(timezone.utc),
            ))

        fts = ConversationFullTextSearch(path)
        authorization = OfflineIndexAuthorization(
            canonical_state_path=path,
            writer_host_id="isolated-fixture",
            writer_fence_ref="fixture-fence",
            operator_approval_ref="synthetic-approval",
        )
        assert fts.rebuild_offline(
            authorization=authorization,
            independently_verify_fenced_approval=lambda request:
                request is authorization,
        ).ready
        results = fts.keyword_search(
            session_id=first.id, terms=("violet",),
            principal=local,
        )
        assert [row.content for row in results] == ["violet local only source"]
        with pytest.raises(PermissionError, match="audience mismatch"):
            fts.keyword_search(
                session_id=first.id, terms=("violet",),
                principal=discord,
            )
        with pytest.raises(PermissionError, match="audience mismatch"):
            fts.keyword_search(
                session_id=second.id, terms=("violet",),
                principal=local,
            )
        assert [row.content for row in fts.keyword_search(
            session_id=second.id, terms=("violet",),
            principal=discord,
        )] == ["violet Discord only source"]
        with pytest.raises(TypeError, match="PrincipalContext"):
            fts.keyword_search(
                session_id=first.id, terms=("violet",), principal=None,
            )
        with pytest.raises(PermissionError, match="audience mismatch"):
            fts.keyword_search(
                session_id="unknown-session", terms=("violet",),
                principal=local,
            )
    finally:
        source.close()
