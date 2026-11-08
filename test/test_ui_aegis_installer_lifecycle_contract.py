"""Team B AG-D011 safety contract: two preview launchers, no service mutation.

CI tests intentionally never invoke a real installation, owner approval or Core.
"""
from __future__ import annotations

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
THEME = ROOT / "contracts/ui/aegis-theme-v1.json"

MUTATIONS = ("install", "update", "repair", "rollback", "uninstall", "purge")
READ_ONLY = ("status", "doctor")


def test_theme_remains_one_canonical_22_token_manifest():
    data = json.loads(THEME.read_text(encoding="utf-8"))
    assert data["schema"] == "aegis.ui.theme.v1"
    assert len(data["tokens"]) == 22
    for key, expected in {
        "primary": "#9400D3", "accent": "#00C2FF",
        "success": "#39FF14", "background": "#000000",
    }.items():
        assert data["tokens"][key] == expected


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"),
                    reason="Linux Bash runner only")
@pytest.mark.parametrize("operation", READ_ONLY)
def test_bash_status_and_doctor_are_unverified_read_only(operation):
    result = subprocess.run(
        ["bash", str(BASH), "--operation", operation, "--json"],
        capture_output=True, text=True, timeout=15, env={**os.environ, "NO_COLOR": "1"},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["operation"] == operation
    assert data["result"] == "NO_CHANGES_MADE"
    assert data["service_state"] == "NOT_OBSERVED"
    assert data["signed_release"] == "NOT_VERIFIED"
    assert data["executed"] is False
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"),
                    reason="Linux Bash runner only")
@pytest.mark.parametrize("operation", MUTATIONS)
def test_bash_mutation_fails_closed_without_authority(operation, tmp_path):
    untouched = tmp_path / "protected-identity"
    result = subprocess.run(
        ["bash", str(BASH), "--operation", operation, "--dry-run", "--json"],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "NO_COLOR": "1", "AEGIS_IDENTITY_HOME": str(untouched)},
    )
    assert result.returncode == 3, result.stderr
    data = json.loads(result.stdout)
    assert data["operation"] == operation
    assert data["result"] == "BLOCKED"
    assert data["authority"] == "NOT_CONNECTED"
    assert not data["executed"] and not data["owner_approved"]
    assert not data["core_activated"]
    assert not untouched.exists()
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"),
                    reason="Linux Bash runner only")
@pytest.mark.parametrize("extra", [
    ["--authorize-all"], ["--operation", "bogus"],
    ["--operation"], ["--json"],
])
def test_bash_unknown_or_underspecified_requests_rejected(extra):
    result = subprocess.run(
        ["bash", str(BASH), *extra],
        input="", capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
@pytest.mark.parametrize("operation", READ_ONLY)
def test_powershell_status_and_doctor_are_unverified(operation):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
         str(POWERSHELL), "-Operation", operation, "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["operation"] == operation
    assert data["service_state"] == "NOT_OBSERVED"
    assert data["result"] == "NO_CHANGES_MADE"
    assert data["executed"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
@pytest.mark.parametrize("operation", MUTATIONS)
def test_powershell_mutation_fails_closed_without_authority(operation):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
         str(POWERSHELL), "-Operation", operation, "-DryRun", "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 3, result.stderr
    data = json.loads(result.stdout)
    assert data["operation"] == operation
    assert data["result"] == "BLOCKED"
    assert not data["owner_approved"] and not data["executed"]


def test_bootstrap_contract_does_not_embed_an_alternative_authority():
    bash = BASH.read_text(encoding="utf-8")
    windows = POWERSHELL.read_text(encoding="utf-8")
    for source in (bash, windows):
        assert "aegis-theme-v1.json" in source
        assert "SIGNED_RELEASE=NOT_VERIFIED" in source
        assert "SAFE/STOP" in source
        assert "NO_COLOR" in source
        assert "PREVIEW ONLY" in source or "PREVIEW_ONLY" in source
    for disallowed in ("sudo systemctl ", "Start-Service ", "New-Service ",
                       "Invoke-Expression ", "curl | bash", "SOFIA_OWNER_SECRET"):
        assert disallowed not in bash and disallowed not in windows
