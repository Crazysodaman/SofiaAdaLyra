"""Capability and side-effect policy for production adapter invocation."""
from __future__ import annotations
from dataclasses import dataclass
from .model import AdapterManifest,SideEffectClass

@dataclass(frozen=True)
class InvocationContext:
    actor_id:str
    capabilities:frozenset[str]
    allowed_side_effects:frozenset[SideEffectClass]
    def __post_init__(self):
        if not self.actor_id.strip(): raise ValueError("actor_id required")

class InvocationPolicy:
    def require(self,manifest:AdapterManifest,context:InvocationContext)->None:
        missing=set(manifest.required_capabilities)-set(context.capabilities)
        if missing: raise PermissionError("missing required capabilities: "+", ".join(sorted(missing)))
        if manifest.side_effect not in context.allowed_side_effects:
            raise PermissionError(f"side effect not authorized: {manifest.side_effect.value}")
