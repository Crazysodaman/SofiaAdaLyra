"""CA-3004/3005 installed wheel provenance and failed-start cleanup.

Source tests authored only. Deferred CI/Windows acceptance remains required.
"""
from pathlib import Path
import tomllib

import pytest

import sofia.platform.verify.cognition_v2_baseline as baseline


def test_baseline_uses_actual_installed_distribution_resources(tmp_path):
    config = baseline._configuration(tmp_path)
    source = baseline.INSTALLED_SOFIA_ROOT
    assert Path(config.constitution_path) == source / "core/constitution/constitution.md"
    assert Path(config.constitution_hash_path) == source / "core/constitution/constitution.sha256"
    assert Path(config.identity_path) == source / "core/identity/identity.json"
    assert Path(config.avatar_path) == source / "core/embodiment/avatar.json"
    assert Path(config.filesystem_root) == tmp_path


def test_baseline_wheel_manifest_includes_required_constitution_identity_avatar():
    repo = Path(__file__).resolve().parents[1]
    source = tomllib.loads((repo / "pyproject.toml").read_text(
        encoding="utf-8",
    ))
    package_data = source["tool"]["setuptools"]["package-data"]
    assert set(package_data["sofia.core.constitution"]).issuperset({
        "constitution.md", "constitution.sha256",
    })
    assert "identity.json" in package_data["sofia.core.identity"]
    assert "avatar.json" in package_data["sofia.core.embodiment"]


def test_failed_baseline_startup_attempts_owner_shutdown_before_temp_cleanup(
    tmp_path, monkeypatch,
):
    calls = []

    class FailingApplication:
        def __init__(self, config):
            calls.append("construct")
        def start(self):
            calls.append("start")
            raise RuntimeError("injected failure after partially opened stores")
        def shutdown(self):
            calls.append("shutdown")

    monkeypatch.setattr(baseline, "SofiaApplication", FailingApplication)
    with pytest.raises(RuntimeError, match="injected failure"):
        baseline.capture_baseline()
    assert calls == ["construct", "start", "shutdown"]
