"""Host-owned registry for read-only local cognitive capabilities."""
from __future__ import annotations

from pathlib import Path

from sofia.capability.system import CapabilitySystem
from sofia.knowledge.capability import KnowledgeSearchCapability, KnowledgeSourceReadCapability
from sofia.knowledge.lifecycle import KnowledgeLifecycle
from sofia.knowledge.persistence import JsonKnowledgeStore
from sofia.machine.capability import MachineInspectionCapability
from sofia.system.capability import create_system_capabilities
from sofia.system.factory import create_system_backend


class ToolCatalog:
    def __init__(
        self,
        capability_system: CapabilitySystem,
        *,
        repository_root: Path,
        state_path: Path | str,
    ) -> None:
        self._system = capability_system
        self._root = repository_root
        self._state_path = Path(state_path)

    def register(self) -> None:
        backend = create_system_backend()
        if backend is not None:
            for item in create_system_capabilities(backend):
                self._system.register(item.capability, item.execute)

        machine = MachineInspectionCapability()
        self._system.register(machine.capability, machine.execute)

        store = JsonKnowledgeStore(
            self._state_path.with_name("knowledge.json")
        )
        lifecycle = KnowledgeLifecycle(
            self._state_path.with_name("knowledge-lifecycle.json")
        )
        source = KnowledgeSourceReadCapability(self._root)
        search = KnowledgeSearchCapability(store, lifecycle)

        self._system.register(source.capability, source.execute)
        self._system.register(search.capability, search.execute)
