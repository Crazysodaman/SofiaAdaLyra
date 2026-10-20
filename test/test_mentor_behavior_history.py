"""Behavior trend records only bounded local numeric aggregates, no raw chat."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sofia.mentor.behavior_history import (
    empty_counts, merge_scores, read_counts, save_counts, public_free_summary
)
from sofia.mentor.behavior_monitor import BehaviorMonitor, EMOTION_CRITERIA
from sofia.mentor.personality_review import CRITERIA


class TestBehaviorScoreHistory(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "public-repo"
        self.root.mkdir()
        self.private = Path(self.tmp.name) / "outside-repo" / "behavior_scores.json"

    @staticmethod
    def scores():
        return (
            {k: 3 for k in CRITERIA},
            {k: (None if k == "expression_coherence" else 2)
             for k in EMOTION_CRITERIA}
        )

    def test_only_numeric_counts_survive_restart(self):
        personality, emotion = self.scores()
        history = merge_scores(empty_counts(), personality, emotion)
        save_counts(self.private, history, repo=self.root)
        restored = read_counts(self.private)
        self.assertEqual(restored["reviewed_turns"], 1)
        self.assertEqual(restored["emotion"]["expression_coherence"]["count"], 0)
        self.assertEqual(restored["personality"]["factual_grounding"]["sum"], 3)
        self.assertNotIn("token", self.private.read_text().lower())
        summary = public_free_summary(restored)
        self.assertEqual(summary["grades"]["factual_grounding"] if "factual_grounding" in summary["grades"] else summary["grades"]["personality"]["factual_grounding"], 3)
        self.assertIsNone(summary["grades"]["emotion"]["expression_coherence"])
        self.assertTrue(summary["local_only"])

    def test_rejects_git_checkout_destination(self):
        personality, emotion = self.scores()
        history = merge_scores(empty_counts(), personality, emotion)
        with self.assertRaisesRegex(ValueError, "public Git"):
            save_counts(self.root / "docs" / "scores.json", history, repo=self.root)

    def test_corrupt_score_records_are_not_loaded(self):
        self.private.parent.mkdir()
        self.private.write_text('{"schema":"bad"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_counts(self.private)

    def test_out_of_bounds_score_or_fake_count_rejected(self):
        personality, emotion = self.scores()
        personality["factual_grounding"] = 9
        with self.assertRaises(ValueError):
            merge_scores(empty_counts(), personality, emotion)
        bad = empty_counts()
        bad["personality"]["factual_grounding"]["sum"] = 10
        with self.assertRaises(ValueError):
            save_counts(self.private, bad, repo=self.root)

    def test_private_monitor_stores_only_counts_and_no_user_content(self):
        from datetime import datetime, timezone
        from sofia.mentor.behavior_monitor import BehaviorMonitor
        personality, emotion = self.scores()
        def reviewer(*, repo, turn, model):
            return {
                "schema": "sofia.mentor.behavior-private-review.v1",
                "status": "PROVISIONAL_LOCAL_LLM_REVIEW",
                "source": "observed-application-response",
                "personality_scores": personality,
                "emotion_scores": emotion,
                "commands_executed": 0, "cloud_api_calls": 0,
            }
        monitor = BehaviorMonitor(
            repo=self.root, evaluator=reviewer, history_path=self.private
        )
        now = datetime.now(timezone.utc)
        monitor.observe(
            user_text="SECRET PRIVATE HUMAN PROMPT", response_text="SECRET PRIVATE ANSWER",
            now=now,
        )
        self.assertEqual(monitor.review_next(now=now)["status"], "provisional_review_complete")
        self.assertEqual(read_counts(self.private)["reviewed_turns"], 1)
        self.assertNotIn("SECRET", self.private.read_text(encoding="utf-8"))
        again = BehaviorMonitor(repo=self.root, evaluator=reviewer, history_path=self.private)
        self.assertEqual(again.snapshot()["local_score_total_reviews"], 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
