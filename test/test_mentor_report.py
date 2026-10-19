"""MENTOR human report is complete, cautious and usable as an Actions artifact."""
from __future__ import annotations
from contextlib import redirect_stdout
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sofia.mentor.audit import MentorAuditError, SCHEMA, STAGES
from sofia.mentor.report import markdown_report
from sofia.mentor.__main__ import main


class TestMentorReport(unittest.TestCase):
    def _sample(self):
        phase = {name: 0 for name in STAGES}
        return {
            "schema": SCHEMA,
            "source_revision": "a" * 40,
            "generated_at": "2026-10-19T22:00:00+00:00",
            "summary": {
                "total_tasks": 780, "audited_tasks": 114, "unassessed_tasks": 666,
                "historical_revision_records": 114, "failed_document_checks": 0,
                "stages": dict(phase, NOT_WORKED_ON=666, CODED_UNFINISHED=16,
                               PRODUCTION_CODED=11, TESTED=87, TESTED_CI=0),
            },
            "phases": {f"{i:02d}": dict(phase) for i in range(17)},
            "findings": [], "limitations": ["Not an operational host check."],
        }

    def test_human_report_contains_relevant_numbers_and_safety_caveat(self):
        text = markdown_report(self._sample())
        self.assertIn("114 / 780", text)
        self.assertIn("**666**", text)
        self.assertIn("| TESTED_CI | 0 |", text)
        self.assertIn("not production certification", text)
        self.assertIn("Not an operational host check.", text)
        self.assertEqual(sum(line.startswith("| 0") or line.startswith("| 1")
                             for line in text.splitlines()), 17)

    def test_refuses_malformed_reports_or_inflated_stage_counts(self):
        report = self._sample()
        report["schema"] = "unreviewed"
        with self.assertRaises(MentorAuditError):
            markdown_report(report)
        report = self._sample()
        report["summary"]["stages"]["TESTED"] = 88
        with self.assertRaises(MentorAuditError):
            markdown_report(report)

    def test_cli_rejects_unsafe_markdown_target(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.md"
            target.symlink_to(Path(tmp) / "outside.md")
            with patch("sofia.mentor.__main__.audit_checkout", return_value=self._sample()):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        main(["audit", "--repo", tmp, "--markdown", str(target)]), 2
                    )
            self.assertFalse((Path(tmp) / "outside.md").exists())


if __name__ == "__main__":
    unittest.main()
