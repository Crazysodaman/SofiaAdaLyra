"""LINK-01 role and launcher production boundaries."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform import launcher
from sofia.platform.run import systemd_runtime


def test_integrated_compatibility_roles_preserve_current_runtime(monkeypatch):
    monkeypatch.delenv("SOFIA_PLATFORM_ROLES", raising=False)
    roles = PlatformRoleConfiguration.from_environment()
    assert roles.roles == (PlatformRole.CORE_HOST, PlatformRole.MODULE_HOST)


@pytest.mark.parametrize("value", [
    "", "CORE_HOST,", "core_host", "UNKNOWN", "CORE_HOST,CORE_HOST",
    "STANDBY,CORE_HOST",
])
def test_platform_roles_reject_ambiguous_or_unsafe_configuration(value):
    with pytest.raises((ValueError, TypeError)):
        PlatformRoleConfiguration.parse(value)


def test_core_link_and_module_host_are_composable_without_core_authority():
    roles = PlatformRoleConfiguration.parse("CORE_LINK,MODULE_HOST")
    assert roles.supports(PlatformRole.CORE_LINK)
    assert roles.supports(PlatformRole.MODULE_HOST)
    with pytest.raises(PermissionError, match="CORE_HOST"):
        roles.require(PlatformRole.CORE_HOST)


def test_status_is_core_free_and_does_not_touch_canonical_state(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "CORE_LINK,MODULE_HOST")
    sys.modules.pop("sofia.core.launcher", None)
    assert launcher.main(["status"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "roles": ["CORE_LINK", "MODULE_HOST"],
        "schema": "companion.platform.roles.v1",
    }
    assert "sofia.core.launcher" not in sys.modules


def test_core_link_desktop_fails_closed_without_importing_core(monkeypatch, capsys):
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "CORE_LINK,MODULE_HOST")
    sys.modules.pop("sofia.core.launcher", None)
    assert launcher.main(["desktop"]) == 2
    assert "SOFIA_CORE_LINK_BINDING_STORE is required" in capsys.readouterr().err
    assert "sofia.core.launcher" not in sys.modules


def test_python_module_status_path_does_not_import_core_in_fresh_process():
    code = (
        "import os,sys; "
        "os.environ['SOFIA_PLATFORM_ROLES']='CORE_LINK,MODULE_HOST'; "
        "from sofia.platform.launcher import main; "
        "result=main(['status']); "
        "assert result == 0; "
        "assert 'sofia.core.launcher' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_core_link_desktop_diagnostic_does_not_import_any_core_package():
    code = (
        "import os,sys; "
        "os.environ['SOFIA_PLATFORM_ROLES']='CORE_LINK,MODULE_HOST'; "
        "os.environ.pop('SOFIA_CORE_LINK_BINDING_STORE',None); "
        "from sofia.platform.launcher import main; "
        "result=main(['desktop']); "
        "assert result == 2; "
        "assert not [name for name in sys.modules if name.startswith('sofia.core')]"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_core_link_tray_diagnostic_does_not_import_any_core_package():
    code = (
        "import os,sys; "
        "os.environ['SOFIA_PLATFORM_ROLES']='CORE_LINK,MODULE_HOST'; "
        "os.environ.pop('SOFIA_CORE_LINK_BINDING_STORE',None); "
        "from sofia.platform.launcher import main; "
        "result=main(['tray']); "
        "assert result == 2; "
        "assert not [name for name in sys.modules if name.startswith('sofia.core')]"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_core_link_settings_diagnostic_does_not_import_any_core_package():
    code = (
        "import os,sys; "
        "os.environ['SOFIA_PLATFORM_ROLES']='CORE_LINK,MODULE_HOST'; "
        "os.environ.pop('SOFIA_CORE_LINK_BINDING_STORE',None); "
        "from sofia.platform.launcher import main; "
        "result=main(['settings']); "
        "assert result == 2; "
        "assert not [name for name in sys.modules if name.startswith('sofia.core')]"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_core_link_control_center_diagnostic_does_not_import_core():
    code = (
        "import os,sys; "
        "os.environ['SOFIA_PLATFORM_ROLES']='CORE_LINK,MODULE_HOST'; "
        "os.environ.pop('SOFIA_CORE_LINK_BINDING_STORE',None); "
        "from sofia.platform.launcher import main; "
        "result=main(['control-center']); "
        "assert result == 2; "
        "assert not [name for name in sys.modules if name.startswith('sofia.core')]"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_legacy_python_module_entrypoint_fails_closed_without_core_import():
    code = (
        "import os,sys; "
        "os.environ['SOFIA_PLATFORM_ROLES']='CORE_LINK,MODULE_HOST'; "
        "from sofia.__main__ import main; "
        "\ntry: main(argv=())\n"
        "except SystemExit as exc: assert 'CORE_HOST' in str(exc)\n"
        "else: raise AssertionError('Core-free entrypoint did not refuse')\n"
        "assert 'sofia.core.launcher' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_headless_core_host_role_is_explicit_in_unit():
    unit = systemd_runtime.render_unit(systemd_runtime.SystemdRuntimeSpec(
        python_path=systemd_runtime.PurePosixPath("/opt/sofia/bin/python"),
        state_root=systemd_runtime.PurePosixPath("/var/lib/sofia"),
        environment_file=systemd_runtime.PurePosixPath("/etc/sofia/runtime.env"),
    ))
    assert "Environment=SOFIA_PLATFORM_ROLES=CORE_HOST,MODULE_HOST" in unit


def test_launcher_installs_xdg_clients_without_starting_core(
    monkeypatch, tmp_path, capsys,
):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    sys.modules.pop("sofia.core.launcher", None)

    assert launcher.main(["install-ui", "--tray-autostart"]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["platform"] == "linux-xdg"
    assert len(receipt["installed"]) == 4
    assert len(receipt["autostart"]) == 1
    assert "sofia.core.launcher" not in sys.modules


def test_headless_runtime_refuses_core_free_role_before_state_access(monkeypatch):
    monkeypatch.setattr(systemd_runtime.sys, "platform", "linux")
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "MODULE_HOST")
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "production")
    monkeypatch.setenv("SOFIA_IDENTITY_BOOTSTRAP_MODE", "require_existing")
    with pytest.raises(PermissionError, match="CORE_HOST"):
        systemd_runtime.run_headless(stop_event=systemd_runtime.Event())


def test_direct_application_composition_refuses_core_free_role_before_db_access(
    monkeypatch, tmp_path: Path,
):
    from sofia.platform.application.bootstrap import SofiaApplication
    from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration

    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "CORE_LINK,MODULE_HOST")
    missing = tmp_path / "must-not-be-created.db"
    config = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=missing,
        provider=ProviderConfiguration(provider="ollama", model="unused"),
        filesystem_root=tmp_path,
    )
    with pytest.raises(PermissionError, match="CORE_HOST"):
        SofiaApplication(config)
    assert not missing.exists()

