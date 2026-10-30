"""Production-machinery install tests for separated component wheels.

A real virtual environment receives the actual built wheels through pip, the
same installer surface production uses, and the full lifecycle is observed:
SDK+Platform without Core, Core installation without overwriting Platform or
SDK files, and Core uninstall that preserves the Platform installation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from sofia.platform.verify.component_artifacts import build_all_components

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def component_wheels(tmp_path_factory) -> dict[str, Path]:
    return build_all_components(
        tmp_path_factory.mktemp("production-wheels"), repo=ROOT
    )


@pytest.fixture(scope="module")
def production_venv(tmp_path_factory, component_wheels) -> dict[str, object]:
    venv_root = tmp_path_factory.mktemp("production-venv")
    python = (
        venv_root / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else venv_root / "bin" / "python"
    )
    context = {"venv_root": venv_root, "python": python, "log": []}

    def run(args: list[str], *, timeout: int = 600) -> str:
        completed = subprocess.run(
            [str(python), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        context["log"].append((tuple(args), completed.returncode))
        if completed.returncode:
            raise RuntimeError(
                f"command failed ({completed.returncode}): {args}\n"
                f"{completed.stdout}\n{completed.stderr}"
            )
        return completed.stdout.strip()

    context["run"] = run
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    run(["-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
         str(component_wheels["sdk"])])
    run(["-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
         str(component_wheels["platform"])])
    run(["-m", "pip", "install", "--disable-pip-version-check",
         "cryptography", "tzdata"])
    run(["-m", "pip", "check"])
    return context


def _wheel_entry_bytes(wheel: Path, name: str) -> bytes:
    with zipfile.ZipFile(wheel) as archive:
        return archive.read(name)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_production_component_install_lifecycle(production_venv, component_wheels):
    run = production_venv["run"]
    venv_root = production_venv["venv_root"]
    if sys.platform == "win32":
        site_packages = venv_root / "Lib" / "site-packages"
    else:
        site_packages = next((venv_root / "lib").glob("python*/site-packages"))
    sofia_root = site_packages / "sofia"

    installed_init = sofia_root / "__init__.py"
    sdk_init_bytes = _wheel_entry_bytes(component_wheels["sdk"], "sofia/__init__.py")
    assert installed_init.is_file()
    assert installed_init.read_bytes() == sdk_init_bytes

    platform_marker = "sofia/platform/run/active_release.py"
    platform_marker_path = sofia_root / "platform" / "run" / "active_release.py"
    assert platform_marker_path.is_file()
    platform_marker_digest = _sha256(platform_marker_path)
    assert platform_marker_digest == hashlib.sha256(
        _wheel_entry_bytes(component_wheels["platform"], platform_marker)
    ).hexdigest()

    core_probe = (
        "import sofia.core.constitution\n"
        "import sofia.core.identity.model\n"
        "import sofia.sdk.cognition_model\n"
        "import sofia.platform.run.active_release\n"
        "print('core-absent-probe-ok')\n"
    )
    without_core = subprocess.run(
        [str(production_venv["python"]), "-c", core_probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert without_core.returncode != 0
    assert "core-absent-probe-ok" not in without_core.stdout
    assert "sofia.core" in without_core.stderr

    run(["-m", "pip", "install", "--disable-pip-version-check", "--no-deps",
         str(component_wheels["core"])])
    run(["-m", "pip", "check"])

    assert installed_init.read_bytes() == sdk_init_bytes
    assert _sha256(platform_marker_path) == platform_marker_digest

    with_core = subprocess.run(
        [str(production_venv["python"]), "-c", core_probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert with_core.returncode == 0, with_core.stderr
    assert "core-absent-probe-ok" in with_core.stdout

    core_constitution = sofia_root / "core" / "constitution" / "constitution.md"
    assert core_constitution.is_file()

    run(["-m", "pip", "uninstall", "-y", "sofia-core"])

    assert installed_init.is_file()
    assert installed_init.read_bytes() == sdk_init_bytes
    assert _sha256(platform_marker_path) == platform_marker_digest
    after_uninstall = subprocess.run(
        [str(production_venv["python"]), "-c", core_probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert after_uninstall.returncode != 0
    run(["-m", "pip", "check"])

    assert any(
        path.name.startswith("sofia_platform-0.1.0.dist-info")
        for path in site_packages.glob("*.dist-info")
    )
    assert not any(
        path.name.startswith("sofia_core-") or path.name.startswith("sofia-core-")
        for path in site_packages.glob("*.dist-info")
    )


def test_production_venv_kept_platform_without_core(
    production_venv, component_wheels
):
    python = production_venv["python"]
    probe = "import sofia.platform.run.active_release; print('platform-ok')"
    completed = subprocess.run(
        [str(python), "-c", probe],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(production_venv["venv_root"]),
    )
    assert completed.returncode == 0, completed.stderr
    assert "platform-ok" in completed.stdout
