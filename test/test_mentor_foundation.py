"""MENTOR audits what evidence says, never what a model wishes were true."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sofia.core.mentor import MentorAuditError, audit_checkout, compare_reports
from sofia.core.mentor.__main__ import main
from sofia.core.mentor.audit import DOCUMENTS, INDEX, LEDGER, STAGES


class TestMentorFoundation(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.revision = "a" * 40
        ids = ([f"CA-{i:04d}" for i in range(1, 701)]
               + [f"ML-{i:03d}" for i in range(1, 41)]
               + [f"GA-{i:03d}" for i in range(1, 41)])
        self.ids = ids
        self._write(INDEX, "# Task index\n\n"
                    + "".join(f"| {task_id} | 01 | requirement for {task_id} |\n"
                              for task_id in ids))
        for name in DOCUMENTS:
            self._write(name, "# Reference\n"
                        + ("".join(f"### {task_id}\n\n" for task_id in ids)
                           if name.endswith("Sofia_Complete_System_Atlas.md") else ""))
        self._write(LEDGER, json.dumps({"schema_version": 1, "tasks": []}))
        self._write("src/sofia/core/life/example.py", "def example(): pass\n")

    def _write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _ledger(self, *records):
        self._write(LEDGER, json.dumps({"schema_version": 1, "tasks": list(records)}))

    def _record(self, stage="CODED_UNFINISHED"):
        return {
            "task_id": "CA-0001", "stage": stage,
            "source_sha": self.revision,
            "source_paths": ["src/sofia/core/life/example.py"],
            "production_entrypoint": "SofiaApplication.life",
            "tests": [{"command": "pytest example", "result": "1 passed"}],
            "ci_runs": [],
            "open_clauses": ["Real-host verification outstanding"],
        }

    def test_full_780_inventory_is_unassessed_until_real_records_exist(self):
        report = audit_checkout(self.root, revision=self.revision)
        self.assertEqual(report["summary"]["total_tasks"], 780)
        self.assertEqual(report["summary"]["unassessed_tasks"], 780)
        self.assertEqual(report["summary"]["audited_tasks"], 0)
        self.assertEqual(report["summary"]["stages"]["NOT_WORKED_ON"], 780)
        self.assertEqual(report["summary"]["family_counts"], {
            "CA": 700, "ML": 40, "GA": 40,
        })
        self.assertFalse(report["findings"])
        self.assertFalse(list(self.root.glob("*.db")))

    def test_recorded_tests_do_not_imply_ci_or_live_host(self):
        row = self._record("TESTED")
        self._ledger(row)
        report = audit_checkout(self.root, revision="b" * 40)
        entry = next(x for x in report["tasks"] if x["task_id"] == "CA-0001")
        self.assertEqual(entry["stage"], "TESTED")
        self.assertFalse(entry["same_source_revision"])
        self.assertFalse(entry["ci_independently_checked"])
        self.assertEqual(report["summary"]["historical_revision_records"], 1)

    def test_comparison_is_only_recorded_stage_delta(self):
        before = audit_checkout(self.root, revision=self.revision)
        self._ledger(self._record("CODED_UNFINISHED"))
        after = audit_checkout(self.root, revision=self.revision)
        result = compare_reports(before, after)
        self.assertEqual(result["reported_promotions"], 1)
        self.assertEqual(result["reported_downgrades"], 0)
        self.assertEqual(result["changes"][0]["task_id"], "CA-0001")
        self.assertTrue(result["changes"][0]["requires_independent_proof"])

    def test_invented_ci_requires_run_receipts(self):
        self._ledger(self._record("TESTED_CI"))
        with self.assertRaisesRegex(MentorAuditError, "missing CI"):
            audit_checkout(self.root, revision=self.revision)

    def test_missing_test_proof_refuses_claim(self):
        item = self._record("TESTED")
        item["tests"] = []
        self._ledger(item)
        with self.assertRaisesRegex(MentorAuditError, "executed tests"):
            audit_checkout(self.root, revision=self.revision)

    def test_traversal_and_missing_evidence_refuse(self):
        item = self._record()
        item["source_paths"] = ["../other/secret.py"]
        self._ledger(item)
        with self.assertRaises(MentorAuditError):
            audit_checkout(self.root, revision=self.revision)

    def test_extra_and_duplicate_task_rows_refused(self):
        index = self.root / INDEX
        with index.open("a", encoding="utf-8") as stream:
            stream.write("| CA-0001 | 01 | another claim |\n")
        with self.assertRaisesRegex(MentorAuditError, "bad task"):
            audit_checkout(self.root, revision=self.revision)

    def test_atlas_loss_is_visible_failure_not_task_promotion(self):
        self._write(DOCUMENTS[2], "# Atlas\n### CA-0001\n")
        result = audit_checkout(self.root, revision=self.revision)
        self.assertEqual(result["summary"]["failed_document_checks"], 1)
        self.assertEqual(result["findings"][0]["kind"], "atlas_mismatch")
        self.assertEqual(result["summary"]["stages"]["NOT_WORKED_ON"], 780)

    def test_cli_audit_and_task_does_not_create_writer(self):
        output = self.root / "mentor-report.json"
        with patch("sofia.core.mentor.audit._head", return_value=self.revision):
            with redirect_stdout(io.StringIO()):
                code = main(["audit", "--repo", str(self.root), "--output", str(output)])
            self.assertEqual(code, 0)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["total_tasks"], 780)
            with redirect_stdout(io.StringIO()) as written:
                code = main(["audit", "--repo", str(self.root), "--task", "ML-002"])
            self.assertEqual(code, 0)
            self.assertIn("ML-002", written.getvalue())
        self.assertFalse(list(self.root.glob("*.db")))

    def test_reports_reject_unknown_schema_and_inventory(self):
        initial = audit_checkout(self.root, revision=self.revision)
        other = dict(initial)
        other["schema"] = "untrusted"
        with self.assertRaises(MentorAuditError):
            compare_reports(initial, other)
        other = dict(initial)
        other["tasks"] = initial["tasks"][:-1]
        with self.assertRaises(MentorAuditError):
            compare_reports(initial, other)


if __name__ == "__main__":
    unittest.main()
