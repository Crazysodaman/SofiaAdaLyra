from datetime import datetime, timezone
from hashlib import sha256
import json
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.dev.release import ReleaseManifest
from sofia.dev.release_cli import sign_release_bundle
from sofia.run.release import directory_sha256
from sofia.safe.release_ed25519 import Ed25519ReleaseSignatureVerifier


def test_sign_release_bundle_writes_host_verifiable_signature(tmp_path):
    root = tmp_path / "bundle"
    artifact = root / "artifact"
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
    lock = b"x==1 --hash=sha256:" + b"a" * 64 + b"\n"
    (artifact / "requirements.lock").write_bytes(lock)
    (root / "requirements.lock").write_bytes(lock)
    sbom = b"{}"
    provenance = b"{}"
    (root / "sbom.cdx.json").write_bytes(sbom)
    (root / "provenance.intoto.json").write_bytes(provenance)
    verification = json.dumps(
        {
            "phase": "full",
            "git_revision": "1" * 40,
            "tracked_tree_clean": True,
            "accepted": True,
            "commands": [{"name": "pytest", "returncode": 0}],
        },
        sort_keys=True,
    ).encode()
    (root / "verification-evidence.json").write_bytes(verification)
    manifest = ReleaseManifest(
        release_id="r1",
        git_revision="1" * 40,
        application_version="0.1.0",
        python_version="3.12",
        dependency_lock_sha256=sha256(lock).hexdigest(),
        sbom_sha256=sha256(sbom).hexdigest(),
        provenance_sha256=sha256(provenance).hexdigest(),
        verification_evidence_sha256=sha256(verification).hexdigest(),
        verification_phase="full",
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        constitution_sha256="2" * 64,
        configuration_schema_version=1,
        created_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
        artifact_sha256=directory_sha256(artifact),
    )
    (root / "release-manifest.json").write_bytes(manifest.canonical_bytes())

    private = Ed25519PrivateKey.generate()
    private_path = tmp_path / "key.pem"
    private_path.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    signature = sign_release_bundle(
        root,
        private_key_path=private_path,
        signer_key_id="test-key",
    )

    assert (root / "release-signature.bin").read_bytes() == signature
    assert (root / "signer-key-id.txt").read_text().strip() == "test-key"
    verifier = Ed25519ReleaseSignatureVerifier({"test-key": public})
    assert verifier.verify(
        manifest=manifest,
        signature=signature,
        signer_key_id="test-key",
    )
