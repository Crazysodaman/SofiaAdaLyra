"""Git mailbox safety: only public allowlisted observations, no runtime commands."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from sofia.mentor.__main__ import main
from sofia.mentor.exchange import (
    INBOX, INBOX_SCHEMA, OUTBOX, OUTBOX_SCHEMA, MentorExchangeError,
    public_outbox, read_review, validate_advisory_review, write_public_outbox,
)


class TestMentorGitMailbox(TestCase):
    def setUp(self):
        self.t = TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.revision = "b" * 40

    def report(self):
        tasks = [
            {"task_id": "CA-0001", "phase": "00",
             "stage": "TESTED", "same_source_revision": False,
             "brief": "Safe task brief",
             "open_clauses": ["real host acceptance missing"]},
        ]
        tasks += [
            {"task_id": f"CA-{i:04d}", "phase": "01",
             "stage": "NOT_WORKED_ON", "same_source_revision": False}
            for i in range(2, 701)
        ]
        tasks += [
            {"task_id": f"{group}-{i:03d}", "phase": "14",
             "stage": "NOT_WORKED_ON", "same_source_revision": False}
            for group in ("ML", "GA") for i in range(1, 41)
        ]
        stages = {
            "NOT_WORKED_ON": 779, "CODED_UNFINISHED": 0,
            "PRODUCTION_CODED": 0, "TESTED": 1, "TESTED_CI": 0,
        }
        return {
            "source_revision": self.revision,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_tasks": 780, "audited_tasks": 1,
                "unassessed_tasks": 779, "historical_revision_records": 1,
                "stages": stages, "failed_document_checks": 0,
            },
            "phases": {
                "00": {**{k: 0 for k in stages}, "TESTED": 1},
                "01": {**{k: 0 for k in stages}, "NOT_WORKED_ON": 699},
                "14": {**{k: 0 for k in stages}, "NOT_WORKED_ON": 80},
            },
            "tasks": tasks,
        }

    def review(self):
        return {
            "schema": INBOX_SCHEMA,
            "visibility": "public",
            "reviewed_source_revision": self.revision,
            "review_created_at": "2026-10-19T23:50:00+00:00",
            "reviewer": "chatgpt-mentor",
            "summary": "Source-stage record is not live task acceptance.",
            "recommendations": [{
                "id": "REV-001",
                "task_ids": ["CA-0001"],
                "severity": "needs-verification",
                "action": "run-safe-test",
                "observation": "Local tests are listed but live host evidence is absent.",
                "suggested_check": "Perform approved focused regression review.",
                "acceptance": "Record real test outcome with pinned revision.",
                "requires_owner_approval": True,
            }],
            "limitations": ["Advisory only, no authorized code execution."],
        }

    def test_public_export_has_only_allowlisted_metadata(self):
        with patch("sofia.mentor.exchange.audit_checkout", return_value=self.report()):
            doc = public_outbox(self.root)
        self.assertEqual(doc["schema"], OUTBOX_SCHEMA)
        self.assertEqual(doc["visibility"], "public")
        self.assertEqual(doc["summary"]["total_tasks"], 780)
        self.assertEqual(len(doc["tasks"]), 780)
        self.assertNotIn("brief", doc["tasks"][0])
        self.assertNotIn("open_clauses", doc["tasks"][0])
        self.assertNotIn("private chat", json.dumps(doc).lower())
        self.assertNotIn("sofia.db", json.dumps(doc["tasks"]).lower())
        self.assertEqual(doc["tasks"][0]["id"], "CA-0001")

    def test_export_writes_only_designated_path_and_never_commits(self):
        with patch("sofia.mentor.exchange.audit_checkout", return_value=self.report()):
            result = write_public_outbox(self.root)
        self.assertEqual(result["path"], OUTBOX)
        self.assertFalse(result["git_committed"])
        self.assertFalse(result["git_pushed"])
        artifact = json.loads((self.root / OUTBOX).read_text(encoding="utf-8"))
        self.assertEqual(len(artifact["tasks"]), 780)
        self.assertFalse(list(self.root.glob("*.db")))

    def test_export_does_not_follow_symlinks_or_write_elsewhere(self):
        with patch("sofia.mentor.exchange.audit_checkout", return_value=self.report()):
            with self.assertRaises(MentorExchangeError):
                write_public_outbox(self.root, "../private.json")
            with self.assertRaises(MentorExchangeError):
                write_public_outbox(self.root, "docs/mentor_exchange/inbox/latest.json")

    def test_good_inbound_review_is_display_only(self):
        data = self.review()
        target = self.root / INBOX
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(read_review(self.root), data)
        self.assertTrue(data["recommendations"][0]["requires_owner_approval"])

    def test_review_may_not_authorize_execution_or_extra_fields(self):
        document = self.review()
        document["recommendations"][0]["requires_owner_approval"] = False
        with self.assertRaisesRegex(MentorExchangeError, "execution authority"):
            validate_advisory_review(document)
        document = self.review()
        document["tools"] = [{"shell": "rm -rf"}]
        with self.assertRaisesRegex(MentorExchangeError, "unexpected fields"):
            validate_advisory_review(document)

    def test_review_is_rejected_if_missing_provenance_or_oversized(self):
        document = self.review()
        document["reviewed_source_revision"] = "HEAD"
        with self.assertRaises(MentorExchangeError):
            validate_advisory_review(document)
        document = self.review()
        document["recommendations"][0]["suggested_check"] = "x" * 2000
        with self.assertRaises(MentorExchangeError):
            validate_advisory_review(document)

    def test_cli_exports_and_reads_without_action_execution(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with patch("sofia.mentor.exchange.audit_checkout", return_value=self.report()):
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["exchange-export", "--repo", str(self.root)]), 0)
            self.assertIn("git_pushed", output.getvalue())
        p = self.root / INBOX
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(self.review()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main(["exchange-read", "--repo", str(self.root)]), 0)
        self.assertIn('"automatic_actions_authorized": false', output.getvalue())


if __name__ == "__main__":
    import unittest
    unittest.main()
