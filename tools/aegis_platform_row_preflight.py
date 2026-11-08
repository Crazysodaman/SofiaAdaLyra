"""Read-only, exact-checkout Platform 1.0 component-test inventory.

This produces PRE-FLIGHT evidence, never installed-host or production approval.
The canonical 38-row acceptance matrix remains authoritative. Every row
requires separate signed Windows/Debian installation and operator receipts.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import re
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


# E-004: strictly read-only *evidence intake*, NOT another installer/attestor.
# These file names describe Team E's pending receipt bundle only. They are not
# Team A's management protocol, B's signed package format or an approval API.
D028_HOST_IDS = ("W-EMPTY", "D-HUB", "D-CLIENT", "W-PEER")
D028_PHASE_IDS = (
    "BASELINE", "OFFLINE_SEED", "OWNER_ENABLED_PRIMARY", "SELECTIVE_CATALOG",
    "TRANSFER_AND_NEGATIVES", "COEXISTENCE_AND_RETENTION",
    "REPLICA_AND_RECOVERY", "UI_AND_RUNBOOK",
)
D028_EVIDENCE_FILES = (
    "release-manifest.json", "host-inventory.json", "signed-artifacts.json",
    "cross-host-receipts.json", "network-denials.json", "backup-restore.json",
)
D028_TOPOLOGY_PATH = (
    Path(__file__).resolve().parent.parent
    / "test" / "fixtures" / "aegis_d028" / "qa_four_host_topology.json"
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\\Z")


def _safe_evidence_path(root: Path, relative: str) -> Path:
    """Restrict intake to existing local regular files, never link chains."""
    if (not isinstance(relative, str) or not relative
            or relative.startswith(("/", "\\"))
            or "\\" in relative or ":" in relative
            or ".." in Path(relative).parts):
        raise ValueError("invalid evidence relative path")
    parts = Path(relative).parts
    p = root
    for part in parts:
        p = p / part
        if p.is_symlink():
            raise ValueError("evidence symlinks are forbidden")
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError("evidence must remain inside bundle")
    return p


def _read_bounded_json(root: Path, relative: str) -> dict | None:
    """Read strictly bounded, data-only metadata; never treat it as a grant."""
    path = _safe_evidence_path(root, relative)
    if not path.is_file():
        return None
    if path.stat().st_size > 65536:
        raise ValueError("oversized evidence metadata")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("evidence object required")
    return loaded


def make_d028_four_host_preflight(
    source_sha: str, *, topology: dict, evidence_dir: Path | None = None,
) -> dict:
    """Inspect one lab plan/receipt set, with *no* network, signatures or effects.

    Metadata cannot certify native OS runtime, signatures or owner permission.
    Even an apparently complete fixture always requires B's canonical signed
    release and independent E witnesses. No scenario may become PASS here.
    """
    if (not isinstance(source_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None):
        raise ValueError("full exact checkout SHA required")
    if not isinstance(topology, dict):
        raise ValueError("topology object required")
    if (topology.get("schema") != "aegis.qa.d028.disposable-four-host-plan.v1"
            or topology.get("state") != "PLAN_ONLY"
            or topology.get("production_authorized") is not False
            or topology.get("release_accepted") is not False
            or topology.get("live_production_targets") != []
            or topology.get("actual_host_ids") != []):
        raise ValueError("unsafe, modified or production-facing topology")
    hosts = topology.get("hosts", [])
    if (not isinstance(hosts, list) or len(hosts) != 4
            or any(not isinstance(h, dict) for h in hosts)
            or {h.get("id") for h in hosts} != set(D028_HOST_IDS)
            or any(h.get("platform_id") != "OBSERVE_AFTER_INSTALL" for h in hosts)):
        raise ValueError("topology must contain four unexecuted lab hosts")
    roles = {h["id"]: h.get("role") for h in hosts}
    if (roles != {"W-EMPTY": "EMPTY_PLATFORM_CLIENT",
                  "D-HUB": "SOLE_PRIMARY_HUB",
                  "D-CLIENT": "ENROLLED_INDEPENDENT_RECIPIENT",
                  "W-PEER": "ENROLLED_SENDER_PEER"}):
        raise ValueError("one initial lab primary only")
    logical = topology.get("logical_library", {})
    if (not isinstance(logical, dict) or logical.get("primary_count") != 1
            or logical.get("primary_test_host") != "D-HUB"
            or logical.get("read_replica_test_hosts_initially") != []
            or logical.get("owner_authority") != "SAME_CANONICAL_PLATFORM_SAFE_STOP"
            or logical.get("publisher_signing_authority")
            != "EXTERNAL_INDEPENDENT_TRUST_ROOT"):
        raise ValueError("second primary, signer or owner authority not permitted")
    network = topology.get("network_isolation", {})
    if (not isinstance(network, dict) or network.get("user_production_lan") != "DENY"
            or network.get("real_host_dns_and_discovery") != "DISABLED"
            or network.get("no_real_addresses_or_hostnames_embedded") is not True
            or not str(network.get("wan", "")).startswith("DENY_BY_DEFAULT")):
        raise ValueError("disposable network isolation is mandatory")
    phases = topology.get("phase_sequence", [])
    if (not isinstance(phases, list) or len(phases) != len(D028_PHASE_IDS)
            or tuple(p.get("id") for p in phases) != D028_PHASE_IDS
            or any(p.get("status") != "NOT_EXECUTED" for p in phases)):
        raise ValueError("executed or altered phase is not a source fixture")
    if (topology.get("original_acceptance_rows") != COUNT
            or topology.get("required_completed_lib_cases") != len(LIB_ROWS)
            or topology.get("acceptance_claim") != "NOT_CLAIMED"
            or topology.get("proposed_real_primary_placement", {}).get(
                "deployment_authorized") is not False):
        raise ValueError("acceptance or real deployment forged")

    root = None
    missing = []
    invalid = []
    verified_byte_digests = []
    if evidence_dir is not None:
        root = evidence_dir
        if (root.is_symlink() or not root.is_dir()
                or not root.resolve().is_dir()):
            raise ValueError("evidence directory must be a real local directory")
        for name in D028_EVIDENCE_FILES:
            try:
                item = _read_bounded_json(root, name)
            except (ValueError, OSError, json.JSONDecodeError):
                invalid.append(name)
                continue
            if item is None:
                missing.append(name)
            elif item.get("source_sha") != source_sha:
                invalid.append(name + ":SOURCE_SHA_MISMATCH")
        # Metadata integrity is not publisher-authenticated software.
        try:
            signed = _read_bounded_json(root, "signed-artifacts.json")
        except (ValueError, OSError, json.JSONDecodeError):
            signed = None
        if signed is not None and signed.get("source_sha") == source_sha:
            artifacts = signed.get("artifacts", [])
            if not isinstance(artifacts, list) or len(artifacts) > 32:
                invalid.append("signed-artifacts.json:INVALID_COUNT")
                artifacts = []
            for idx, artifact in enumerate(artifacts):
                if not isinstance(artifact, dict):
                    invalid.append("artifact:INVALID_OBJECT")
                    continue
                name = artifact.get("path")
                expected = artifact.get("sha256")
                if (not isinstance(expected, str)
                        or _SHA256_PATTERN.fullmatch(expected) is None):
                    invalid.append(f"artifact[{idx}]:INVALID_SHA256")
                    continue
                try:
                    p = _safe_evidence_path(root, name)
                    if not p.is_file():
                        raise ValueError("artifact bytes absent")
                    digest = sha256()
                    with p.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != expected:
                        raise ValueError("artifact byte SHA256 mismatch")
                    verified_byte_digests.append(expected)
                except (ValueError, OSError):
                    invalid.append(f"artifact[{idx}]:BYTE_INTEGRITY_FAILED")
    cases = []
    for key, rows in LIB_ROWS.items():
        state = "NOT_EXECUTED"
        if root is not None:
            try:
                case = _read_bounded_json(root, key + ".json")
                if case is None:
                    missing.append(key + ".json")
                elif (case.get("scenario_id") != key
                      or case.get("source_sha") != source_sha):
                    state = "REJECTED_UNBOUND_CASE_RECEIPT"
                    invalid.append(key + ".json:UNBOUND")
                else:
                    state = "RECEIPT_PRESENT_INDEPENDENT_REVIEW_REQUIRED"
            except (ValueError, OSError, json.JSONDecodeError):
                state = "REJECTED_INVALID_CASE_RECEIPT"
                invalid.append(key + ".json:INVALID")
        cases.append({
            "scenario_id": key, "refined_platform_rows": [f"{i:02d}" for i in rows],
            "receipt_inspection": state,
            "acceptance": "NOT_CLAIMED",
            "signed_installed_host_witness": "NOT_VERIFIED",
        })
    return {
        "schema": "aegis.d028.four-host-evidence-intake.v1",
        "source_sha": source_sha,
        "host_ids": list(D028_HOST_IDS),
        "one_initial_primary": True,
        "initial_replica_count": 0,
        "topology_status": "PLAN_VALIDATED_NOT_EXECUTED",
        "evidence_dir_supplied": root is not None,
        "evidence_missing": sorted(set(missing)),
        "evidence_invalid": sorted(set(invalid)),
        "byte_digests_verified_only": verified_byte_digests,
        "publisher_signature_and_revocation": "NOT_INDEPENDENTLY_VERIFIED",
        "OS_installed_service_and_enrolled_SAFE": "NOT_INDEPENDENTLY_VERIFIED",
        "signed_Hub_index_and_peer_receipts": "NOT_INDEPENDENTLY_VERIFIED",
        "scenario_count": len(cases),
        "scenarios": cases,
        "release_accepted": False,
        "production_authorized": False,
        "acceptance": "NOT_CLAIMED",
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
    parser.add_argument("--d028-four-host", action="store_true",
                        help="Add read-only four-host plan/receipt inspection, never certify")
    parser.add_argument("--d028-evidence-dir", type=Path,
                        help="Optional local evidence bundle, never a trusted signed host verdict")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = make_report(
        args.junit, _git_sha(), sys.platform,
        include_artifact_library=args.include_artifact_library,
    )
    if args.d028_evidence_dir and not args.d028_four_host:
        parser.error("--d028-evidence-dir requires --d028-four-host")
    if args.d028_four_host:
        topology = json.loads(D028_TOPOLOGY_PATH.read_text(encoding="utf-8"))
        report["d028_four_host"] = make_d028_four_host_preflight(
            report["source_sha"], topology=topology,
            evidence_dir=args.d028_evidence_dir,
        )
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if args.d028_evidence_dir is not None:
        # A source-data intake cannot certify native service origin, a trusted
        # publisher root or installed-host independent observer. Never return
        # successful CI status from an unverified/fabricated receipt bundle.
        receipt = report["d028_four_host"]
        if receipt["evidence_invalid"] or receipt["evidence_missing"]:
            return 2  # Incomplete, stale, tampered or unsafe evidence.
        return 3  # Byte inventory only; independent signed-host review required.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
