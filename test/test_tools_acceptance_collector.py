"""Collector tests prove PASS requires mapped tests plus every declared field."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.platform_release import (
    PlatformReleaseAsset, PlatformReleaseManifest, PlatformReleaseTarget,
)
from tools.aegis_acceptance_collector import collect
from tools.aegis_platform_row_preflight import COUNT, LIB_ROWS, PROBES

pytestmark = pytest.mark.pkg_ops

SOURCE = "a" * 40
SIGNER = "test-signer"


def _release(tmp_path: Path) -> tuple[Path, PlatformReleaseManifest]:
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
        "test-collector-release", "0.1.0", 1, SOURCE,
        PlatformReleaseTarget.DEBIAN12_X86_64, SDK_PROTOCOL_VERSION,
        "3.12.16", tuple(entries),
    )
    (root / "release-manifest.json").write_bytes(manifest.canonical_bytes)
    (root / "release-signature.json").write_text(json.dumps({
        "signer_key_id": SIGNER,
        "signature_b64": "AA==",
    }), encoding="utf-8")
    (root / "artifact-digests.json").write_text(json.dumps({
        "schema": "aegis.platform.release-artifact-digests.v1",
        "source_sha": SOURCE,
        "manifest_digest": manifest.digest,
        "manifest_sha256": sha256(manifest.canonical_bytes).hexdigest(),
        "signer_key_id": SIGNER,
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


def _row_receipts(tmp_path: Path, manifest: PlatformReleaseManifest) -> Path:
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
            "signer_key_id": SIGNER,
            "witnessed_at": "2026-11-15T00:00:00+00:00",
            "receipt_sha256": "b" * 64,
        }

    rows = {
        f"{number:02d}": {
            "windows": observation(f"W-{number:02d}"),
            "debian12": observation(f"D-{number:02d}"),
            "ci_run_url": f"https://ci.invalid/aegis/runs/{number}",
            "test_ids": [f"test-{number:02d}"],
            "reviewer": "synthetic-reviewer",
            "witnessed_at": "2026-11-15T00:00:00+00:00",
            "release_manifest_sha256": manifest_sha,
            "release_signature_verified": True,
        }
        for number in range(1, COUNT + 1)
    }
    path = tmp_path / "row-receipts.json"
    path.write_text(json.dumps({
        "schema": "aegis.platform.acceptance.row-receipts.v1",
        "source_sha": SOURCE,
        "rows": rows,
    }), encoding="utf-8")
    return path


def _campaign(tmp_path: Path, *, source_sha: str = SOURCE) -> Path:
    path = tmp_path / "campaign.json"
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


def _collect(tmp_path: Path, **changes):
    release, manifest = _release(tmp_path)
    parameters = dict(
        junit_path=_junit(tmp_path),
        source_sha=SOURCE,
        runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest),
        campaign_report_path=_campaign(tmp_path),
    )
    parameters.update(changes)
    return collect(**parameters), release, manifest


def test_complete_declared_evidence_is_pass_but_release_remains_no_go(
    tmp_path: Path,
) -> None:
    report, _release_dir, _manifest = _collect(tmp_path)
    assert report["release_verdict"] == "NO_GO"
    assert report["release_accepted"] is False
    assert report["production_authorized"] is False
    assert report["authoritative_status_unchanged"] is True
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


def test_missing_row_field_blocks_only_that_row(tmp_path: Path) -> None:
    report, release, manifest = _collect(tmp_path)
    receipts = json.loads(_row_receipts(tmp_path, manifest).read_text())
    receipts["rows"]["01"].pop("debian12")
    path = tmp_path / "row-receipts-incomplete.json"
    path.write_text(json.dumps(receipts), encoding="utf-8")
    changed = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release, row_receipts_path=path,
        campaign_report_path=_campaign(tmp_path),
    )
    first = changed["platform"]["rows"][0]
    assert first["row_id"] == "01"
    assert first["status"] == "BLOCKED"
    assert "debian12" in first["missing"]
    assert changed["platform"]["counts"]["PASS"] == 24


def test_row_receipt_source_mismatch_blocks(tmp_path: Path) -> None:
    release, manifest = _release(tmp_path)
    receipts = json.loads(_row_receipts(tmp_path, manifest).read_text())
    receipts["source_sha"] = "b" * 40
    path = tmp_path / "row-receipts-wrong-source.json"
    path.write_text(json.dumps(receipts), encoding="utf-8")
    report = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release, row_receipts_path=path,
        campaign_report_path=_campaign(tmp_path),
    )
    assert report["platform"]["counts"]["PASS"] == 0
    assert report["platform"]["counts"]["BLOCKED"] == 38
    assert report["platform"]["counts"]["NOT_TESTED"] == 0


def test_tampered_release_artifact_digest_blocks(tmp_path: Path) -> None:
    release, manifest = _release(tmp_path)
    digests = json.loads((release / "artifact-digests.json").read_text())
    digests["assets"][0]["sha256"] = "0" * 64
    (release / "artifact-digests.json").write_text(json.dumps(digests))
    report = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest),
        campaign_report_path=_campaign(tmp_path),
    )
    assert report["release_evidence"]["artifact_digests_valid"] is False
    assert report["platform"]["counts"]["PASS"] == 0


def test_absent_junit_never_passes(tmp_path: Path) -> None:
    release, manifest = _release(tmp_path)
    report = collect(
        junit_path=None, source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest),
        campaign_report_path=_campaign(tmp_path),
    )
    assert report["platform"]["counts"]["PASS"] == 0
    assert report["platform"]["counts"]["NOT_TESTED"] == 25
    assert report["platform"]["counts"]["BLOCKED"] == 13
    assert report["artifact_library"]["counts"]["PASS"] == 16


def test_absent_campaign_never_passes_library(tmp_path: Path) -> None:
    release, manifest = _release(tmp_path)
    report = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest),
        campaign_report_path=None,
    )
    assert report["artifact_library"]["counts"]["PASS"] == 0
    assert report["artifact_library"]["counts"]["NOT_TESTED"] == 16


def test_campaign_source_mismatch_blocks_library(tmp_path: Path) -> None:
    release, manifest = _release(tmp_path)
    report = collect(
        junit_path=_junit(tmp_path), source_sha=SOURCE, runner="win32",
        release_dir=release,
        row_receipts_path=_row_receipts(tmp_path, manifest),
        campaign_report_path=_campaign(tmp_path, source_sha="b" * 40),
    )
    assert report["artifact_library"]["counts"]["PASS"] == 0
    assert report["artifact_library"]["counts"]["BLOCKED"] == 16


def test_collector_does_not_modify_authoritative_status_text(tmp_path: Path) -> None:
    status = (
        Path(__file__).resolve().parents[1]
        / "docs" / "development" / "PLATFORM_1_0_ACCEPTANCE.md"
    )
    before = status.read_bytes()
    _collect(tmp_path)
    assert status.read_bytes() == before
