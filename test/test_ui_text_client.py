from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from sofia.cognition.model import CognitiveResponse
from sofia.conversation.model import (
    ConversationMessage,
    ConversationRole,
)
from sofia.ui.drafts import UIDraftStore
from sofia.ui.text import UITextClient


class FakeConversation:
    def __init__(self) -> None:
        self.session_id = "session-1"
        self._messages: list[ConversationMessage] = []
        self.fail = False
        self.responded_with: list[str] = []

    def messages(self) -> tuple[ConversationMessage, ...]:
        return tuple(self._messages)

    def respond(self, content: str) -> CognitiveResponse:
        self.responded_with.append(content)
        if self.fail:
            raise RuntimeError("generation failed")

        now = datetime.now(timezone.utc)
        self._messages.extend(
            (
                ConversationMessage(
                    id=str(uuid4()),
                    session_id=self.session_id,
                    role=ConversationRole.USER,
                    content=content,
                    created_at=now,
                ),
                ConversationMessage(
                    id=str(uuid4()),
                    session_id=self.session_id,
                    role=ConversationRole.ASSISTANT,
                    content="response",
                    created_at=now,
                ),
            )
        )
        return CognitiveResponse(content="response")


def client(
    tmp_path: Path,
    conversation: FakeConversation | None = None,
):
    conversation = conversation or FakeConversation()
    drafts = UIDraftStore(tmp_path / "sofia.db")
    return UITextClient(
        conversation=conversation,
        drafts=drafts,
        client_id="desktop",
    ), conversation, drafts


def test_history_projects_persisted_messages_without_rewriting(
    tmp_path: Path,
):
    ui, conversation, drafts = client(tmp_path)
    now = datetime.now(timezone.utc)
    original = ConversationMessage(
        id="message-1",
        session_id="session-1",
        role=ConversationRole.USER,
        content="exact original",
        created_at=now,
    )
    conversation._messages.append(original)

    history = ui.history()

    assert len(history) == 1
    assert history[0].message_id == original.id
    assert history[0].session_id == original.session_id
    assert history[0].actor == "user"
    assert history[0].content == original.content
    assert history[0].created_at == original.created_at
    drafts.close()


def test_unsent_draft_never_enters_conversation_history(
    tmp_path: Path,
):
    ui, conversation, drafts = client(tmp_path)

    ui.save_draft("not sent yet")

    assert conversation.messages() == ()
    assert ui.history() == ()
    assert ui.draft().content == "not sent yet"
    drafts.close()


def test_send_saved_draft_uses_canonical_conversation_and_clears_after_success(
    tmp_path: Path,
):
    ui, conversation, drafts = client(tmp_path)
    ui.save_draft("send this")

    response = ui.send()

    assert response.content == "response"
    assert conversation.responded_with == ["send this"]
    assert ui.draft() is None
    assert [item.actor for item in ui.history()] == [
        "user",
        "sofia",
    ]
    drafts.close()


def test_failed_send_preserves_draft_for_recovery(
    tmp_path: Path,
):
    conversation = FakeConversation()
    conversation.fail = True
    ui, _, drafts = client(tmp_path, conversation)
    ui.save_draft("do not lose me")

    with pytest.raises(RuntimeError, match="generation failed"):
        ui.send()

    assert ui.draft() is not None
    assert ui.draft().content == "do not lose me"
    drafts.close()


def test_explicit_send_clears_stale_saved_draft_only_after_success(
    tmp_path: Path,
):
    ui, conversation, drafts = client(tmp_path)
    ui.save_draft("old draft")

    ui.send("new explicit message")

    assert conversation.responded_with == [
        "new explicit message"
    ]
    assert ui.draft() is None
    drafts.close()


def test_text_client_requires_active_session(
    tmp_path: Path,
):
    conversation = FakeConversation()
    conversation.session_id = None
    drafts = UIDraftStore(tmp_path / "sofia.db")
    ui = UITextClient(
        conversation=conversation,
        drafts=drafts,
        client_id="desktop",
    )

    with pytest.raises(RuntimeError):
        _ = ui.session_id

    with pytest.raises(RuntimeError):
        ui.save_draft("cannot bind without session")

    drafts.close()


def test_blank_send_is_rejected_before_conversation_call(
    tmp_path: Path,
):
    ui, conversation, drafts = client(tmp_path)

    with pytest.raises(ValueError):
        ui.send("   ")

    assert conversation.responded_with == []
    drafts.close()
