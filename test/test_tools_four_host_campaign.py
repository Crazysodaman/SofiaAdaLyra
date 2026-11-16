"""The D028 four-host campaign consumes only declared, byte-checked evidence."""
from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
import json
from pathlib import Path
import struct

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.platform_release import (
    PlatformReleaseAsset, PlatformReleaseManifest, PlatformReleaseTarget,
)
from tools.aegis_four_host_campaign import (
    D028_TOPOLOGY_PATH, LIB_ROWS, run_campaign,
)

pytestmark = pytest.mark.pkg_ops

SOURCE = "a" * 40
SIGNER = "test-p6-campaign"
TT = "2026-11-15T00:00:00+00:00"
HOST_TARGET = {
    "W-EMPTY": PlatformReleaseTarget.WINDOWS_X86_64,
    "D-HUB": PlatformReleaseTarget.DEBIAN12_X86_64,
    "D-CLIENT": PlatformReleaseTarget.DEBIAN12_X86_64,
    "W-PEER": PlatformReleaseTarget.WINDOWS_X86_64,
}


def _topology() -> dict:
    return json.loads(D028_TOPOLOGY_PATH.read_text(encoding="utf-8"))


def _key(tmp_path: Path):
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "trusted-public.pem"
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path.write_bytes(public)
    return key, path, public


def _elf() -> bytes:
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 62)
    return bytes(data) + b"GLIBC_2.34\0"


def _pe() -> bytes:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<H", data, 68, 0x8664)
    struct.pack_into("<H", data, 88, 0x20B)
    return bytes(data)


def _write(root: Path, relative: str, data: bytes) -> dict:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"receipt_path": relative, "receipt_sha256": sha256(data).hexdigest()}


def _release(
    root: Path, *, target: PlatformReleaseTarget, source_sha: str,
    wheels: dict[str, Path], service: bytes, key: Ed25519PrivateKey,
):
    assets = root / "assets"
    assets.mkdir(parents=True)
    files: dict[str, tuple[str, bytes]] = {}
    for kind, wheel in wheels.items():
        files[wheel.name] = (kind, wheel.read_bytes())
    service_name = (
        "aegis-platform-service.exe"
        if target is PlatformReleaseTarget.WINDOWS_X86_64
        else "aegis-platform-service"
    )
    files[service_name] = ("service", service)
    files["python-runtime.zip"] = ("python-runtime", b"test-runtime")
    files["dependency-index.json"] = ("dependency-lock", b'{"wheels":[]}')
    files["sbom.json"] = ("sbom", b'{"bomFormat":"CycloneDX"}')
    files["provenance.json"] = ("provenance", b'{"synthetic":true}')
    assets_list = []
    for name, (kind, data) in sorted(files.items()):
        (assets / name).write_bytes(data)
        assets_list.append(PlatformReleaseAsset(
            kind, ArtifactReference(name, sha256(data).hexdigest(), len(data)),
        ))
    manifest = PlatformReleaseManifest(
        "test-release", "0.1.0", 1, source_sha, target,
        SDK_PROTOCOL_VERSION, "3.12.16", tuple(assets_list),
    )
    signature = b64encode(key.sign(manifest.digest.encode("ascii"))).decode("ascii")
    (root / "release-manifest.json").write_bytes(manifest.canonical_bytes)
    (root / "release-signature.json").write_bytes(json.dumps({
        "signer_key_id": SIGNER, "signature_b64": signature,
    }, sort_keys=True, separators=(",", ":")).encode())
    service_sha = sha256(service).hexdigest()
    return manifest, service_sha, {
        name: sha256(data).hexdigest() for name, (_, data) in files.items()
    }


def _host_receipt(root: Path, host: str, service_sha: str) -> dict:
    service_receipt = _write(
        root, f"artifacts/hosts/{host}-service.json",
        json.dumps({"host": host, "observation": "synthetic"}).encode(),
    )
    boot = _write(
        root, f"artifacts/hosts/{host}-boot.json",
        json.dumps({"host": host, "boot": "synthetic"}).encode(),
    )
    return {
        "host_id": host,
        "release_target": HOST_TARGET[host].value,
        "platform_id": f"00000000-0000-4000-8000-{host.casefold():0<12}"[:36],
        "service_binary_sha256": service_sha,
        "signer_key_id": SIGNER,
        "os_build": "synthetic-test-build",
        "service_receipt": {
            "observed": True, "result": "SERVICE_HEALTHY", **service_receipt,
        },
        "boot_receipts": [boot],
    }


