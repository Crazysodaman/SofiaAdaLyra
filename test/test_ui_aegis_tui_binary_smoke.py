"""Native binary smoke contract: no Core, no guessed live service state."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "target" / "debug" / (
    "aegis_tui.exe" if os.name == "nt" else "aegis_tui"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    assert BIN.is_file(), "CI must build actual Rust TUI binary before testing"
    return subprocess.run(
        [str(BIN), *args], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        timeout=15,
    )


def test_native_tui_headless_status_is_explicitly_unavailable():
    observed = _run("--status")
    assert observed.returncode == 3
    assert "status=UNAVAILABLE" in observed.stdout
    assert "source=UNVERIFIED" in observed.stdout
    assert "HEALTHY" not in observed.stdout
    assert "\x1b" not in observed.stdout


def test_native_tui_unknown_command_is_denied():
    observed = _run("--install")
    assert observed.returncode == 2
    assert "Unknown option" in observed.stderr
    assert not observed.stdout


def test_native_tui_noninteractive_menu_is_plain_and_does_not_modify_service():
    observed = _run("--plain")
    assert observed.returncode == 0
    assert "AEGIS PLATFORM" in observed.stdout
    assert "MANAGEMENT SERVICE UNAVAILABLE" in observed.stdout
    assert "[8] Fleet" in observed.stdout
    assert "[9] Library > Catalog" in observed.stdout
    assert "[15] Library > History" in observed.stdout
    assert "No operation performed" in observed.stdout or (
        "no operation performed" in observed.stdout.lower()
    )
    assert "\x1b" not in observed.stdout


def test_native_tui_help_is_read_only():
    observed = _run("--help")
    assert observed.returncode == 0
    assert "read-only" in observed.stdout.lower()


def test_native_tui_library_status_is_unknown_not_empty_or_verified():
    observed = _run("--library-status")
    assert observed.returncode == 3
    assert "library=UNAVAILABLE" in observed.stdout
    assert "source=UNVERIFIED" in observed.stdout
    assert "received_bytes=UNKNOWN" in observed.stdout
    assert "verified_bytes=UNKNOWN" in observed.stdout
    assert "installed=UNKNOWN" in observed.stdout
    assert "internet_fallback=DISABLED" in observed.stdout
    assert "actions=DISABLED" in observed.stdout
    assert "\x1b" not in observed.stdout


def test_native_tui_library_json_is_unknown_not_empty_or_installed():
    import json

    result = _run("--library-json")
    assert result.returncode == 3
    data = json.loads(result.stdout)
    assert data["schema"] == "aegis.ui.library.offline-status.v1"
    assert data["library"] == "UNAVAILABLE"
    assert data["source"] == "UNVERIFIED"
    for field in ("catalog", "downloaded", "verified", "staged",
                  "installed", "active", "received_bytes", "verified_bytes"):
        assert data[field] is None
    assert data["internet_fallback"] == "DISABLED"
    assert data["actions_enabled"] is False
    assert "\x1b" not in result.stdout


def test_native_tui_json_platform_status_is_not_false_live_success():
    import json

    result = _run("--status-json")
    assert result.returncode == 3
    data = json.loads(result.stdout)
    assert data["schema"] == "aegis.ui.platform.status-display.v1"
    assert data["status"] == "UNAVAILABLE"
    assert data["source"] == "UNVERIFIED"
    assert data["platform_generation"] is None
    assert data["operator_stop"] is None
    assert data["core_started"] is None
    assert data["installation"] == "NOT_CURRENTLY_VERIFIED"
    assert data["actions_enabled"] is False
    assert "\x1b" not in result.stdout
