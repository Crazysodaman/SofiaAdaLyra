"""B-004 stock-OS publisher proof checks actual Ed25519 signature.

The OS native CLI does not invoke Python, but this pytest fixture uses the
repository's disposable signer to build real canonical release bytes.
Authenticating a manifest is NOT verifying every asset or approving install.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from test.test_ops_platform_installer_bundle import reviewed

pytestmark = [
    pytest.mark.pkg_ui,
    pytest.mark.skipif(os.name == "nt" or not shutil.which("openssl"),
                       reason="Debian Bash and stock OpenSSL native proof"),
]
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging/installers/install-aegis.sh"


def args_for(reviewed):
    builder, stage, manifest, pinned = reviewed
    return [
        "--verify-publisher", str(stage),
        "--publisher-key", str(pinned["trusted_public_key"]),
        "--publisher-sha256", pinned["trusted_key_sha256"],
        "--publisher-signer", pinned["trusted_signer_key_id"],
        "--json",
    ]


def exec_review(reviewed, *, args=None):
    return subprocess.run(
        ["bash", str(SCRIPT), *(args if args is not None else args_for(reviewed))],
        capture_output=True, text=True, timeout=20,
        env={**os.environ, "NO_COLOR": "1"},
    )


def test_stock_cli_independently_checks_actual_ed25519_manifest_signature(reviewed):
    builder, stage, manifest, pinned = reviewed
    result = exec_review(reviewed)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "aegis.installer.publisher-check.v1"
    assert payload["result"] == "SIGNED_MANIFEST_ONLY"
    assert payload["signature_verified"] is True
    assert payload["manifest_sha256"] == manifest.digest
    assert payload["signer_key_id"] == pinned["trusted_signer_key_id"]
    assert payload["publisher_key_sha256"] == pinned["trusted_key_sha256"]
    assert payload["assets_verified"] is False
    assert payload["executed"] is False
    assert payload["owner_approved"] is False
    assert payload["core_activated"] is False
    assert "\x1b" not in result.stdout


@pytest.mark.parametrize("defect", [
    "wrong-root", "wrong-signer", "no-fingerprint", "noncanonical-envelope",
    "signature-tamper", "trailing-newline", "embedded-nul",
    "manifest-tamper", "key-inside-bundle",
    "key-symlink", "missing-manifest", "unapproved-operation", "dry-run",
])
def test_stock_cli_does_not_accept_hostile_publisher_or_grant_install(
        reviewed, defect, tmp_path):
    builder, stage, manifest, pinned = reviewed
    args = args_for(reviewed)
    if defect == "wrong-root":
        args[5] = "0" * 64
    elif defect == "wrong-signer":
        args[7] = "forged-signer"
    elif defect == "no-fingerprint":
        args = args[:4] + args[6:]
    elif defect == "noncanonical-envelope":
        file = stage / "release-signature.json"
        payload = json.loads(file.read_text())
        payload["owner_authorized"] = True
        file.write_text(json.dumps(payload, sort_keys=True))
    elif defect == "signature-tamper":
        file = stage / "release-signature.json"
        payload = json.loads(file.read_text())
        payload["signature_b64"] = "A" * 86 + "=="
        file.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    elif defect == "trailing-newline":
        file = stage / "release-signature.json"
        file.write_bytes(file.read_bytes() + b"\n")
    elif defect == "embedded-nul":
        file = stage / "release-signature.json"
        file.write_bytes(file.read_bytes() + b"\x00")
    elif defect == "manifest-tamper":
        file = stage / "release-manifest.json"
        file.write_bytes(file.read_bytes() + b" ")
    elif defect == "key-inside-bundle":
        key = stage / "self-trust.pem"
        key.write_bytes(Path(pinned["trusted_public_key"]).read_bytes())
        args[3] = str(key)
    elif defect == "key-symlink":
        key = tmp_path / "alias.pem"
        key.symlink_to(pinned["trusted_public_key"])
        args[3] = str(key)
    elif defect == "missing-manifest":
        (stage / "release-manifest.json").unlink()
    elif defect == "unapproved-operation":
        args += ["--operation", "install"]
    elif defect == "dry-run":
        args += ["--dry-run"]
    response = exec_review(reviewed, args=args)
    assert response.returncode in (2, 3), (defect, response.stdout, response.stderr)
    assert "SIGNED_MANIFEST_ONLY" not in response.stdout


def test_stock_publisher_proof_rejects_unknown_action_flag(reviewed):
    response = exec_review(reviewed, args=args_for(reviewed) + ["--authorize-all"])
    assert response.returncode == 2