def _case(root: Path, scenario: str, *, manifest, service_sha: str,
          content_sha: str) -> dict:
    positive = _write(
        root, f"artifacts/receipts/{scenario}-positive.json",
        json.dumps({"scenario": scenario, "case": "positive"}).encode(),
    )
    negative = _write(
        root, f"artifacts/receipts/{scenario}-negative.json",
        json.dumps({"scenario": scenario, "case": "negative"}).encode(),
    )
    receipts = {}
    for field in (
        "owner_authorization_receipts", "source_trust_receipts",
        "transfer_receipts", "install_or_runtime_receipts",
    ):
        receipts[field] = [_write(
            root, f"artifacts/receipts/{scenario}-{field}.json",
            json.dumps({"scenario": scenario, "kind": field}).encode(),
        )]
    return {
        "schema": "aegis.d028.library-case.v1",
        "scenario_id": scenario,
        "source_sha": SOURCE,
        "status": "PASS",
        "owner_team": "E",
        "workflow_url": "https://ci.invalid/aegis/runs/1",
        "host_ids": list(HOST_TARGET),
        "os_builds": ["synthetic-test-build"],
        "sdk_protocol": "1.0",
        "release_target": PlatformReleaseTarget.DEBIAN12_X86_64.value,
        "manifest_sha256": manifest.digest,
        "artifact_manifest_sha256": service_sha,
        "artifact_content_sha256": content_sha,
        "publisher_signer_key_id": SIGNER,
        "positive_cases": [{"case_id": "positive", "result": "PASS", **positive}],
        "negative_cases": [{
            "case_id": "negative", "result": "DENIED",
            "denial_observed": True, **negative,
        }],
        "witnessed_at": TT,
        "reviewer": "synthetic-reviewer",
        "observed_result": "synthetic harness fixture only",
        "remaining_blockers": [],
        **receipts,
    }


def _bundle(tmp_path: Path, platform_wheels: dict[str, Path]):
    root = tmp_path / "evidence"
    root.mkdir()
    key, trusted_key, public = _key(tmp_path)
    deb, deb_service, deb_assets = _release(
        root / "release-debian12-x86_64",
        target=PlatformReleaseTarget.DEBIAN12_X86_64, source_sha=SOURCE,
        wheels=platform_wheels, service=_elf(), key=key,
    )
    _win, win_service, _win_assets = _release(
        root / "release-windows-x86_64",
        target=PlatformReleaseTarget.WINDOWS_X86_64, source_sha=SOURCE,
        wheels=platform_wheels, service=_pe(), key=key,
    )
    artifacts = []
    for host in HOST_TARGET:
        service_bytes = (
            _pe() if HOST_TARGET[host] is PlatformReleaseTarget.WINDOWS_X86_64
            else _elf()
        )
        record = _write(
            root, f"artifacts/services/{host}-service.bin", service_bytes,
        )
        artifacts.append({"path": record["receipt_path"],
                          "sha256": record["receipt_sha256"]})
    (root / "signed-artifacts.json").write_text(json.dumps({
        "source_sha": SOURCE, "artifacts": artifacts,
    }), encoding="utf-8")
    hosts = [
        _host_receipt(
            root, host,
            win_service if HOST_TARGET[host] is PlatformReleaseTarget.WINDOWS_X86_64
            else deb_service,
        )
        for host in HOST_TARGET
    ]
    (root / "host-inventory.json").write_text(json.dumps({
        "source_sha": SOURCE, "hosts": hosts,
    }), encoding="utf-8")
    transfers = []
    for source_host, target_host, digest in (
        ("D-HUB", "D-CLIENT", deb_service),
        ("W-PEER", "D-CLIENT", win_service),
    ):
        receipt = _write(
            root, f"artifacts/cross/{source_host}-{target_host}.json",
            json.dumps({"transfer": [source_host, target_host]}).encode(),
        )
        transfers.append({
            "source_host": source_host, "target_host": target_host,
            "artifact_sha256": digest, "signer_key_id": SIGNER,
            "result": "TRANSFER_VERIFIED", **receipt,
        })
    (root / "cross-host-receipts.json").write_text(json.dumps({
        "source_sha": SOURCE, "receipts": transfers,
    }), encoding="utf-8")
    denials = []
    for host in HOST_TARGET:
        receipt = _write(
            root, f"artifacts/denials/{host}.json",
            json.dumps({"host": host, "denied": True}).encode(),
        )
        denials.append({
            "host_id": host, "denied": True, "denial_observed": True,
            **receipt,
        })
    (root / "network-denials.json").write_text(json.dumps({
        "source_sha": SOURCE, "denials": denials,
    }), encoding="utf-8")
    backup = _write(
        root, "artifacts/backup/restore.json",
        json.dumps({"restore": True}).encode(),
    )
    (root / "backup-restore.json").write_text(json.dumps({
        "source_sha": SOURCE, "restore_verified": True,
        "excludes": ["sofia.db", "core_identity", "owner_secret"],
        **backup,
    }), encoding="utf-8")
    content_sha = deb_assets[platform_wheels["sdk"].name]
    for scenario in LIB_ROWS:
        (root / f"{scenario}.json").write_text(json.dumps(
            _case(
                root, scenario, manifest=deb, service_sha=deb_service,
                content_sha=content_sha,
            )
        ), encoding="utf-8")
    return root, key, trusted_key, public, deb, deb_service


