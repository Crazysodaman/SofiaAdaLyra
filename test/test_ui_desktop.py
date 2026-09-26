import importlib
import sys

from sofia.ui.desktop import (
    _TkDesktopWorkbench,
    _chamfer_points,
    _format_exception_chain,
    main,
)


def test_desktop_module_import_does_not_eagerly_import_tkinter():
    sys.modules.pop("sofia.ui.desktop", None)
    before = set(sys.modules)

    importlib.import_module("sofia.ui.desktop")

    added = set(sys.modules) - before
    assert "tkinter" not in added
    assert "tkinter.ttk" not in added


def test_desktop_main_is_callable():
    assert callable(main)


def test_exception_chain_includes_root_cause():
    try:
        try:
            raise ValueError("inner failure")
        except ValueError as exc:
            raise RuntimeError("outer failure") from exc
    except RuntimeError as error:
        detail = _format_exception_chain(error)

    assert "RuntimeError: outer failure" in detail
    assert "Caused by: ValueError: inner failure" in detail


def test_exception_chain_rejects_non_exception():
    import pytest

    with pytest.raises(TypeError):
        _format_exception_chain("not an exception")


def test_chamfer_points_use_shallow_45_degree_cuts():
    assert _chamfer_points(100, 60, 10) == (
        10, 0,
        90, 0,
        100, 10,
        100, 50,
        90, 60,
        10, 60,
        0, 50,
        0, 10,
    )


def test_chamfer_points_clamp_for_small_controls():
    points = _chamfer_points(12, 8, 10)

    assert min(points) >= 0
    assert max(points[0::2]) <= 12
    assert max(points[1::2]) <= 8


class _FakeText:
    def __init__(self):
        self.state = "disabled"
        self.content = "old text"
        self.modified = True

    def cget(self, key):
        assert key == "state"
        return self.state

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]

    def edit_modified(self, value):
        self.modified = value

    def delete(self, start, end):
        assert start == "1.0"
        assert end == "end"
        if self.state != "disabled":
            self.content = ""

    def insert(self, start, content):
        assert start == "1.0"
        if self.state != "disabled":
            self.content = content


def test_replace_input_clears_disabled_composer_and_restores_state():
    fake = type("WorkbenchStub", (), {})()
    fake._input = _FakeText()

    _TkDesktopWorkbench._replace_input(fake, "")

    assert fake._input.content == ""
    assert fake._input.state == "disabled"
    assert fake._input.modified is False
