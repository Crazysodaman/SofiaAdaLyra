"""Consent/boundary follow-up continuity without replaying prior contact."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import InteractiveConversationService

AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"
NOW = datetime(2026, 9, 23, 22, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("followup", ["why", "what if it was wanted"])
def test_short_followup_stays_bound_to_prior_interaction(monkeypatch, tmp_path, followup):
    current = CognitiveMessage(role=CognitiveRole.USER, content=followup)
    original = CognitiveRequest(messages=(current,))
    monkeypatch.setattr(
        EmotionalConversationService, "_build_request", lambda self: original,
    )

    previous_user = SimpleNamespace(
        id="gesture-1", session_id="session-1", role=ConversationRole.USER,
        content="*touches your groin*", created_at=NOW,
    )
    previous_assistant = SimpleNamespace(
        id="assistant-1", session_id="session-1", role=ConversationRole.ASSISTANT,
        content="Not right now.", created_at=NOW,
    )
    current_user = SimpleNamespace(
        id="followup-1", session_id="session-1", role=ConversationRole.USER,
        content=followup, created_at=NOW,
    )
    monkeypatch.setattr(
        InteractiveConversationService, "messages",
        lambda self: (previous_user, previous_assistant, current_user),
    )

    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(
        personality=object(),
        embodiment=AvatarStore(AVATAR).load(),
        configuration=SimpleNamespace(state_path=tmp_path / "sofia.db"),
    )

    result = service._build_request()
    prompt = result.messages[0].content

    assert result.messages[-1] is current
    assert "TRUSTED INTERACTION FOLLOW-UP" in prompt
    assert '"prior_region_id": "groin"' in prompt
    assert '"prior_gesture": "touch"' in prompt
    assert "Mutual willingness matters" in prompt
    assert "not enough by itself" in prompt
    assert "inappropriate or disrespectful" in prompt
    assert "no new action executed" in prompt
    assert not (tmp_path / "sofia.db").exists()


def test_new_interaction_prompt_rejects_region_based_moralizing(monkeypatch):
    content = "*touches your groin*"
    original = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.USER, content=content),
    ))
    monkeypatch.setattr(
        EmotionalConversationService, "_build_request", lambda self: original,
    )
    user = SimpleNamespace(
        id="gesture-1", session_id="session-1", role=ConversationRole.USER,
        content=content, created_at=NOW,
    )
    monkeypatch.setattr(
        InteractiveConversationService, "messages", lambda self: (user,),
    )

    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(
        personality=object(), embodiment=AvatarStore(AVATAR).load(),
    )

    prompt = service._build_request().messages[0].content
    assert "User desire is not Sofía's consent" in prompt
    assert "not want it" in prompt
    assert "change her mind" in prompt
    assert "generic safety lecture" in prompt
