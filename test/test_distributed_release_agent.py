from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.dev.release import ReleaseManifest
from sofia.dev.release_signing import sign_manifest
from sofia.distributed.release_agent import AgentReleaseService
from sofia.run.release import directory_sha256
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 4, 23, 0, tzinfo=timezone.utc)


def make_bundle(root: Path, private, *, release_id="release-1"):
    bundle = root / release_id
    artifact = bundle / "artifact"
    artifact.mkdir(parents=True)
    wheel = artifact / "sofia_ada_lyra-0.1.0-py3-none-any.whl"
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
    lock = (
        b"cryptography==50.0.2 --hash=sha256:"
        + b"a" * 64
        + b"\n"
    )
    (artifact / "requirements.lock").write_bytes(lock)
    (bundle / "requirements.lock").write_bytes(lock)
    sbom = b"{}"
    provenance = b"{}"
    (bundle / "sbom.cdx.json").write_bytes(sbom)
    (bundle / "provenance.intoto.json").write_bytes(provenance)
    manifest = ReleaseManifest(
        release_id=release_id,
        git_revision="1" * 40,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_sha256=sha256(lock).hexdigest(),
        sbom_sha256=sha256(sbom).hexdigest(),
        provenance_sha256=sha256(provenance).hexdigest(),
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        constitution_sha256="2" * 64,
        configuration_schema_version=1,
        created_at=NOW,
        artifact_sha256=directory_sha256(artifact),
    )
    (bundle / "release-manifest.json").write_bytes(
        manifest.canonical_bytes()
    )
    (bundle / "release-signature.bin").write_bytes(
        sign_manifest(manifest, private_key=private)
    )
    (bundle / "signer-key-id.txt").write_text(
        "test-key\n",
        encoding="utf-8",
    )
    return bundle, manifest


def test_agent_release_service_verifies_stages_and_activates_signed_bundle(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    SQLiteStatePlane(state)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path = tmp_path / "release.pub"
    public_path.write_bytes(public)
    _, manifest = make_bundle(tmp_path / "inbox", private)

    service = AgentReleaseService(
        state_path=state,
        release_root=tmp_path / "runtime",
        inbox_root=tmp_path / "inbox",
        trusted_key_file=public_path,
        trusted_key_id="test-key",
    )

    staged = service.stage(
        {
            "release_id": manifest.release_id,
            "manifest_sha256": manifest.manifest_sha256,
        }
    )
    assert staged["staged"] is True

    active = service.activate(
        {
            "release_id": manifest.release_id,
            "manifest_sha256": manifest.manifest_sha256,
        }
    )
    assert active["active"] is True
    assert active["release_id"] == manifest.release_id
    assert active["manifest_sha256"] == manifest.manifest_sha256