def _run(tmp_path: Path, platform_wheels: dict[str, Path], **changes):
    root, key, trusted_key, public, deb, service = _bundle(
        tmp_path, platform_wheels,
    )
    parameters = dict(
        source_sha=SOURCE,
        topology=_topology(),
        evidence_dir=root,
        trusted_public_key=trusted_key,
        trusted_key_sha256=sha256(public).hexdigest(),
        trusted_signer_key_id=SIGNER,
    )
    parameters.update(changes)
    return run_campaign(**parameters), root, trusted_key


def test_no_evidence_is_not_tested_and_never_pass() -> None:
    report = run_campaign(source_sha=SOURCE, topology=_topology())
    assert report["mode"] == "NO_EVIDENCE"
    assert report["counts"]["NOT_TESTED"] == 16
    assert report["counts"]["PASS"] == 0
    assert report["release_accepted"] is False
    assert report["acceptance"] == "NOT_CLAIMED"


def test_simulation_is_explicitly_labeled() -> None:
    report = run_campaign(
        source_sha=SOURCE, topology=_topology(), simulate=True,
    )
    assert report["mode"] == "SIMULATED"
    assert report["simulated"] is True
    assert report["simulation_label"].startswith("SIMULATED_")
    assert report["counts"]["SIMULATED"] == 16
    assert report["counts"]["PASS"] == 0
    assert report["installed_host_certified"] is False


