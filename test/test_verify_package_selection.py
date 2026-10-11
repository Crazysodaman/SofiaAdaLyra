"""Source-level checks for nonempty package collection gates; not yet run."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import conftest

from sofia.verify.package_selection import (
    PackageSelectionProbe, expected_packages,
)
from sofia.verify.v18_roadmap import RoadmapIntegrityError


ROOT = Path(__file__).resolve().parents[1]


def test_package_markers_exactly_match_all_22_ci_matrix_entries():
    names = expected_packages(ROOT)
    assert len(names) == 22
    assert {"pkg_body", "pkg_verify", "pkg_safe"}.issubset(names)


def test_body_package_has_a_real_repository_owned_selection_root():
    path = ROOT / "test" / "test_body_matrix.py"
    assert path.is_file()
    assert "pkg_body" in conftest._explicit_package_markers(path)


def test_probe_counts_actual_selected_items_not_source_filename():
    class Item:
        def __init__(self, nodeid, names):
            self.nodeid = nodeid
            self.names = names

        def iter_markers(self, name=None):
            if name in self.names:
                return iter([name])
            return iter(())

    probe = PackageSelectionProbe(("pkg_body", "pkg_verify"))
    probe.pytest_collection_finish(SimpleNamespace(items=[
        Item("test/test_body_matrix.py::test_one", ("pkg_body",)),
        Item("test/test_verify_gate.py::test_two", ("pkg_verify",)),
        Item("test/test_cross.py::test_three", ("pkg_body", "pkg_verify")),
    ]))
    assert probe.collection_finished is True
    assert len(probe.selected["pkg_body"]) == 2
    assert len(probe.selected["pkg_verify"]) == 2


def test_drift_between_22_marker_config_and_workflow_is_rejected(tmp_path):
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nmarkers = ["pkg_body: physical safety"]\n',
        encoding="utf-8",
    )
    (tmp_path / ".github/workflows/package-tests.yml").write_text(
        "matrix:\n  - pkg_verify\n", encoding="utf-8",
    )
    with pytest.raises(RoadmapIntegrityError, match="22 distinct"):
        expected_packages(tmp_path)
