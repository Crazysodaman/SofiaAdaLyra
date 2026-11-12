"""B-004 stock Windows Authenticode gate refuses unsigned native bootstrap.

Positive publisher-signed WinVerifyTrust evidence requires an independently
approved real signing certificate and release artifact, not a disposable test
signature. This deliberately does NOT pretend to certify production signing.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = [
    pytest.mark.pkg_ui,
    pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 Authenticode"),
]
SCRIPT = Path(__file__).resolve().parents[1] / "packaging/installers/Install-Aegis.ps1"


@pytest.fixture
def fake_executable(tmp_path):
    path = tmp_path / "unsigned-disposable-bootstrap.exe"
    path.write_bytes(b"MZ\0\0not a signed Windows PE")
    return path, sha256(path.read_bytes()).hexdigest()


def invoke(*args):
    return subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
         *args], capture_output=True, text=True, timeout=30,
    )


def test_native_publisher_proof_refuses_unsigned_even_if_sha_matches(fake_executable):
    path, digest = fake_executable
    result = invoke(
        "-VerifyPublisherBootstrap", str(path),
        "-TrustedPublisherThumbprint", "a" * 40,
        "-TrustedBootstrapSha256", digest, "-Json",
    )
    assert result.returncode == 3
    assert "AUTHENTICODE_BINARY_ONLY" not in result.stdout
    assert "owner_approved" not in result.stdout


@pytest.mark.parametrize("defect", (
    "bad-cert-pin", "bad-sha", "no-cert", "no-sha",
    "service-install", "mixed-seed", "dry-run",
))
def test_native_publisher_proof_fail_closed_on_bad_or_ambiguous_input(
        fake_executable, defect):
    path, digest = fake_executable
    args = [
        "-VerifyPublisherBootstrap", str(path),
        "-TrustedPublisherThumbprint", "a" * 40,
        "-TrustedBootstrapSha256", digest, "-Json",
    ]
    if defect == "bad-cert-pin":
        args[3] = "not-a-certhash"
    elif defect == "bad-sha":
        args[5] = "0" * 64
    elif defect == "no-cert":
        args = args[:2] + args[4:]
    elif defect == "no-sha":
        args = args[:4] + args[6:]
    elif defect == "service-install":
        args += ["-Operation", "install"]
    elif defect == "mixed-seed":
        args += ["-VerifySeed", str(path)]
    else:
        args += ["-DryRun"]
    result = invoke(*args)
    assert result.returncode in (2, 3), (defect, result.stdout, result.stderr)
    assert "AUTHENTICODE_BINARY_ONLY" not in result.stdout
