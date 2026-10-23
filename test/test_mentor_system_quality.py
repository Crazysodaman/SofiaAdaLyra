"""Whole-system and personality quality must not reduce to task totals."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from sofia.core.mentor.__main__ import main
from sofia.core.mentor.exchange import public_outbox
from sofia.core.mentor.personality_review import (
    CRITERIA, PersonalityReviewError, load_public_personality_summary,
    public_personality_summary, publish_public_personality_summary, review_response,
)
from sofia.core.mentor.system_parts import PARTS, system_parts_summary


class SystemQualityTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        profile = self.root / "src/sofia/core/personality/personality.json"
        profile.parent.mkdir(parents=True)
        profile.write_text(json.dumps({
            "name": "Sofía", "traits": [
                "evidence-driven", "skeptical", "warm without agreeable",
                "playfully fox-like", "respects authority boundaries",
            ],
            "communication_style": "Direct, accurate, varied, situational, dry humor.",
        }), encoding="utf-8")

    def audit(self):
        phases = ["00", "01", "05", "08", "09", "10", "12", "14"]
        items = [
            {"task_id": f"CA-{i:04d}", "phase": phases[i % len(phases)],
             "stage": "NOT_WORKED_ON", "same_source_revision": False}
            for i in range(1, 701)
        ]
        items.extend([
            {"task_id": f"{family}-{i:03d}", "phase": "14",
             "stage": "NOT_WORKED_ON", "same_source_revision": False}
            for family in ("GA", "ML") for i in range(1, 41)
        ])
        stages = {
            "NOT_WORKED_ON": 780, "CODED_UNFINISHED": 0,
            "PRODUCTION_CODED": 0, "TESTED": 0, "TESTED_CI": 0,
        }
        return {
            "source_revision": "a" * 40,
            "generated_at": "2026-10-19T23:35:00+00:00",
            "tasks": items,
            "summary": {
                "total_tasks": 780, "audited_tasks": 0, "unassessed_tasks": 780,
                "historical_revision_records": 0, "stages": stages,
                "failed_document_checks": 0,
            },
            "phases": {"00": stages},
        }

    @staticmethod
    def pretend_critic(url, payload, headers, timeout):
        criteria = {
            name: {"score": 3, "justification": "Technically grounded and measured."}
            for name in CRITERIA
        }
        return {
            "done": True, "model": payload["model"],
            "message": {"content": json.dumps({
                "criteria": criteria,
                "strengths": ["Good uncertainty handling"],
                "mismatches": ["Could be more concise"],
                "reviewer_uncertainty": "No independent host evidence.",
            })},
        }

    def review(self, *, response="No host proof yet. Inspect the effective listener configuration."):
        return review_response(
            repo=self.root, scenario_id="service-failure",
            response=response, source_kind="owner-selected-sofia-output",
            model="qwen3:14b", sender=self.pretend_critic,
        )

    def test_part_inventory_is_about_systems_not_task_progress(self):
        result = system_parts_summary(self.root, audit=self.audit())
        self.assertEqual(result["part_count"], 15)
        self.assertEqual(len({p["id"] for p in result["parts"]}), 15)
        self.assertIn("personality", [p["id"] for p in result["parts"]])
        self.assertIn("safety", [p["id"] for p in result["parts"]])
        for part in result["parts"]:
            self.assertEqual(part["runtime_status"], "unknown_no_host_observation")
            self.assertEqual(part["test_execution_status"], "not_verified_by_this_export")
            self.assertIn(part["source_status"], ("source_present", "source_incomplete"))
            self.assertNotIn("operational", part["source_status"])
        self.assertEqual(result["personality"]["response_match"], "UNASSESSED")
        self.assertEqual(result["personality"]["actual_responses_reviewed"], 0)

    def test_outbox_prioritizes_parts_and_personality_over_task_counts(self):
        sample = self.audit()
        with patch("sofia.core.mentor.exchange.audit_checkout", return_value=sample):
            out = public_outbox(self.root)
        self.assertEqual(out["system"]["part_count"], 15)
        self.assertEqual(out["system"]["personality"]["response_match"], "UNASSESSED")
        self.assertEqual(len(out["tasks"]), 780)
        self.assertNotIn("No host proof yet", json.dumps(out))
        self.assertIn("Prioritize system.parts", out["read_me"])

    def test_private_model_review_validated_and_not_ground_truth(self):
        result = self.review()
        self.assertEqual(result["average"], 3)
        self.assertEqual(result["assessment_status"], "PROVISIONAL_LOCAL_LLM_REVIEW")
        self.assertFalse(result["response_provenance_verified"])
        self.assertFalse(result["raw_response_included"])
        self.assertTrue(result["human_or_independent_review_required"])
        self.assertEqual(set(result["rubric"]), set(CRITERIA))

    def test_local_review_never_uses_cloud_or_tools(self):
        requests = []
        def sender(url, payload, headers, timeout):
            requests.append((url, payload, headers))
            return self.pretend_critic(url, payload, headers, timeout)
        review_response(
            repo=self.root, scenario_id="service-failure",
            response="Observed log and proposed listener test.",
            model="qwen3:14b", source_kind="model-only-synthetic",
            sender=sender,
        )
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][0], "http://127.0.0.1:11434/api/chat")
        self.assertEqual(requests[0][1]["tools"], [])
        self.assertEqual(requests[0][1]["keep_alive"], 0)
        self.assertNotIn("Authorization", requests[0][2])

    def test_published_aggregate_omits_raw_text_and_rationales(self):
        secret = "Private demo context: SENSITIVE_DATA_12345. It is not host evidence."
        result = self.review(response=secret)
        safe = public_personality_summary(result)
        self.assertNotIn("SENSITIVE_DATA_12345", json.dumps(safe))
        self.assertNotIn("justification", json.dumps(safe))
        self.assertEqual(safe["rubric_scores"]["factual_grounding"], 3)
        self.assertFalse(safe["response_provenance_verified"])
        stamp = publish_public_personality_summary(self.root, result)
        self.assertFalse(stamp["git_pushed"])
        self.assertFalse(stamp["git_committed"])
        loaded = load_public_personality_summary(self.root)
        self.assertEqual(loaded, safe)
        self.assertNotIn("SENSITIVE_DATA_12345", json.dumps(loaded))

    def test_review_scores_appear_provisionally_not_as_operational_proof(self):
        result = self.review()
        publish_public_personality_summary(self.root, result)
        systems = system_parts_summary(self.root, audit=self.audit())
        score = systems["personality"]
        self.assertEqual(score["response_match"], "PROVISIONAL_LOCAL_LLM_REVIEW")
        self.assertEqual(score["owner_selected_responses_reviewed"], 1)
        self.assertEqual(score["actual_responses_reviewed"], 0)
        self.assertEqual(score["provisional_scores"]["factual_grounding"], 3)
        profile_file = self.root / "src/sofia/core/personality/personality.json"
        profile_file.write_text(json.dumps({
            "name": "Sofía", "traits": ["profile changed"], "communication_style": "updated"
        }), encoding="utf-8")
        outdated = system_parts_summary(self.root, audit=self.audit())["personality"]
        self.assertEqual(outdated["response_match"], "UNASSESSED")

    def test_fake_or_inflated_rubric_is_refused(self):
        record = self.review()
        record["rubric"]["factual_grounding"]["score"] = 5
        with self.assertRaises(PersonalityReviewError):
            public_personality_summary(record)
        record = self.review()
        record["response_provenance_verified"] = True
        with self.assertRaises(PersonalityReviewError):
            public_personality_summary(record)
        record = self.review()
        safe = public_personality_summary(record)
        safe["raw_transcript_exported"] = True
        file = self.root / "docs/mentor_exchange/evidence/personality_latest.json"
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps(safe), encoding="utf-8")
        with self.assertRaises(PersonalityReviewError):
            load_public_personality_summary(self.root)

    def test_local_cli_requires_idle_before_private_file_access(self):
        with patch("sofia.core.mentor.__main__.review_response",
                   side_effect=AssertionError("should not call reviewer")):
            from sofia.core.mentor.personality_review import PUBLIC_SUMMARY
            result = main([
                "personality-review", "--repo", str(self.root),
                "--response-file", str(self.root / "private.txt"),
                "--scenario", "service-failure", "--mentor-model", "qwen3:14b",
                "--source-kind", "owner-selected-sofia-output",
            ])
        self.assertEqual(result, 2)
        self.assertFalse((self.root / PUBLIC_SUMMARY).exists())

    def test_private_cli_reports_without_writing_public_summary_implicitly(self):
        chosen = self.root / "response.txt"
        chosen.write_text("The listener status isn't verified.", encoding="utf-8")
        with patch("sofia.core.mentor.__main__.review_response", return_value=self.review()):
            output = StringIO()
            with redirect_stdout(output):
                code = main([
                    "personality-review", "--repo", str(self.root),
                    "--response-file", str(chosen),
                    "--scenario", "service-failure", "--mentor-model", "qwen3:14b",
                    "--source-kind", "owner-selected-sofia-output",
                    "--confirm-idle",
                ])
        self.assertEqual(code, 0)
        self.assertIn('"private": true', output.getvalue())
        from sofia.core.mentor.personality_review import PUBLIC_SUMMARY
        self.assertFalse((self.root / PUBLIC_SUMMARY).exists())

if __name__ == "__main__":
    import unittest
    unittest.main()
