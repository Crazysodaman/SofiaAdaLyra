"""Offline conversation projection tests without contacting Ollama."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sofia.application.conversation_service import ConversationService
from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.personality.emotion import EmotionalJournal
from sofia.social.principals import SPARKS_PRINCIPAL_ID


def _service(monkeypatch, tmp_path, *, personality=True):
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content='Good girl. *Head pats.*',
    ),))
    message = SimpleNamespace(
        id='user-message-1', content='Good girl. *Head pats.*',
        role=ConversationRole.USER,
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(ConversationService, '_build_request', lambda self: request)
    monkeypatch.setattr(EmotionalConversationService, 'messages', lambda self: (message,))
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object() if personality else None)
    service._emotional_journal = EmotionalJournal(tmp_path / 'state.db')
    return service, request


def test_user_cue_reaches_llm_as_bounded_context_after_canonical_system(monkeypatch, tmp_path):
    service, original = _service(monkeypatch, tmp_path)
    result = service._build_request()
    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert 'TRUSTED RUNTIME CLOCK' not in result.messages[0].content
    assert 'MODELED EMOTIONAL CONTEXT' in result.messages[0].content
    assert result.messages[-1] is original.messages[-1]
    assert len(service.emotional_journal.recent(now=datetime.now(timezone.utc))) == 1
    second = service._build_request()
    assert len(service.emotional_journal.recent(now=datetime.now(timezone.utc))) == 1
    assert second.messages[-1] is original.messages[-1]


def test_no_personality_means_no_implicit_persona_or_emotional_projection(monkeypatch, tmp_path):
    service, original = _service(monkeypatch, tmp_path, personality=False)
    assert service._build_request() is original
    assert service.emotional_journal.recent(now=datetime.now(timezone.utc)) == ()



def test_explicit_return_duration_reaches_reunion_appraisal(monkeypatch, tmp_path):
    departure = datetime.now(timezone.utc) - timedelta(days=7)
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content="I'll be back in a week.",
    ),))
    user = SimpleNamespace(
        id="departure-plan", content="I'll be back in a week.",
        role=ConversationRole.USER, created_at=departure,
    )
    monkeypatch.setattr(ConversationService, "_build_request", lambda self: request)
    monkeypatch.setattr(
        EmotionalConversationService, "messages", lambda self: (user,),
    )
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object())
    service._emotional_journal = EmotionalJournal(tmp_path / "state.db")

    service._build_request()
    reunion_at = departure + timedelta(days=7)
    event_id = service.emotional_journal.observe_contact(
        subject=service._relationship_subject(),
        message_id="return",
        occurred_at=reunion_at,
    )

    assert event_id == "reunion:return"
    event = service.emotional_journal.recent(now=reunion_at)[0]
    assert {"relief", "warmth", "fondness"} <= set(event.current_emotions)
    assert "anger" not in event.current_emotions


def test_unbound_primary_emotion_scope_matches_authenticated_sparks_principal(tmp_path):
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(
        personality=object(),
        core_state=SimpleNamespace(
            relationships=(SimpleNamespace(subject="Sparks"),),
        ),
    )
    service._session = None
    service._social_store = None
    service._emotional_journal = EmotionalJournal(tmp_path / "state.db")

    assert service._relationship_subject() == SPARKS_PRINCIPAL_ID
    assert service.relationship_scope.principal_id == SPARKS_PRINCIPAL_ID

    now = datetime.now(timezone.utc)
    service.emotional_journal.record(
        event_id="discord-shared-emotion",
        source="observed",
        evidence_ref="discord:test",
        description="Authenticated Discord relationship state.",
        emotions=("warmth",),
        occurred_at=now,
        subject=SPARKS_PRINCIPAL_ID,
        scope=service.relationship_scope,
    )

    state = service.current_emotional_state(now=now)
    assert "warmth" in {
        item.name for item in state.active
    }

def test_emotional_projection_preserves_parent_tool_gate(monkeypatch, tmp_path):
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="hru",
            ),
        ),
        allow_tools=False,
    )
    message = SimpleNamespace(
        id="user-message-tool-gate",
        content="hru",
        role=ConversationRole.USER,
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        ConversationService,
        "_build_request",
        lambda self: request,
    )
    monkeypatch.setattr(
        EmotionalConversationService,
        "messages",
        lambda self: (message,),
    )
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object())
    service._emotional_journal = EmotionalJournal(tmp_path / "tool-gate.db")

    result = service._build_request()

    assert result.allow_tools is False
    assert result.tools == ()



@pytest.mark.parametrize(
    "history_policy_name",
    ("LAST_TURN", "TOPIC_WINDOW", "BOUNDED_RECENT"),
)
def test_emotional_projection_does_not_reinject_excluded_environment(
    monkeypatch,
    tmp_path,
    history_policy_name,
):
    from sofia.cognition.matrix import ContextPlan, HistoryPolicy, MatrixDomain

    class EnvironmentMustNotBeRead:
        def snapshot(self, **_kwargs):
            raise AssertionError(
                "ENVIRONMENT was excluded by the matrix but was read anyway"
            )

    service, original = _service(monkeypatch, tmp_path)
    service._runtime.environment_service = EnvironmentMustNotBeRead()
    history_policy = getattr(HistoryPolicy, history_policy_name)
    service._current_context_plan = ContextPlan(
        included_domains=(MatrixDomain.EMOTION,),
        excluded_domains=tuple(
            domain
            for domain in MatrixDomain
            if domain is not MatrixDomain.EMOTION
        ),
        history_policy=history_policy,
        max_history_messages=3,
    )

    result = service._build_request()

    assert result is not original
    assert "MODELED EMOTIONAL CONTEXT" in result.messages[0].content
    assert "Weather condition:" in result.messages[0].content
    assert "Weather condition: unknown" in result.messages[0].content


def test_emotional_projection_is_absent_when_emotion_domain_is_excluded(
    monkeypatch,
    tmp_path,
):
    from sofia.cognition.matrix import ContextPlan, HistoryPolicy, MatrixDomain

    service, original = _service(monkeypatch, tmp_path)
    service._current_context_plan = ContextPlan(
        included_domains=(MatrixDomain.SOCIAL,),
        excluded_domains=tuple(
            domain
            for domain in MatrixDomain
            if domain is not MatrixDomain.SOCIAL
        ),
        history_policy=HistoryPolicy.BOUNDED_RECENT,
        max_history_messages=12,
    )

    result = service._build_request()

    assert result is original
