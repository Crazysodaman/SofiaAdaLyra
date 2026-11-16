"""Aggregate conservative Platform 38-row and LIB-01..16 acceptance evidence.

This produces a separate machine-readable report.  It never edits the
authoritative status text in ``docs/development/PLATFORM_1_0_ACCEPTANCE.md`` and
never emits a release GO verdict.  A row/scenario is ``PASS`` only when every
required evidence field is present and internally consistent; otherwise it is
``FAIL``, ``BLOCKED`` or ``NOT_TESTED``.

The collector verifies ``release-manifest.json`` and
``release-signature.json`` with the canonical ``PlatformReleaseVerifier`` and a
caller-supplied Ed25519 public key, fingerprint and signer key ID.  It never
trusts self-declared ``release_signature_verified`` booleans, and a missing or
invalid release signature leaves every mapped row ``BLOCKED``.  The overall
``release_verdict`` is always ``NO_GO``.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_ROOT / "src"))
    sys.path.insert(0, str(_ROOT))

from sofia.platform.ops.platform_release import (  # noqa: E402
    PlatformReleaseRejected, PlatformReleaseVerifier,
)
from sofia.sdk.cognition_json import loads_strict_model_json  # noqa: E402
from sofia.sdk.platform_release import PlatformReleaseManifest  # noqa: E402

from tools.aegis_platform_row_preflight import (  # noqa: E402
    COUNT, LIB_ROWS, PROBES, make_report,
)

SCHEMA = "aegis.platform.acceptance-collector.v1"
ROW_RECEIPT_SCHEMA = "aegis.platform.acceptance.row-receipts.v1"
CAMPAIGN_SCHEMA = "aegis.d028.four-host-campaign.v1"

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_DEFAULT_MAX_AGE_DAYS = 30
_REQUIRED_RELEASE_KINDS = frozenset({
    "sdk", "platform", "service", "python-runtime",
    "dependency-lock", "sbom", "provenance",
})

ROW_RECEIPT_FIELDS = (
    "windows", "debian12", "ci_run_url", "test_ids", "reviewer",
    "witnessed_at", "release_manifest_sha256", "negative_cases",
)
OS_RECEIPT_FIELDS = (
    "host_id", "observed", "result", "service_binary_sha256",
    "artifact_manifest_sha256", "signer_key_id", "witnessed_at",
    "receipt_sha256", "negative_cases",
)
ROW_RECEIPTS_TOP_FIELDS = frozenset({"schema", "source_sha", "rows"})
SIGNATURE_FIELDS = frozenset({"signer_key_id", "signature_b64"})


class CollectorError(RuntimeError):
    """Raised when collector input is malformed."""


def _read_json(path: Path, *, limit: int = 1024 * 1024) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise CollectorError(f"collector input is not a regular file: {path}")
    size = path.stat().st_size
    if not 1 <= size <= limit:
        raise CollectorError(f"collector input is outside bounded size: {path}")
    loaded = loads_strict_model_json(path.read_bytes().decode("utf-8"))
    if type(loaded) is not dict:
        raise CollectorError(f"collector input must be a JSON object: {path}")
    return loaded


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha() -> str:
    repo = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", "rev-parse", "HEAD"],
        cwd=str(repo), capture_output=True, text=True, timeout=30,
    )
    if completed.returncode != 0:
        raise CollectorError("cannot observe exact source SHA")
    value = completed.stdout.strip()
    if not _SHA40.fullmatch(value):
        raise CollectorError("Git returned an invalid source SHA")
    return value


def _parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _timestamp_issues(
    value: object, *, now: datetime, max_age_days: int, label: str,
) -> list[str]:
    witnessed = _parse_timestamp(value)
    if witnessed is None:
        return [f"{label}:WITNESSED_AT_INVALID"]
    issues: list[str] = []
    if witnessed > now + timedelta(hours=1):
        issues.append(f"{label}:RECEIPT_FROM_FUTURE")
    if now - witnessed > timedelta(days=max_age_days):
        issues.append(f"{label}:RECEIPT_STALE")
    return issues


def _load_trusted_key(
    public_key: Path | None, key_sha256: str | None, signer_key_id: str | None,
) -> tuple[bytes | None, list[str]]:
    if (public_key is None or not key_sha256
            or not isinstance(signer_key_id, str) or not signer_key_id):
        return None, ["RELEASE_TRUST_ROOT_ABSENT"]
    if not _SHA64.fullmatch(str(key_sha256)):
        return None, ["RELEASE_TRUSTED_KEY_SHA256_INVALID"]
    path = Path(public_key).absolute()
    if path.is_symlink() or not path.is_file():
        return None, ["RELEASE_TRUSTED_PUBLIC_KEY_UNAVAILABLE"]
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != key_sha256:
        return None, ["RELEASE_TRUSTED_KEY_SHA256_MISMATCH"]
    try:
        key = serialization.load_pem_public_key(raw)
    except (TypeError, ValueError):
        return None, ["RELEASE_TRUSTED_PUBLIC_KEY_INVALID"]
    if not isinstance(key, Ed25519PublicKey):
        return None, ["RELEASE_TRUSTED_PUBLIC_KEY_NOT_ED25519"]
    return raw, []


def collect_release_evidence(
    release_dir: Path | None, *, source_sha: str,
    trusted_public_key: Path | None = None,
    trusted_key_sha256: str | None = None,
    trusted_signer_key_id: str | None = None,
) -> dict[str, object]:
    """Read and cryptographically verify the assembled release inventory."""
    if release_dir is None:
        return {
            "present": False,
            "source_sha_match": False,
            "signature_present": False,
            "signature_verified": False,
            "required_kinds_complete": False,
            "artifact_digests_valid": False,
            "asset_digests": {},
            "manifest_digest": None,
            "manifest_sha256": None,
            "signer_key_id": None,
            "issues": ["RELEASE_DIRECTORY_ABSENT"],
        }
    root = Path(release_dir).absolute()
    issues: list[str] = []
    if root.is_symlink() or not root.is_dir():
        raise CollectorError("release directory must be a local directory")
    manifest_path = root / "release-manifest.json"
    signature_path = root / "release-signature.json"
    digests_path = root / "artifact-digests.json"
    manifest = None
    if not manifest_path.is_file():
        issues.append("release-manifest.json missing")
    else:
        try:
            manifest = PlatformReleaseManifest.from_payload(
                _read_json(manifest_path, limit=131072)
            )
        except (CollectorError, ValueError, TypeError) as error:
            issues.append(f"release-manifest.json: {error}")
    signature_present = False
    signature_verified = False
    signer_key_id = None
    trusted_key, trust_issues = _load_trusted_key(
        trusted_public_key, trusted_key_sha256, trusted_signer_key_id,
    )
    issues.extend(trust_issues)
    if not signature_path.is_file():
        issues.append("release-signature.json missing")
    else:
        try:
            envelope = _read_json(signature_path, limit=16384)
            if set(envelope) != SIGNATURE_FIELDS:
                issues.append("release-signature.json noncanonical")
            else:
                signature_present = True
                signer_key_id = envelope["signer_key_id"]
                if signer_key_id != trusted_signer_key_id:
                    issues.append("release-signature.json:UNEXPECTED_SIGNER")
                elif (trusted_key is not None and manifest is not None
                      and not trust_issues):
                    verifier = PlatformReleaseVerifier(
                        {trusted_signer_key_id: trusted_key}
                    )
                    try:
                        verifier.verify_manifest_reference(
                            manifest.to_payload(),
                            signature_b64=envelope["signature_b64"],
                            signer_key_id=trusted_signer_key_id,
                            expected_source_sha=source_sha,
                            expected_target=manifest.target,
                            minimum_revision=manifest.revision,
                        )
                        signature_verified = True
                    except (PlatformReleaseRejected, OSError, ValueError,
                            TypeError) as error:
                        issues.append(
                            "release-signature.json:INVALID:"
                            f"{type(error).__name__}"
                        )
        except (CollectorError, ValueError) as error:
            issues.append(f"release-signature.json: {error}")
    if not signature_verified:
        issues.append("RELEASE_SIGNATURE_NOT_VERIFIED")
    manifest_digest = manifest.digest if manifest is not None else None
    manifest_sha256 = (
        sha256(manifest.canonical_bytes).hexdigest()
        if manifest is not None else None
    )
    source_sha_match = bool(manifest is not None and manifest.source_sha == source_sha)
    required_kinds_complete = bool(
        manifest is not None
        and _REQUIRED_RELEASE_KINDS <= {asset.kind for asset in manifest.assets}
    )
    if not source_sha_match:
        issues.append("release manifest source SHA mismatch")
    if not required_kinds_complete:
        issues.append("release manifest required asset kinds incomplete")
    manifest_assets = (
        {
            asset.reference.path: asset.reference.sha256
            for asset in manifest.assets
        }
        if manifest is not None else {}
    )
    asset_digests: dict[str, str] = dict(manifest_assets)
    artifact_digests_valid = False
    if manifest is None:
        issues.append("artifact digests cannot be checked without manifest")
    elif not digests_path.is_file():
        issues.append("artifact-digests.json missing")
    else:
        try:
            digests = _read_json(digests_path, limit=1024 * 1024)
            digest_issues: list[str] = []
            if digests.get("source_sha") != source_sha:
                digest_issues.append("artifact-digests source SHA mismatch")
            if digests.get("manifest_digest") != manifest_digest:
                digest_issues.append("artifact-digests manifest digest mismatch")
            if digests.get("manifest_sha256") != manifest_sha256:
                digest_issues.append("artifact-digests manifest file digest mismatch")
            entries = digests.get("assets")
            if not isinstance(entries, list) or not entries:
                digest_issues.append("artifact-digests has no assets")
            else:
                declared: dict[str, str] = {}
                for entry in entries:
                    if type(entry) is not dict:
                        digest_issues.append("artifact-digests entry not object")
                        continue
                    path = entry.get("path")
                    digest = entry.get("sha256")
                    if (not isinstance(path, str)
                            or not _SHA64.fullmatch(str(digest or ""))):
                        digest_issues.append("artifact-digests entry invalid")
                        continue
                    declared[path] = digest
                if set(declared) != set(manifest_assets):
                    digest_issues.append("artifact-digests asset set mismatch")
                for path, expected in manifest_assets.items():
                    if declared.get(path) != expected:
                        digest_issues.append(
                            f"artifact-digests digest mismatch: {path}"
                        )
                    asset = root / "assets" / path
                    if not asset.is_file() or asset.is_symlink():
                        digest_issues.append(
                            f"artifact bytes unavailable: {path}"
                        )
                    elif _sha256_file(asset) != expected:
                        digest_issues.append(
                            f"artifact bytes digest mismatch: {path}"
                        )
            issues.extend(digest_issues)
            artifact_digests_valid = not digest_issues
        except (CollectorError, ValueError) as error:
            issues.append(f"artifact-digests.json: {error}")
    return {
        "present": True,
        "source_sha_match": source_sha_match,
        "signature_present": signature_present,
        "signature_verified": signature_verified,
        "required_kinds_complete": required_kinds_complete,
        "artifact_digests_valid": artifact_digests_valid,
        "asset_digests": asset_digests,
        "manifest_digest": manifest_digest,
        "manifest_sha256": manifest_sha256,
        "signer_key_id": signer_key_id,
        "issues": sorted(set(issues)),
    }


def _validate_os_receipt(
    value: object, *, source_sha: str, release: dict[str, object],
    now: datetime, max_age_days: int,
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    invalid: list[str] = []
    if type(value) is not dict:
        return ["OS_RECEIPT_NOT_OBJECT"], []
    for field in OS_RECEIPT_FIELDS:
        if field not in value:
            missing.append(field)
    if missing:
        return sorted(set(missing)), []
    if set(value) != set(OS_RECEIPT_FIELDS):
        invalid.append("OS_RECEIPT_UNKNOWN_FIELDS")
    if value.get("observed") is not True:
        invalid.append("OS_RECEIPT_NOT_OBSERVED")
    if value.get("result") != "PASS":
        invalid.append("OS_RECEIPT_RESULT_NOT_PASS")
    if not isinstance(value.get("host_id"), str) or not value.get("host_id"):
        missing.append("host_id")
    if not _SHA64.fullmatch(str(value.get("service_binary_sha256", ""))):
        invalid.append("service_binary_sha256")
    if not _SHA64.fullmatch(str(value.get("artifact_manifest_sha256", ""))):
        invalid.append("artifact_manifest_sha256")
    if not _SHA64.fullmatch(str(value.get("receipt_sha256", ""))):
        invalid.append("receipt_sha256")
    negatives = value.get("negative_cases")
    if (not isinstance(negatives, list) or not negatives
            or any(not isinstance(item, str) or not item.strip()
                   for item in negatives)):
        invalid.append("OS_RECEIPT_NEGATIVE_CASES_MISSING")
    invalid.extend(_timestamp_issues(
        value.get("witnessed_at"), now=now,
        max_age_days=max_age_days, label="OS_RECEIPT",
    ))
    if release.get("signer_key_id") is not None:
        if value.get("signer_key_id") != release["signer_key_id"]:
            invalid.append("OS_RECEIPT_SIGNER_MISMATCH")
    if release.get("manifest_digest") is not None:
        if value.get("artifact_manifest_sha256") != release["manifest_digest"]:
            invalid.append("OS_RECEIPT_MANIFEST_MISMATCH")
    service_digests = {
        digest for path, digest in release.get("asset_digests", {}).items()
        if path.casefold().startswith("aegis-platform-service")
    }
    if service_digests and value.get("service_binary_sha256") not in service_digests:
        invalid.append("OS_RECEIPT_SERVICE_DIGEST_MISMATCH")
    return sorted(set(missing)), sorted(set(invalid))


def load_row_receipts(
    path: Path | None, *, source_sha: str,
) -> dict[str, object]:
    if path is None:
        return {"present": False, "schema_ok": False, "rows": {}, "issues": ["ROW_RECEIPTS_ABSENT"]}
    try:
        document = _read_json(path, limit=4 * 1024 * 1024)
    except (ValueError, UnicodeDecodeError) as error:
        raise CollectorError(f"invalid row-receipt JSON: {error}") from error
    issues: list[str] = []
    if set(document) != ROW_RECEIPTS_TOP_FIELDS:
        issues.append("ROW_RECEIPT_FIELDS_MISMATCH")
    if document.get("schema") != ROW_RECEIPT_SCHEMA:
        issues.append("ROW_RECEIPT_SCHEMA_MISMATCH")
    if document.get("source_sha") != source_sha:
        issues.append("ROW_RECEIPT_SOURCE_SHA_MISMATCH")
    rows = document.get("rows")
    if not isinstance(rows, dict):
        return {
            "present": True, "schema_ok": False, "rows": {},
            "issues": issues + ["ROW_RECEIPTS_NOT_OBJECT"],
        }
    return {
        "present": True,
        "schema_ok": not issues,
        "rows": rows,
        "issues": issues,
    }


def _platform_rows(
    *,
    base_report: dict[str, Any],
    row_receipts: dict[str, object],
    release: dict[str, object],
    junit_present: bool,
    now: datetime,
    max_age_days: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for base in base_report["rows"]:
        number = int(base["row_id"])
        configured = list(PROBES.get(number, ()))
        missing: list[str] = []
        invalid: list[str] = []
        component_ready = False
        if not configured:
            status = "BLOCKED"
            missing.append("NO_MAPPED_TEST")
        elif not junit_present:
            status = "NOT_TESTED"
            missing.append("JUNIT_EVIDENCE_ABSENT")
        elif base["preflight"] == "COMPONENT_FAIL":
            status = "FAIL"
            invalid.append("MAPPED_TEST_FAILED")
        elif base["preflight"] != "COMPONENT_PASS_ONLY":
            status = "BLOCKED"
            missing.append(str(base["preflight"]))
        else:
            status = "BLOCKED"
            component_ready = True
        receipt = (
            row_receipts.get("rows", {}).get(f"{number:02d}")
            if row_receipts.get("present") else None
        )
        if status != "FAIL":
            if not row_receipts.get("present"):
                missing.append("ROW_RECEIPT_ABSENT")
            elif not row_receipts.get("schema_ok"):
                missing.extend(row_receipts.get("issues", []))
            elif type(receipt) is not dict:
                missing.append("ROW_RECEIPT_ABSENT")
            else:
                if set(receipt) - set(ROW_RECEIPT_FIELDS):
                    invalid.append("ROW_RECEIPT_UNKNOWN_FIELDS")
                for field in ROW_RECEIPT_FIELDS:
                    if field not in receipt or receipt[field] in (None, "", []):
                        missing.append(field)
                invalid.extend(_timestamp_issues(
                    receipt.get("witnessed_at"), now=now,
                    max_age_days=max_age_days, label="ROW_RECEIPT",
                ))
                if not isinstance(receipt.get("test_ids"), list) or not receipt.get("test_ids"):
                    missing.append("test_ids")
                if not isinstance(receipt.get("ci_run_url"), str) or not receipt.get("ci_run_url"):
                    missing.append("ci_run_url")
                if not isinstance(receipt.get("reviewer"), str) or not receipt.get("reviewer"):
                    missing.append("reviewer")
                negatives = receipt.get("negative_cases")
                if (not isinstance(negatives, list) or not negatives
                        or any(not isinstance(item, str) or not item.strip()
                               for item in negatives)):
                    invalid.append("ROW_RECEIPT_NEGATIVE_CASES_MISSING")
                if receipt.get("release_manifest_sha256") != release.get("manifest_sha256"):
                    invalid.append("ROW_RECEIPT_MANIFEST_DIGEST_MISMATCH")
                for platform_name in ("windows", "debian12"):
                    os_missing, os_invalid = _validate_os_receipt(
                        receipt.get(platform_name),
                        source_sha=base_report["source_sha"],
                        release=release, now=now,
                        max_age_days=max_age_days,
                    )
                    missing.extend(
                        f"{platform_name}.{field}" for field in os_missing
                    )
                    invalid.extend(
                        f"{platform_name}.{field}" for field in os_invalid
                    )
            if not release.get("present"):
                missing.append("RELEASE_EVIDENCE_ABSENT")
            else:
                for field in (
                    "source_sha_match", "signature_present",
                    "signature_verified", "required_kinds_complete",
                    "artifact_digests_valid",
                ):
                    if not release.get(field):
                        missing.append(f"RELEASE_{field.upper()}")
        if invalid:
            status = "FAIL"
        elif status != "FAIL" and status != "NOT_TESTED":
            status = "PASS" if component_ready and not missing else "BLOCKED"
        rows.append({
            "row_id": base["row_id"],
            "status": status,
            "status_scope": "COMPONENT_AND_DECLARED_HOST_RECEIPTS_ONLY",
            "mapped_test_files": configured,
            "observed_cases": base["observed_cases"],
            "missing": sorted(set(missing)),
            "invalid": sorted(set(invalid)),
            "acceptance": "NOT_CLAIMED",
            "signed_installed_host_certified": False,
        })
    return rows


def load_campaign_report(
    path: Path | None, *, source_sha: str,
) -> dict[str, object]:
    if path is None:
        return {"present": False, "report": None, "issues": ["CAMPAIGN_REPORT_ABSENT"]}
    document = _read_json(path, limit=8 * 1024 * 1024)
    issues: list[str] = []
    if document.get("schema") != CAMPAIGN_SCHEMA:
        issues.append("CAMPAIGN_SCHEMA_MISMATCH")
    if document.get("source_sha") != source_sha:
        issues.append("CAMPAIGN_SOURCE_SHA_MISMATCH")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(LIB_ROWS):
        issues.append("CAMPAIGN_SCENARIO_COUNT")
    return {"present": True, "report": document, "issues": issues}


def _library_scenarios(
    *, campaign: dict[str, object],
) -> list[dict[str, object]]:
    scenarios: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    report = campaign.get("report")
    if isinstance(report, dict):
        for item in report.get("scenarios", []):
            if type(item) is dict and isinstance(item.get("scenario_id"), str):
                by_id[item["scenario_id"]] = item
    for scenario_id, rows in LIB_ROWS.items():
        item = by_id.get(scenario_id)
        if not campaign.get("present"):
            status = "NOT_TESTED"
            missing = ["CAMPAIGN_REPORT_ABSENT"]
            invalid: list[str] = []
        elif campaign.get("issues"):
            status = "BLOCKED"
            missing = list(campaign.get("issues", []))
            invalid = []
        elif item is None:
            status = "NOT_TESTED"
            missing = ["SCENARIO_RECEIPT_ABSENT"]
            invalid = []
        else:
            status = str(item.get("status", "BLOCKED"))
            if status not in {"PASS", "FAIL", "BLOCKED", "NOT_TESTED", "SIMULATED"}:
                status = "FAIL"
            missing = list(item.get("missing", []))
            invalid = list(item.get("invalid", []))
            if status == "PASS" and (missing or invalid):
                status = "BLOCKED"
        scenarios.append({
            "scenario_id": scenario_id,
            "refined_platform_rows": [f"{row:02d}" for row in rows],
            "status": status,
            "status_scope": (
                "SIMULATED_LOCAL_DISPOSABLE" if status == "SIMULATED"
                else "EVIDENCE_BUNDLE_ONLY"
            ),
            "missing": sorted(set(missing)),
            "invalid": sorted(set(invalid)),
            "acceptance": "NOT_CLAIMED",
            "installed_host_certified": False,
        })
    return scenarios


def _counts(values: list[str]) -> dict[str, int]:
    counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "NOT_TESTED": 0, "SIMULATED": 0}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def collect(
    *,
    junit_path: Path | None,
    source_sha: str,
    runner: str,
    release_dir: Path | None = None,
    row_receipts_path: Path | None = None,
    campaign_report_path: Path | None = None,
    trusted_public_key: Path | None = None,
    trusted_key_sha256: str | None = None,
    trusted_signer_key_id: str | None = None,
    now: datetime | None = None,
    max_age_days: int = _DEFAULT_MAX_AGE_DAYS,
) -> dict[str, object]:
    if not isinstance(source_sha, str) or not _SHA40.fullmatch(source_sha):
        raise CollectorError("exact lowercase 40-hex source SHA required")
    if not isinstance(max_age_days, int) or max_age_days < 1:
        raise CollectorError("max_age_days must be a positive integer")
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None or observed_now.utcoffset() is None:
        raise CollectorError("evaluation time must be timezone aware")
    base_report = make_report(
        junit_path, source_sha, runner, include_artifact_library=True,
    )
    release = collect_release_evidence(
        release_dir, source_sha=source_sha,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
    )
    row_receipts = load_row_receipts(row_receipts_path, source_sha=source_sha)
    campaign = load_campaign_report(
        campaign_report_path, source_sha=source_sha,
    )
    rows = _platform_rows(
        base_report=base_report,
        row_receipts=row_receipts,
        release=release,
        junit_present=bool(junit_path is not None and Path(junit_path).is_file()),
        now=observed_now,
        max_age_days=max_age_days,
    )
    scenarios = _library_scenarios(campaign=campaign)
    platform_counts = _counts([str(row["status"]) for row in rows])
    library_counts = _counts([str(item["status"]) for item in scenarios])
    return {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "runner": runner,
        "authoritative_status_unchanged": True,
        "authoritative_status_path": "docs/development/PLATFORM_1_0_ACCEPTANCE.md",
        "release_verdict": "NO_GO",
        "release_accepted": False,
        "production_authorized": False,
        "acceptance": "NOT_CLAIMED",
        "notes": [
            "PASS is scoped to mapped source tests plus declared host receipts.",
            "Release rows require a verified PlatformReleaseVerifier signature.",
            "Self-declared release_signature_verified booleans are never trusted.",
            "This report does not independently certify an installed OS service.",
            "Authoritative row/scenario text was not modified.",
        ],
        "platform": {
            "row_count": COUNT,
            "rows": rows,
            "counts": platform_counts,
        },
        "artifact_library": {
            "scenario_count": len(LIB_ROWS),
            "scenarios": scenarios,
            "counts": library_counts,
        },
        "release_evidence": release,
        "row_receipts": {
            "present": row_receipts.get("present"),
            "schema_ok": row_receipts.get("schema_ok"),
            "issues": row_receipts.get("issues", []),
        },
        "campaign_report": {
            "present": campaign.get("present"),
            "issues": campaign.get("issues", []),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "release-signature.json must be an Ed25519 signature over the "
            "PlatformReleaseManifest digest; tools/build_aegis_release.py "
            "emits the canonical manifest and signature pair."
        ),
    )
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--runner", default=sys.platform)
    parser.add_argument(
        "--release-dir", type=Path,
        help="Release directory; signature requires the three trust arguments.",
    )
    parser.add_argument("--row-receipts", type=Path)
    parser.add_argument("--campaign-report", type=Path)
    parser.add_argument(
        "--trusted-public-key", type=Path,
        help="PEM Ed25519 public key trusted for release signatures.",
    )
    parser.add_argument(
        "--trusted-key-sha256",
        help="Lowercase SHA-256 of the exact PEM public-key file bytes.",
    )
    parser.add_argument(
        "--signer-key-id",
        help="Expected signer key ID in release-signature.json.",
    )
    parser.add_argument(
        "--max-age-days", type=int, default=_DEFAULT_MAX_AGE_DAYS,
        help="Reject host receipts older than this many days.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.release_dir is not None:
        missing = [
            name for name, value in (
                ("--trusted-public-key", args.trusted_public_key),
                ("--trusted-key-sha256", args.trusted_key_sha256),
                ("--signer-key-id", args.signer_key_id),
            ) if value is None
        ]
        if missing:
            parser.error(
                "signed release verification requires " + ", ".join(missing)
            )
    try:
        source_sha = args.source_sha or _git_sha()
        report = collect(
            junit_path=args.junit,
            source_sha=source_sha,
            runner=args.runner,
            release_dir=args.release_dir,
            row_receipts_path=args.row_receipts,
            campaign_report_path=args.campaign_report,
            trusted_public_key=args.trusted_public_key,
            trusted_key_sha256=args.trusted_key_sha256,
            trusted_signer_key_id=args.signer_key_id,
            max_age_days=args.max_age_days,
        )
        payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        return 0
    except (CollectorError, OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(
            json.dumps({
                "schema": SCHEMA,
                "result": "COLLECTOR_REFUSED",
                "reason": str(error),
                "release_verdict": "NO_GO",
                "release_accepted": False,
                "production_authorized": False,
            }, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
