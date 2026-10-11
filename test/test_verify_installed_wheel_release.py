"""Release gate must test installed wheel bytes, never implicitly ./src.

Tests authored for the deferred exact-SHA verification campaign.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.verify import gate, source_provenance


def test_installed_package_provenance_rejects_checkout_import(tmp_path, monkeypatch):
    repo = tmp_path / "checkout"
    package = repo / "src" / "sofia"
    package.mkdir(parents=True)
    origin = package / "__init__.py"
    origin.write_text("", encoding="utf-8")
    venv = tmp_path / "release-venv"
    venv.mkdir()
    monkeypatch.setattr(gate.sys, "prefix", str(venv))
    monkeypatch.setattr(gate.sys, "base_prefix", str(tmp_path / "base"))
    monkeypatch.setattr(
        gate.importlib.util, "find_spec",
        lambda name: SimpleNamespace(origin=str(origin)),
    )
    with pytest.raises(RuntimeError, match="outside the release venv"):
        gate._assert_installed_wheel_origin(repo)


def test_installed_package_provenance_accepts_real_venv_package_root(
    tmp_path, monkeypatch,
):
    repo = tmp_path / "checkout"
    repo.mkdir()
    venv = tmp_path / "release-venv"
    package = venv / "Lib" / "site-packages" / "sofia"
    package.mkdir(parents=True)
    origin = package / "__init__.py"
    origin.write_text("", encoding="utf-8")
    monkeypatch.setattr(gate.sys, "prefix", str(venv))
    monkeypatch.setattr(gate.sys, "base_prefix", str(tmp_path / "base"))
    monkeypatch.setattr(
        gate.importlib.util, "find_spec",
        lambda name: SimpleNamespace(origin=str(origin)),
    )
    gate._assert_installed_wheel_origin(repo)


def test_release_workflow_explicitly_requests_installed_distribution():
    root = Path(__file__).resolve().parents[1]
    pipeline = (root / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8",
    )
    assert "sofia.verify.gate --phase full --installed-wheel-only" in pipeline
    assert "--repo" in pipeline


def test_release_pytest_marker_flag_is_isolated_from_developer_runs():
    from sofia.verify import package_selection
    # Release gating opts in explicitly through the caller's environment,
    # leaving regular editable-package developer commands unchanged.
    import inspect
    assert "SOFIA_VERIFY_INSTALLED_ONLY" in inspect.getsource(
        package_selection.collect_package_selection
    )


def test_release_provenance_requires_identical_installed_python_modules(tmp_path):
    archive = tmp_path / "archive"
    staged = archive / "src" / "sofia"
    installed = tmp_path / "wheel-venv" / "site-packages" / "sofia"
    sources = {
        "__init__.py": "# Sofía entrypoint\\n",
        "safe/permissions.py": "PERMISSION_LEVEL = 5\\n",
    }
    for relative, code in sources.items():
        for root in (staged, installed):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(code, encoding="utf-8")

    report = source_provenance._prove_installed_python_matches_archive(
        archive, installed,
    )
    assert report["installed_python_module_count"] == 2
    assert len(report["installed_python_source_sha256"]) == 64

    (installed / "safe/permissions.py").write_text(
        "PERMISSION_LEVEL = 1\\n", encoding="utf-8",
    )
    with pytest.raises(ValueError, match="code differs"):
        source_provenance._prove_installed_python_matches_archive(archive, installed)


def test_release_provenance_refuses_missing_or_extra_wheel_modules(tmp_path):
    archive = tmp_path / "archive"
    staged = archive / "src" / "sofia"
    installed = tmp_path / "site-packages" / "sofia"
    staged.mkdir(parents=True)
    installed.mkdir(parents=True)
    for root in (staged, installed):
        (root / "__init__.py").write_text("# module\\n", encoding="utf-8")

    (installed / "unexpected.py").write_text("pass\\n", encoding="utf-8")
    with pytest.raises(ValueError, match="membership differs"):
        source_provenance._prove_installed_python_matches_archive(archive, installed)

    (installed / "unexpected.py").unlink()
    (staged / "required.py").write_text("pass\\n", encoding="utf-8")
    with pytest.raises(ValueError, match="membership differs"):
        source_provenance._prove_installed_python_matches_archive(archive, installed)
