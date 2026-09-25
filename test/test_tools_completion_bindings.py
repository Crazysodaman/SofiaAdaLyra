from pathlib import Path

from sofia.cognition.tools import (
    create_knowledge_tool_bindings,
    create_machine_tool_bindings,
    create_system_tool_bindings,
)

def test_core_tool_binding_catalog(tmp_path: Path):
    bindings = (
        create_system_tool_bindings()
        + create_machine_tool_bindings()
        + create_knowledge_tool_bindings(tmp_path)
    )
    names = {item.definition.name for item in bindings}
    assert {
        "inspect_processes",
        "inspect_system",
        "inspect_network",
        "inspect_services",
        "inspect_machine",
        "read_knowledge_source",
        "search_knowledge",
    }.issubset(names)
