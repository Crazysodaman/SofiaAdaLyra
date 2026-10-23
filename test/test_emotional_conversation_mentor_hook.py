"""Production final-response hook preserves original replies and permission gates."""
from __future__ import annotations

from threading import RLock
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from sofia.platform.application.conversation_service import ConversationService
from sofia.platform.application.emotional_conversation import EmotionalConversationService


class TestMentorFinalResponseHook(TestCase):
    def service(self, observer):
        srv = EmotionalConversationService.__new__(EmotionalConversationService)
        srv._active_channel = "conversation"
        srv._active_user_requests = 0
        srv._model_lock = RLock()
        srv._activity_group = None
        srv._last_turn_replayed = False
        srv._mentor_behavior_monitor = observer
        return srv

    def test_after_settled_reply_observer_sees_final_text_and_emotional_state(self):
        observer = Mock()
        state = SimpleNamespace(tone="settled", active=())
        answer = SimpleNamespace(content="The listener state is not verified.")
        svc = self.service(observer)
        with (
            patch.object(ConversationService, "respond", return_value=answer),
            patch.object(EmotionalConversationService, "_persist_pending_emotion_appraisal"),
            patch.object(EmotionalConversationService, "_persist_pending_user_affect"),
            patch.object(EmotionalConversationService, "_record_expression_decision"),
            patch.object(EmotionalConversationService, "current_emotional_state",
                         return_value=state),
            patch("sofia.platform.application.emotional_conversation.emit_performance"),
            patch("sofia.platform.application.emotional_conversation.performance_trace_enabled",
                  return_value=False),
        ):
            result = svc.respond("Can you prove the service is live?", channel="conversation")
        self.assertIs(result, answer)
        observer.observe.assert_called_once_with(
            user_text="Can you prove the service is live?",
            response_text=answer.content, emotional_state=state,
            channel="conversation",
        )
        self.assertEqual(svc._active_user_requests, 0)

    def test_mentor_failure_never_changes_reply_or_interrupts_user(self):
        observer = Mock()
        observer.observe.side_effect = ValueError("private user content must not be logged")
        answer = SimpleNamespace(content="I cannot confirm that without a check.")
        svc = self.service(observer)
        with (
            patch.object(ConversationService, "respond", return_value=answer),
            patch.object(EmotionalConversationService, "_persist_pending_emotion_appraisal"),
            patch.object(EmotionalConversationService, "_persist_pending_user_affect"),
            patch.object(EmotionalConversationService, "_record_expression_decision"),
            patch.object(EmotionalConversationService, "current_emotional_state",
                         return_value=SimpleNamespace(tone="positive", active=())),
            patch("sofia.platform.application.emotional_conversation.emit_performance"),
            patch("sofia.platform.application.emotional_conversation.performance_trace_enabled",
                  return_value=False),
            patch("sofia.platform.application.emotional_conversation._LOG") as log,
        ):
            self.assertIs(svc.respond("Check it"), answer)
        self.assertEqual(svc._active_user_requests, 0)
        message = str(log.warning.call_args)
        self.assertIn("ValueError", message)
        self.assertNotIn("private user content", message)

    def test_replayed_turn_is_not_counted_twice(self):
        observer = Mock()
        answer = SimpleNamespace(content="A previously completed turn")
        svc = self.service(observer)
        def replayed(*args, **kwargs):
            svc._last_turn_replayed = True
            return answer
        with (
            patch.object(ConversationService, "respond", side_effect=replayed),
            patch.object(EmotionalConversationService, "_persist_pending_emotion_appraisal") as appraise,
            patch.object(EmotionalConversationService, "_record_expression_decision") as express,
            patch("sofia.platform.application.emotional_conversation.emit_performance"),
            patch("sofia.platform.application.emotional_conversation.performance_trace_enabled",
                  return_value=False),
        ):
            self.assertIs(svc.respond("repeat"), answer)
        observer.observe.assert_not_called()
        appraise.assert_not_called()
        express.assert_not_called()


if __name__ == "__main__":
    import unittest
    unittest.main()
