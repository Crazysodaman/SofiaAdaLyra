"""Provenance policy tests; synthetic ZIPs/mocked gh are NOT real attestations."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import zipfile

import pytest

from sofia.platform.verify.keyless_release import (
    REPOSITORY, inspect_subject, prepare_subjects, verify_subjects,
)

SHA = "a" * 40
WORKFLOW = ".github/workflows/debian-release-candidate.yml"


def archive(tmp_path, name="integrated", *, revision=SHA, evidence_changes=None,
            prefix="", extra=None):
    directory = tmp_path / name
    directory.mkdir(exist_ok=True)
    path = directory / f"{name}.zip"
    evidence = {
        "git_revision": revision, "accepted": True, "tracked_tree_clean": True,
        "phase": "full", "commands": [{"returncode": 0}],
    }
    evidence.update(evidence_changes or {})
    evidence_bytes = json.dumps(evidence).encode()
    components = name == "components"
    manifest = {
        "git_revision": revision, "verification_phase": "full",
        "verification_evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
    }
    if components:
        manifest["components"] = [{"component": key} for key in ("sdk", "platform", "core")]
    with zipfile.ZipFile(path, "w") as target:
        target.writestr(prefix + "release-manifest.json", json.dumps(manifest))
        target.writestr(prefix + "verification-evidence.json", evidence_bytes)
        for wheel in (("sdk", "platform", "core") if components else ("integrated",)):
            target.writestr(prefix + f"artifact/{wheel}.whl", b"synthetic test wheel")
        for key, value in (extra or {}).items():
            # A string filename is normalized by ZipInfo on Windows. Build
            # the raw malicious header rather than accidentally a safe path.
            entry = zipfile.ZipInfo()
            entry.filename = key
            target.writestr(entry, value)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def subjects(tmp_path):
    first, first_digest = archive(tmp_path, prefix="release-evidence/")
    second, second_digest = archive(tmp_path, "components")
    output = tmp_path / "policy"
    prepare_subjects([(first.parent, first_digest), (second.parent, second_digest)], SHA, output)
    return output, first, second


def test_real_upload_layouts_prepare_exact_archive_digests(subjects):
    output, first, second = subjects
    rows = json.loads((output / "subjects.json").read_text())
    assert [row["format"] for row in rows] == ["integrated", "components"]
    for path in (first, second):
        assert f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path}" in (
            output / "subjects.sha256"
        ).read_text()


def test_raw_client_filename_without_zip_extension_is_supported(tmp_path):
    first, first_digest = archive(tmp_path)
    second, second_digest = archive(tmp_path, "components")
    first.rename(first.parent / "artifact")
    second.rename(second.parent / "artifact")
    output = tmp_path / "policy"
    prepare_subjects([(first.parent, first_digest), (second.parent, second_digest)], SHA, output)
    assert len(json.loads((output / "subjects.json").read_text())) == 2


@pytest.mark.parametrize("change", [
    {"accepted": False}, {"tracked_tree_clean": False}, {"phase": "static"},
    {"git_revision": "b" * 40}, {"commands": []},
    {"commands": [{"returncode": 1}]}, {"commands": [{"returncode": False}]},
])
def test_nonpassing_or_unbound_evidence_cannot_be_attested(tmp_path, change):
    path, digest = archive(tmp_path, evidence_changes=change)
    with pytest.raises(ValueError):
        inspect_subject(path, digest, SHA)


def test_tampered_download_is_rejected_before_archive_inspection(tmp_path):
    path, digest = archive(tmp_path)
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="digest mismatch"):
        inspect_subject(path, digest, SHA)


@pytest.mark.parametrize("name", (
    "../escape", "/absolute", "bad\\entry", "C:/absolute", "bad\x00entry",
))
def test_archive_traversal_is_refused_without_extraction(tmp_path, name):
    path, digest = archive(tmp_path, extra={name: "untrusted"})
    with pytest.raises(ValueError, match="unsafe release archive"):
        inspect_subject(path, digest, SHA)


def test_redirected_subject_cannot_be_signed(tmp_path):
    path, digest = archive(tmp_path)
    link = tmp_path / "redirect.zip"
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip("host denies unprivileged symlinks")
    with pytest.raises(ValueError, match="redirected"):
        inspect_subject(link, digest, SHA)


def verify(subjects, tmp_path, run, **context):
    output, *_ = subjects
    values = dict(repository=REPOSITORY, workflow=WORKFLOW,
                  source_ref="refs/heads/main", revision=SHA)
    values.update(context)
    receipt = tmp_path / "receipt.json"
    verify_subjects(output / "subjects.json", receipt=receipt, run=run, **values)
    return receipt


def test_verifier_enforces_all_identity_constraints_and_both_digests(subjects, tmp_path):
    commands = []

    def mocked_gh(command, **kwargs):
        commands.append(command)
        assert kwargs == dict(check=True, capture_output=True, text=True, timeout=180)
        return SimpleNamespace(stdout='[{"test_only": "not a real attestation"}]')

    receipt = verify(subjects, tmp_path, mocked_gh)
    assert len(commands) == 2
    for command in commands:
        for flag, expected in {
            "--repo": REPOSITORY, "--signer-workflow": f"{REPOSITORY}/{WORKFLOW}",
            "--source-ref": "refs/heads/main", "--source-digest": SHA,
            "--signer-digest": SHA, "--predicate-type": "https://slsa.dev/provenance/v1",
            "--cert-oidc-issuer": "https://token.actions.githubusercontent.com",
        }.items():
            assert command[command.index(flag) + 1] == expected
        assert "--deny-self-hosted-runners" in command
        assert "--bundle" not in command  # Online repository identity resolution.
    assert json.loads(receipt.read_text())["production_authorized"] is False


@pytest.mark.parametrize("context", [
    {"repository": "attacker/SofiaAdaLyra"}, {"workflow": ".github/workflows/other.yml"},
    {"source_ref": "refs/pull/121/merge"}, {"revision": "short"},
])
def test_unapproved_context_denied_before_gh(subjects, tmp_path, context):
    def forbidden(*args, **kwargs):
        pytest.fail("unapproved context reached cryptographic verifier")
    with pytest.raises(ValueError):
        verify(subjects, tmp_path, forbidden, **context)
    assert not (tmp_path / "receipt.json").exists()


def test_failed_crypto_verification_removes_stale_receipt(subjects, tmp_path):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("stale success")
    def reject(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)
    with pytest.raises(subprocess.CalledProcessError):
        verify(subjects, tmp_path, reject)
    assert not receipt.exists()


def test_empty_cryptographic_result_cannot_report_success(subjects, tmp_path):
    with pytest.raises(ValueError, match="no cryptographically verified"):
        verify(subjects, tmp_path, lambda *a, **k: SimpleNamespace(stdout="[]"))
    assert not (tmp_path / "receipt.json").exists()


def test_late_subject_mutation_prevents_success_receipt(subjects, tmp_path):
    _, first, _ = subjects
    count = 0
    def mutate_after_last_verification(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            first.write_bytes(first.read_bytes() + b"late mutation")
        return SimpleNamespace(stdout='[{"test_only": true}]')
    with pytest.raises(ValueError, match="changed during"):
        verify(subjects, tmp_path, mutate_after_last_verification)
    assert not (tmp_path / "receipt.json").exists()
