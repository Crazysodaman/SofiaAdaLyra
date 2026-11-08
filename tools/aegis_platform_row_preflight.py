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
    1: ("test_ops_platform_install.py", "test_ops_platform_release_staging.py", "test_ops_platform_installation.py"),
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
    19: ("test_ops_platform_install.py", "test_ops_platform_cache_security.py", "test_ops_platform_installation.py"),
    20: ("test_platform_installation_identity.py",),
    21: ("test_signed_core_definitions.py", "test_core_definition_path_security.py"),
    25: ("test_platform_release_contract.py",),
    26: ("test_platform_service_lock_security.py",),
    27: ("test_rust_platform_service.py", "test_rust_platform_scm.py"),
    28: ("test_platform_optional_dependencies.py", "test_component_artifact_separation.py"),
    29: ("test_platform_release_verifier.py", "test_ops_signed_vm_release.py"),
    38: ("test_ui_aegis_theme_contract.py",),
}

# AG-D028 LIB scenarios refine existing rows, never create row 39. This map is
# source-pinned to draft PR #248's release specification and must be reviewed
# again at the A/C/B integration contract freeze. It is NOT execution evidence.
LIB_ROWS: dict[str, tuple[int, ...]] = {
    "LIB-01": (1, 2, 3, 5, 28, 30, 38),
    "LIB-02": (1, 2, 3, 7, 28, 30, 33, 38),
    "LIB-03": (10, 11, 12, 13, 14, 19, 29, 31),
    "LIB-04": (2, 3, 21, 22, 24, 28, 35),
    "LIB-05": (21, 22, 23, 24, 26, 35),
    "LIB-06": (17, 18, 25, 28, 36),
    "LIB-07": (10, 11, 12, 13, 14, 17, 18, 19, 29, 31, 36),
    "LIB-08": (10, 11, 12, 13, 14, 21, 31, 37),
    "LIB-09": (17, 18, 19, 21, 25, 28, 29),
    "LIB-10": (8, 9, 19, 20, 26, 29),
    "LIB-11": (19, 25, 28, 29),
    "LIB-12": (19, 20, 26, 29, 37),
    "LIB-13": (10, 11, 12, 19, 22, 29, 37),
    "LIB-14": (30, 31, 32, 33, 34, 35, 36, 37, 38),
    "LIB-15": (1, 5, 8, 16, 19, 20, 29, 30),
    "LIB-16": (29, 30, 32, 33, 34, 35, 36, 37, 38),
}
assert tuple(LIB_ROWS) == tuple(f"LIB-{i:02d}" for i in range(1, 17))
assert all(set(rows) <= set(range(1, COUNT + 1)) for rows in LIB_ROWS.values())


def make_library_preflight() -> dict:
    """Conservative AG-D028 work inventory; NOT a signed host witness.

    Never ingest a JUnit result as release-level LIB acceptance. Host-specific
    authentication/signature/STOP/negative receipts are independently required.
    """
    return {
        "schema": "aegis.artifact-library.acceptance-preflight.v1",
        "source_spec": "AG-D028 PR #248 (draft; requires contract review)",
        "scenario_count": len(LIB_ROWS),
        "acceptance": "NOT_CLAIMED",
        "release_accepted": False,
        "production_authorized": False,
        "scenarios": [
            {
                "scenario_id": scenario,
                "refined_platform_rows": [f"{row:02d}" for row in rows],
                "preflight": "BLOCKED_NO_SIGNED_INSTALLED_HOST_EVIDENCE",
                "acceptance": "NOT_CLAIMED",
                "signed_windows_debian_host_receipts": "REQUIRED",
                "positive_negative_cases": "NOT_VERIFIED",
            }
            for scenario, rows in LIB_ROWS.items()
        ],
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
        ["git", "-c", f"safe.directory={Path.cwd().resolve()}", "rev-parse", "HEAD"],
        capture_output=True, text=True,
        timeout=10, check=True,
    )
    sha = result.stdout.strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("Git returned invalid exact checkout SHA")
    return sha


def make_report(
    junit_path: Path | None, source_sha: str, platform: str,
    *, include_artifact_library: bool = False,
) -> dict:
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
        elif not all(bool(observed.get(filename)) for filename in configured):
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
    report = {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "runner": platform,
        "junit_source": source,
        "release_accepted": False,
        "production_authorized": False,
        "row_count": len(rows),
        "rows": rows,
    }
    if include_artifact_library:
        report["artifact_library"] = make_library_preflight()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--include-artifact-library", action="store_true",
                        help="Include conservative LIB-01..16 preflight, never release PASS")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = make_report(
        args.junit, _git_sha(), sys.platform,
        include_artifact_library=args.include_artifact_library,
    )
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
