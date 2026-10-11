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


def test_release_gate_tests_the_exact_candidate_wheel_not_a_separate_source_install():
    """The SHA-matched publishable wheel must be installed before provenance and tests."""
    root = Path(__file__).resolve().parents[1]
    pipeline = (root / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8",
    )
    build = pipeline.index("- name: Build wheel twice and require reproducibility")
    install = pipeline.index("- name: Install exactly the reproducibly built candidate wheel")
    provenance = pipeline.index("- name: Assert exact source and installed package provenance")
    verification = pipeline.index("- name: Run revision-bound verification gate")
    release = pipeline.index("- name: Construct and verify release evidence")
    assert build < install < provenance < verification < release
    assert '"RELEASE_WHEEL_SHA256=$HashA"' in pipeline
    assert '$actualHash -ne $env:RELEASE_WHEEL_SHA256' in pipeline
    assert 'pip install --no-index --no-deps --force-reinstall "$wheelPath"' in pipeline
    assert 'pip install --no-deps "$env:SOFIA_RELEASE_SOURCE"' not in pipeline


def test_release_artifacts_do_not_dirty_exact_sha_checkout_before_gate():
    """Fresh checkout must stay clean while wheel and source proof are produced."""
    root = Path(__file__).resolve().parents[1]
    pipeline = (root / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8",
    )
    assert 'SOFIA_RELEASE_VENV=$(Join-Path $env:RUNNER_TEMP' in pipeline
    assert 'SOFIA_RELEASE_EVIDENCE=$(Join-Path $env:RUNNER_TEMP' in pipeline
    assert 'SOFIA_VERIFICATION_EVIDENCE=$(Join-Path $env:RUNNER_TEMP' in pipeline
    assert '$distA = Join-Path $env:RUNNER_TEMP "sofia-dist-a"' in pipeline
    assert '$distB = Join-Path $env:RUNNER_TEMP "sofia-dist-b"' in pipeline
    assert '"RELEASE_WHEEL=$($WheelA.FullName)"' in pipeline
    assert 'python -m venv .releasevenv' not in pipeline
    assert 'Copy-Item $WheelA.FullName $WheelA.Name' not in pipeline
    assert '--evidence "$env:SOFIA_RELEASE_EVIDENCE"' in pipeline
    assert '--evidence-path "$env:SOFIA_VERIFICATION_EVIDENCE"' in pipeline


def test_release_workflow_invocation_and_fail_closed_build_tools():
    """Release candidate refuses a failed dependency or wheel subprocess."""
    pipeline = (
        (Path(__file__).resolve().parents[1] / ".github/workflows/release-candidate.yml")
        .read_text(encoding="utf-8")
    )
    assert '& & "$env:SOFIA_RELEASE_VENV' not in pipeline
    assert '& "$env:SOFIA_RELEASE_VENV\\Scripts\\python.exe" @Args' in pipeline
    for command in (
        "-m pip install --require-hashes -r requirements.lock.windows-py312.txt",
        "-m pip install --require-hashes -r requirements.verify.lock.windows-py312.txt",
        '-m pip wheel --no-build-isolation --no-deps --wheel-dir "$distA"',
        '-m pip wheel --no-build-isolation --no-deps --wheel-dir "$distB"',
    ):
        start = pipeline.index(command)
        assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in pipeline[
            start : start + 180
        ]


def test_release_build_backend_is_hash_pinned_and_never_re_resolved_in_isolated_build():
    """Source provenance requires a reviewed backend, not opaque PyPI build isolation."""
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8",
    )
    lock = (root / "requirements.build.lock.windows-py312.txt").read_text(
        encoding="utf-8",
    )
    assert "setuptools==80.9.0 --hash=sha256:" in lock
    assert "062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922" in lock
    assert (
        "pip install --require-hashes --only-binary=:all: "
        "-r requirements.build.lock.windows-py312.txt"
    ) in workflow
    for output in ("$distA", "$distB"):
        assert f'pip wheel --no-build-isolation --no-deps --wheel-dir "{output}"' in workflow
    assert "pip wheel --no-deps --wheel-dir" not in workflow
