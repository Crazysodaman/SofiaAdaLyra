"""PKG-OPS fleet telemetry, lifecycle and placement primitives."""
from .model import HostLifecycle, HostTelemetry, FleetHost, WorkloadContract, WorkloadState
from .fleet import FleetRegistry, FleetRemovalApprovalRequired
from .placement import PlacementDecision, PlacementEngine
__all__=["HostLifecycle","HostTelemetry","FleetHost","WorkloadContract","WorkloadState","FleetRegistry","FleetRemovalApprovalRequired","PlacementDecision","PlacementEngine"]
