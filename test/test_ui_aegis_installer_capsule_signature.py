"""B-006 stock Debian Ed25519 signature over complete offline capsule bytes.

The disposable test key exists only in process memory; it is not an owner
principal, product publisher or production release signing authority.
The Bash verifier uses only system utilities and does not invoke Python.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

pytestmark = [
    pytest.mark.pkg_ui,
    pytest.mark.skipif(os.name == "nt", reason="stock Linux Bash/OpenSSL verifier"),
]
SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "packaging/installers/verify-aegis-capsule.sh"
)
SIGNER = "disposable-test-publisher"
DOMAIN = b"aegis.offline.capsule.v1\0"


@pytest.fixture
def sealed_capsule(tmp_path):
    media = tmp_path / "media"
    trust = tmp_path / "out-of-band-publisher-root"
    media.mkdir()
    trust.mkdir()
    capsule = media / "aegis-test-capsule.zip"
    capsule.write_bytes(b"synthetic test capsule, not real release material")
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    trusted = trust / "publisher.pem"
    trusted.write_bytes(public)
    signature = media / "capsule.sig"
    digest = sha256(capsule.read_bytes()).hexdigest()
    signature.write_bytes(key.sign(DOMAIN + SIGNER.encode("ascii") + b"\0"
                                   + digest.encode("ascii")))
    return capsule, signature, trusted, sha256(public).hexdigest()


def invoke(scope, *extra):
    capsule, signature, trusted, pin = scope
    return subprocess.run(
        ["bash", str(SCRIPT),
         "--capsule", str(capsule),
         "--signature", str(signature),
         "--publisher-key", str(trusted),
         "--publisher-sha256", pin,
         "--publisher-signer", SIGNER, *extra],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )


def test_stock_shell_signed_capsule_is_authenticated_without_install(sealed_capsule):
    syntax = subprocess.run(["bash", "-n", str(SCRIPT)],
                            capture_output=True, text=True, timeout=10)
    assert syntax.returncode == 0, syntax.stderr
    result = invoke(sealed_capsule)
    assert result.returncode == 0, result.stderr
    proof = json.loads(result.stdout)
    assert proof["schema"] == "aegis.offline.capsule-signature.v1"
    assert proof["result"] == "SIGNED_CAPSULE_BYTES_ONLY"
    assert proof["capsule_sha256"] == sha256(sealed_capsule[0].read_bytes()).hexdigest()
    assert proof["publisher_public_key_sha256"] == sealed_capsule[3]
    assert proof["publisher_delivery_verified"] is True
    assert proof["release_manifest_verified"] is False
    assert proof["release_assets_verified"] is False
    assert proof["publisher_revocation_current"] is False
    assert proof["owner_approved"] is False
    assert proof["executed"] is False
    assert proof["core_activated"] is False


@pytest.mark.parametrize("defect", (
    "changed-capsule", "wrong-publisher", "wrong-signer",
    "missing-key-pin", "bad-key-pin", "truncated-signature",
    "extra-signature-bytes", "publisher-in-media-dir",
    "capsule-symlink", "unknown-option",
))
def test_stock_shell_capsule_signature_refuses_hostile_input(
        sealed_capsule, defect, tmp_path):
    capsule, signature, public, pin = sealed_capsule
    override = (capsule, signature, public, pin)
    extra = ()
    if defect == "changed-capsule":
        with capsule.open("ab") as file:
            file.write(b"modified after signing")
    elif defect == "wrong-publisher":
        second = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        public.write_bytes(second)
    elif defect == "wrong-signer":
        extra = ("--publisher-signer", "forged")
    elif defect == "missing-key-pin":
        override = (capsule, signature, public, "")
    elif defect == "bad-key-pin":
        override = (capsule, signature, public, "f" * 64)
    elif defect == "truncated-signature":
        signature.write_bytes(signature.read_bytes()[:40])
    elif defect == "extra-signature-bytes":
        signature.write_bytes(signature.read_bytes() + b"extra")
    elif defect == "publisher-in-media-dir":
        internal = capsule.parent / "publisher.pem"
        internal.write_bytes(public.read_bytes())
        override = (capsule, signature, internal, pin)
    elif defect == "capsule-symlink":
        link = tmp_path / "alias.zip"
        link.symlink_to(capsule)
        override = (link, signature, public, pin)
    else:
        extra = ("--install",)
    outcome = invoke(override, *extra)
    assert outcome.returncode in (2, 3), (defect, outcome.stdout, outcome.stderr)
    assert "SIGNED_CAPSULE_BYTES_ONLY" not in outcome.stdout


def test_capsule_approval_cannot_be_created_by_command_line(sealed_capsule):
    for flag in ("--yes", "--force", "--approve", "--install", "--unsafe"):
        result = invoke(sealed_capsule, flag)
        assert result.returncode == 2
        assert "SIGNED_CAPSULE_BYTES_ONLY" not in result.stdout
