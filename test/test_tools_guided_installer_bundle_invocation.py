"""Invocation-level tests over real assembler output and real launcher files.

The disposable runtime is replaced with an argument echo so these tests do not
install, elevate, register a service or invoke real Core cognition.  They still
exercise the generated release/installer layout, launcher discovery, trust
presence checks, argument forwarding and --no-color compatibility.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from test.test_tools_build_aegis_release import (
    _assemble,
    _installer_changes,
    _pe,
)
from test.test_ui_aegis_installer_guided_launchers import (
    _compile_echo_exe,
    _windows_runtime_available,
)

ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = ROOT / "packaging" / "installers"
WINDOWS = "windows-x86_64"
DEBIAN = "debian12-x86_64"
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")


def _real_installer_dir(tmp_path: Path) -> Path:
    target = tmp_path / "real-installer"
    target.mkdir()
    for name in ("Install-Aegis.ps1", "install-aegis.sh", "Start-AegisSetup.ps1"):
        shutil.copyfile(INSTALLERS / name, target / name)
    (target / "Aegis-Setup.exe").write_bytes(_pe())
    return target


@pytest.fixture(scope="module")
def generated_bundles(tmp_path_factory, platform_wheels):
    tmp = tmp_path_factory.mktemp("installer-invocation")
    changes = _installer_changes(tmp)
    changes["installer_dir"] = _real_installer_dir(tmp)
    _repo, _sha, _key, _public, output, _result = _assemble(
        tmp, platform_wheels, **changes,
    )
    return output


def _msys_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) >= 2 and value[1] == ":":
        return f"/{value[0].lower()}{value[2:]}"
    return value


def _linux_uname_shim(tmp_path: Path) -> str:
    env_file = tmp_path / "linux-uname-bash-env"
    env_file.write_text(
        "uname() { case \"$1\" in -s) echo Linux;; -m) echo x86_64;; "
        "*) command uname \"$@\";; esac; }\n",
        encoding="ascii",
    )
    return str(env_file)


def _trust_root(bundle: Path, destination: Path) -> Path:
    destination.mkdir()
    shutil.copyfile(
        bundle / "installer" / "trusted-publisher.pem",
        destination / "trusted-publisher.pem",
    )
    shutil.copyfile(bundle / "installer" / "trust.json", destination / "trust.json")
    return destination


def _copy_bundle(generated_bundles: Path, target: str, tmp_path: Path) -> Path:
    destination = tmp_path / target
    shutil.copytree(generated_bundles / target, destination)
    return destination


def _replace_windows_runtime(bundle: Path) -> None:
    _compile_echo_exe(bundle / "release" / "runtime" / "python" / "python.exe")


def _replace_linux_runtime(bundle: Path) -> None:
    path = bundle / "release" / "runtime" / "python" / "bin" / "python3.12"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n", encoding="ascii")
    path.chmod(0o755)
    subprocess.run(
        [str(GIT_BASH), "-lc", f"chmod +x '{_msys_path(path)}'"],
        capture_output=True, text=True, timeout=60,
    )


def _powershell(script: Path, *arguments: str, env: dict[str, str]):
    return subprocess.run(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile",
         "-NonInteractive", "-File", str(script), *arguments],
        capture_output=True, text=True, timeout=120, env=env,
    )


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_generated_windows_bundle_forwards_no_color_preview(generated_bundles, tmp_path):
    bundle = _copy_bundle(generated_bundles, WINDOWS, tmp_path)
    _replace_windows_runtime(bundle)
    trust = _trust_root(bundle, tmp_path / "owner-trust")
    env = os.environ.copy()
    env["AEGIS_INSTALLER_TRUST_ROOT"] = str(trust)

    result = _powershell(
        bundle / "installer" / "Install-Aegis.ps1",
        "-Check", "-Json", "-NoColor", env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "platform_installer_guided" in result.stdout
    assert bundle.name in result.stdout
    assert "--bundle-root" in result.stdout
    assert "--check" in result.stdout
    assert "--json" in result.stdout
    assert "--no-color" in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_generated_windows_bundle_normal_status_operation(generated_bundles, tmp_path):
    bundle = _copy_bundle(generated_bundles, WINDOWS, tmp_path)
    _replace_windows_runtime(bundle)
    trust = _trust_root(bundle, tmp_path / "owner-trust")
    env = os.environ.copy()
    env["AEGIS_INSTALLER_TRUST_ROOT"] = str(trust)

    result = _powershell(
        bundle / "installer" / "Install-Aegis.ps1",
        "-Operation", "status", "-NoColor", env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "--operation" in result.stdout
    assert "status" in result.stdout
    assert "--check" not in result.stdout
    assert "--no-color" in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_generated_windows_bundle_missing_trust_denies_before_runtime(
    generated_bundles, tmp_path,
):
    bundle = _copy_bundle(generated_bundles, WINDOWS, tmp_path)
    (bundle / "installer" / "trust.json").unlink()

    result = _powershell(
        bundle / "installer" / "Install-Aegis.ps1", "-Check", "-Json",
        env=os.environ.copy(),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "BLOCKED"
    assert "trust anchor" in payload["message"]
    assert "platform_installer_guided" not in result.stdout


@pytest.mark.skipif(not _windows_runtime_available(), reason="Windows PowerShell 5.1 only")
def test_generated_windows_bundle_missing_runtime_denies(generated_bundles, tmp_path):
    bundle = _copy_bundle(generated_bundles, WINDOWS, tmp_path)
    (bundle / "release" / "runtime" / "python" / "python.exe").unlink()

    result = _powershell(
        bundle / "installer" / "Install-Aegis.ps1", "-Check", "-Json",
        env=os.environ.copy(),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "BLOCKED"
    assert "bundled Python runtime" in payload["message"]
    assert "platform_installer_guided" not in result.stdout


@pytest.mark.skipif(not GIT_BASH.is_file(), reason="Git Bash unavailable")
def test_generated_debian_bundle_missing_runtime_denies(generated_bundles, tmp_path):
    bundle = _copy_bundle(generated_bundles, DEBIAN, tmp_path)
    (bundle / "release" / "runtime" / "python" / "bin" / "python3.12").unlink()
    env = os.environ.copy()
    env["BASH_ENV"] = _linux_uname_shim(tmp_path)

    result = subprocess.run(
        [str(GIT_BASH), str(bundle / "installer" / "install-aegis.sh"),
         "--check", "--json"],
        capture_output=True, text=True, timeout=120, env=env,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "BLOCKED"
    assert "bundled Python runtime" in payload["message"]
    assert "platform_installer_guided" not in result.stdout


@pytest.mark.skipif(not GIT_BASH.is_file(), reason="Git Bash unavailable")
def test_generated_debian_bundle_forwards_no_color_preview(generated_bundles, tmp_path):
    bundle = _copy_bundle(generated_bundles, DEBIAN, tmp_path)
    _replace_linux_runtime(bundle)
    trust = _trust_root(bundle, tmp_path / "owner-trust")
    env = os.environ.copy()
    env["AEGIS_INSTALLER_TRUST_ROOT"] = str(trust)
    env["BASH_ENV"] = _linux_uname_shim(tmp_path)

    result = subprocess.run(
        [str(GIT_BASH), str(bundle / "installer" / "install-aegis.sh"),
         "--check", "--json", "--no-color"],
        capture_output=True, text=True, timeout=120, env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "platform_installer_guided" in result.stdout
    assert bundle.name in result.stdout
    assert "--bundle-root" in result.stdout
    assert "--check" in result.stdout
    assert "--json" in result.stdout
    assert "--no-color" in result.stdout
    assert "\x1b" not in result.stdout


@pytest.mark.skipif(not GIT_BASH.is_file(), reason="Git Bash unavailable")
def test_generated_debian_bundle_normal_verify_operation(generated_bundles, tmp_path):
    bundle = _copy_bundle(generated_bundles, DEBIAN, tmp_path)
    _replace_linux_runtime(bundle)
    trust = _trust_root(bundle, tmp_path / "owner-trust")
    env = os.environ.copy()
    env["AEGIS_INSTALLER_TRUST_ROOT"] = str(trust)
    env["BASH_ENV"] = _linux_uname_shim(tmp_path)

    result = subprocess.run(
        [str(GIT_BASH), str(bundle / "installer" / "install-aegis.sh"),
         "--operation", "verify", "--no-color"],
        capture_output=True, text=True, timeout=120, env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "--operation verify" in result.stdout
    assert "--check" not in result.stdout
    assert "--no-color" in result.stdout
    assert "sudo" not in result.stdout


@pytest.mark.skipif(not GIT_BASH.is_file(), reason="Git Bash unavailable")
def test_generated_debian_bundle_missing_trust_denies_before_runtime(
    generated_bundles, tmp_path,
):
    bundle = _copy_bundle(generated_bundles, DEBIAN, tmp_path)
    (bundle / "installer" / "trust.json").unlink()

    result = subprocess.run(
        [str(GIT_BASH), str(bundle / "installer" / "install-aegis.sh"),
         "--check", "--json"],
        capture_output=True, text=True, timeout=120, env=os.environ.copy(),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["result"] == "BLOCKED"
    assert "trust anchor" in payload["message"]
    assert "platform_installer_guided" not in result.stdout




