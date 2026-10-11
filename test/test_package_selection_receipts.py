"""CA-2304 package-marker attribution proof, authored without execution."""
from pathlib import Path
from types import SimpleNamespace

from sofia.verify.package_selection import PackageSelectionProbe
from test.conftest import _explicit_package_markers


class Item:
    def __init__(self, nodeid, filename, *markers):
        self.nodeid = nodeid
        self.path = Path(filename)
        self._markers = markers

    def iter_markers(self, name=None):
        for marker in self._markers:
            if name is None or name == marker:
                yield SimpleNamespace(name=marker)


def test_body_matrix_has_explicit_real_pkg_body_ownership():
    root = Path(__file__).parent
    marker_set = _explicit_package_markers(root / "test_body_matrix.py")
    assert "pkg_body" in marker_set
    assert "pkg_core" in marker_set


def test_probe_distinguishes_unique_nodes_test_roots_and_cross_package_copies():
    source = [
        Item("test_body_matrix.py::test_body", "test/test_body_matrix.py",
             "pkg_body", "pkg_core"),
        Item("test_body_matrix.py::test_idle", "test/test_body_matrix.py",
             "pkg_body", "pkg_core"),
        Item("test_voice.py::test_live", "test/test_voice.py", "pkg_voice"),
    ]
    probe = PackageSelectionProbe(("pkg_body", "pkg_core", "pkg_voice"))
    probe.pytest_collection_finish(SimpleNamespace(items=source))
    assert probe.collection_finished is True
    assert [len(probe.selected[x]) for x in (
        "pkg_body", "pkg_core", "pkg_voice",
    )] == [2, 2, 1]
    assert len(probe.roots["pkg_body"]) == 1
    assert len(probe.node_ownership) == 3
    assert sum(len(owners) > 1 for owners in probe.node_ownership.values()) == 2


def test_body_only_collection_keeps_other_real_marker_owners_visible():
    probe = PackageSelectionProbe(("pkg_body",))
    probe.pytest_collection_finish(SimpleNamespace(items=[
        Item("test_body_matrix.py::test_real", "test/test_body_matrix.py",
             "pkg_body", "pkg_core"),
    ]))
    assert list(probe.selected["pkg_body"]) == [
        "test_body_matrix.py::test_real",
    ]
    assert probe.node_ownership[
        "test_body_matrix.py::test_real"
    ] == ("pkg_body", "pkg_core")
