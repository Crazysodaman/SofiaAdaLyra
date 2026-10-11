"""Deferred desktop/Discord project-header privacy regression.

Application entrypoint is exercised against real canonical SQLite stores,
without starting models, running tests, using external services or copying
a conversation into another transport.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from sofia.application.bootstrap import SofiaApplication
from sofia.conversation.lifelong import LifelongThreadStore
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def _principal(audience):
    return PrincipalContext(
        principal_id="owner:fixture", audience_id=audience,
        audience_kind=AudienceKind.PRIVATE, display_name="Fixture Owner",
    )


def test_application_never_exposes_foreign_project_names_for_same_owner(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    original = ConversationStore(state)
    social = SocialSessionStore(state)
    threads = LifelongThreadStore(state)
    local = _principal("local:text")
    discord = _principal("discord:dm:owner")
    fixture_app = SimpleNamespace(
        _conversation_service=SimpleNamespace(database_path=state),
    )

    try:
        for name, principal, identifier in (
            ("Private desktop notes", local, "local-original"),
            ("Discord source notes", discord, "discord-original"),
        ):
            session = original.create_session()
            social.bind(session_id=session.id, principal=principal)
            original.save(ConversationMessage(
                id=identifier, session_id=session.id,
                role=ConversationRole.USER, content=name,
                created_at=datetime.now(timezone.utc),
            ))
            thread = threads.get_or_create(
                owner=principal, kind="project", name=name,
            )
            threads.link_message(
                thread_id=thread.thread_id,
                source_message_id=identifier, principal=principal,
            )

        hidden = threads.get_or_create(
            owner=local, kind="project", name="Never linked to originals",
        )
        assert hidden is not None

        local_visible = SofiaApplication.lifelong_threads_for(
            fixture_app, local, limit=2,
        )
        assert [thread.name for thread in local_visible] == [
            "Private desktop notes"
        ]
        discord_visible = SofiaApplication.lifelong_threads_for(
            fixture_app, discord, limit=2,
        )
        assert [thread.name for thread in discord_visible] == [
            "Discord source notes"
        ]
        assert not set(thread.name for thread in local_visible) & set(
            thread.name for thread in discord_visible
        )
    finally:
        original.close()
