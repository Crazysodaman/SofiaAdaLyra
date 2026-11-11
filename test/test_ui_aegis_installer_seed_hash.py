"""B-003 clean-host pre-interpreter byte check, deliberately NOT signature verification.

The PowerShell/Bash entrypoints use stock OS tooling only. No native
installation, owner approval, Core, network or project Python is invoked by
these subprocesses; pytest/Python is only the test harness.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.pkg_ui
ROOT = Path(__file__).resolve().parents[1]
BASH = ROOT / "packaging/installers/install-aegis.sh"
POWERSHELL = ROOT / "packaging/installers/Install-Aegis.ps1"


@pytest.fixture
def seed(tmp_path):
    media = tmp_path / "offline-core-free-seed.bin"
    media.write_bytes(b"Aegis disposable unsigned media bytes for hash preflight only")
    return media, sha256(media.read_bytes()).hexdigest()


@pytest.mark.skipif(os.name == "nt", reason="Bash preflight exercised on Linux")
def test_stock_linux_media_preflight_has_no_install_side_effect(seed, tmp_path):
    media, digest = seed
    output = subprocess.run(
        ["bash", str(BASH), "--verify-seed", str(media),
         "--trusted-seed-sha256", digest, "--json"],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "NO_COLOR": "1"},
    )
    assert output.returncode == 0, output.stderr
    payload = json.loads(output.stdout)
    assert payload["result"] == "HASH_MATCH_ONLY"
    assert payload["sha256"] == digest
    assert payload["signature_verified"] is False
    assert payload["executed"] is False
    assert payload["owner_approved"] is False
    assert payload["core_activated"] is False
    assert not (tmp_path / "sofia.db").exists()
    assert "\x1b" not in output.stdout


@pytest.mark.skipif(os.name == "nt", reason="Bash preflight exercised on Linux")
@pytest.mark.parametrize("mutation", (
    "wrong-digest", "invalid-pin", "no-pin", "missing", "symlink", "parent-symlink",
    "protected-install", "dry-run", "conflicting-check",
))
def test_stock_linux_media_preflight_fails_closed(seed, tmp_path, mutation):
    media, digest = seed
    args = ["--verify-seed", str(media), "--trusted-seed-sha256", digest, "--json"]
    if mutation == "wrong-digest":
        args[-2:] = ["--trusted-seed-sha256", "0" * 64, "--json"]
    elif mutation == "invalid-pin":
        args[-2:] = ["--trusted-seed-sha256", "123", "--json"]
    elif mutation == "no-pin":
        args = ["--verify-seed", str(media), "--json"]
    elif mutation == "missing":
        args[1] = str(tmp_path / "missing.bin")
    elif mutation == "symlink":
        link = tmp_path / "linked.bin"
        link.symlink_to(media)
        args[1] = str(link)
    elif mutation == "parent-symlink":
        folder = tmp_path / "actual"
        folder.mkdir()
        target = folder / "media.bin"
        target.write_bytes(media.read_bytes())
        alias = tmp_path / "redirect"
        alias.symlink_to(folder, target_is_directory=True)
        args[1] = str(alias / "media.bin")
    elif mutation == "protected-install":
        args += ["--operation", "install"]
    elif mutation == "dry-run":
        args += ["--dry-run"]
    else:
        args += ["--check"]
    output = subprocess.run(
        ["bash", str(BASH), *args],
        capture_output=True, text=True, timeout=15,
    )
    assert output.returncode in (2, 3), (mutation, output.stdout, output.stderr)
    assert not (tmp_path / "sofia.db").exists()
    assert "HASH_MATCH_ONLY" not in output.stdout


@pytest.mark.skipif(os.name != "nt", reason="Native Windows PS5.1 only")
def test_stock_windows_media_preflight_has_no_install_side_effect(seed, tmp_path):
    media, digest = seed
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
         str(POWERSHELL), "-VerifySeed", str(media),
         "-TrustedSeedSha256", digest, "-Json"],
        capture_output=True, text=True, timeout=25,
        env={**os.environ, "AEGIS_INSTALLER_TEST_DIAGNOSTICS": "1"},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["result"] == "HASH_MATCH_ONLY"
    assert data["signature_verified"] is False
    assert data["executed"] is False
    assert data["core_activated"] is False
    assert data["sha256"] == digest
    assert not (tmp_path / "sofia.db").exists()


@pytest.mark.skipif(os.name != "nt", reason="Native Windows PS5.1 only")
@pytest.mark.parametrize("mutation", (
    "wrong-digest", "invalid-pin", "no-pin", "missing", "protected-install",
    "dry-run", "conflicting-check",
))
def test_stock_windows_media_preflight_denies_without_trusted_input(seed, tmp_path, mutation):
    media, digest = seed
    args = ["-VerifySeed", str(media), "-TrustedSeedSha256", digest, "-Json"]
    if mutation == "wrong-digest":
        args[3] = "0" * 64
    elif mutation == "invalid-pin":
        args[3] = "invalid"
    elif mutation == "no-pin":
        args = ["-VerifySeed", str(media), "-Json"]
    elif mutation == "missing":
        args[1] = str(tmp_path / "missing.bin")
    elif mutation == "protected-install":
        args += ["-Operation", "install"]
    elif mutation == "dry-run":
        args += ["-DryRun"]
    else:
        args += ["-Check"]
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
         str(POWERSHELL), *args],
        capture_output=True, text=True, timeout=25,
    )
    assert result.returncode in (2, 3), (mutation, result.stdout, result.stderr)
    assert "HASH_MATCH_ONLY" not in result.stdout
    assert not (tmp_path / "sofia.db").exists()
