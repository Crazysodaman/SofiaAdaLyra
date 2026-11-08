"""Actual native TUI CLI evidence; component-only, NOT signed installed-host QA."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "target" / "debug" / ("aegis_tui.exe" if os.name == "nt" else "aegis_tui")
OUT = ROOT / "aegis-native-tui-evidence.json"


def capture(option: str, exit_code: int) -> dict[str, object]:
    result = subprocess.run(
        [str(BIN), option], stdin=subprocess.DEVNULL, capture_output=True,
        text=True, timeout=20, check=False,
        env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
    )
    if result.returncode != exit_code:
        raise AssertionError(f"{option}: exit={result.returncode}; {result.stderr!r}")
    if "\x1b" in result.stdout or "\x1b" in result.stderr:
        raise AssertionError("NO_COLOR incorrectly emitted ANSI")
    return {"option": option, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main() -> int:
    sha = os.environ.get("EXPECTED_SOURCE_SHA", "")
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise AssertionError("exact PR head SHA is required")
    if not BIN.is_file():
        raise AssertionError("native binary missing; cannot invent a receipt")
    checks = [
        capture("--plain", 0),
        capture("--status", 3),
        capture("--library-status", 3),
        capture("--library-json", 3),
        capture("--install", 2),
    ]
    data = json.loads(str(checks[3]["stdout"]))
    if data.get("source") != "UNVERIFIED" or data.get("actions_enabled") is not False:
        raise AssertionError("offline service incorrectly trusted")
    for field in ("catalog", "downloaded", "verified", "staged", "installed",
                  "active", "received_bytes", "verified_bytes"):
        if data.get(field, "MISSING") is not None:
            raise AssertionError(f"{field} must be null/unknown")
    if "Library > History" not in str(checks[0]["stdout"]):
        raise AssertionError("expected native library menu")
    if "Unknown option" not in str(checks[4]["stderr"]):
        raise AssertionError("unexpected executable command accepted")
    receipt = {
        "schema": "aegis.ui.native-test-evidence.v1",
        "evidence_class": "COMPONENT_ONLY_NOT_INSTALLED_HOST",
        "source_sha": sha,
        "runner_os": os.environ.get("RUNNER_OS", "UNKNOWN"),
        "binary_sha256": hashlib.sha256(BIN.read_bytes()).hexdigest(),
        "commands": checks,
        "signed_package_digest": None,
        "installed_service_origin": None,
        "authenticated_platform_id": None,
        "owner_approval_receipt": None,
        "lib14_or_lib16_certification": "NOT_TESTED",
    }
    OUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("AEGIS_NATIVE_TUI_COMPONENT_EVIDENCE=PASS")
    print("EXACT_SOURCE_SHA=" + sha)
    print("BINARY_SHA256=" + str(receipt["binary_sha256"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
