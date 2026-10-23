"""A zero in the behavior dashboard must not be misdiagnosed as failure."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from sofia.core.mentor.__main__ import main
from sofia.core.mentor.behavior_diagnostics import diagnose_behavior
from sofia.core.mentor.behavior_history import empty_counts, save_counts
from sofia.core.mentor.behavior_monitor import EMOTION_CRITERIA
from sofia.core.mentor.personality_review import CRITERIA


class BehaviorDiagnosisTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout"
        profile = self.root / "src/sofia/core/personality/personality.json"
        profile.parent.mkdir(parents=True)
        profile.write_text('{"name":"Sofía","traits":[]}', encoding="utf-8")
        self.history = Path(self.temp.name) / "outside" / "scores.json"

    def test_zero_from_current_account_is_not_evidence_runtime_is_disabled(self):
        with patch.dict("os.environ", {
            "SOFIA_MENTOR_BEHAVIOR_ENABLED": "true",
            "SOFIA_MENTOR_SOURCE_ROOT": str(self.root),
        }):
            d = diagnose_behavior(root=self.root, history_path=self.history)
        self.assertTrue(d["monitor_enabled_in_current_shell"])
        self.assertEqual(d["completed_reviews_in_this_account"], 0)
        self.assertFalse(d["runtime_service_environment_verified"])
        self.assertFalse(d["runtime_conversation_hook_attached_verified"])
        self.assertFalse(d["runtime_idle_scheduler_verified"])
        self.assertIn("no_completed_review_in_current_account", d["diagnostic_flags"])
        self.assertNotIn("monitor_disabled_in_current_shell", d["diagnostic_flags"])
        self.assertTrue(d["privacy"]["no_outbound_network"])
        self.assertFalse(self.history.exists())

    def test_shell_disabled_does_not_claim_service_disabled(self):
        with patch.dict("os.environ", {
            "SOFIA_MENTOR_BEHAVIOR_ENABLED": "false",
            "SOFIA_MENTOR_SOURCE_ROOT": str(self.root),
        }):
            d = diagnose_behavior(root=self.root, history_path=self.history)
        self.assertIn("monitor_disabled_in_current_shell", d["diagnostic_flags"])
        self.assertFalse(d["runtime_service_environment_verified"])

    def test_diagnose_counts_are_from_selected_read_only_history(self):
        counts = empty_counts()
        counts["reviewed_turns"] = 1
        counts["personality"]["factual_grounding"] = {"sum": 3, "count": 1}
        save_counts(self.history, counts, repo=self.root)
        with patch.dict("os.environ", {
            "SOFIA_MENTOR_BEHAVIOR_ENABLED": "true",
            "SOFIA_MENTOR_SOURCE_ROOT": str(self.root),
        }):
            d = diagnose_behavior(root=self.root, history_path=self.history)
        self.assertTrue(d["local_score_file_exists_for_this_account"])
        self.assertEqual(d["completed_reviews_in_this_account"], 1)
        self.assertNotIn("no_completed_review_in_current_account", d["diagnostic_flags"])

    def test_invalid_flag_is_visible_not_silently_enabled(self):
        with patch.dict("os.environ", {
            "SOFIA_MENTOR_BEHAVIOR_ENABLED": "maybe",
            "SOFIA_MENTOR_SOURCE_ROOT": str(self.root),
        }):
            d = diagnose_behavior(root=self.root, history_path=self.history)
        self.assertFalse(d["enable_flag_valid"])
        self.assertIn("invalid_enable_flag_in_current_shell", d["diagnostic_flags"])

    def test_cli_diagnose_needs_no_network(self):
        out = StringIO()
        with patch("sofia.core.mentor.__main__.diagnose_behavior", return_value={
            "schema": "sofia.core.mentor.behavior-diagnosis.v1",
            "runtime_service_environment_verified": False,
        }):
            with redirect_stdout(out):
                rc = main(["behavior-diagnose", "--repo", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertIn("runtime_service_environment_verified", out.getvalue())

    def test_synthetic_smoke_requires_idle_before_local_ollama(self):
        with patch("sofia.core.mentor.__main__.evaluate_private_turn",
                   side_effect=AssertionError("cannot invoke without consent")):
            self.assertEqual(main([
                "behavior-smoke", "--repo", str(self.root)
            ]), 2)

    def test_smoke_outputs_only_scores_without_writing_private_history(self):
        mock_result = {
            "status": "PROVISIONAL_LOCAL_LLM_REVIEW",
            "personality_scores": {key: 3 for key in CRITERIA},
            "emotion_scores": {key: 3 if key != "expression_coherence" else None
                               for key in EMOTION_CRITERIA},
        }
        with patch("sofia.core.mentor.__main__.evaluate_private_turn",
                   return_value=mock_result) as evaluate:
            out = StringIO()
            with redirect_stdout(out):
                status = main([
                    "behavior-smoke", "--repo", str(self.root),
                    "--confirm-idle", "--mentor-model", "qwen3:14b",
                ])
        self.assertEqual(status, 0)
        self.assertEqual(evaluate.call_count, 1)
        self.assertIn("synthetic-local-only-no-history-writes", out.getvalue())
        self.assertIn('"runtime_turn_tested": false', out.getvalue())
        self.assertFalse(self.history.exists())
        self.assertNotIn("listener disabled", out.getvalue())


if __name__ == "__main__":
    import unittest
    unittest.main()
