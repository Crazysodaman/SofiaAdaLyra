"""Read-only, exact-checkout Platform 1.0 component-test inventory.

This produces PRE-FLIGHT evidence, never installed-host or production approval.
The canonical 38-row acceptance matrix remains authoritative. Every row
requires separate signed Windows/Debian installation and operator receipts.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree

SCHEMA = "aegis.platform.acceptance-preflight.v1"
COUNT = 38

# These are *narrow* unit/process/contract probes. A listed file is not
# evidence that the complete release-level acceptance requirement is met.
PROBES: dict[int, tuple[str, ...]] = {
    1: ("test_ops_platform_install.py", "test_ops_platform_release_staging.py"),
    2: ("test_platform_optional_dependencies.py", "test_platform_import_isolation.py"),
    3: ("test_platform_optional_dependencies.py", "test_platform_import_isolation.py"),
    4: ("test_platform_installation_identity.py",),
    5: ("test_rust_platform_service.py", "test_platform_service_session.py"),
    6: ("test_rust_platform_scm.py",),
    7: ("test_rust_platform_service.py",),
    8: ("test_rust_platform_service.py", "test_platform_service_lock_security.py"),
    9: ("test_rust_platform_service.py",),
    11: ("test_safe_operator_stop_revision.py", "test_safe_permission_state_loss.py"),
    12: ("test_safe_permission_state_loss.py", "test_core_link_rust_authority.py"),
    13: ("test_ops_fleet_atomic_enrollment.py",),
    14: ("test_ops_fleet_removal_authority.py",),
    16: ("test_fleet_stale_trust_regression.py",),
    17: ("test_module_lifecycle_v1.py",),
    18: ("test_module_lifecycle_v1.py",),
    19: ("test_ops_platform_install.py", "test_ops_platform_cache_security.py"),
    20: ("test_platform_installation_identity.py",),
    21: ("test_signed_core_definitions.py", "test_core_definition_path_security.py"),
    25: ("test_platform_release_contract.py",),
    26: ("test_platform_service_lock_security.py",),
    27: ("test_rust_platform_service.py", "test_rust_platform_scm.py"),
    28: ("test_platform_optional_dependencies.py", "test_component_artifact_separation.py"),
    29: ("test_platform_release_verifier.py", "test_ops_signed_vm_release.py"),
    38: ("test_ui_aegis_theme_contract.py",),
}

BLOCKED_BY_MISSING_INTEGRATION = frozenset(set(range(1, COUNT + 1)) - PROBES.keys())
assert len(PROBES) == 25 and len(BLOCKED_BY_MISSING_INTEGRATION) == 13


def _case_file(case: ElementTree.Element) -> str:
    direct = case.attrib.get("file", "")
    if direct:
        return Path(direct.replace("\\", "/")).name
    classname = case.attrib.get("classname", "")
    for part in reversed(classname.split(".")):
        if part.startswith("test_"):
            return part if part.endswith(".py") else part + ".py"
    return ""


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
        timeout=10, check=True,
    )
    sha = result.stdout.strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("Git returned invalid exact checkout SHA")
    return sha


def make_report(junit_path: Path | None, source_sha: str, platform: str) -> dict:
    """Build a conservative row-by-row snapshot from actual JUnit testcases."""
    observed: dict[str, list[str]] = defaultdict(list)
    source = "JUNIT_UNAVAILABLE"
    if junit_path is not None and junit_path.is_file():
        source = "JUNIT_TESTCASES"
        root = ElementTree.parse(junit_path).getroot()
        for case in root.iter("testcase"):
            filename = _case_file(case)
            result = "PASS"
            if case.find("failure") is not None or case.find("error") is not None:
                result = "FAIL"
            elif case.find("skipped") is not None:
                result = "SKIP"
            if filename:
                observed[filename].append(result)

    rows = []
    for number in range(1, COUNT + 1):
        configured = PROBES.get(number, ())
        results = [result for filename in configured for result in observed.get(filename, ())]
        if not configured:
            level = "BLOCKED_MISSING_INTEGRATION"
        elif not results:
            level = "PROBE_NOT_RUN"
        elif "FAIL" in results:
            level = "COMPONENT_FAIL"
        elif "SKIP" in results:
            level = "PARTIAL_OR_OS_SKIPPED"
        elif not all(any(observed.get(filename)) for filename in configured):
            level = "PARTIAL_OR_OS_SKIPPED"
        else:
            level = "COMPONENT_PASS_ONLY"
        rows.append({
            "row_id": f"{number:02d}",
            "preflight": level,
            "mapped_test_files": list(configured),
            "observed_cases": len(results),
            "acceptance": "NOT_CLAIMED",
            "signed_installed_host_receipt": "REQUIRED",
        })
    return {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "runner": platform,
        "junit_source": source,
        "release_accepted": False,
        "production_authorized": False,
        "row_count": len(rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = make_report(args.junit, _git_sha(), sys.platform)
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
