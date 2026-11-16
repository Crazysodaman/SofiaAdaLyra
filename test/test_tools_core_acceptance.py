"""Core 1.0 acceptance collector tests.

These tests prove the collector is conservative: PASS requires every declared
evidence kind to be present and valid, skipped tests and missing negatives are
not passes, stale/mismatched receipts fail, and G8 is never inferred from
disposable or source-only evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from tools.aegis_core_acceptance import (
    G8_SCHEMA,
    INVENTORY,
    RECEIPTS_SCHEMA,
    collect,
)

pytestmark = pytest.mark.pkg_verify

SOURCE = "a" * 40
SIGNER = "test-signer"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
HOSTS = {
    "DISPOSABLE-01": "DISPOSABLE",
    "INSTALLED-01": "INSTALLED",
    "REMOTE-01": "REMOTE",
    "OWNER-01": "OWNER",
}
HOST_BY_CLASS = {value: key for key, value in HOSTS.items()}


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
        "signer_key_id": SIGNER,
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


def _receipts(
    tmp_path: Path,
    *,
    mutate=None,
    g8: dict | None = None,
) -> Path:
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
        "signers": [SIGNER],
        "hosts": {
            host_id: {"host_class": host_class}
            for host_id, host_class in HOSTS.items()
        },
        "items": items,
    }
    if mutate is not None:
        mutate(document)
    if g8 is not None:
        document["g8"] = g8
    path = root / "core-receipts.json"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


def _run(tmp_path: Path, **changes):
    parameters = dict(source_sha=SOURCE, runner="win32", now=NOW)
    if "junit_path" not in changes:
        parameters["junit_path"] = _junit(tmp_path)
    if "receipts_path" not in changes:
        parameters["receipts_path"] = _receipts(tmp_path)
    parameters.update(changes)
    return collect(**parameters)


def test_complete_evidence_passes_every_in_scope_item(tmp_path: Path) -> None:
    report = _run(tmp_path)
    scoped = [item for item in INVENTORY if item.release_scope]
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
    report = _run(tmp_path, receipts_path=None)
    assert report["core_release_verdict"] == "NO_GO"
    assert report["source_only"] is True
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["inventory"]["release_scope_counts"]["BLOCKED"] > 0
    assert report["g8"]["certified"] is False


def test_absent_junit_and_receipts_are_not_tested(tmp_path: Path) -> None:
    report = collect(
        junit_path=None, source_sha=SOURCE, runner="win32",
        receipts_path=None, now=NOW,
    )
    assert report["core_release_verdict"] == "NO_GO"
    assert report["inventory"]["counts"]["PASS"] == 0
    assert report["inventory"]["counts"]["NOT_TESTED"] == len(INVENTORY)
    assert report["g8"]["certified"] is False


def test_skipped_source_test_is_never_a_pass(tmp_path: Path) -> None:
    report = _run(
        tmp_path, junit_path=_junit(tmp_path, skip_file="test_beliefs_store.py"),
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
    report = _run(
        tmp_path, junit_path=_junit(tmp_path, fail_file="test_identity.py"),
    )
    affected = next(
        item for item in report["inventory"]["items"] if item["id"] == "CORE-01"
    )
    assert affected["state"] == "FAIL"
    assert "SOURCE_TEST_FAILED" in affected["invalid"]


def test_stale_receipt_fails(tmp_path: Path) -> None:
    def mutate(document: dict) -> None:
        document["items"]["CORE-01"]["evidence"]["owner_host"]["witnessed_at"] = (
            "2000-01-01T00:00:00+00:00"
        )

    report = _run(tmp_path, receipts_path=_receipts(tmp_path, mutate=mutate))
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-01"
    )
    assert item["state"] == "FAIL"
    assert any("RECEIPT_STALE" in value for value in item["invalid"])


def test_mismatched_artifact_digest_fails(tmp_path: Path) -> None:
    def mutate(document: dict) -> None:
        document["items"]["CORE-07"]["evidence"]["installed_artifact"][
            "artifact_sha256"
        ] = "0" * 64

    report = _run(tmp_path, receipts_path=_receipts(tmp_path, mutate=mutate))
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-07"
    )
    assert item["state"] == "FAIL"
    assert any("ARTIFACT_DIGEST_MISMATCH" in value for value in item["invalid"])


def test_mismatched_host_fails(tmp_path: Path) -> None:
    def mutate(document: dict) -> None:
        document["items"]["CORE-02"]["evidence"]["disposable_process"][
            "host_id"
        ] = "UNREGISTERED-HOST"

    report = _run(tmp_path, receipts_path=_receipts(tmp_path, mutate=mutate))
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-02"
    )
    assert item["state"] == "FAIL"
    assert any("HOST_NOT_REGISTERED" in value for value in item["invalid"])


def test_mismatched_source_sha_fails(tmp_path: Path) -> None:
    def mutate(document: dict) -> None:
        document["source_sha"] = "c" * 40

    report = _run(tmp_path, receipts_path=_receipts(tmp_path, mutate=mutate))
    assert report["receipts"]["schema_ok"] is False
    assert report["inventory"]["release_scope_counts"]["PASS"] == 0
    assert report["inventory"]["release_scope_counts"]["FAIL"] == len(
        [item for item in INVENTORY if item.release_scope]
    )
    assert report["core_release_verdict"] == "NO_GO"


def test_missing_negative_cases_fails(tmp_path: Path) -> None:
    def mutate(document: dict) -> None:
        document["items"]["CORE-03"]["evidence"]["disposable_process"][
            "negative_cases"
        ] = []

    report = _run(tmp_path, receipts_path=_receipts(tmp_path, mutate=mutate))
    item = next(
        row for row in report["inventory"]["items"] if row["id"] == "CORE-03"
    )
    assert item["state"] == "FAIL"
    assert any("NEGATIVE_CASES_MISSING" in value for value in item["invalid"])


def test_disposable_evidence_never_certifies_g8(tmp_path: Path) -> None:
    report = _run(tmp_path)
    assert report["g8"]["status"] == "NOT_CERTIFIED"
    assert report["g8"]["certified"] is False
    assert report["g8"]["real_host_receipt_supplied"] is False

    def mutate(document: dict) -> None:
        document["g8"] = {
            "schema": G8_SCHEMA,
            "source_sha": SOURCE,
            "real_host": True,
            "host_id": "DISPOSABLE-01",
            "host_class": "OWNER",
            "remote_host_id": "REMOTE-01",
            "signer_key_id": SIGNER,
            "artifact_path": "artifacts/disposable-g8.bin",
            "artifact_sha256": "d" * 64,
            "application_sha256": "b" * 64,
            "observed": True,
            "result": "PASS",
            "witnessed_at": (NOW - timedelta(hours=1)).isoformat(),
            "negative_cases": ["denied"],
            "owner_approved": True,
        }

    root = tmp_path / "evidence"
    _write_artifact(root, "artifacts/disposable-g8.bin", b"disposable")
    report = _run(
        tmp_path, receipts_path=_receipts(tmp_path, mutate=mutate),
    )
    assert report["g8"]["status"] == "NOT_CERTIFIED"
    assert report["g8"]["certified"] is False


def test_distinct_real_host_g8_receipt_can_certify(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    digest = _write_artifact(root, "artifacts/g8-owner.bin", b"real-owner-host")
    g8 = {
        "schema": G8_SCHEMA,
        "source_sha": SOURCE,
        "real_host": True,
        "host_id": "OWNER-01",
        "host_class": "OWNER",
        "remote_host_id": "REMOTE-01",
        "signer_key_id": SIGNER,
        "artifact_path": "artifacts/g8-owner.bin",
        "artifact_sha256": digest,
        "application_sha256": "b" * 64,
        "observed": True,
        "result": "PASS",
        "witnessed_at": (NOW - timedelta(hours=1)).isoformat(),
        "negative_cases": ["guest-cannot-become-owner"],
        "owner_approved": True,
    }
    report = _run(tmp_path, receipts_path=_receipts(tmp_path, g8=g8))
    assert report["g8"]["status"] == "CERTIFIED"
    assert report["g8"]["certified"] is True
    assert report["core_release_verdict"] == "GO"
    assert report["release_accepted"] is True


def test_collector_does_not_modify_authoritative_documents(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    documents = (
        repo / "docs" / "sofia2" / "CORE_1_0_PLAN.md",
        repo / "docs" / "development"
        / "AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md",
    )
    before = {path: path.read_bytes() for path in documents}
    _run(tmp_path)
    assert all(path.read_bytes() == before[path] for path in documents)
