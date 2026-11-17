"""Team B AG-D011 safety contract: one-step guided launchers, no service mutation.

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


def test_theme_remains_one_canonical_22_token_manifest():
    data = json.loads(THEME.read_text(encoding="utf-8"))
    assert data["schema"] == "aegis.ui.theme.v1"
    assert len(data["tokens"]) == 22
    for key, expected in {
        "primary": "#9400D3", "accent": "#00C2FF",
        "success": "#39FF14", "background": "#000000",
    }.items():
        assert data["tokens"][key] == expected


def test_bootstrap_contract_does_not_embed_an_alternative_authority():
    bash = BASH.read_text(encoding="utf-8")
    windows = POWERSHELL.read_text(encoding="utf-8")
    for source in (bash, windows):
        assert "aegis-theme-v1.json" in source
        assert "SAFE/STOP" in source
        assert "NO_COLOR" in source
        assert "platform_installer_guided" in source
        assert "PREVIEW ONLY" not in source
        assert "MODE=INSTALL" in source
    for disallowed in ("sudo systemctl ", "Start-Service ", "New-Service ",
                       "Invoke-Expression ", "curl | bash", "SOFIA_OWNER_SECRET",
                       "--authorize-all", "--approval-id", "-ApprovalId"):
        assert disallowed not in bash and disallowed not in windows


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"),
                    reason="Linux Bash runner only")
@pytest.mark.parametrize("extra", [
    ["--authorize-all"], ["--operation", "bogus"],
    ["--operation"], ["--check", "--operation", "install"],
    ["--operation", "install", "--check"],
    ["--operation", "install", "--operation", "doctor"],
    ["--operation", "install", "--dry-run"],
])
def test_bash_unknown_or_ambiguous_requests_rejected(extra):
    result = subprocess.run(
        ["bash", str(BASH), *extra],
        input="", capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2


@pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"),
                    reason="Linux Bash runner only")
@pytest.mark.parametrize("incomplete", [
    ["--stage-capsule", "/tmp/unknown.zip"],
    ["--capsule-signature", "/tmp/signature.raw"],
    ["--staging-destination", "/tmp/aegis-stage"],
    ["--operation", "install", "--stage-capsule", "/tmp/unknown.zip"],
    ["--check", "--stage-capsule", "/tmp/unknown.zip"],
    ["--stage-capsule", "/tmp/unknown.zip", "--dry-run"],
])
def test_bash_capsule_staging_requires_complete_separate_trust_inputs(incomplete):
    # Even a purported signed capsule cannot become a native service action.
    result = subprocess.run(
        ["bash", str(BASH), *incomplete],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2
    assert "SIGNED_MEDIA_STAGED_NOT_INSTALLED" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 runner only")
def test_powershell_rejects_ambiguous_check_plus_operation():
    result = subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass",
         "-NoProfile", "-NonInteractive", "-File",
         str(POWERSHELL), "-Check", "-Operation", "install", "-Json"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 2
    assert "cannot be combined" in result.stderr