def test_complete_declared_evidence_passes_bundle_checks_only(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, _root, _key = _run(tmp_path, platform_wheels)
    assert report["mode"] == "EVIDENCE"
    assert report["counts"]["PASS"] == 16
    assert report["counts"]["BLOCKED"] == 0
    assert all(host["status"] == "PASS" for host in report["hosts"].values())
    assert all(
        release["signature_verified"] is True
        for release in report["releases"].values()
    )
    assert report["status_scope"] == "EVIDENCE_BUNDLE_ONLY"
    assert report["installed_host_certified"] is False
    assert report["release_accepted"] is False
    assert report["acceptance"] == "NOT_CLAIMED"


def test_missing_negative_case_blocks(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, root, _key = _run(tmp_path, platform_wheels)
    case = json.loads((root / "LIB-07.json").read_text())
    case.pop("negative_cases")
    (root / "LIB-07.json").write_text(json.dumps(case), encoding="utf-8")
    rerun = run_campaign(
        source_sha=SOURCE, topology=_topology(), evidence_dir=root,
        trusted_public_key=_key, trusted_key_sha256=None,
        trusted_signer_key_id=SIGNER,
    )
    scenario = next(item for item in rerun["scenarios"] if item["scenario_id"] == "LIB-07")
    assert scenario["status"] == "BLOCKED"
    assert "negative_cases" in scenario["missing"]


def test_tampered_receipt_fails(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, root, key = _run(tmp_path, platform_wheels)
    receipt = root / "artifacts" / "receipts" / "LIB-05-positive.json"
    receipt.write_bytes(receipt.read_bytes() + b"tampered")
    rerun = run_campaign(
        source_sha=SOURCE, topology=_topology(), evidence_dir=root,
        trusted_public_key=key, trusted_key_sha256=None,
        trusted_signer_key_id=SIGNER,
    )
    scenario = next(item for item in rerun["scenarios"] if item["scenario_id"] == "LIB-05")
    assert scenario["status"] == "FAIL"
    assert any("BYTES_MISMATCH" in item for item in scenario["invalid"])


def test_wrong_case_source_sha_fails(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, root, key = _run(tmp_path, platform_wheels)
    case = json.loads((root / "LIB-06.json").read_text())
    case["source_sha"] = "b" * 40
    (root / "LIB-06.json").write_text(json.dumps(case), encoding="utf-8")
    rerun = run_campaign(
        source_sha=SOURCE, topology=_topology(), evidence_dir=root,
        trusted_public_key=key, trusted_key_sha256=None,
        trusted_signer_key_id=SIGNER,
    )
    scenario = next(item for item in rerun["scenarios"] if item["scenario_id"] == "LIB-06")
    assert scenario["status"] == "FAIL"
    assert "SOURCE_SHA_MISMATCH" in scenario["invalid"]


def test_without_trusted_key_no_scenario_passes(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, root, _key = _run(
        tmp_path, platform_wheels, trusted_public_key=None,
        trusted_key_sha256=None, trusted_signer_key_id=None,
    )
    assert report["mode"] == "EVIDENCE"
    assert report["counts"]["PASS"] == 0
    assert all(
        release["signature_verified"] is False
        for release in report["releases"].values()
    )


@pytest.mark.parametrize("defect", (
    "production", "second_primary", "wan", "fake_release_pass", "source_sha",
))
def test_invalid_topology_is_rejected(defect: str) -> None:
    topology = _topology()
    source = SOURCE
    if defect == "production":
        topology["live_production_targets"] = ["FORBIDDEN"]
    elif defect == "second_primary":
        topology["logical_library"]["primary_count"] = 2
    elif defect == "wan":
        topology["network_isolation"]["user_production_lan"] = "ALLOW"
    elif defect == "fake_release_pass":
        topology["release_accepted"] = True
    else:
        source = "not-a-sha"
    with pytest.raises((ValueError, RuntimeError)):
        run_campaign(source_sha=source, topology=topology)


def test_missing_host_receipt_blocks(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, root, key = _run(tmp_path, platform_wheels)
    inventory = json.loads((root / "host-inventory.json").read_text())
    inventory["hosts"] = inventory["hosts"][:-1]
    (root / "host-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    rerun = run_campaign(
        source_sha=SOURCE, topology=_topology(), evidence_dir=root,
        trusted_public_key=key, trusted_key_sha256=None,
        trusted_signer_key_id=SIGNER,
    )
    assert rerun["counts"]["PASS"] == 0
    assert any("HOST_COUNT" in item for item in rerun["evidence_invalid"])


def test_missing_metadata_file_blocks(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, root, key = _run(tmp_path, platform_wheels)
    (root / "cross-host-receipts.json").unlink()
    rerun = run_campaign(
        source_sha=SOURCE, topology=_topology(), evidence_dir=root,
        trusted_public_key=key, trusted_key_sha256=None,
        trusted_signer_key_id=SIGNER,
    )
    assert rerun["counts"]["PASS"] == 0
    assert "cross-host-receipts.json" in rerun["evidence_missing"]


def test_fabricated_signed_artifact_digest_fails(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    report, root, key = _run(tmp_path, platform_wheels)
    signed = json.loads((root / "signed-artifacts.json").read_text())
    signed["artifacts"][0]["sha256"] = "0" * 64
    (root / "signed-artifacts.json").write_text(json.dumps(signed), encoding="utf-8")
    rerun = run_campaign(
        source_sha=SOURCE, topology=_topology(), evidence_dir=root,
        trusted_public_key=key, trusted_key_sha256=None,
        trusted_signer_key_id=SIGNER,
    )
    assert rerun["counts"]["PASS"] == 0
    assert any("BYTE_INTEGRITY_FAILED" in item for item in rerun["evidence_invalid"])
