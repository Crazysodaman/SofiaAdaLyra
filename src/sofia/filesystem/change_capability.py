"""Cognitive capability for deterministic filesystem change observation."""
from __future__ import annotations
from pathlib import Path
from dataclasses import asdict
from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from .changes import detect_changes
from .observation import FilesystemObserver,FilesystemObservationStore

FILESYSTEM_CHANGES_CAPABILITY=Capability(
    "filesystem.changes",
    "Observe the authorized repository and report factual changes since the previous stored observation.",
)

class FilesystemChangesCapability:
    def __init__(self,root:Path,store:FilesystemObservationStore)->None:
        self.root=root.resolve(); self.store=store; self.observer=FilesystemObserver(self.root)
        self.capability=FILESYSTEM_CHANGES_CAPABILITY
    def execute(self,request:CapabilityRequest):
        if request.parameters: raise ValueError("filesystem.changes takes no parameters")
        previous=self.store.latest(self.root)
        current=self.observer.observe()
        event=detect_changes(previous,current)
        self.store.record(current)
        def item(change):
            return {
                "kind":change.kind.value,
                "path":str(change.path.relative_to(self.root)),
                "previous_hash":None if change.previous is None else change.previous.content_hash,
                "current_hash":None if change.current is None else change.current.content_hash,
            }
        return {
            "baseline_available":event.baseline_available,
            "previous_observed_at":None if event.previous_observed_at is None else event.previous_observed_at.isoformat(),
            "current_observed_at":event.current_observed_at.isoformat(),
            "total_changes":event.total_changes,
            "new":tuple(item(x) for x in event.new),
            "modified":tuple(item(x) for x in event.modified),
            "removed":tuple(item(x) for x in event.removed),
        }

def create_filesystem_changes_binding()->CognitiveToolBinding:
    return CognitiveToolBinding(
        definition=CognitiveToolDefinition(
            name="inspect_filesystem_changes",
            description="Observe Sofía's authorized repository and report factual file changes since the previous stored observation.",
            parameters={"type":"object","properties":{},"additionalProperties":False},
        ),
        capability_name="filesystem.changes",
    )
