"""Real stock-Bash Debian12 offline prerequisites (read-only).

Only the pytest test runner uses Python. The evaluated shell source does
not invoke Python, Git, Cargo, Ollama, Core, curl, apt or a network service.
On non-Debian12/non-systemd CI hosts it must truthfully deny the target.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = [
    pytest.mark.pkg_ui,
    pytest.mark.skipif(os.name == "nt", reason="Debian stock-Bash host probe"),
]

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "packaging/installers/debian12-offline-prerequisites.sh"
)


def execute(*args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True, text=True, timeout=15,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )


def test_stock_shell_syntax_and_unknown_args_fail_closed():
    syntax = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True, text=True, timeout=10,
    )
    assert syntax.returncode == 0, syntax.stderr
    for bad in ("--yes", "--install", "--skip-trust", "--debian12", "--root"):
        result = execute(bad)
        assert result.returncode == 2, (bad, result.stdout, result.stderr)
        assert "PREREQUISITES_PRESENT_ONLY" not in result.stdout


def test_actual_os_prerequisites_never_assert_install_or_trust():
    result = execute("--json")
    assert result.returncode in (0, 3), result.stderr
    data = json.loads(result.stdout)
    assert data["schema"] == "aegis.installer.debian12-offline-prerequisites.v1"
    assert type(data["debian12"]) is bool
    assert type(data["x86_64"]) is bool
    assert type(data["openssl_ed25519"]) is bool
    assert type(data["systemd_manager"]) is bool
    if result.returncode == 0:
        assert data["result"] == "PREREQUISITES_PRESENT_ONLY"
        assert all(data[key] is True for key in (
            "debian12", "x86_64", "openssl_ed25519", "systemd_manager",
        ))
        assert data["missing_binaries"] == ""
    else:
        assert data["result"] == "BLOCKED"
        assert not all(data[key] for key in (
            "debian12", "x86_64", "openssl_ed25519", "systemd_manager",
        )) or bool(data["missing_binaries"])
    for key in ("network_requested", "download_performed", "publisher_trust_verified",
                "owner_authorized", "service_mutated", "core_activated"):
        assert data[key] is False


def test_human_readable_mode_is_not_an_authorization_grant():
    result = execute("--plain")
    assert result.returncode in (0, 3)
    assert "PUBLISHER_TRUST=NOT_VERIFIED" in result.stdout
    assert "INSTALL_AUTHORITY=NOT_CONNECTED" in result.stdout
    assert "SERVICE_MUTATION=FALSE" in result.stdout
