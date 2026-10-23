"""Read-only capability adapter over Sofía's capability self-model.

This adapter exposes only the awareness projection through the existing
CapabilitySystem. It performs no writes, executes no module code, grants
no privilege, and requires the caller's authorization before running,
matching the house pattern of `sofia.codebase.capability`.
"""
from __future__ import annotations

from sofia.capability.model import (
    Capability,
    CapabilityRequest,
)
from sofia.core.modreg.self_model import CapabilitySelfModel


MODULE_AWARENESS_CAPABILITY = Capability(
    name="modules.awareness.inspect",
    description=(
        "Read-only projection of Sofía's capability self-model: module "
        "awareness rows and the honest bounded summary. No writes, no "
        "execution, no grants."
    ),
)


class ModuleAwarenessCapability:
    """Adapter between the generic capability system and the self-model."""

    def __init__(self, self_model: CapabilitySelfModel) -> None:
        if not isinstance(self_model, CapabilitySelfModel):
            raise TypeError(
                "ModuleAwarenessCapability requires a CapabilitySelfModel"
            )
        self._self_model = self_model

    @property
    def capability(self) -> Capability:
        return MODULE_AWARENESS_CAPABILITY

    @property
    def self_model(self) -> CapabilitySelfModel:
        return self._self_model

    def execute(
        self, request: CapabilityRequest,
    ) -> tuple[tuple, str]:
        if not isinstance(request, CapabilityRequest):
            raise TypeError("request must be a CapabilityRequest")
        if request.capability.name != MODULE_AWARENESS_CAPABILITY.name:
            raise ValueError(
                "ModuleAwarenessCapability received an unsupported "
                "capability request"
            )
        rows = self._self_model.project()
        return rows, self._self_model.awareness_summary()
