"""CA-4106/4110/5302/5306/5505 canonical Main ordering regressions.

These tests are intentionally written but are not executed in the V18 coding
campaign. They exercise the real canonical SQLite stores without a model.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from sofia.cognition.model import CognitiveResponse
from sofia.conversation.lifelong import (
    CanonicalTurnConflict, CanonicalTurnUncertain, LifelongThreadStore,
)
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_social]


def infrastructure(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    messages = ConversationStore(path)
    social = SocialSessionStore(path)
    turns = LifelongThreadStore(path)
    principal = PrincipalContext(
        principal_id="sparks", audience_id="local:text",
        audience_kind=AudienceKind.PRIVATE, display_name="Sparks",
    )
    session = messages.create_session()
    social.bind(session_id=session.id, principal=principal)
    return messages, social, turns, principal, session


def persist_settled_turn(
    messages, turns, principal, session, *, event_id, content, response, now,
):
    admission = turns.admit_turn(
        event_id=event_id, principal=principal, session_id=session.id,
        channel="desktop", content=content, runtime_id="runtime:test",
        now=now,
    )
    user = ConversationMessage(
        admission.user_message_id, session.id, ConversationRole.USER,
        content, now,
    )
    assistant = ConversationMessage(
        admission.assistant_message_id, session.id,
        ConversationRole.ASSISTANT, response, now + timedelta(microseconds=1),
    )
    messages.save(user)
    messages.save(assistant)
    thread = turns.get_or_create(owner=principal)
    turns.link_message(
        thread_id=thread.thread_id, source_message_id=user.id,
        principal=principal,
    )
    turns.link_message(
        thread_id=thread.thread_id, source_message_id=assistant.id,
        principal=principal,
    )
    result = CognitiveResponse(response, evidence_refs=(user.id,))
    turns.settle_turn(
        admission=admission, principal=principal, response=result,
        now=now + timedelta(microseconds=2),
    )
    return admission, result


def test_server_assigns_unique_order_to_concurrent_authenticated_turns(tmp_path):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)

    def admit(index):
        return turns.admit_turn(
            event_id=f"desktop:parallel:{index}", principal=principal,
            session_id=session.id, channel="desktop",
            content=f"message {index}", runtime_id="runtime:test", now=now,
        ).canonical_sequence

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            sequences = tuple(pool.map(admit, range(8)))
        assert sorted(sequences) == list(range(1, 9))
    finally:
        messages.close()


def test_completed_retry_returns_same_response_and_conflict_never_reexecutes(tmp_path):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        admission, response = persist_settled_turn(
            messages, turns, principal, session,
            event_id="desktop:retry:one", content="exact source",
            response="settled response", now=now,
        )
        replay = turns.admit_turn(
            event_id=admission.event_id, principal=principal,
            session_id=session.id, channel="desktop", content="exact source",
            runtime_id="runtime:test", now=now + timedelta(seconds=1),
        )
        assert replay.status == "completed"
        assert replay.response == response
        assert replay.user_message_id == admission.user_message_id
        with pytest.raises(CanonicalTurnConflict):
            turns.admit_turn(
                event_id=admission.event_id, principal=principal,
                session_id=session.id, channel="desktop", content="changed source",
                runtime_id="runtime:test", now=now + timedelta(seconds=2),
            )
    finally:
        messages.close()


def test_restart_marks_unsettled_turn_uncertain_and_blocks_replay(tmp_path):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        turns.admit_turn(
            event_id="discord:interrupted:one", principal=principal,
            session_id=session.id, channel="discord", content="may have run",
            runtime_id="runtime:before", now=now,
        )
        assert turns.recover_interrupted_turns(
            runtime_id="runtime:after", now=now + timedelta(seconds=1),
        ) == 1
        with pytest.raises(CanonicalTurnUncertain):
            turns.admit_turn(
                event_id="discord:interrupted:one", principal=principal,
                session_id=session.id, channel="discord", content="may have run",
                runtime_id="runtime:after", now=now + timedelta(seconds=2),
            )
    finally:
        messages.close()


def test_same_event_cannot_cross_audience_or_inherit_source_authority(tmp_path):
    messages, social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    other = PrincipalContext(
        principal_id=principal.principal_id,
        audience_id="discord:dm:42", audience_kind=AudienceKind.PRIVATE,
        display_name="Sparks",
    )
    other_session = messages.create_session()
    social.bind(session_id=other_session.id, principal=other)
    try:
        turns.admit_turn(
            event_id="shared-client-id", principal=principal,
            session_id=session.id, channel="desktop", content="same text",
            runtime_id="runtime:test", now=now,
        )
        with pytest.raises(CanonicalTurnConflict):
            turns.admit_turn(
                event_id="shared-client-id", principal=other,
                session_id=other_session.id, channel="discord",
                content="same text", runtime_id="runtime:test", now=now,
            )
    finally:
        messages.close()


def test_main_projection_uses_server_order_not_link_or_client_time(tmp_path):
    messages, _social, turns, principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    try:
        first, _ = persist_settled_turn(
            messages, turns, principal, session,
            event_id="desktop:ordered:first", content="first",
            response="first response", now=now + timedelta(hours=1),
        )
        second, _ = persist_settled_turn(
            messages, turns, principal, session,
            event_id="desktop:ordered:second", content="second",
            response="second response", now=now,
        )
        thread = turns.get_or_create(owner=principal)
        page = turns.visible_message_page(
            thread_id=thread.thread_id, principal=principal, limit=10,
        )
        assert [item.canonical_sequence for item in page] == [
            first.canonical_sequence, first.canonical_sequence,
            second.canonical_sequence, second.canonical_sequence,
        ]
        assert [item.turn_position for item in page] == [0, 1, 0, 1]
    finally:
        messages.close()


def test_original_source_message_identity_cannot_be_overwritten(tmp_path):
    messages, _social, _turns, _principal, session = infrastructure(tmp_path)
    now = datetime.now(timezone.utc)
    original = ConversationMessage(
        "immutable-message", session.id, ConversationRole.USER,
        "original bytes", now,
    )
    try:
        messages.save(original)
        messages.save(original)
        with pytest.raises(ValueError, match="different immutable bytes"):
            messages.save(ConversationMessage(
                original.id, session.id, ConversationRole.USER,
                "rewritten bytes", now,
            ))
        assert messages.list_messages(session.id) == (original,)
    finally:
        messages.close()
