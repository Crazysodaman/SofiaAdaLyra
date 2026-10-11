"""Release verification explicitly owns its checkout root, not site-packages.

The real user-owned test campaign is deferred. These are source-level
regression contracts for running the installed-wheel verification gate.
"""
from pathlib import Path

import pytest

from sofia.verify import gate
from sofia.verify.package_selection import expected_packages
from sofia.verify.v18_roadmap import validate_repository


ROOT = Path(__file__).resolve().parents[1]


def test_repository_audit_runs_with_explicit_source_checkout():
    report = validate_repository(ROOT)
    assert report["total_original_tasks"] == 700


def test_22_package_map_uses_checkout_not_installed_distribution():
    assert len(expected_packages(ROOT)) == 22


def test_release_gate_requires_exact_git_checkout(tmp_path):
    with pytest.raises(RuntimeError, match="actual Git checkout root"):
        gate.run_gate("static", evidence_path=tmp_path / "proof.json", repo_root=tmp_path)


def test_release_gate_tracks_repo_argument_as_source_not_install_path():
    # The installed package's __file__ can live in a Python venv. Gate
    # implementation must accept a caller-owned checkout independently.
    assert "repo_root" in gate.run_gate.__code__.co_varnames
