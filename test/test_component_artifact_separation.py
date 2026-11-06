"""G2-B component artifact separation tests.

These tests build real component wheels from the integrated source tree and
verify exclusive file ownership, wheel contents, and installed-artifact
import isolation with Core absent. They exercise installed artifact
semantics (extracted wheel payloads), not checkout source-tree semantics.
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import venv

import pytest

from sofia.platform.verify.component_artifacts import (
    BUILD_SCHEMA,
    COMPONENT_DISTRIBUTIONS,
    CORE_ASSET_FILES,
    INSTALLED_ISOLATED_MODULES,
    ComponentArtifactError,
    build_all_components,
    inspect_wheel,
    load_component_manifest,
    repository_root,
    verify_component_separation,
    verify_installed_imports,
    verify_integrated_parity,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def component_wheels(tmp_path_factory) -> dict[str, Path]:
    output_dir = tmp_path_factory.mktemp("component-wheels")
    return build_all_components(output_dir, repo=ROOT)


def test_component_manifest_declares_exclusive_ownership():
    components = load_component_manifest(ROOT)
    assert set(components) == set(COMPONENT_DISTRIBUTIONS)
    owned_packages: set[str] = set()
    for component in components.values():
        packages = set(component["packages"])  # type: ignore[arg-type]
        assert not packages & owned_packages, packages & owned_packages
        owned_packages |= packages
    core = components["core"]
    declared_assets = {
        f"{package.replace('.', '/')}/{file_name}"
        for package, files in core["package_data"].items()  # type: ignore[union-attr]
        for file_name in files  # type: ignore[union-attr]
    }
    assert declared_assets == set(CORE_ASSET_FILES)


def test_component_wheels_have_exclusive_file_ownership(component_wheels):
    report = verify_component_separation(component_wheels)
    assert report.as_dict() == {
        "schema": BUILD_SCHEMA,
        "core_free_platform": True,
        "core_free_sdk": True,
        "platform_free_core": True,
        "platform_free_sdk": True,
        "sdk_free_core": True,
        "sdk_free_platform": True,
        "core_assets_present": True,
        "platform_entry_point_present": True,
        "package_root_single_owner": True,
        "dependency_graph_acyclic": True,
    }


def test_core_wheel_carries_every_constitution_asset(component_wheels):
    core_report = inspect_wheel(component_wheels["core"], "sofia-core")
    for asset in CORE_ASSET_FILES:
        assert asset in core_report.files, asset
    platform_report = inspect_wheel(component_wheels["platform"], "sofia-platform")
    sdk_report = inspect_wheel(component_wheels["sdk"], "sofia-sdk")
    for asset in CORE_ASSET_FILES:
        assert asset not in platform_report.files
        assert asset not in sdk_report.files
    assert "sofia/__init__.py" in sdk_report.files
    assert "sofia/__init__.py" not in platform_report.files
    assert "sofia/__init__.py" not in core_report.files


def test_installed_platform_imports_without_core(component_wheels):
    result = verify_installed_imports(component_wheels)
    assert result["schema"] == BUILD_SCHEMA
    assert result["launcher_status"] is True


def test_unconfigured_installed_platform_has_no_core_host_role(component_wheels, tmp_path):
    from sofia.platform.verify.component_artifacts import (
        _extract_wheel, _run_core_blocked_probe,
    )

    site_dir = tmp_path / "site"
    for distribution in ("sdk", "platform"):
        _extract_wheel(component_wheels[distribution], site_dir)
    _run_core_blocked_probe([site_dir], (
        "import sys\n"
        "from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration\n"
        "assert PlatformRoleConfiguration.from_environment().roles == (PlatformRole.MODULE_HOST,)\n"
        "from sofia.platform.launcher import main\n"
        "assert main(['status']) == 0\n"
        "assert not [name for name in sys.modules if name == 'sofia.core' or name.startswith('sofia.core.')]\n"
    ))


def test_clean_venv_platform_status_survives_core_uninstall(component_wheels, tmp_path):
    """Exercise actual pip installation with no checkout/user-site fallback."""
    environment_root = tmp_path / "installation"
    venv.EnvBuilder(with_pip=True).create(environment_root)
    python = environment_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("SOFIA_") and key not in {"PYTHONPATH", "PYTHONHOME"}
    }
    state_root = tmp_path / "personal-state"
    state_root.mkdir()
    marker = state_root / "preserved.txt"
    marker.write_text("disposable private state", encoding="utf-8")
    environment["SOFIA_STATE_ROOT"] = str(state_root)

    def run(*arguments):
        completed = subprocess.run(
            [str(python), "-I", *arguments], cwd=tmp_path,
            capture_output=True, text=True, timeout=120, env=environment,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout

    run("-m", "pip", "install", "--no-index", "--no-deps",
        str(component_wheels["sdk"]), str(component_wheels["platform"]))
    status_probe = (
        "import sys\n"
        "from sofia.platform.launcher import main\n"
        "assert main(['status']) == 0\n"
        "assert not [name for name in sys.modules if name == 'sofia.core' or name.startswith('sofia.core.')]\n"
    )
    assert json.loads(run("-c", status_probe))["roles"] == ["MODULE_HOST"]
    run("-m", "pip", "install", "--no-index", "--no-deps", str(component_wheels["core"]))
    assert json.loads(run("-c", status_probe))["roles"] == ["CORE_HOST", "MODULE_HOST"]
    run("-m", "pip", "uninstall", "--yes", "sofia-core")
    assert json.loads(run("-c", status_probe))["roles"] == ["MODULE_HOST"]
    assert marker.read_text(encoding="utf-8") == "disposable private state"
    assert sorted(path.name for path in state_root.iterdir()) == ["preserved.txt"]


@pytest.mark.parametrize("component", COMPONENT_DISTRIBUTIONS)
def test_single_component_cli_reports_built_distribution(component_wheels, monkeypatch, capsys, component, tmp_path):
    from sofia.platform.verify import component_artifacts

    # RC verification imports this module from an installed wheel. Source
    # selection is explicit; package location need not be a checkout.
    monkeypatch.setattr(
        component_artifacts, "__file__", str(tmp_path / "site-packages" / "component_artifacts.py"),
    )
    monkeypatch.setattr(
        component_artifacts, "build_component",
        lambda distribution, *args, **kwargs: component_wheels[distribution],
    )
    assert component_artifacts.main([
        "--dist", component, "--output", str(tmp_path), "--repo", str(ROOT),
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["distribution"] == f"sofia-{component}"
    assert report["wheel"] == str(component_wheels[component])


def test_installed_isolation_surface_covers_source_canonical_list():
    from test.test_platform_import_isolation import ISOLATED_MODULES

    assert set(ISOLATED_MODULES) <= set(INSTALLED_ISOLATED_MODULES)


def test_integrated_parity_imports_all_components(component_wheels):
    result = verify_integrated_parity(component_wheels)
    assert result == {"schema": BUILD_SCHEMA, "parity_imports": "ok"}


def test_build_reports_wheel_sha256(component_wheels):
    import re

    wheel_path = component_wheels["platform"]
    report = inspect_wheel(wheel_path, "sofia-platform")
    assert re.fullmatch(r"[0-9a-f]{64}", report.sha256)
    assert report.name == "sofia-platform"
    assert report.version == "0.1.0"
    assert any(path.startswith("sofia/platform/") for path in report.files)


def test_unknown_distribution_is_rejected(component_wheels, tmp_path):
    from sofia.platform.verify.component_artifacts import build_component

    components = load_component_manifest(ROOT)
    with pytest.raises(ComponentArtifactError):
        build_component("unknown", tmp_path, repo=ROOT, manifest=components)
