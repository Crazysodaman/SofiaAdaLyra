"""Read-only capability wrapper for one configured external adapter."""
from __future__ import annotations

from sofia.capability.model import Capability, CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from sofia.external.adapter import ExternalIntegrationAdapter


class ExternalObservationCapability:
    def __init__(
        self,
        *,
        capability_name: str,
        tool_name: str,
        description: str,
        adapter: ExternalIntegrationAdapter,
    ) -> None:
        self.adapter = adapter
        self.capability = Capability(capability_name, description)
        self.binding = CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name=tool_name,
                description=description,
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
            capability_name=capability_name,
        )

    def execute(self, request: CapabilityRequest):
        if request.parameters:
            raise ValueError("external observation tools accept no parameters")
        observation = self.adapter.observe()
        return {
            "system_id": observation.system_id,
            "source": observation.source_name,
            "observed_at": observation.observed_at.isoformat(),
            "evidence": observation.evidence,
        }
