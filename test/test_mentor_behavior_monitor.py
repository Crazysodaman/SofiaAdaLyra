"""Live-turn monitoring never changes foreground response or discloses texts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from sofia.core.mentor.behavior_monitor import (
    BehaviorMonitor, EMOTION_CRITERIA, TTL, PrivateTurn,
    _assess_json, behavior_monitor_enabled, evaluate_private_turn,
    register_behavior_monitor,
)
from sofia.core.mentor.personality_review import CRITERIA


NOW = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)


def fake_assessment():
    return {
        "personality": {
            key: {"score": 3, "reason": "Reason grounded in visible conversation."}
            for key in CRITERIA
        },
        "emotion": {
            key: {"score": None if key == "expression_coherence" else 3,
                  "reason": "No voice receipt." if key == "expression_coherence"
                  else "Tone appropriate to the conversation."}
            for key in EMOTION_CRITERIA
        },
        "strengths": ["No forced jokes."],
        "concerns": [],
        "uncertainty": "Actual sound, avatar output and private context not tested.",
    }


class BehaviorMonitorTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = self.root / "src/sofia/core/personality/personality.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({
            "name": "Sofía",
            "traits": ["skeptical", "warm", "natural", "honest"],
            "communication_style": "Be precise and contextual.",
        }), encoding="utf-8")

    def report(self, *args, **kwargs):
        return {
            "schema": "sofia.core.mentor.behavior-private-review.v1",
            "status": "PROVISIONAL_LOCAL_LLM_REVIEW",
            "source": "observed-application-response",
            "personality_scores": {x: 3 for x in CRITERIA},
            "emotion_scores": {x: (None if x == "expression_coherence" else 3)
                               for x in EMOTION_CRITERIA},
            "commands_executed": 0, "cloud_api_calls": 0,
        }

    def test_flag_is_off_by_default_and_fail_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(behavior_monitor_enabled())
        with patch.dict("os.environ", {"SOFIA_MENTOR_BEHAVIOR_ENABLED": "true"}):
            self.assertTrue(behavior_monitor_enabled())
        with patch.dict("os.environ", {"SOFIA_MENTOR_BEHAVIOR_ENABLED": "unclear"}):
            with self.assertRaises(ValueError):
                behavior_monitor_enabled()

    def test_observe_is_fast_and_saves_no_raw_text_in_snapshot(self):
        monitor = BehaviorMonitor(repo=self.root, evaluator=self.report)
        state = SimpleNamespace(tone="positive", active=(
            SimpleNamespace(name="curiosity", intensity=0.4),))
        monitor.observe(
            user_text="SENSITIVE-USER-NOTE", response_text="SENSITIVE-RESPONSE",
            emotional_state=state, channel="discord", now=NOW,
        )
        snap = monitor.snapshot()
        self.assertEqual(snap["observed_turns"], 1)
        self.assertEqual(snap["pending_private_turns"], 1)
        self.assertNotIn("SENSITIVE", json.dumps(snap))
        self.assertFalse(snap["exported_to_public_git"])
        outcome = monitor.review_next(now=NOW + timedelta(seconds=5))
        self.assertEqual(outcome["status"], "provisional_review_complete")
        self.assertEqual(monitor.snapshot()["reviewed_turns"], 1)
        self.assertNotIn("SENSITIVE", json.dumps(monitor.snapshot()))

    def test_queue_is_bounded_and_expired_samples_are_not_reviewed(self):
        observed = []
        def evaluator(**kw):
            observed.append(kw["turn"])
            return self.report()
        monitor = BehaviorMonitor(repo=self.root, evaluator=evaluator)
        for i in range(8):
            monitor.observe(user_text=f"private{i}", response_text="answer",
                            now=NOW + timedelta(seconds=i))
        self.assertEqual(monitor.snapshot()["pending_private_turns"], 4)
        result = monitor.review_next(now=NOW + TTL + timedelta(minutes=1))
        self.assertEqual(result["status"], "no_eligible_private_sample")
        self.assertEqual(monitor.snapshot()["pending_private_turns"], 0)
        self.assertFalse(observed)

    def test_skips_unbounded_or_missing_turns_without_persisting(self):
        monitor = BehaviorMonitor(repo=self.root, evaluator=self.report)
        monitor.observe(user_text="a" * 3501, response_text="fine", now=NOW)
        monitor.observe(user_text="question", response_text=" ", now=NOW)
        self.assertEqual(monitor.snapshot()["skipped_turns"], 2)
        self.assertEqual(monitor.snapshot()["pending_private_turns"], 0)

    def test_only_local_ollama_receives_modelled_affect_context(self):
        calls = []
        def sender(url, payload, headers, timeout):
            calls.append((url, payload, headers, timeout))
            return {"model": payload["model"], "done": True,
                    "message": {"content": json.dumps(fake_assessment())}}
        turn = PrivateTurn(
            prompt="Why is this service down?",
            answer="We do not know whether the listener is bound yet.",
            tone="settled", emotions=(("curiosity", 0.3),),
            channel="conversation", recorded_at=NOW,
        )
        result = evaluate_private_turn(
            repo=self.root, turn=turn, model="qwen3:14b", sender=sender,
        )
        self.assertEqual(result["status"], "PROVISIONAL_LOCAL_LLM_REVIEW")
        self.assertEqual(result["emotion_scores"]["expression_coherence"], None)
        self.assertFalse(result["voice_or_avatar_output_verified"])
        self.assertFalse(result["human_review_required"] is False)
        self.assertEqual(len(calls), 1)
        url, payload, headers, timeout = calls[0]
        self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(payload["think"])
        self.assertEqual(payload["tools"], [])
        self.assertEqual(payload["keep_alive"], 0)
        self.assertIsNone(headers.get("Authorization"))
        self.assertIn("curiosity", payload["messages"][1]["content"])

    def test_critic_cannot_certify_unobserved_voice_avatar_delivery(self):
        def sender(url, payload, headers, timeout):
            # Even a confident 4/4 from Qwen is not physical output proof.
            sample = fake_assessment()
            sample["emotion"]["expression_coherence"]["score"] = 4
            sample["emotion"]["expression_coherence"]["reason"] = (
                "I assume the avatar rendered perfectly."
            )
            return {"model": payload["model"], "done": True,
                    "message": {"content": json.dumps(sample)}}
        turn = PrivateTurn(
            prompt="Are you there?", answer="Yes, what needs investigating?",
            tone="settled", emotions=(), channel="conversation", recorded_at=NOW,
        )
        result = evaluate_private_turn(
            repo=self.root, turn=turn, model="qwen3:14b", sender=sender,
        )
        self.assertIsNone(result["emotion_scores"]["expression_coherence"])
        self.assertFalse(result["voice_or_avatar_output_verified"])

    def test_invalid_or_incomplete_critique_never_passes(self):
        x = fake_assessment()
        x["emotion"]["natural_not_performative"]["score"] = 9
        with self.assertRaises(ValueError):
            _assess_json(x)
        x = fake_assessment()
        del x["personality"]["factual_grounding"]
        with self.assertRaises(ValueError):
            _assess_json(x)
        x = fake_assessment()
        x["emotion"]["expression_coherence"]["score"] = None
        self.assertTrue(_assess_json(x))

    def test_reviewer_failure_does_not_requeue_or_expose_content(self):
        def fail(**kw):
            raise ValueError("Sensitive plaintext in exception")
        monitor = BehaviorMonitor(repo=self.root, evaluator=fail)
        monitor.observe(user_text="SENSITIVE INPUT", response_text="SENSITIVE OUTPUT", now=NOW)
        result = monitor.review_next(now=NOW)
        self.assertEqual(result, {
            "status": "review_failed", "error_kind": "ValueError",
            "commands_executed": 0,
        })
        self.assertNotIn("SENSITIVE", json.dumps(monitor.snapshot()))
        self.assertEqual(monitor.snapshot()["pending_private_turns"], 0)

    def test_auto_registration_uses_existing_scheduler_and_real_idle_gate(self):
        pending = {}
        def record(name, callback, **kw):
            pending[name] = (callback, kw)
        service = SimpleNamespace(
            _mentor_behavior_monitor=None, ready_for_idle_reflection=lambda *, idle_seconds: idle_seconds == 300,
        )
        app = SimpleNamespace(_conversation_service=service, _mentor_behavior_monitor=None)
        activity = SimpleNamespace(effective="gaming")
        activity_store = SimpleNamespace(state=lambda host: activity)
        coordinator = SimpleNamespace(set_task=record)
        monitor = BehaviorMonitor(repo=self.root, evaluator=self.report)
        with patch.dict("os.environ", {"SOFIA_MENTOR_BEHAVIOR_ENABLED": "true"}):
            ok = register_behavior_monitor(
                application=app, coordinator=coordinator, activity_store=activity_store,
                host_id="dev-test-host", repo=self.root, monitor=monitor,
            )
        self.assertTrue(ok)
        self.assertIs(app._mentor_behavior_monitor, monitor)
        self.assertIs(service._mentor_behavior_monitor, monitor)
        callback, settings = pending["mentor_behavior_review"]
        self.assertEqual(settings["interval_seconds"], 300)
        for unsafe in ("gaming", "busy", "do_not_disturb", "unknown"):
            activity.effective = unsafe
            self.assertFalse(settings["ready"]())
        activity.effective = "idle"
        self.assertTrue(settings["ready"]())
        activity.effective = "normal"
        self.assertTrue(settings["ready"]())
        self.assertEqual(callback(NOW)["status"], "no_eligible_private_sample")

    def test_no_flag_means_no_hook_no_worker(self):
        calls = []
        app = SimpleNamespace(_conversation_service=SimpleNamespace(
            ready_for_idle_reflection=lambda **kw: True))
        with patch.dict("os.environ", {}, clear=True):
            enabled = register_behavior_monitor(
                application=app, coordinator=SimpleNamespace(
                    set_task=lambda *a, **kw: calls.append(a)),
                activity_store=None, host_id="test", repo=self.root,
            )
        self.assertFalse(enabled)
        self.assertFalse(calls)
        self.assertFalse(hasattr(app._conversation_service, "_mentor_behavior_monitor"))

    def test_snapshot_is_not_live_host_or_emotion_proof(self):
        monitor = BehaviorMonitor(repo=self.root, evaluator=self.report)
        monitor.observe(user_text="hi", response_text="hello", now=NOW)
        monitor.review_next(now=NOW)
        snap = monitor.snapshot()
        self.assertFalse(snap["human_validation_completed"])
        self.assertFalse(snap["exported_to_public_git"])
        self.assertTrue(snap["last_provisional_scores"]["human_review_required"])
        self.assertFalse(snap["last_provisional_scores"]["voice_or_avatar_output_verified"])


if __name__ == "__main__":
    import unittest
    unittest.main()
