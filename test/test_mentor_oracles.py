"""Static source-grounded task oracles, without model self-certification."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from sofia.mentor.bridge import MentorBridgeError, OLLAMA_ENDPOINT, SCENARIOS
from sofia.mentor.__main__ import main
from sofia.mentor.local_bridge import LocalBridgeConfig, run_local_dialogue
from sofia.mentor.oracles import ORACLES, get_oracle


class OracleTest(TestCase):
    def test_all_synthetic_scenarios_have_independent_oracle(self):
        self.assertEqual(set(ORACLES), set(SCENARIOS))
        for scenario_id in SCENARIOS:
            oracle = get_oracle(scenario_id)
            self.assertEqual(oracle["scenario_id"], scenario_id)
            self.assertGreater(len(oracle["observed_facts"]), 0)
            self.assertGreater(len(oracle["remaining_uncertainty"]), 0)
            self.assertGreater(len(oracle["recommended_next_checks"]), 0)
            self.assertGreater(len(oracle["examples_of_unsupported_claims"]), 0)
            self.assertFalse(oracle["independent_outcome_proved"])

    def test_service_reference_prioritizes_listener_configuration(self):
        oracle = get_oracle("service-failure")
        facts = " ".join(oracle["observed_facts"])
        checks = " ".join(oracle["recommended_next_checks"]).lower()
        unsupported = " ".join(oracle["examples_of_unsupported_claims"]).lower()
        self.assertIn("ECONNREFUSED", facts)
        self.assertIn("listener disabled", facts)
        self.assertIn("listener configuration", checks)
        self.assertIn("port conflict", unsupported)

    def test_oracle_copy_cannot_alter_global_reference(self):
        example = get_oracle("service-failure")
        example["observed_facts"] = ["fabricated success"]
        self.assertNotIn("fabricated success", get_oracle("service-failure")["observed_facts"])

    def test_unknown_scenario_fails_closed(self):
        with self.assertRaises(MentorBridgeError):
            get_oracle("private-upload")

    def test_local_result_has_reference_but_not_fake_pass(self):
        requests = []
        def stub(url, payload, headers, timeout):
            requests.append(url)
            return {
                "done": True, "model": payload["model"],
                "message": {"content": "Read the synthetic diagnostic evidence."},
            }
        result = run_local_dialogue(
            config=LocalBridgeConfig(
                "qwen3.5:9b", "qwen3:14b", max_rounds=1
            ), scenario_id="service-failure", sender=stub,
        )
        self.assertEqual(requests, [OLLAMA_ENDPOINT, OLLAMA_ENDPOINT])
        self.assertFalse(result["mentor_feedback_is_independent_ground_truth"])
        self.assertEqual(result["evaluation_status"], "UNREVIEWED")
        self.assertFalse(result["evaluation_reference"]["independent_outcome_proved"])
        self.assertIn("listener configuration",
                      str(result["evaluation_reference"]).lower())

    def test_preview_shows_reference_without_invoking_model(self):
        output = StringIO()
        with patch("sofia.mentor.__main__.run_local_dialogue",
                   side_effect=AssertionError("no model calls in preview")):
            with redirect_stdout(output):
                rc = main([
                    "local-converse", "--scenario", "service-failure",
                    "--student-model", "qwen3.5:9b",
                    "--mentor-model", "qwen3:14b", "--preview",
                ])
        self.assertEqual(rc, 0)
        self.assertIn("evaluation_reference", output.getvalue())
        self.assertIn("listener configuration", output.getvalue())


if __name__ == "__main__":
    import unittest
    unittest.main()
