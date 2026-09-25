"""Runtime capability catalog exposed as a read-only cognitive tool."""
from __future__ import annotations
from typing import Iterable
from sofia.capability.model import Capability,CapabilityRequest
from sofia.capability.system import CapabilitySystem
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding

TOOL_CATALOG_CAPABILITY=Capability(
    name="tool.catalog",
    description="List the canonical capabilities registered in this Sofía runtime and whether each has standing authorization.",
)

class ToolCatalogCapability:
    def __init__(self,system:CapabilitySystem,standing_allowed:Iterable[str])->None:
        self.system=system; self.allowed=frozenset(standing_allowed); self.capability=TOOL_CATALOG_CAPABILITY
    def execute(self,request:CapabilityRequest):
        if request.parameters: raise ValueError("tool.catalog does not accept parameters")
        return tuple({
            "name":cap.name,
            "description":cap.description,
            "standing_authorized":cap.name in self.allowed,
        } for cap in self.system.capabilities())

def create_tool_catalog_binding()->CognitiveToolBinding:
    return CognitiveToolBinding(
        definition=CognitiveToolDefinition(
            name="tool_catalog",
            description="List tools/capabilities actually registered in the current runtime and which have standing authorization. Read-only.",
            parameters={"type":"object","properties":{},"additionalProperties":False},
        ),
        capability_name="tool.catalog",
    )
