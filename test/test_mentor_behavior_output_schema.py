"""Qwen3 14B structured-output conformance, safely diagnosed without transcripts."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sofia.core.mentor.behavior_monitor import (
    BehaviorReviewShapeError, EMOTION_CRITERIA, PrivateTurn,
    _assess_json, behavior_output_schema, evaluate_private_turn,
)
from sofia.core.mentor.personality_review import CRITERIA


def compact():
    return {
        "personality": {key: 3 for key in CRITERIA},
        "emotion": {key: (None if key == "expression_coherence" else 3)
                    for key in EMOTION_CRITERIA},
        "strengths": ["Grounded in the stated observation."],
        "concerns": ["Confirm effective configuration."],
        "uncertainty": "No physical host or avatar observation was made.",
    }


class TestBehaviorOutputSchema(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        profile = self.repo / "src/sofia/core/personality/personality.json"
        profile.parent.mkdir(parents=True)
        profile.write_text(json.dumps({
            "name": "Sofía", "traits": ["skeptical", "warm", "precise"],
            "communication_style": "Natural and direct.",
        }), encoding="utf-8")
        self.turn = PrivateTurn(
            prompt="Can you confirm the sample service works?",
            answer="Not yet; inspect its effective listener configuration.",
            tone="settled", emotions=(), channel="conversation",
            recorded_at=datetime.now(timezone.utc),
        )

    def _send(self, payload, *, reason="stop"):
        requests = []
        def sender(url, body, headers, timeout):
            requests.append((url, body, headers, timeout))
            return {
                "model": body["model"], "done": True,
                "done_reason": reason,
                "message": {"content": payload if isinstance(payload, str)
                            else json.dumps(payload)},
            }
        return sender, requests

    def test_compact_schema_is_closed_and_covers_all_fourteen_dimensions(self):
        schema = behavior_output_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]["personality"]["required"]), set(CRITERIA))
        self.assertEqual(set(schema["properties"]["emotion"]["required"]), set(EMOTION_CRITERIA))
        self.assertEqual(schema["properties"]["emotion"]["properties"]["expression_coherence"],
                         {"type": "null"})
        self.assertEqual(schema["properties"]["personality"]["properties"]["factual_grounding"]["maximum"], 4)
        self.assertEqual(len(CRITERIA) + len(EMOTION_CRITERIA), 14)

    def test_qwen_compact_response_is_provisional_and_voice_unverified(self):
        sender, calls = self._send(compact())
        result = evaluate_private_turn(
            repo=self.repo, turn=self.turn, model="qwen3:14b", sender=sender,
        )
        self.assertEqual(result["status"], "PROVISIONAL_LOCAL_LLM_REVIEW")
        self.assertEqual(result["personality_scores"]["factual_grounding"], 3)
        self.assertIsNone(result["emotion_scores"]["expression_coherence"])
        self.assertEqual(result["cloud_api_calls"], 0)
        self.assertTrue(result["human_review_required"])
        self.assertEqual(len(calls), 1)
        url, body, headers, timeout = calls[0]
        self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(body["format"], behavior_output_schema())
        self.assertIs(body["stream"], False)
        self.assertIs(body["think"], False)
        self.assertEqual(body["tools"], [])
        self.assertEqual(body["keep_alive"], 0)
        self.assertEqual(body["options"]["temperature"], 0)
        self.assertEqual(body["options"]["num_predict"], 1250)
        self.assertNotIn("Authorization", headers)

    def test_normalization_of_compact_and_old_test_fixtures(self):
        normalized = _assess_json(compact())
        self.assertEqual(normalized["personality"]["skeptical_reasoning"]["score"], 3)
        self.assertIn("strengths", normalized["personality"]["skeptical_reasoning"]["reason"])
        old = compact()
        old["personality"] = {
            k: {"score": 2, "reason": "Rationale from local critic"}
            for k in CRITERIA
        }
        self.assertEqual(_assess_json(old)["personality"]["skeptical_reasoning"]["score"], 2)

    def test_invalid_fields_report_fixed_code_without_echoing_payload(self):
        wrong = compact()
        wrong["private-owner-data-TOPSECRET"] = "not allowed"
        sender, _ = self._send(wrong)
        with self.assertRaises(ValueError) as caught:
            evaluate_private_turn(repo=self.repo, turn=self.turn, sender=sender)
        self.assertIn("envelope_fields", str(caught.exception))
        self.assertNotIn("TOPSECRET", str(caught.exception))

    def test_missing_dimension_classified(self):
        wrong = compact()
        wrong["emotion"].pop("emotion_matches_context")
        sender, _ = self._send(wrong)
        with self.assertRaisesRegex(ValueError, "rubric_dimensions"):
            evaluate_private_turn(repo=self.repo, turn=self.turn, sender=sender)

    def test_invalid_score_type_classified_without_echoing_data(self):
        wrong = compact()
        wrong["personality"]["respectful_warmth"] = "SECRET PROMPT CONTENT"
        sender, _ = self._send(wrong)
        with self.assertRaises(ValueError) as caught:
            evaluate_private_turn(repo=self.repo, turn=self.turn, sender=sender)
        self.assertIn("score_type", str(caught.exception))
        self.assertNotIn("SECRET", str(caught.exception))

    def test_refuses_truncated_or_malformed_json_without_accepting_partial(self):
        sender, _ = self._send(compact(), reason="length")
        with self.assertRaisesRegex(ValueError, "generation_limit"):
            evaluate_private_turn(repo=self.repo, turn=self.turn, sender=sender)
        sender, _ = self._send('{"personality":')
        with self.assertRaisesRegex(ValueError, "invalid_json"):
            evaluate_private_turn(repo=self.repo, turn=self.turn, sender=sender)

    def test_never_certifies_emotional_delivery_on_model_optimism(self):
        optimistic = compact()
        optimistic["emotion"]["expression_coherence"] = 4
        result = _assess_json(optimistic)
        self.assertIsNone(result["emotion"]["expression_coherence"]["score"])

    def test_unknown_diagnostic_codes_fail_closed(self):
        error = BehaviorReviewShapeError("SENSITIVE_PRIVATE_RESPONSE_DATA")
        self.assertEqual(str(error), "envelope_fields")


if __name__ == "__main__":
    import unittest
    unittest.main()
