"""Simultaneous conversation and model thought never enter runtime together."""
from threading import Event, RLock, Thread
from time import monotonic
from types import SimpleNamespace

from sofia.application.conversation_service import ConversationService
from sofia.application.emotional_conversation import EmotionalConversationService


def test_conversation_and_idle_thought_share_a_model_lock(monkeypatch):
    entered = Event()
    release = Event()
    background_entered = Event()
    calls = []

    def respond(_self, _content):
        calls.append("conversation:start")
        entered.set()
        assert release.wait(timeout=3)
        calls.append("conversation:end")
        return "reply"

    monkeypatch.setattr(ConversationService, "respond", respond)
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(personality=object())
    service._model_lock = RLock()
    service._active_user_requests = 0
    service._last_user_activity = monotonic() - 60

    def reflect(self, *, event_id):
        calls.append("reflection:start")
        background_entered.set()
        return "thought"

    monkeypatch.setattr(EmotionalConversationService, "_reflect_on_event_locked", reflect)
    user = Thread(target=lambda: service.respond("Hi"))
    worker = Thread(target=lambda: service.reflect_on_event(event_id="observed-event"))
    user.start()
    assert entered.wait(timeout=3)
    assert not service.ready_for_idle_reflection(idle_seconds=0.1)
    worker.start()
    assert not background_entered.wait(timeout=0.05)
    release.set()
    user.join(timeout=3)
    worker.join(timeout=3)
    assert not user.is_alive() and not worker.is_alive()
    assert calls == ["conversation:start", "conversation:end", "reflection:start"]
    assert not service.ready_for_idle_reflection(idle_seconds=45)
