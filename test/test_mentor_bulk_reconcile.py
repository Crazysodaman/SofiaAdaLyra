"""Bulk reconciliation is a triage index, never a stage-promotion engine."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

from sofia.mentor.audit import MentorAuditError
from sofia.mentor.bulk_reconcile import _leads, reconcile_checkout


class TestBulkReconcile(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        records = []
        for name in [f"CA-{i:03d}" for i in range(1, 701)] + [
            f"{kind}-{i:03d}" for kind in ("ML", "GA") for i in range(1, 41)
        ]:
            records.append({"task_id": name, "phase": "00", "audited": False})
        for row in records[15:129]:
            row["audited"] = True
            row["stage"] = "TESTED"
        self.snapshot = {
            "source_revision": "a" * 40,
            "tasks": records,
        }
        road = self.root / "docs/development"
        road.mkdir(parents=True)
        rows = []
        for record in records:
            key = record["task_id"]
            rows.append(
                f"| {key} | - | Build | Unknown | Open | Open | Open | Open | "
                "Review src/sofia/life/coordinator.py and verified learning | "
                "Check original behavior. |"
            )
        (road / "v18-full-780-task-design-code-gate-status-2026-10-17.md").write_text(
            "\n".join(rows), encoding="utf-8"
        )
        (road / "v18-phase08-personality-status-evidence.json").write_text(
            json.dumps({"tasks": [
                {"id": records[i]["task_id"], "level": 3} for i in range(15)
            ]}), encoding="utf-8",
        )
        (road / "v18-unassessed-421-requirements-audit-2026-10-17.json").write_text(
            json.dumps({"tasks": [{
                "id": "CA-130",
                "candidate_tracked_source_paths_unverified": [
                    "src/sofia/life/coordinator.py"
                ],
            }]}), encoding="utf-8",
        )
        (self.root / "src/sofia/life").mkdir(parents=True)
        (self.root / "src/sofia/life/coordinator.py").write_text(
            "def example(): pass\n", encoding="utf-8"
        )
        self.tracked = {"src/sofia/life/coordinator.py"}

    def test_all_651_are_triaged_not_promoted(self):
        with patch("sofia.mentor.bulk_reconcile.audit_checkout",
                   return_value=self.snapshot), patch(
            "sofia.mentor.bulk_reconcile._git_files", return_value=self.tracked
        ):
            result = reconcile_checkout(self.root)
        self.assertEqual(result["summary"]["classified"], 129)
        self.assertEqual(result["summary"]["unverified_reconciled"], 651)
        self.assertEqual(result["summary"]["tasks_promoted"], 0)
        self.assertEqual(len(result["unverified_tasks"]), 651)
        row = next(r for r in result["unverified_tasks"]
                   if r["task_id"] == "CA-130")
        self.assertIn("src/sofia/life/coordinator.py", row["code_leads"])
        self.assertIsNone(row["code_implemented"])
        self.assertFalse(row["gate4_accepted"])
        self.assertFalse(row["tests_executed"])

    def test_missing_code_is_not_interpreted_as_missing_implementation(self):
        code, tests, basis = _leads(
            "CA-130", "Unrelated hardware requirements", {}, set()
        )
        self.assertEqual((code, tests, basis),
                         ([], [], "no_candidate_identified"))

    def test_conflicting_registers_fail_closed(self):
        self.snapshot["tasks"][0]["audited"] = True
        self.snapshot["tasks"][0]["stage"] = "TESTED"
        with patch("sofia.mentor.bulk_reconcile.audit_checkout",
                   return_value=self.snapshot), patch(
            "sofia.mentor.bulk_reconcile._git_files", return_value=self.tracked
        ):
            with self.assertRaisesRegex(MentorAuditError, "competing"):
                reconcile_checkout(self.root)

    def test_duplicate_master_requirement_refused(self):
        master = self.root / "docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md"
        master.write_text(master.read_text(encoding="utf-8") +
                          "\n| CA-130 | - | Build | Unknown | x | x | x | x | duplicate | x |\n",
                          encoding="utf-8")
        with patch("sofia.mentor.bulk_reconcile.audit_checkout",
                   return_value=self.snapshot):
            with self.assertRaises(MentorAuditError):
                reconcile_checkout(self.root)
