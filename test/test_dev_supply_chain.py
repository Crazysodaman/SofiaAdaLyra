from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import zipfile

import pytest

from sofia.dev.release_signing import sign_manifest
from sofia.dev.supply_chain import (
    canonical_dependency_lock,
    construct_release_evidence,
    generate_sbom,
    parse_requirements_lock,
    verify_release_evidence,
)
from sofia.safe.release_ed25519 import Ed25519ReleaseSignatureVerifier
from sofia.run.release import directory_sha256

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


NOW = datetime(2026, 10, 3, 3, 0, tzinfo=timezone.utc)
GIT = "1" * 40
CONSTITUTION = "2" * 64


def make_wheel(path: Path) -> Path:
    wheel = path / "sofia_ada_lyra-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("sofia/__init__.py", "")
        archive.writestr(
            "sofia_ada_lyra-0.1.0.dist-info/METADATA",
            "Name: sofia-ada-lyra\nVersion: 0.1.0\n",
        )
        archive.writestr(
            "sofia_ada_lyra-0.1.0.dist-info/RECORD",
            "",
        )
    return wheel


def make_lock(path: Path) -> Path:
    lock = path / "requirements.lock"
    lock.write_text(
        "# exact resolved production lock\n"
        "cryptography==46.0.1\n"
        "pypdf==6.1.1 --hash=sha256:" + ("a" * 64) + "\n",
        encoding="utf-8",
    )
    return lock


def make_verification(
    path: Path,
    *,
    accepted: bool = True,
    revision: str = GIT,
    tracked_tree_clean: bool = True,
) -> Path:
    evidence = path / "verification-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "phase": "full",
                "git_revision": revision,
                "tracked_tree_clean": tracked_tree_clean,
                "accepted": accepted,
                "commands": [{"name": "pytest", "returncode": 0 if accepted else 1}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return evidence


def test_lock_requires_exact_pins(tmp_path):
    lock = tmp_path / "bad.lock"
    lock.write_text("cryptography>=46\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact pin"):
        parse_requirements_lock(lock)


def test_lock_is_canonical_and_sorted(tmp_path):
    lock = make_lock(tmp_path)
    canonical = canonical_dependency_lock(lock).decode("utf-8")
    assert canonical.splitlines() == [
        "cryptography==46.0.1",
        "pypdf==6.1.1 --hash=sha256:" + ("a" * 64),
    ]


def test_sbom_is_deterministic_from_lock(tmp_path):
    lock = make_lock(tmp_path)
    first = generate_sbom(
        lock,
        application_name="sofia-ada-lyra",
        application_version="0.1.0",
    )
    second = generate_sbom(
        lock,
        application_name="sofia-ada-lyra",
        application_version="0.1.0",
    )
    assert first == second
    payload = json.loads(first)
    assert payload["bomFormat"] == "CycloneDX"
    assert [item["name"] for item in payload["components"]] == [
        "cryptography",
        "pypdf",
    ]


def test_construct_and_verify_release_evidence(tmp_path):
    lock = make_lock(tmp_path)
    wheel = make_wheel(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source", encoding="utf-8")
    output = tmp_path / "release"
    verification = make_verification(tmp_path)

    result = construct_release_evidence(
        release_id="sofia-0.1.0-test",
        git_revision=GIT,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_path=lock,
        wheel_path=wheel,
        source_dir=source,
        verification_evidence_path=verification,
        constitution_sha256=CONSTITUTION,
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        configuration_schema_version=1,
        output_dir=output,
        created_at=NOW,
    )

    verified = verify_release_evidence(output)
    assert verified.manifest_sha256 == result.manifest.manifest_sha256
    assert result.manifest.dependency_lock_sha256 == sha256(
        canonical_dependency_lock(lock)
    ).hexdigest()
    assert result.artifact_path.is_file()
    assert (result.artifact_path.parent / "requirements.lock").is_file()
    assert result.manifest.artifact_sha256 == directory_sha256(
        result.artifact_path.parent
    )


def test_verifier_rejects_tampered_artifact(tmp_path):
    lock = make_lock(tmp_path)
    wheel = make_wheel(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("source", encoding="utf-8")
    output = tmp_path / "release"
    verification = make_verification(tmp_path)
    result = construct_release_evidence(
        release_id="sofia-0.1.0-test",
        git_revision=GIT,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_path=lock,
        wheel_path=wheel,
        source_dir=source,
        verification_evidence_path=verification,
        constitution_sha256=CONSTITUTION,
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        configuration_schema_version=1,
        output_dir=output,
        created_at=NOW,
    )
    result.artifact_path.write_bytes(b"tampered")
    with pytest.raises(Exception):
        verify_release_evidence(output)


@pytest.mark.parametrize(
    ("accepted", "revision", "tracked_tree_clean", "message"),
    (
        (False, GIT, True, "not accepted"),
        (True, "9" * 40, True, "revision does not match"),
        (True, GIT, False, "clean tracked tree"),
    ),
)
def test_release_construction_requires_accepted_revision_bound_verification(
    tmp_path,
    accepted,
    revision,
    tracked_tree_clean,
    message,
):
    lock = make_lock(tmp_path)
    wheel = make_wheel(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("source", encoding="utf-8")
    verification = make_verification(
        tmp_path,
        accepted=accepted,
        revision=revision,
        tracked_tree_clean=tracked_tree_clean,
    )

    with pytest.raises(ValueError, match=message):
        construct_release_evidence(
            release_id="sofia-0.1.0-test",
            git_revision=GIT,
            application_version="0.1.0",
            python_version="3.12.10",
            dependency_lock_path=lock,
            wheel_path=wheel,
            source_dir=source,
            verification_evidence_path=verification,
            constitution_sha256=CONSTITUTION,
            state_schema_min=1,
            state_schema_max=1,
            fleet_protocol_version="1.0",
            fleet_agent_version="0.1.0",
            configuration_schema_version=1,
            output_dir=tmp_path / "release",
            created_at=NOW,
        )


def test_offline_signer_matches_existing_release_verifier(tmp_path):
    lock = make_lock(tmp_path)
    wheel = make_wheel(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("source", encoding="utf-8")
    verification = make_verification(tmp_path)
    result = construct_release_evidence(
        release_id="sofia-0.1.0-test",
        git_revision=GIT,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_path=lock,
        wheel_path=wheel,
        source_dir=source,
        verification_evidence_path=verification,
        constitution_sha256=CONSTITUTION,
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        configuration_schema_version=1,
        output_dir=tmp_path / "release",
        created_at=NOW,
    )

    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = sign_manifest(result.manifest, private_key=private)
    verifier = Ed25519ReleaseSignatureVerifier({"test-key": public_pem})

    assert verifier.verify(
        manifest=result.manifest,
        signature=signature,
        signer_key_id="test-key",
    ) is True
