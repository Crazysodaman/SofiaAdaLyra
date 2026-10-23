"""Static safety contract for operator-side Windows runtime diagnosis.

Windows process/SCM evidence must still be obtained from an actual Venus run.
These tests do NOT simulate or certify a live host.
"""
from __future__ import annotations

from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose_sofia_windows_runtime.ps1"


class WindowsReadOnlyObservationScriptTests(TestCase):
    def test_script_is_present_and_labels_unverified_runtime(self):
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("sofia.platform.runtime.windows-observation.v1", content)
        self.assertIn("no_child_bootstrap_or_stopped_application_unverified", content)
        self.assertIn("unknown_not_reading_database", content)
        self.assertIn("SCM RUNNING means wrapper alive", content)
        self.assertIn("headless service", content)
        self.assertIn("messages_redacted", content)

    def test_only_observation_apis_and_no_commands_for_mutation(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for call in ("Get-CimInstance", "Get-ItemProperty", "Get-WinEvent"):
            self.assertIn(call, text)
        # Script is operator-side, never launched by canonical Sofia.
        forbidden = (
            "Restart-Service", "Start-Service", "Stop-Service", "Set-Service",
            "Set-ItemProperty", "New-ItemProperty", "Remove-ItemProperty",
            "RegCreateKey", "Set-Content", "Out-File", "Invoke-Sqlcmd",
            "sqlite3", "Start-Process", "Stop-Process", "sc.exe config",
        )
        executable = "\n".join(
            line for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ).casefold()
        for item in forbidden:
            with self.subTest(forbidden=item):
                self.assertNotIn(item.casefold(), executable)

    def test_does_not_dump_private_commands_or_log_messages(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("$report | ConvertTo-Json -Depth 5", text)
        self.assertNotIn("stdout.log", text)
        self.assertNotIn("Get-Content", text)
        self.assertIn("windows_service_errors", text)
        self.assertIn("python_service_errors", text)
        self.assertIn("messages_redacted = $true", text)


if __name__ == "__main__":
    import unittest
    unittest.main()
