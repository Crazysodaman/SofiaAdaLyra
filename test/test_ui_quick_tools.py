import pytest

from sofia.ui.quick_tools import (
    QUICK_TOOLS,
    quick_tool_by_label,
    quick_tool_labels,
)


def test_quick_tools_have_unique_ids_and_labels():
    assert len({tool.tool_id for tool in QUICK_TOOLS}) == len(QUICK_TOOLS)
    assert len({tool.label for tool in QUICK_TOOLS}) == len(QUICK_TOOLS)


def test_quick_tool_labels_preserve_registry_order():
    assert quick_tool_labels() == tuple(
        tool.label for tool in QUICK_TOOLS
    )


def test_quick_tool_lookup_returns_reviewed_prompt():
    tool = quick_tool_by_label("Hardware Summary")

    assert tool.tool_id == "hardware"
    assert "Inspect this computer's CPU" in tool.prompt


def test_quick_tool_lookup_rejects_unknown_label():
    with pytest.raises(KeyError):
        quick_tool_by_label("Launch Missiles")


def test_quick_tool_lookup_rejects_blank_label():
    with pytest.raises(ValueError):
        quick_tool_by_label("   ")
