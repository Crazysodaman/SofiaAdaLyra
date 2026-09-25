"""Composition seam for Sofía's host-owned read-only tool catalog."""
from __future__ import annotations

from pathlib import Path

from sofia.capability.system import CapabilitySystem
from sofia.cognition.tools import (
    CognitiveToolBinding,
    create_knowledge_tool_bindings,
    create_machine_tool_bindings,
    create_system_tool_bindings,
)
from sofia.knowledge.capability import KnowledgeSearchCapability,KnowledgeSourceReadCapability
from sofia.knowledge.lifecycle import KnowledgeLifecycle
from sofia.knowledge.persistence import JsonKnowledgeStore
from sofia.machine.capability import MachineInspectionCapability
from sofia.system.capability import create_system_capabilities
from sofia.system.factory import create_system_backend

LOCAL_READONLY_CAPABILITIES=frozenset({
    "process.inspect",
    "system.inspect",
    "network.inspect",
    "service.inspect",
    "machine.inspect",
})

FILESYSTEM_SCOPED_READONLY_CAPABILITIES=frozenset({
    "knowledge.source.read",
    "knowledge.search",
})

def install_readonly_capabilities(
    capability_system:CapabilitySystem,
    *,
    repository_root:Path,
    state_path:Path,
)->None:
    backend=create_system_backend()
    if backend is not None:
        for item in create_system_capabilities(backend):
            capability_system.register(item.capability,item.execute)
    machine=MachineInspectionCapability()
    capability_system.register(machine.capability,machine.execute)
    store=JsonKnowledgeStore(state_path.with_name("knowledge.json"))
    lifecycle=KnowledgeLifecycle(state_path.with_name("knowledge-lifecycle.json"))
    source=KnowledgeSourceReadCapability(repository_root)
    search=KnowledgeSearchCapability(store,lifecycle)
    capability_system.register(source.capability,source.execute)
    capability_system.register(search.capability,search.execute)

def create_readonly_tool_bindings(repository_root:Path)->tuple[CognitiveToolBinding,...]:
    return (
        create_system_tool_bindings()
        + create_machine_tool_bindings()
        + create_knowledge_tool_bindings(repository_root)
    )
