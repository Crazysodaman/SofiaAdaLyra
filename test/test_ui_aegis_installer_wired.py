"""The legacy --wired manual-input path is retired in favour of one-step guided.

The guided orchestrator discovers the release bundle, trust anchor and bundled
runtime. Launchers may not ask the owner for a Python path, release root, hashes,
approval ids or service commands on the default path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.pkg_ui
ROOT = Path(__file__).resolve().parents[1]
BASH = ROOT / "packaging/installers/install-aegis.sh"
POWERSHELL = ROOT / "packaging/installers/Install-Aegis.ps1"


def test_guided_launchers_do_not_use_the_legacy_manual_cli_adapter():
    bash = BASH.read_text(encoding="utf-8")
    windows = POWERSHELL.read_text(encoding="utf-8")
    for source in (bash, windows):
        assert "platform_installer_guided" in source
        assert "platform_installer_cli" not in source
        assert "--wired" not in source
        assert "$Wired" not in source
        assert "-Wired" not in source
        assert "--release-root" not in source
        assert "--bundled-python" not in source
        for forbidden in (
            "--approval-id", "-ApprovalId", "--code-approval-id",
            "-CodeApprovalId", "--safe-state", "-SafeState",
            "--minimum-revision", "-MinimumRevision",
        ):
            assert forbidden not in source


def test_guided_launchers_use_only_bundle_relative_discovery():
    bash = BASH.read_text(encoding="utf-8")
    windows = POWERSHELL.read_text(encoding="utf-8")
    for source in (bash, windows):
        assert "release-manifest.json" in source
        assert "runtime/python" in source
        assert "installer" in source
        assert "trusted-publisher.pem" in source
        assert "trust.json" in source
