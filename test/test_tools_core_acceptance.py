"""Core 1.0 acceptance collector tests.

These tests prove the collector is conservative: PASS requires every declared
evidence kind plus a real Ed25519 signature from a caller-trusted key.  Unsigned,
forged, wrong-key, wrong-SHA, stale, skipped and missing-negative evidence can
never pass.  G8 is never certified by disposable fixtures.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.aegis_core_acceptance import (
    G8_SCHEMA,
    INVENTORY,
    RECEIPTS_SCHEMA,
    CoreAcceptanceError,
    collect,
)

pytestmark = pytest.mark.pkg_verify

SOURCE = "a" * 40
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
HOSTS = {
    "DISPOSABLE-01": "DISPOSABLE",
    "INSTALLED-01": "INSTALLED",
    "REMOTE-01": "REMOTE",
    "OWNER-01": "OWNER",
}
HOST_BY_CLASS = {value: key for key, value in HOSTS.items()}


@dataclass(frozen=True)
class Signer:
    key: Ed25519PrivateKey
    key_id: str
    public_path: Path
    fingerprint: str


def _signer(tmp_path: Path, *, key_id: str = "owner-key-1", name: str = "owner") -> Signer:
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path = tmp_path / f"{name}.pem"
    path.write_bytes(public)
    return Signer(key, key_id, path, sha256(public).hexdigest())


def _canonical(document: dict) -> bytes:
    payload = {key: value for key, value in document.items() if key != "signature"}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sign(document: dict, signer: Signer) -> None:
    signature = signer.key.sign(_canonical(document))
    document["signature"] = {
        "algorithm": "Ed25519",
        "signer_key_id": signer.key_id,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }


def _junit(
    tmp_path: Path,
    *,
    skip_file: str | None = None,
    fail_file: str | None = None,
) -> Path:
    cases: list[str] = []
    seen: set[str] = set()
    for spec in INVENTORY:
        for filename in spec.source_tests:
            if filename in seen:
                continue
            seen.add(filename)
            stem = filename[:-3] if filename.endswith(".py") else filename
            if filename == skip_file:
                cases.append(
                    f'<testcase classname="test.{stem}" name="probe">'
                    '<skipped message="host-conditional"/></testcase>'
                )
            elif filename == fail_file:
                cases.append(
                    f'<testcase classname="test.{stem}" name="probe">'
                    '<failure message="synthetic failure"/></testcase>'
                )
            else:
                cases.append(
                    f'<testcase classname="test.{stem}" name="probe"/>'
                )
    path = tmp_path / "core-acceptance-junit.xml"
    path.write_text(
        "<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def _write_artifact(root: Path, relative: str, data: bytes) -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256(data).hexdigest()


def _entry(root: Path, item_id: str, kind: str) -> dict:
    host_class = {
        "disposable_process": "DISPOSABLE",
        "installed_artifact": "INSTALLED",
        "remote_conversation": "REMOTE",
        "owner_host": "OWNER",
    }[kind]
    relative = f"artifacts/{item_id}-{kind}.bin"
    digest = _write_artifact(root, relative, f"{item_id}:{kind}".encode())
    entry = {
        "host_id": HOST_BY_CLASS[host_class],
        "host_class": host_class,
        "signer_key_id": "owner-key-1",
        "artifact_path": relative,
        "artifact_sha256": digest,
        "application_sha256": "b" * 64,
        "observed": True,
        "result": "PASS",
        "witnessed_at": (NOW - timedelta(hours=1)).isoformat(),
        "negative_cases": ["unauthorized-attempt-denied"],
    }
    if kind == "owner_host":
        entry["real_host"] = True
    return entry


def _receipt_document(tmp_path: Path, signer: Signer, mutate=None) -> dict:
    root = tmp_path / "evidence"
    root.mkdir(parents=True, exist_ok=True)
    items = {}
    for spec in INVENTORY:
        evidence = {
            kind: _entry(root, spec.item_id, kind)
            for kind in spec.required
            if kind != "source_tests"
        }
        items[spec.item_id] = {
            "source_sha": SOURCE,
            "evidence": evidence,
        }
    document = {
        "schema": RECEIPTS_SCHEMA,
        "source_sha": SOURCE,
        "hosts": {
            host_id: {"host_class": host_class}
            for host_id, host_class in HOSTS.items()
        },
        "items": items,
    }
    for record in document["items"].values():
        for entry in record["evidence"].values():
            entry["signer_key_id"] = signer.key_id
    if mutate is not None:
        mutate(document)
    return document


def _receipts(
    tmp_path: Path,
    signer: Signer,
    *,
    mutate=None,
    sign: bool = True,
) -> Path:
    document = _receipt_document(tmp_path, signer, mutate)
    if sign:
        _sign(document, signer)
    path = tmp_path / "evidence" / "core-receipts.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def _g8_document(tmp_path: Path, signer: Signer, *, host_class: str = "DISPOSABLE") -> dict:
    root = tmp_path / "evidence"
    digest = _write_artifact(root, "artifacts/g8-owner.bin", b"disposable-g8")
    return {
        "schema": G8_SCHEMA,
        "source_sha": SOURCE,
        "hosts": {
            "G8-HOST": {"host_class": host_class},
            "G8-REMOTE": {"host_class": "REMOTE"},
        },
        "receipt": {
            "host_id": "G8-HOST",
            "host_class": host_class,
            "signer_key_id": signer.key_id,
            "artifact_path": "artifacts/g8-owner.bin",
            "artifact_sha256": digest,
            "application_sha256": "b" * 64,
            "observed": True,
            "result": "PASS",
            "witnessed_at": (NOW - timedelta(hours=1)).isoformat(),
            "negative_cases": ["guest-cannot-become-owner"],
            "real_host": True,
            "remote_host_id": "G8-REMOTE",
            "owner_approved": True,
        },
    }


def _write_g8(tmp_path: Path, signer: Signer, document: dict) -> Path:
    _sign(document, signer)
    path = tmp_path / "evidence" / "g8-receipt.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def _run(tmp_path: Path, signer: Signer, **changes):
    parameters = dict(
        source_sha=SOURCE,
        runner="win32",
        now=NOW,
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        signer_key_id=signer.key_id,
    )
    if "junit_path" not in changes:
        parameters["junit_path"] = _junit(tmp_path)
    if "receipts_path" not in changes:
        parameters["receipts_path"] = _receipts(tmp_path, signer)
    parameters.update(changes)
    return collect(**parameters)


def _scoped_items(report: dict) -> list[dict]:
    return [item for item in report["inventory"]["items"] if item["release_scope"]]


def test_valid_signed_complete_evidence_passes_at_declared_scope(
    tmp_path: Path,
) -> None:
    signer = _signer(tmp_path)
    report = _run(tmp_path, signer)
    scoped = [item for item in INVENTORY if item.release_scope]
    assert report["receipts"]["signature_valid"] is True
    assert report["inventory"]["release_scope_counts"]["PASS"] == len(scoped)
    assert report["inventory"]["release_scope_counts"]["FAIL"] == 0
    assert report["inventory"]["counts"]["PASS"] == len(scoped)
    deferred = next(
        item for item in report["inventory"]["items"] if item["id"] == "CORE-34"
    )
    assert deferred["state"] == "NOT_TESTED"
    assert deferred["release_scope"] is False
    assert report["core_release_verdict"] == "GO"
    assert report["release_accepted"] is False
    assert report["g8"]["status"] == "NOT_CERTIFIED"
    assert report["authoritative_status_unchanged"] is True


def test_missing_receipts_are_not_passes(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report = _run(tmp_path, signer, receipts_path=None)
    assert report["core_release_verdict"] == "NO_GO"
    assert report["source_only"] is True
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["inventory"]["release_scope_counts"]["BLOCKED"] > 0
    assert report["g8"]["certified"] is False


def test_absent_junit_and_receipts_are_not_tested(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report = collect(
        junit_path=None, source_sha=SOURCE, runner="win32",
        receipts_path=None, now=NOW,
        trusted_public_key=signer.public_path,
        trusted_key_sha256=signer.fingerprint,
        signer_key_id=signer.key_id,
    )
    assert report["core_release_verdict"] == "NO_GO"
    assert report["inventory"]["counts"]["PASS"] == 0
    assert report["inventory"]["counts"]["NOT_TESTED"] == len(INVENTORY)
    assert report["g8"]["certified"] is False


def test_unsigned_receipts_are_blocked_and_no_go(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, sign=False),
    )
    assert report["receipts"]["signature_valid"] is False
    assert report["evidence_scope"] == "UNTRUSTED_RECEIPTS"
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["inventory"]["release_scope_counts"]["BLOCKED"] == len(
        [item for item in INVENTORY if item.release_scope]
    )
    assert all(item["state"] == "BLOCKED" for item in _scoped_items(report))
    assert any(
        "RECEIPTS_SIGNATURE_UNTRUSTED" in value
        for item in _scoped_items(report) for value in item["missing"]
    )
    assert report["core_release_verdict"] == "NO_GO"
    assert report["release_accepted"] is False


def test_forged_signature_is_blocked(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    path = _receipts(tmp_path, signer)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["signature"]["signature_b64"] = base64.b64encode(
        b"\x00" * 64
    ).decode("ascii")
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    report = _run(tmp_path, signer, receipts_path=path)
    assert report["receipts"]["signature_valid"] is False
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["core_release_verdict"] == "NO_GO"
    assert all(item["state"] == "BLOCKED" for item in _scoped_items(report))


def test_wrong_key_signature_is_blocked(tmp_path: Path) -> None:
    trusted = _signer(tmp_path, key_id="owner-key-1", name="trusted")
    other = _signer(tmp_path, key_id="owner-key-1", name="other")
    report = _run(
        tmp_path, trusted,
        receipts_path=_receipts(tmp_path, other),
    )
    assert report["receipts"]["signature_valid"] is False
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["core_release_verdict"] == "NO_GO"
    assert all(item["state"] == "BLOCKED" for item in _scoped_items(report))


def test_wrong_source_sha_never_passes(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["source_sha"] = "c" * 40

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    assert report["receipts"]["signature_valid"] is True
    assert report["receipts"]["schema_ok"] is False
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["core_release_verdict"] == "NO_GO"


def test_skipped_source_test_is_never_a_pass(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report = _run(
        tmp_path, signer,
        junit_path=_junit(tmp_path, skip_file="test_beliefs_store.py"),
    )
    affected = [
        item for item in report["inventory"]["items"]
        if item["id"] in {"CORE-06", "B01"}
    ]
    assert affected
    for item in affected:
        assert item["state"] != "PASS"
        assert any(
            "SOURCE_TEST_SKIPPED:test_beliefs_store.py" in value
            for value in item["missing"]
        )
    assert report["core_release_verdict"] == "NO_GO"


def test_failed_source_test_is_a_fail(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    report = _run(
        tmp_path, signer,
        junit_path=_junit(tmp_path, fail_file="test_identity.py"),
    )
    affected = next(
        item for item in report["inventory"]["items"] if item["id"] == "CORE-01"
    )
    assert affected["state"] == "FAIL"
    assert "SOURCE_TEST_FAILED" in affected["invalid"]


def test_stale_receipt_fails(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["items"]["CORE-01"]["evidence"]["owner_host"]["witnessed_at"] = (
            "2000-01-01T00:00:00+00:00"
        )

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-01"
    )
    assert item["state"] == "FAIL"
    assert any("RECEIPT_STALE" in value for value in item["invalid"])
    assert report["core_release_verdict"] == "NO_GO"


def test_future_receipt_fails(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["items"]["CORE-01"]["evidence"]["owner_host"]["witnessed_at"] = (
            NOW + timedelta(days=2)
        ).isoformat()

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-01"
    )
    assert item["state"] == "FAIL"
    assert any("RECEIPT_FROM_FUTURE" in value for value in item["invalid"])


def test_mismatched_artifact_digest_fails(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["items"]["CORE-07"]["evidence"]["installed_artifact"][
            "artifact_sha256"
        ] = "0" * 64

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-07"
    )
    assert item["state"] == "FAIL"
    assert any("ARTIFACT_DIGEST_MISMATCH" in value for value in item["invalid"])


def test_mismatched_host_fails(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["items"]["CORE-02"]["evidence"]["disposable_process"][
            "host_id"
        ] = "UNREGISTERED-HOST"

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-02"
    )
    assert item["state"] == "FAIL"
    assert any("HOST_NOT_REGISTERED" in value for value in item["invalid"])


def test_missing_negative_cases_fails(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["items"]["CORE-03"]["evidence"]["disposable_process"][
            "negative_cases"
        ] = []

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-03"
    )
    assert item["state"] == "FAIL"
    assert any("NEGATIVE_CASES_MISSING" in value for value in item["invalid"])


def test_unknown_receipt_field_fails(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["signers"] = [signer.key_id]

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    assert report["receipts"]["signature_valid"] is True
    assert report["receipts"]["schema_ok"] is False
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["core_release_verdict"] == "NO_GO"


def test_duplicate_json_keys_are_refused(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    path = _receipts(tmp_path, signer)
    raw = path.read_text(encoding="utf-8")
    raw = raw.replace('"items":', '"items": {}, "items":', 1)
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(CoreAcceptanceError):
        _run(tmp_path, signer, receipts_path=path)


def test_embedded_g8_is_never_certified(tmp_path: Path) -> None:
    signer = _signer(tmp_path)

    def mutate(document: dict) -> None:
        document["g8"] = _g8_document(tmp_path, signer)["receipt"]

    report = _run(
        tmp_path, signer,
        receipts_path=_receipts(tmp_path, signer, mutate=mutate),
    )
    assert report["g8"]["status"] == "NOT_CERTIFIED"
    assert report["g8"]["certified"] is False
    assert report["release_accepted"] is False


def test_disposable_g8_receipt_is_never_certified(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    document = _g8_document(tmp_path, signer, host_class="DISPOSABLE")
    g8_path = _write_g8(tmp_path, signer, document)
    report = _run(tmp_path, signer, g8_receipt_path=g8_path)
    assert report["g8_receipt"]["signature_valid"] is True
    assert report["g8"]["status"] == "NOT_CERTIFIED"
    assert report["g8"]["certified"] is False
    assert report["release_accepted"] is False


def test_collector_does_not_modify_authoritative_documents(tmp_path: Path) -> None:
    signer = _signer(tmp_path)
    repo = Path(__file__).resolve().parents[1]
    documents = (
        repo / "docs" / "sofia2" / "CORE_1_0_PLAN.md",
        repo / "docs" / "development"
        / "AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md",
    )
    before = {path: path.read_bytes() for path in documents}
    _run(tmp_path, signer)
    assert all(path.read_bytes() == before[path] for path in documents)
