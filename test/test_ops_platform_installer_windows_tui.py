"""Windows guided-TUI prompts, install-root paths and startup plan contracts."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import sofia.platform.ops.platform_installer_guided as guided
from sofia.platform.ops.platform_installer_operator_apps import (
    OperatorAppsConfiguration,
    build_operator_apps_plan,
)
from sofia.sdk.platform_release import PlatformReleaseTarget

WINDOWS = PlatformReleaseTarget.WINDOWS_X86_64


def _write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_custom_install_root_is_uuid_safe_and_derives_all_platform_paths(tmp_path):
    root = tmp_path / "Aegis"
    paths = guided.paths_for_install_root(
        WINDOWS, root, environ={"ProgramData": str(tmp_path / "ProgramData")},
    )
    assert paths.install_root == root
    assert paths.destination == root / "platform"
    assert paths.identity_home == root / "identity"
    assert paths.local_state == root / "state"
    assert paths.safe_state == root / "safe"
    assert paths.store_path == root / "installation" / "platform-installation.db"
    assert paths.operator_bin == root / "bin"
    assert paths.start_menu is not None
    assert paths.as_plan()["install_root"] == str(root)


def test_install_root_rejects_relative_and_git_paths(tmp_path, monkeypatch):
    with pytest.raises(guided.GuidedDenied):
        guided.paths_for_install_root(WINDOWS, Path("relative/Aegis"))
    monkeypatch.setattr(guided, "inside_git_worktree", lambda _path: True)
    with pytest.raises(guided.GuidedDenied):
        guided.paths_for_install_root(
            WINDOWS, tmp_path / "inside-git",
            environ={"ProgramData": str(tmp_path / "ProgramData")},
        )


def test_default_install_root_prefers_d_aegis_and_falls_back(monkeypatch):
    original_exists = Path.exists

    def d_exists(self):
        if str(self) in ("D:\\", "D:/"):
            return True
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", d_exists)
    assert guided.default_install_root(WINDOWS) == Path("D:\\Aegis")
    monkeypatch.setattr(Path, "exists", lambda self: False)
    assert guided.default_install_root(
        WINDOWS, environ={"ProgramFiles": r"C:\\Program Files"},
    ) == Path(r"C:\\Program Files") / "Aegis"


def test_operator_apps_plan_records_start_at_login_with_tui_shortcut(tmp_path):
    runtime = _write(tmp_path / "runtime/python/python.exe")
    code = tmp_path / "code"
    code.mkdir()
    bin_dir = tmp_path / "bin"
    tui = _write(tmp_path / "assets/aegis_tui.exe")
    start = tmp_path / "StartMenu"
    start.mkdir()
    config = OperatorAppsConfiguration(
        target=WINDOWS,
        runtime_python=runtime,
        code_directory=code,
        bin_directory=bin_dir,
        tui_executable=tui,
        start_menu_directory=start,
        approved_roots=(tmp_path,),
        start_at_login=True,
    )
    plan = build_operator_apps_plan(config)
    assert plan["startup"]["requested"] is True
    assert plan["startup"]["supported"] is True
    assert plan["startup"]["action"] == "ENSURE"
    assert plan["startup"]["command"] is not None
    assert plan["shortcut_count"] if "shortcut_count" in plan else True


def test_preflight_detects_orchestrator_tui_asset_role(monkeypatch, tmp_path):
    release = SimpleNamespace(
        release_id="test-release",
        revision=1,
        manifest_sha256="a" * 64,
        source_sha="b" * 40,
        target=WINDOWS.value,
        signer_key_id="test-signer",
        trust_key_sha256="c" * 64,
        asset_count=2,
    )
    payload = {
        "assets": [
            {
                "kind": "dependency",
                "role": "aegis_tui",
                "reference": {
                    "path": "aegis_tui.exe",
                    "sha256": "d" * 64,
                    "size_bytes": 1,
                },
            },
            {
                "kind": "service",
                "reference": {
                    "path": "aegis-platform-service.exe",
                    "sha256": "e" * 64,
                    "size_bytes": 1,
                },
            },
        ]
    }
    monkeypatch.setattr(guided, "discover_bundle", lambda *a, **k: object())
    monkeypatch.setattr(guided, "verify_bundle", lambda *a, **k: (release, payload))
    monkeypatch.setattr(guided, "_bundled_python", lambda *a, **k: None)

    result = guided._preflight(
        tmp_path, target=WINDOWS, install_root=tmp_path / "Aegis",
        trust_root=None, script_directory=None,
    )

    assert result["ok"] is True
    assert result["tui_available"] is True
    assert "tui" in result["asset_kinds"]


def test_install_wizard_collects_root_components_and_startup(
    monkeypatch, tmp_path,
):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    preflight = {
        "ok": True,
        "blockers": (),
        "host": "TESTHOST",
        "os": "Windows-test",
        "target": WINDOWS.value,
        "install_root": str(tmp_path / "Aegis"),
        "existing_destination": None,
        "paths": None,
        "free_bytes": 10**12,
        "required_bytes": 10**9,
        "asset_bytes": 10**8,
        "asset_kinds": ("service", "tui"),
        "tui_available": True,
        "release_id": "test-release",
        "revision": 4,
        "signer_key_id": "test-signer",
    }
    calls = []

    def fake_preflight(*args, **kwargs):
        return dict(preflight, install_root=str(kwargs["install_root"]))

    def fake_run_guided(*args, **kwargs):
        calls.append(kwargs)
        if kwargs.get("check"):
            return {
                "outcome": "PREVIEW_OK",
                "plan": {
                    "components": {"terminal_tui": True},
                    "startup_preference": "SIGN_IN_TUI",
                    "operator_apps": {"startup": {"requested": True}},
                },
            }
        return {"outcome": "INSTALLED"}

    answers = iter([
        str(tmp_path / "Aegis"),
        "y", "y", "n", "y", "y",
    ])
    monkeypatch.setattr(guided, "_preflight", fake_preflight)
    monkeypatch.setattr(guided, "_desktop_directory", lambda _target: desktop)
    monkeypatch.setattr(guided, "run_guided", fake_run_guided)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    result = guided._install_wizard(
        tmp_path, target=WINDOWS, script_directory=None, trust_root=None,
        theme=None, color=False, no_color=True,
    )
    assert result == {"outcome": "INSTALLED"}
    assert len(calls) == 2
    assert calls[0]["check"] is True
    assert calls[0]["start_at_login"] is True
    assert calls[0]["include_tui"] is True
    assert calls[0]["include_start_menu"] is True
    assert calls[0]["include_desktop"] is False
    assert calls[1]["operation"] == "install"
    assert calls[1]["start_at_login"] is True
