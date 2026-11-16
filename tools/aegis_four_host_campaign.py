"""Fail-closed W-EMPTY/D-HUB/D-CLIENT/W-PEER LIB campaign evidence harness.

The harness validates a *declared* disposable four-host topology and, when
supplied, a local evidence bundle.  It reuses the existing D028 plan validator
and the canonical signed Platform release verifier.  It never installs, enrolls,
starts a service, signs a production release or invents an installed-host result.

``PASS`` in this report means only that every *declared evidence field* is
present and internally consistent.  It is scoped to the evidence bundle and is
NOT an independent installed-host certification.  Missing evidence is always
``BLOCKED`` or ``NOT_TESTED``.  Local disposable fabrication is possible only
with ``--simulate`` and is labelled ``SIMULATED``.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

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
    D028_HOST_IDS, D028_TOPOLOGY_PATH, LIB_ROWS,
    _hash_bounded_evidence_artifact, _safe_evidence_path,
    make_d028_four_host_preflight,
)

SCHEMA = "aegis.d028.four-host-campaign.v1"
LIB_CASE_SCHEMA = "aegis.d028.library-case.v1"
SIMULATION_LABEL = "SIMULATED_LOCAL_DISPOSABLE_NOT_INSTALLED_HOST_EVIDENCE"

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_PLACEHOLDERS = {
    "", "OBSERVE_AFTER_INSTALL", "UNKNOWN", "UNVERIFIED", "NOT_COLLECTED",
    "GENERATE_BY_SIGNED_PLATFORM_SERVICE_NOT_A_TEST_VALUE", "TBD", "NONE",
}
_RELEASE_DIR = re.compile(r"release-([A-Za-z0-9_.-]+)\Z")
_TARGET_HOSTS = {
    "windows-x86_64": ("W-EMPTY", "W-PEER"),
    "debian12-x86_64": ("D-HUB", "D-CLIENT"),
}
_HOST_TARGET = {
    host: target for target, hosts in _TARGET_HOSTS.items() for host in hosts
}
LIB_CASE_FIELDS = (
    "scenario_id", "source_sha", "status", "owner_team", "workflow_url",
    "host_ids", "os_builds", "sdk_protocol", "release_target",
    "manifest_sha256", "artifact_manifest_sha256", "artifact_content_sha256",
    "publisher_signer_key_id", "positive_cases", "negative_cases",
    "owner_authorization_receipts", "source_trust_receipts",
    "transfer_receipts", "install_or_runtime_receipts",
    "witnessed_at", "reviewer", "observed_result", "remaining_blockers",
)
_RECEIPT_FIELDS = (
    "owner_authorization_receipts", "source_trust_receipts",
    "transfer_receipts", "install_or_runtime_receipts",
)
_REQUIRED_RECEIPTS = {
    "LIB-03": ("owner_authorization_receipts", "source_trust_receipts", "transfer_receipts"),
    "LIB-07": ("source_trust_receipts", "transfer_receipts"),
    "LIB-08": ("owner_authorization_receipts", "source_trust_receipts"),
    "LIB-13": ("owner_authorization_receipts", "source_trust_receipts"),
    "LIB-16": ("owner_authorization_receipts", "source_trust_receipts", "transfer_receipts"),
}
_DEFAULT_REQUIRED_RECEIPTS = ("source_trust_receipts", "install_or_runtime_receipts")


class CampaignEvidenceError(RuntimeError):
    """Raised when an evidence bundle cannot be consumed safely."""


def _read_json(root: Path, relative: str, *, limit: int = 65536) -> dict:
    path = _safe_evidence_path(root, relative)
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(relative)
    size = path.stat().st_size
    if not 1 <= size <= limit:
        raise ValueError(f"{relative} is outside bounded size")
    loaded = loads_strict_model_json(path.read_bytes().decode("utf-8"))
    if type(loaded) is not dict:
        raise ValueError(f"{relative} must be a JSON object")
    return loaded


def _git_sha() -> str:
    repo = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", "rev-parse", "HEAD"],
        cwd=str(repo), capture_output=True, text=True, timeout=30,
    )
    if completed.returncode != 0:
        raise CampaignEvidenceError("cannot observe exact source SHA")
    value = completed.stdout.strip()
    if not _SHA40.fullmatch(value):
        raise CampaignEvidenceError("Git returned an invalid source SHA")
    return value


def _load_topology(path: Path | None, source_sha: str) -> dict:
    topology_path = Path(path) if path is not None else D028_TOPOLOGY_PATH
    topology = json.loads(topology_path.read_text(encoding="utf-8"))
    # Reuse the fail-closed plan validator. It requires exactly four unexecuted
    # disposable hosts, one D-HUB primary, zero initial replicas and no
    # production/acceptance claim.
    make_d028_four_host_preflight(source_sha, topology=topology)
    return topology


def _release_candidates(root: Path) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    if (root / "release-manifest.json").is_file():
        candidates.append(("", root))
    for child in sorted(root.iterdir()):
        match = _RELEASE_DIR.fullmatch(child.name)
        if (match is not None and child.is_dir()
                and (child / "release-manifest.json").is_file()):
            candidates.append((match.group(1), child))
    return candidates


def _verify_release(
    directory: Path, *, source_sha: str,
    trusted_public_key: Path | None, trusted_key_sha256: str | None,
    trusted_signer_key_id: str | None,
) -> tuple[PlatformReleaseManifest, dict[str, object], list[str]]:
    missing: list[str] = []
    invalid: list[str] = []
    manifest_path = directory / "release-manifest.json"
    signature_path = directory / "release-signature.json"
    if not manifest_path.is_file():
        missing.append(f"{directory.name}/release-manifest.json")
        raise CampaignEvidenceError("release manifest is missing")
    if not signature_path.is_file():
        missing.append(f"{directory.name}/release-signature.json")
        raise CampaignEvidenceError("release signature is missing")
    manifest = PlatformReleaseManifest.from_payload(
        _read_json(directory, "release-manifest.json", limit=131072)
    )
    if manifest.source_sha != source_sha:
        invalid.append(f"{manifest_path.name}:SOURCE_SHA_MISMATCH")
    envelope = _read_json(directory, "release-signature.json", limit=16384)
    if set(envelope) != {"signer_key_id", "signature_b64"}:
        invalid.append("release-signature.json:NONCANONICAL")
        raise CampaignEvidenceError("release signature envelope is not canonical")
    signer_key_id = envelope["signer_key_id"]
    if not isinstance(signer_key_id, str) or not signer_key_id:
        invalid.append("release-signature.json:SIGNER_MISSING")
    signature_verified = False
    if trusted_public_key is not None:
        if not isinstance(trusted_signer_key_id, str) or not trusted_signer_key_id:
            raise CampaignEvidenceError("--signer-key-id is required with trusted key")
        if signer_key_id != trusted_signer_key_id:
            invalid.append("release-signature.json:UNEXPECTED_SIGNER")
        key_path = Path(trusted_public_key).absolute()
        if key_path.is_symlink() or not key_path.is_file():
            raise CampaignEvidenceError("trusted public key must be a regular file")
        key_bytes = key_path.read_bytes()
        if trusted_key_sha256 is not None:
            if not _SHA64.fullmatch(trusted_key_sha256):
                raise CampaignEvidenceError("trusted key fingerprint must be SHA-256")
            if sha256(key_bytes).hexdigest() != trusted_key_sha256:
                raise CampaignEvidenceError("trusted key fingerprint mismatch")
        try:
            PlatformReleaseVerifier({signer_key_id: key_bytes}).verify(
                manifest.to_payload(),
                signature_b64=envelope["signature_b64"],
                signer_key_id=signer_key_id,
                assets_root=directory / "assets",
                expected_source_sha=source_sha,
                expected_target=manifest.target,
                minimum_revision=manifest.revision,
            )
            signature_verified = True
        except (PlatformReleaseRejected, OSError, ValueError, TypeError) as error:
            invalid.append(f"release:{type(error).__name__}:{error}")
    return manifest, {
        "target": manifest.target.value,
        "release_id": manifest.release_id,
        "revision": manifest.revision,
        "manifest_digest": manifest.digest,
        "manifest_sha256": sha256(
            manifest.canonical_bytes
        ).hexdigest(),
        "signer_key_id": signer_key_id,
        "signature_verified": signature_verified,
        "asset_sha256": {
            asset.reference.path: asset.reference.sha256
            for asset in manifest.assets
        },
        "service_sha256": next(
            asset.reference.sha256 for asset in manifest.assets
            if asset.kind == "service"
        ),
    }, missing + invalid


def _discover_releases(
    root: Path, *, source_sha: str, trusted_public_key: Path | None,
    trusted_key_sha256: str | None, trusted_signer_key_id: str | None,
) -> tuple[dict[str, dict[str, object]], list[str], list[str]]:
    releases: dict[str, dict[str, object]] = {}
    missing: list[str] = []
    invalid: list[str] = []
    candidates = _release_candidates(root)
    if not candidates:
        missing.append("release-manifest.json")
        return releases, missing, invalid
    for label, directory in candidates:
        try:
            manifest, record, problems = _verify_release(
                directory, source_sha=source_sha,
                trusted_public_key=trusted_public_key,
                trusted_key_sha256=trusted_key_sha256,
                trusted_signer_key_id=trusted_signer_key_id,
            )
        except (CampaignEvidenceError, OSError, ValueError, TypeError) as error:
            invalid.append(f"{directory.name}:{type(error).__name__}:{error}")
            continue
        invalid.extend(problems)
        target = manifest.target.value
        if target in releases:
            invalid.append(f"release-{target}:DUPLICATE_TARGET")
            continue
        releases[target] = record
    return releases, missing, invalid


def _verify_receipt(
    root: Path, item: object, *, denial_expected: bool = False,
) -> str | None:
    """Return an invalid reason, or None when the receipt bytes are present."""
    if type(item) is not dict:
        return "RECEIPT_NOT_OBJECT"
    path = item.get("receipt_path")
    digest = item.get("receipt_sha256")
    if not isinstance(path, str) or not isinstance(digest, str):
        return "RECEIPT_FIELDS_MISSING"
    if not _SHA64.fullmatch(digest):
        return "RECEIPT_DIGEST_INVALID"
    try:
        observed = _hash_bounded_evidence_artifact(root, path)
    except (ValueError, OSError) as error:
        return f"RECEIPT_BYTES_UNAVAILABLE:{error}"
    if observed != digest:
        return "RECEIPT_BYTES_MISMATCH"
    if denial_expected and item.get("denial_observed") is not True:
        return "DENIAL_NOT_OBSERVED"
    return None


def _verify_receipt_list(
    root: Path, values: object, *, denial_expected: bool = False,
) -> tuple[int, list[str]]:
    if not isinstance(values, list):
        return 0, ["RECEIPT_LIST_INVALID"]
    problems: list[str] = []
    for index, item in enumerate(values):
        problem = _verify_receipt(root, item, denial_expected=denial_expected)
        if problem is not None:
            problems.append(f"receipt[{index}]:{problem}")
    return len(values), problems


def _verify_signed_artifacts(
    root: Path, *, source_sha: str,
) -> tuple[set[str], list[str], list[str]]:
    missing: list[str] = []
    invalid: list[str] = []
    digests: set[str] = set()
    try:
        document = _read_json(root, "signed-artifacts.json")
    except FileNotFoundError:
        return digests, ["signed-artifacts.json"], invalid
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return digests, missing, [f"signed-artifacts.json:{error}"]
    if document.get("source_sha") != source_sha:
        invalid.append("signed-artifacts.json:SOURCE_SHA_MISMATCH")
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 64:
        invalid.append("signed-artifacts.json:INVALID_ARTIFACT_LIST")
        return digests, missing, invalid
    for index, artifact in enumerate(artifacts):
        if type(artifact) is not dict:
            invalid.append(f"artifact[{index}]:NOT_OBJECT")
            continue
        path = artifact.get("path")
        expected = artifact.get("sha256")
        if not isinstance(path, str) or not isinstance(expected, str):
            invalid.append(f"artifact[{index}]:FIELDS_MISSING")
            continue
        if not _SHA64.fullmatch(expected):
            invalid.append(f"artifact[{index}]:SHA_INVALID")
            continue
        try:
            observed = _hash_bounded_evidence_artifact(root, path)
        except (ValueError, OSError) as error:
            invalid.append(f"artifact[{index}]:BYTES_UNAVAILABLE:{error}")
            continue
        if observed != expected:
            invalid.append(f"artifact[{index}]:BYTE_INTEGRITY_FAILED")
            continue
        digests.add(expected)
    return digests, missing, invalid


def _verify_hosts(
    root: Path, *, source_sha: str, releases: dict[str, dict[str, object]],
    signed_artifacts: set[str],
) -> tuple[dict[str, dict[str, object]], list[str], list[str]]:
    missing: list[str] = []
    invalid: list[str] = []
    hosts_state: dict[str, dict[str, object]] = {
        host: {"status": "NOT_TESTED", "issues": []} for host in D028_HOST_IDS
    }
    try:
        inventory = _read_json(root, "host-inventory.json", limit=131072)
    except FileNotFoundError:
        return hosts_state, ["host-inventory.json"], invalid
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return hosts_state, missing, [f"host-inventory.json:{error}"]
    if inventory.get("source_sha") != source_sha:
        invalid.append("host-inventory.json:SOURCE_SHA_MISMATCH")
    hosts = inventory.get("hosts")
    if not isinstance(hosts, list) or len(hosts) != 4:
        invalid.append("host-inventory.json:HOST_COUNT")
        return hosts_state, missing, invalid
    observed_ids: set[str] = set()
    platform_ids: set[str] = set()
    for entry in hosts:
        if type(entry) is not dict:
            invalid.append("host-inventory.json:HOST_NOT_OBJECT")
            continue
        host_id = entry.get("host_id")
        if host_id not in D028_HOST_IDS:
            invalid.append("host-inventory.json:UNKNOWN_HOST")
            continue
        if host_id in observed_ids:
            invalid.append(f"host-inventory.json:{host_id}:DUPLICATE")
            continue
        observed_ids.add(host_id)
        issues: list[str] = []
        target = entry.get("release_target")
        if target != _HOST_TARGET[host_id]:
            issues.append("RELEASE_TARGET_DOES_NOT_MATCH_HOST_ROLE")
        release = releases.get(str(target))
        if release is None:
            issues.append("RELEASE_TARGET_MISSING")
        platform_id = entry.get("platform_id")
        if (not isinstance(platform_id, str) or platform_id.upper() in _PLACEHOLDERS
                or len(platform_id) < 8):
            issues.append("PLATFORM_ID_NOT_OBSERVED")
        elif platform_id in platform_ids:
            issues.append("PLATFORM_ID_NOT_UNIQUE")
        else:
            platform_ids.add(platform_id)
        os_build = entry.get("os_build")
        if not isinstance(os_build, str) or os_build.upper() in _PLACEHOLDERS:
            issues.append("OS_BUILD_NOT_OBSERVED")
        signer = entry.get("signer_key_id")
        if release is not None and signer != release["signer_key_id"]:
            issues.append("SIGNER_DOES_NOT_MATCH_RELEASE")
        service_sha = entry.get("service_binary_sha256")
        if not isinstance(service_sha, str) or not _SHA64.fullmatch(service_sha):
            issues.append("SERVICE_DIGEST_INVALID")
        else:
            if release is not None and service_sha != release["service_sha256"]:
                issues.append("SERVICE_DIGEST_DOES_NOT_MATCH_RELEASE")
            if service_sha not in signed_artifacts:
                issues.append("SERVICE_DIGEST_NOT_IN_SIGNED_ARTIFACTS")
        service_receipt = entry.get("service_receipt")
        if type(service_receipt) is not dict:
            issues.append("SERVICE_RECEIPT_MISSING")
        else:
            if service_receipt.get("observed") is not True:
                issues.append("SERVICE_NOT_OBSERVED")
            if service_receipt.get("result") not in {
                "SERVICE_HEALTHY", "SERVICE_OBSERVED", "VERIFIED",
            }:
                issues.append("SERVICE_RESULT_INVALID")
            problem = _verify_receipt(root, service_receipt)
            if problem is not None:
                issues.append(f"SERVICE_{problem}")
        boot_receipts = entry.get("boot_receipts")
        if not isinstance(boot_receipts, list) or not boot_receipts:
            issues.append("BOOT_RECEIPTS_MISSING")
        else:
            for index, receipt in enumerate(boot_receipts):
                problem = _verify_receipt(root, receipt)
                if problem is not None:
                    issues.append(f"BOOT[{index}]_{problem}")
        hosts_state[host_id] = {
            "status": "BLOCKED" if issues else "PASS",
            "issues": issues,
            "release_target": target,
            "platform_id": platform_id,
            "service_binary_sha256": service_sha,
        }
    if observed_ids != set(D028_HOST_IDS):
        invalid.append("host-inventory.json:HOST_SET_INCOMPLETE")
    return hosts_state, missing, invalid


def _verify_cross_host(
    root: Path, *, source_sha: str, releases: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    missing: list[str] = []
    invalid: list[str] = []
    try:
        document = _read_json(root, "cross-host-receipts.json")
    except FileNotFoundError:
        return [], ["cross-host-receipts.json"], invalid
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return [], missing, [f"cross-host-receipts.json:{error}"]
    if document.get("source_sha") != source_sha:
        invalid.append("cross-host-receipts.json:SOURCE_SHA_MISMATCH")
    receipts = document.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        invalid.append("cross-host-receipts.json:NO_RECEIPTS")
        return [], missing, invalid
    all_digests = {
        digest for release in releases.values()
        for digest in release["asset_sha256"].values()
    }
    signers = {release["signer_key_id"] for release in releases.values()}
    verified: list[dict[str, object]] = []
    for index, receipt in enumerate(receipts):
        if type(receipt) is not dict:
            invalid.append(f"cross-host[{index}]:NOT_OBJECT")
            continue
        source_host = receipt.get("source_host")
        target_host = receipt.get("target_host")
        if (source_host not in D028_HOST_IDS
                or target_host not in D028_HOST_IDS):
            invalid.append(f"cross-host[{index}]:UNKNOWN_HOST")
            continue
        if receipt.get("signer_key_id") not in signers:
            invalid.append(f"cross-host[{index}]:SIGNER_MISMATCH")
        digest = receipt.get("artifact_sha256")
        if not isinstance(digest, str) or digest not in all_digests:
            invalid.append(f"cross-host[{index}]:ARTIFACT_DIGEST_MISMATCH")
        if receipt.get("result") not in {"TRANSFER_VERIFIED", "TRANSFER_DENIED"}:
            invalid.append(f"cross-host[{index}]:RESULT_INVALID")
        problem = _verify_receipt(
            root, receipt,
            denial_expected=receipt.get("result") == "TRANSFER_DENIED",
        )
        if problem is not None:
            invalid.append(f"cross-host[{index}]:{problem}")
            continue
        verified.append(receipt)
    pairs = {
        (item.get("source_host"), item.get("target_host"))
        for item in verified
    }
    if ("D-HUB", "D-CLIENT") not in pairs:
        missing.append("cross-host-receipts.json:D-HUB->D-CLIENT")
    if ("W-PEER", "D-CLIENT") not in pairs:
        missing.append("cross-host-receipts.json:W-PEER->D-CLIENT")
    return verified, missing, invalid


def _verify_network_denials(
    root: Path, *, source_sha: str,
) -> tuple[int, list[str], list[str]]:
    try:
        document = _read_json(root, "network-denials.json")
    except FileNotFoundError:
        return 0, ["network-denials.json"], []
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return 0, [], [f"network-denials.json:{error}"]
    invalid: list[str] = []
    if document.get("source_sha") != source_sha:
        invalid.append("network-denials.json:SOURCE_SHA_MISMATCH")
    denials = document.get("denials")
    if not isinstance(denials, list):
        return 0, [], ["network-denials.json:INVALID_LIST"]
    observed = set()
    for index, denial in enumerate(denials):
        if type(denial) is not dict:
            invalid.append(f"denial[{index}]:NOT_OBJECT")
            continue
        host = denial.get("host_id")
        if host not in D028_HOST_IDS:
            invalid.append(f"denial[{index}]:UNKNOWN_HOST")
            continue
        if denial.get("denied") is not True:
            invalid.append(f"denial[{index}]:NOT_DENIED")
        problem = _verify_receipt(root, denial, denial_expected=True)
        if problem is not None:
            invalid.append(f"denial[{index}]:{problem}")
            continue
        observed.add(host)
    missing = [
        f"network-denials.json:{host}" for host in D028_HOST_IDS
        if host not in observed
    ]
    return len(observed), missing, invalid


def _verify_backup_restore(
    root: Path, *, source_sha: str,
) -> tuple[list[str], list[str]]:
    try:
        document = _read_json(root, "backup-restore.json")
    except FileNotFoundError:
        return ["backup-restore.json"], []
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return [], [f"backup-restore.json:{error}"]
    invalid: list[str] = []
    missing: list[str] = []
    if document.get("source_sha") != source_sha:
        invalid.append("backup-restore.json:SOURCE_SHA_MISMATCH")
    if document.get("restore_verified") is not True:
        missing.append("backup-restore.json:RESTORE_NOT_VERIFIED")
    excludes = document.get("excludes")
    required_excludes = {"sofia.db", "core_identity", "owner_secret"}
    if not isinstance(excludes, list) or not required_excludes <= set(excludes):
        invalid.append("backup-restore.json:PRIVATE_STATE_EXCLUSIONS_MISSING")
    problem = _verify_receipt(root, document)
    if problem is not None:
        invalid.append(f"backup-restore.json:{problem}")
    return missing, invalid


def validate_library_case(
    case: object, *, root: Path, source_sha: str,
    releases: dict[str, dict[str, object]],
) -> tuple[str, list[str], list[str]]:
    """Validate one LIB case; PASS is scoped to declared evidence completeness."""
    missing: list[str] = []
    invalid: list[str] = []
    if type(case) is not dict:
        return "FAIL", missing, ["CASE_NOT_OBJECT"]
    scenario_id = case.get("scenario_id")
    if scenario_id not in LIB_ROWS:
        return "FAIL", missing, ["SCENARIO_ID_INVALID"]
    if case.get("source_sha") != source_sha:
        invalid.append("SOURCE_SHA_MISMATCH")
    declared_status = case.get("status")
    if declared_status in {"FAIL", "BLOCKED", "NOT_TESTED"}:
        return str(declared_status), missing, invalid
    if declared_status != "PASS":
        invalid.append("STATUS_INVALID")
    for field in LIB_CASE_FIELDS:
        if field not in case:
            missing.append(field)
    if missing:
        return "BLOCKED", missing, invalid
    if case.get("owner_team") != "E":
        invalid.append("OWNER_TEAM_NOT_E")
    workflow_url = case.get("workflow_url")
    if not isinstance(workflow_url, str) or not workflow_url.strip():
        missing.append("workflow_url")
    host_ids = case.get("host_ids")
    if (not isinstance(host_ids, list) or not host_ids
            or any(host not in D028_HOST_IDS for host in host_ids)):
        missing.append("host_ids")
    os_builds = case.get("os_builds")
    if not isinstance(os_builds, list) or not os_builds:
        missing.append("os_builds")
    if not isinstance(case.get("sdk_protocol"), str) or not case.get("sdk_protocol"):
        missing.append("sdk_protocol")
    target = case.get("release_target")
    release = releases.get(str(target))
    if release is None:
        missing.append("release_target")
        release_assets: set[str] = set()
        signers: set[str] = set()
        manifest_digests: set[str] = set()
    else:
        release_assets = set(release["asset_sha256"].values())
        signers = {str(release["signer_key_id"])}
        manifest_digests = {str(release["manifest_digest"])}
    if case.get("manifest_sha256") not in manifest_digests:
        invalid.append("MANIFEST_DIGEST_MISMATCH")
    if case.get("publisher_signer_key_id") not in signers:
        invalid.append("SIGNER_MISMATCH")
    for field in ("artifact_manifest_sha256", "artifact_content_sha256"):
        digest = case.get(field)
        if not isinstance(digest, str) or not _SHA64.fullmatch(digest):
            missing.append(field)
        elif digest not in release_assets:
            invalid.append(f"{field.upper()}_MISMATCH")
    positive = case.get("positive_cases")
    if not isinstance(positive, list) or not positive:
        missing.append("positive_cases")
    else:
        for index, item in enumerate(positive):
            if type(item) is not dict or item.get("result") != "PASS":
                invalid.append(f"positive[{index}]:NOT_PASS")
                continue
            problem = _verify_receipt(root, item)
            if problem is not None:
                invalid.append(f"positive[{index}]:{problem}")
    negative = case.get("negative_cases")
    if not isinstance(negative, list) or not negative:
        missing.append("negative_cases")
    else:
        for index, item in enumerate(negative):
            if type(item) is not dict:
                invalid.append(f"negative[{index}]:NOT_OBJECT")
                continue
            if item.get("result") not in {"DENIED", "REFUSED", "PASS"}:
                invalid.append(f"negative[{index}]:NOT_DENIED")
            problem = _verify_receipt(root, item, denial_expected=True)
            if problem is not None:
                invalid.append(f"negative[{index}]:{problem}")
    required_receipts = _REQUIRED_RECEIPTS.get(
        str(scenario_id), _DEFAULT_REQUIRED_RECEIPTS,
    )
    for field in _RECEIPT_FIELDS:
        values = case.get(field)
        if not isinstance(values, list):
            invalid.append(f"{field.upper()}_NOT_LIST")
            continue
        if field in required_receipts and not values:
            missing.append(field)
            continue
        for index, item in enumerate(values):
            problem = _verify_receipt(root, item)
            if problem is not None:
                invalid.append(f"{field}[{index}]:{problem}")
    witnessed_at = case.get("witnessed_at")
    try:
        observed = datetime.fromisoformat(str(witnessed_at))
        if observed.tzinfo is None or observed.utcoffset() is None:
            invalid.append("WITNESSED_AT_NOT_TIMEZONE_AWARE")
    except (TypeError, ValueError):
        invalid.append("WITNESSED_AT_INVALID")
    reviewer = case.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        missing.append("reviewer")
    observed_result = case.get("observed_result")
    if not isinstance(observed_result, str) or not observed_result.strip():
        missing.append("observed_result")
    blockers = case.get("remaining_blockers")
    if not isinstance(blockers, list):
        missing.append("remaining_blockers")
    elif blockers:
        missing.append("remaining_blockers")
    if invalid:
        return "FAIL", sorted(set(missing)), sorted(set(invalid))
    if missing:
        return "BLOCKED", sorted(set(missing)), sorted(set(invalid))
    return "PASS", [], []


def _scenario_report(
    root: Path, *, source_sha: str, releases: dict[str, dict[str, object]],
    hosts: dict[str, dict[str, object]], cross_host_ok: bool,
    network_ok: bool, backup_ok: bool,
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    scenarios: list[dict[str, object]] = []
    missing_all: list[str] = []
    invalid_all: list[str] = []
    for scenario_id, rows in LIB_ROWS.items():
        relative = scenario_id + ".json"
        missing: list[str] = []
        invalid: list[str] = []
        try:
            case = _read_json(root, relative, limit=131072)
        except FileNotFoundError:
            case = None
            missing.append(relative)
        except (ValueError, OSError, json.JSONDecodeError) as error:
            case = None
            invalid.append(f"{relative}:{error}")
        if case is None:
            status = "NOT_TESTED" if missing else "FAIL"
        else:
            status, case_missing, case_invalid = validate_library_case(
                case, root=root, source_sha=source_sha, releases=releases,
            )
            missing.extend(case_missing)
            invalid.extend(case_invalid)
            if status == "PASS":
                blockers: list[str] = []
                if not releases:
                    blockers.append("NO_VERIFIED_RELEASE")
                elif not all(
                    release["signature_verified"] for release in releases.values()
                ):
                    blockers.append("RELEASE_SIGNATURE_NOT_VERIFIED")
                if not all(
                    host["status"] == "PASS" for host in hosts.values()
                ):
                    blockers.append("HOST_RECEIPTS_INCOMPLETE")
                if not cross_host_ok:
                    blockers.append("CROSS_HOST_RECEIPTS_INCOMPLETE")
                if not network_ok:
                    blockers.append("NETWORK_DENIALS_INCOMPLETE")
                if not backup_ok:
                    blockers.append("BACKUP_RESTORE_INCOMPLETE")
                if blockers:
                    status = "BLOCKED"
                    missing.extend(blockers)
        scenarios.append({
            "scenario_id": scenario_id,
            "refined_platform_rows": [f"{row:02d}" for row in rows],
            "status": status,
            "status_scope": "EVIDENCE_BUNDLE_ONLY",
            "missing": sorted(set(missing)),
            "invalid": sorted(set(invalid)),
            "acceptance": "NOT_CLAIMED",
            "installed_host_certified": False,
        })
        missing_all.extend(missing)
        invalid_all.extend(invalid)
    return scenarios, missing_all, invalid_all


def _counts(values: list[str]) -> dict[str, int]:
    counts = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "NOT_TESTED": 0, "SIMULATED": 0}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def run_campaign(
    *,
    source_sha: str,
    topology: dict,
    evidence_dir: Path | None = None,
    trusted_public_key: Path | None = None,
    trusted_key_sha256: str | None = None,
    trusted_signer_key_id: str | None = None,
    simulate: bool = False,
) -> dict[str, object]:
    """Validate the declared topology and optional evidence bundle."""
    if not isinstance(source_sha, str) or not _SHA40.fullmatch(source_sha):
        raise CampaignEvidenceError("exact lowercase 40-hex source SHA required")
    plan = make_d028_four_host_preflight(source_sha, topology=topology)
    base = {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "topology_status": plan["topology_status"],
        "host_ids": list(D028_HOST_IDS),
        "one_initial_primary": True,
        "initial_replica_count": 0,
        "status_scope": "EVIDENCE_BUNDLE_ONLY",
        "installed_host_certified": False,
        "release_accepted": False,
        "production_authorized": False,
        "acceptance": "NOT_CLAIMED",
    }
    if simulate:
        scenarios = [{
            "scenario_id": scenario_id,
            "refined_platform_rows": [f"{row:02d}" for row in rows],
            "status": "SIMULATED",
            "status_scope": "SIMULATED_LOCAL_DISPOSABLE",
            "missing": [],
            "invalid": [],
            "acceptance": "NOT_CLAIMED",
            "installed_host_certified": False,
        } for scenario_id, rows in LIB_ROWS.items()]
        base.update({
            "mode": "SIMULATED",
            "simulated": True,
            "simulation_label": SIMULATION_LABEL,
            "scenarios": scenarios,
            "hosts": {
                host: {"status": "SIMULATED", "issues": []}
                for host in D028_HOST_IDS
            },
            "counts": _counts([item["status"] for item in scenarios]),
            "evidence_missing": [],
            "evidence_invalid": [],
            "blocked_reasons": ["SIMULATED_NOT_INSTALLED_HOST_EVIDENCE"],
        })
        return base

    if evidence_dir is None:
        scenarios = [{
            "scenario_id": scenario_id,
            "refined_platform_rows": [f"{row:02d}" for row in rows],
            "status": "NOT_TESTED",
            "status_scope": "EVIDENCE_BUNDLE_ONLY",
            "missing": ["EVIDENCE_DIRECTORY_ABSENT"],
            "invalid": [],
            "acceptance": "NOT_CLAIMED",
            "installed_host_certified": False,
        } for scenario_id, rows in LIB_ROWS.items()]
        base.update({
            "mode": "NO_EVIDENCE",
            "simulated": False,
            "evidence_directory_supplied": False,
            "scenarios": scenarios,
            "hosts": {
                host: {"status": "NOT_TESTED", "issues": ["EVIDENCE_DIRECTORY_ABSENT"]}
                for host in D028_HOST_IDS
            },
            "counts": _counts([item["status"] for item in scenarios]),
            "evidence_missing": ["EVIDENCE_DIRECTORY_ABSENT"],
            "evidence_invalid": [],
            "blocked_reasons": ["NO_EVIDENCE_DIRECTORY"],
        })
        return base

    root = Path(evidence_dir).absolute()
    if root.is_symlink() or not root.is_dir() or not root.resolve().is_dir():
        raise CampaignEvidenceError("evidence directory must be a real local directory")

    releases, release_missing, release_invalid = _discover_releases(
        root, source_sha=source_sha,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
    )
    signed_artifacts, artifact_missing, artifact_invalid = _verify_signed_artifacts(
        root, source_sha=source_sha,
    )
    hosts, host_missing, host_invalid = _verify_hosts(
        root, source_sha=source_sha, releases=releases,
        signed_artifacts=signed_artifacts,
    )
    cross_host, cross_missing, cross_invalid = _verify_cross_host(
        root, source_sha=source_sha, releases=releases,
    )
    denial_count, denial_missing, denial_invalid = _verify_network_denials(
        root, source_sha=source_sha,
    )
    backup_missing, backup_invalid = _verify_backup_restore(
        root, source_sha=source_sha,
    )
    scenarios, case_missing, case_invalid = _scenario_report(
        root, source_sha=source_sha, releases=releases, hosts=hosts,
        cross_host_ok=bool(cross_host) and not cross_missing,
        network_ok=denial_count == len(D028_HOST_IDS) and not denial_missing,
        backup_ok=not backup_missing,
    )

    missing = sorted(set(
        release_missing + artifact_missing + host_missing + cross_missing
        + denial_missing + backup_missing + case_missing
    ))
    invalid = sorted(set(
        release_invalid + artifact_invalid + host_invalid + cross_invalid
        + denial_invalid + backup_invalid + case_invalid
    ))
    if invalid:
        # One fabricated or inconsistent declared file makes the whole bundle
        # untrustworthy. Never let another scenario remain PASS.
        for item in scenarios:
            if item["status"] == "PASS":
                item["status"] = "BLOCKED"
                item["missing"].append("EVIDENCE_INVALID_PRESENT")
    statuses = [str(item["status"]) for item in scenarios]
    base.update({
        "mode": "EVIDENCE",
        "simulated": False,
        "evidence_directory_supplied": True,
        "releases": {
            target: {
                "release_id": record["release_id"],
                "revision": record["revision"],
                "manifest_digest": record["manifest_digest"],
                "signer_key_id": record["signer_key_id"],
                "signature_verified": record["signature_verified"],
            }
            for target, record in sorted(releases.items())
        },
        "signer_key_ids": sorted({
            str(record["signer_key_id"]) for record in releases.values()
        }),
        "hosts": hosts,
        "cross_host_receipts": len(cross_host),
        "network_denials": denial_count,
        "scenarios": scenarios,
        "counts": _counts(statuses),
        "evidence_missing": missing,
        "evidence_invalid": invalid,
        "blocked_reasons": sorted(set(
            missing + invalid + [str(item["status"]) for item in scenarios
                                 if item["status"] != "PASS"]
        )),
    })
    if not releases:
        base["mode"] = "NO_VERIFIED_RELEASE"
    return base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha")
    parser.add_argument("--topology", type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--trusted-public-key", type=Path)
    parser.add_argument("--trusted-key-sha256")
    parser.add_argument("--signer-key-id")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        source_sha = args.source_sha or _git_sha()
        if args.simulate and args.evidence_dir is not None:
            raise CampaignEvidenceError("--simulate cannot consume host evidence")
        if args.evidence_dir is not None and args.trusted_public_key is None:
            # Allowed: the report will explicitly record that signatures were
            # not independently verified and therefore will not PASS.
            pass
        topology = _load_topology(args.topology, source_sha)
        report = run_campaign(
            source_sha=source_sha,
            topology=topology,
            evidence_dir=args.evidence_dir,
            trusted_public_key=args.trusted_public_key,
            trusted_key_sha256=args.trusted_key_sha256,
            trusted_signer_key_id=args.signer_key_id,
            simulate=args.simulate,
        )
        payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
        if args.simulate:
            return 0
        if args.evidence_dir is None:
            return 3
        if report["evidence_missing"] or report["evidence_invalid"]:
            return 2
        if report["counts"].get("PASS", 0) != len(LIB_ROWS):
            return 2
        # Complete declared evidence still requires independent review.
        return 4
    except (CampaignEvidenceError, OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(
            json.dumps({
                "schema": SCHEMA,
                "mode": "REJECTED",
                "reason": str(error),
                "installed_host_certified": False,
                "release_accepted": False,
                "production_authorized": False,
                "acceptance": "NOT_CLAIMED",
            }, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
