"""Collector tests prove PASS requires mapped tests plus a verified release.

The release manifest is signed by a real disposable Ed25519 key.  Unsigned,
forged, wrong-key, wrong-SHA and stale evidence can never pass.  The collector
always keeps the overall Platform release verdict at NO_GO.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.platform_release import (
    PlatformReleaseAsset, PlatformReleaseManifest, PlatformReleaseTarget,
)
from tools.aegis_acceptance_collector import collect
from tools.aegis_platform_row_preflight import COUNT, LIB_ROWS, PROBES

pytestmark = pytest.mark.pkg_ops

SOURCE = "a" * 40
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Signer:
    key: Ed25519PrivateKey
    key_id: str
    public_path: Path
    fingerprint: str


def _signer(tmp_path: Path, *, key_id: str = "release-key-1", name: str = "release") -> Signer:
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path = tmp_path / f"{name}.pem"
    path.write_bytes(public)
    return Signer(key, key_id, path, sha256(public).hexdigest())


def _release(
    tmp_path: Path,
    signer: Signer,
    *,
    source_sha: str = SOURCE,
    signature_b64: str | None = None,
) -> tuple[Path, PlatformReleaseManifest]:
    root = tmp_path / "release"
    assets = root / "assets"
    assets.mkdir(parents=True)
    files = {
        "sofia_sdk.whl": ("sdk", b"sdk-wheel-fixture"),
        "sofia_platform.whl": ("platform", b"platform-wheel-fixture"),
        "aegis-platform-service": ("service", b"service-fixture"),
        "python-runtime.zip": ("python-runtime", b"runtime-fixture"),
        "dependency-index.json": ("dependency-lock", b"lock-fixture"),
        "sbom.json": ("sbom", b"sbom-fixture"),
        "provenance.json": ("provenance", b"provenance-fixture"),
    }
    entries = []
    asset_records = []
    for name, (kind, data) in sorted(files.items()):
        (assets / name).write_bytes(data)
        digest = sha256(data).hexdigest()
        entries.append(PlatformReleaseAsset(
            kind, ArtifactReference(name, digest, len(data)),
        ))
        asset_records.append({
            "kind": kind, "path": name, "sha256": digest,
            "size_bytes": len(data),
        })
    manifest = PlatformReleaseManifest(
        "test-collector-release", "0.1.0", 1, source_sha,
        PlatformReleaseTarget.DEBIAN12_X86_64, SDK_PROTOCOL_VERSION,
        "3.12.16", tuple(entries),
    )
    (root / "release-manifest.json").write_bytes(manifest.canonical_bytes)
    signed = signature_b64 or base64.b64encode(
        signer.key.sign(manifest.digest.encode("ascii"))
    ).decode("ascii")
    (root / "release-signature.json").write_text(json.dumps({
        "signer_key_id": signer.key_id,
        "signature_b64": signed,
    }), encoding="utf-8")
    (root / "artifact-digests.json").write_text(json.dumps({
        "schema": "aegis.platform.release-artifact-digests.v1",
        "source_sha": source_sha,
        "manifest_digest": manifest.digest,
        "manifest_sha256": sha256(manifest.canonical_bytes).hexdigest(),
        "signer_key_id": signer.key_id,
        "assets": asset_records,
    }), encoding="utf-8")
    return root, manifest


def _junit(tmp_path: Path) -> Path:
    cases = []
    seen: set[str] = set()
    for files in PROBES.values():
        for filename in files:
            if filename in seen:
                continue
            seen.add(filename)
            stem = filename[:-3] if filename.endswith(".py") else filename
            cases.append(
                f'<testcase classname="test.{stem}" name="passes"/>'
            )
    path = tmp_path / "junit.xml"
    path.write_text(
        "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def _skipped_junit(tmp_path: Path, filename: str) -> Path:
    cases = []
    seen: set[str] = set()
    for files in PROBES.values():
        for candidate in files:
            if candidate in seen:
                continue
            seen.add(candidate)
            stem = candidate[:-3] if candidate.endswith(".py") else candidate
            if candidate == filename:
                cases.append(
                    f'<testcase classname="test.{stem}" name="skipped">'
                    '<skipped message="host-conditional"/></testcase>'
                )
            else:
                cases.append(
                    f'<testcase classname="test.{stem}" name="passes"/>'
                )
    path = tmp_path / "junit-skipped.xml"
    path.write_text(
        "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def _row_receipts(
    tmp_path: Path, manifest: PlatformReleaseManifest, signer: Signer,
) -> Path:
    service_sha = next(
        asset.reference.sha256 for asset in manifest.assets
        if asset.kind == "service"
    )
    manifest_sha = sha256(manifest.canonical_bytes).hexdigest()

    def observation(host: str) -> dict:
        return {
            "host_id": host,
            "observed": True,
            "result": "PASS",
            "service_binary_sha256": service_sha,
            "artifact_manifest_sha256": manifest.digest,
            "signer_key_id": signer.key_id,
            "witnessed_at": NOW.isoformat(),
            "receipt_sha256": "b" * 64,
            "negative_cases": ["unauthorized-enrollment-denied"],
        }

    rows = {
        f"{number:02d}": {
            "windows": observation(f"W-{number:02d}"),
            "debian12": observation(f"D-{number:02d}"),
            "ci_run_url": f"https://ci.invalid/aegis/runs/{number}",
            "test_ids": [f"test-{number:02d}"],
            "reviewer": "synthetic-reviewer",
            "witnessed_at": NOW.isoformat(),
            "release_manifest_sha256": manifest_sha,
            "negative_cases": ["unauthenticated-host-denied"],
        }
        for number in range(1, COUNT + 1)
    }
    path = tmp_path / "row-receipts.json"
    path.write_text(json.dumps({
        "schema": "aegis.platform.acceptance.row-receipts.v1",
        "source_sha": manifest.source_sha,
        "rows": rows,
    }), encoding="utf-8")
    return path


def _campaign(tmp_path: Path, *, source_sha: str = SOURCE) -> Path:
    path = tmp_path / f"campaign-{source_sha[:4]}.json"
    path.write_text(json.dumps({
        "schema": "aegis.d028.four-host-campaign.v1",
        "source_sha": source_sha,
        "mode": "EVIDENCE",
        "scenarios": [
            {
                "scenario_id": scenario,
                "refined_platform_rows": [f"{row:02d}" for row in rows],
                "status": "PASS",
                "missing": [],
                "invalid": [],
                "acceptance": "NOT_CLAIMED",
            }
            for scenario, rows in LIB_ROWS.items()
        ],
    }), encoding="utf-8")
    return path


def _collect(tmp_path: Path, signer: Signer, **changes):
    release, manifest = _release(tmp_path, signer)
    parameters = dict(
        junit_path=_junit(tmp_path),
        source_sha=SOURCE,
        runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest, signer),
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    parameters.update(changes)
    return collect(**parameters), release, manifest


def test_valid_signed_release_and_host_receipts_pass_but_release_remains_no_go(
    tmp_path: Path,
) -> None:
    signer = _signer(tmp_path)
    report, _release_dir, _manifest = _collect(tmp_path, signer)
    assert report["release_verdict"] == "NO_GO"
    assert report["release_accepted"] is False
    assert report["production_authorized"] is False
    assert report["authoritative_status_unchanged"] is True
    assert report["release_evidence"]["signature_verified"] is True
    assert report["platform"]["row_count"] == 38
    assert report["platform"]["counts"]["PASS"] == len(PROBES) == 25
    assert report["platform"]["counts"]["BLOCKED"] == 13
    assert report["platform"]["counts"]["FAIL"] == 0
    assert report["artifact_library"]["scenario_count"] == 16
    assert report["artifact_library"]["counts"]["PASS"] == 16
    assert all(
        row["signed_installed_host_certified"] is False
        for row in report["platform"]["rows"]
    )


def test_unsigned_self_asserted_signature_blocks_every_row(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report, release, _manifest = _collect(tmp_path, signer)
    (release / "release-signature.json").write_text(json.dumps({
        "signer_key_id": signer.key_id,
        "signature_b64": "AA==",
    }), encoding="utf-8")
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, _manifest, signer),
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    assert changed["release_evidence"]["signature_verified"] is False
    assert changed["release_evidence"]["signature_present"] is True
    assert changed["platform"]["counts"]["PASS"] == 0
    assert changed["platform"]["counts"]["BLOCKED"] == 38
    assert changed["platform"]["counts"]["FAIL"] == 0
    assert changed["release_verdict"] == "NO_GO"
    assert changed["release_accepted"] is False


def test_missing_release_signature_blocks_every_row(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report, release, _manifest = _collect(tmp_path, signer)
    (release / "release-signature.json").unlink()
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, _manifest, signer),
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    assert changed["release_evidence"]["signature_verified"] is False
    assert changed["platform"]["counts"]["PASS"] == 0
    assert changed["platform"]["counts"]["BLOCKED"] == 38
    assert changed["release_verdict"] == "NO_GO"


def test_wrong_key_release_signature_blocks_every_row(tmp_path: Path) -> None:
    trusted = _signer(tmp_path, key_id="release-key-1", name="trusted")
    other = _signer(tmp_path, key_id="release-key-1", name="other")
    release, manifest = _release(tmp_path, other)
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest, trusted),
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=trusted.public_path,
        trusted_key_sha256=trusted.fingerprint,
        trusted_signer_key_id=trusted.key_id,
        now=NOW,
    )
    assert changed["release_evidence"]["signature_verified"] is False
    assert changed["platform"]["counts"]["PASS"] == 0
    assert changed["platform"]["counts"]["BLOCKED"] == 38
    assert changed["release_verdict"] == "NO_GO"


def test_wrong_source_release_signature_blocks_every_row(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    release, manifest = _release(tmp_path, signer, source_sha="b" * 40)
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest, signer),
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    assert changed["release_evidence"]["signature_verified"] is False
    assert changed["release_evidence"]["source_sha_match"] is False
    assert changed["platform"]["counts"]["PASS"] == 0
    assert changed["platform"]["counts"]["BLOCKED"] == 38
    assert changed["release_verdict"] == "NO_GO"


def test_missing_row_field_blocks_only_that_row(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report, release, manifest = _collect(tmp_path, signer)
    receipts = json.loads(_row_receipts(tmp_path, manifest, signer).read_text())
    receipts["rows"]["01"].pop("debian12")
    path = tmp_path / "row-receipts-incomplete.json"
    path.write_text(json.dumps(receipts), encoding="utf-8")
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release, row_receipts_path=path,
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    first = changed["platform"]["rows"][0]
    assert first["row_id"] == "01"
    assert first["status"] == "BLOCKED"
    assert "debian12" in first["missing"]
    assert changed["platform"]["counts"]["PASS"] == 24


def test_row_signature_boolean_is_not_trusted(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    _report, release, manifest = _collect(tmp_path, signer)
    receipts = json.loads(_row_receipts(tmp_path, manifest, signer).read_text())
    receipts["rows"]["01"]["release_signature_verified"] = True
    path = tmp_path / "row-receipts-boolean.json"
    path.write_text(json.dumps(receipts), encoding="utf-8")
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release, row_receipts_path=path,
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    first = changed["platform"]["rows"][0]
    assert first["status"] == "FAIL"
    assert "ROW_RECEIPT_UNKNOWN_FIELDS" in first["invalid"]


def test_stale_row_receipt_is_rejected(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    _report, release, manifest = _collect(tmp_path, signer)
    receipts = json.loads(_row_receipts(tmp_path, manifest, signer).read_text())
    receipts["rows"]["01"]["witnessed_at"] = "2000-01-01T00:00:00+00:00"
    path = tmp_path / "row-receipts-stale.json"
    path.write_text(json.dumps(receipts), encoding="utf-8")
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release, row_receipts_path=path,
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    first = changed["platform"]["rows"][0]
    assert first["status"] != "PASS"
    assert any("RECEIPT_STALE" in value for value in first["invalid"])
    assert changed["platform"]["counts"]["PASS"] == 24


def test_missing_row_negative_cases_is_rejected(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    _report, release, manifest = _collect(tmp_path, signer)
    receipts = json.loads(_row_receipts(tmp_path, manifest, signer).read_text())
    receipts["rows"]["01"]["windows"]["negative_cases"] = []
    path = tmp_path / "row-receipts-no-negatives.json"
    path.write_text(json.dumps(receipts), encoding="utf-8")
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release, row_receipts_path=path,
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    first = changed["platform"]["rows"][0]
    assert first["status"] != "PASS"
    assert any(
        "NEGATIVE_CASES_MISSING" in value for value in first["invalid"]
    )
    assert changed["platform"]["counts"]["PASS"] == 24


def test_row_receipt_source_mismatch_blocks(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    release, manifest = _release(tmp_path, signer)
    receipts = json.loads(_row_receipts(tmp_path, manifest, signer).read_text())
    receipts["source_sha"] = "b" * 40
    path = tmp_path / "row-receipts-wrong-source.json"
    path.write_text(json.dumps(receipts), encoding="utf-8")
    report = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release, row_receipts_path=path,
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    assert report["platform"]["counts"]["PASS"] == 0
    assert report["platform"]["counts"]["BLOCKED"] == 38
    assert report["platform"]["counts"]["NOT_TESTED"] == 0


def test_tampered_release_artifact_digest_blocks(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    release, manifest = _release(tmp_path, signer)
    digests = json.loads((release / "artifact-digests.json").read_text())
    digests["assets"][0]["sha256"] = "0" * 64
    (release / "artifact-digests.json").write_text(json.dumps(digests))
    report = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest, signer),
        campaign_report_path=_campaign(tmp_path),
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        trusted_signer_key_id=signer.key_id,
        now=NOW,
    )
    assert report["release_evidence"]["artifact_digests_valid"] is False
    assert report["platform"]["counts"]["PASS"] == 0


def test_skipped_junit_is_never_a_pass(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report, _release_dir, _manifest = _collect(
        tmp_path, signer,
        junit_path=_skipped_junit(tmp_path, "test_rust_platform_service.py"),
    )
    affected = [
        row for row in report["platform"]["rows"]
        if "test_rust_platform_service.py" in row["mapped_test_files"]
    ]
    assert affected
    for row in affected:
        assert row["status"] != "PASS"
    assert report["release_verdict"] == "NO_GO"


def test_absent_junit_never_passes(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report, release, manifest = _collect(tmp_path, signer, junit_path=None)
    assert report["platform"]["counts"]["PASS"] == 0
    assert report["platform"]["counts"]["NOT_TESTED"] == 25
    assert report["platform"]["counts"]["BLOCKED"] == 13
    assert report["artifact_library"]["counts"]["PASS"] == 16


def test_absent_campaign_never_passes_library(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report, release, manifest = _collect(
        tmp_path, signer, campaign_report_path=None,
    )
    assert report["artifact_library"]["counts"]["PASS"] == 0
    assert report["artifact_library"]["counts"]["NOT_TESTED"] == 16


def test_campaign_source_mismatch_blocks_library(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report, release, manifest = _collect(
        tmp_path, signer,
        campaign_report_path=_campaign(tmp_path, source_sha="b" * 40),
    )
    assert report["artifact_library"]["counts"]["PASS"] == 0
    assert report["artifact_library"]["counts"]["BLOCKED"] == 16


def test_collector_does_not_modify_authoritative_status_text(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    status = (
        Path(__file__).resolve().parents[1]
        / "docs" / "development" / "PLATFORM_1_0_ACCEPTANCE.md"
    )
    before = status.read_bytes()
    _collect(tmp_path, signer)
    assert status.read_bytes() == before
