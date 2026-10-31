"""Application composition for durable Fleet node retirement."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.core.cognition.v2 import (
    CognitiveEvidenceLedger,
    FleetCognitiveEvidenceBridge,
)
from sofia.platform.ops.model import HostLifecycle
from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
from sofia.platform.state.sqlite_plane import SQLiteStatePlane


def reconcile_retired_node(
    state_path: Path | str, *, node_id: UUID, now: datetime,
) -> tuple[str, ...]:
    """Quarantine the OPS host and revoke current Core evidence.

    Identity, endpoint and grant revocation remain owned by PKG-NET. This
    function reconciles their consequence into existing OPS and Cognition
    owners without deleting historical evidence.
    """
    path = Path(state_path)
    registry = StatePlaneFleetRegistry(SQLiteStatePlane(path))
    matches = tuple(host for host in registry.hosts() if host.node_id == node_id)
    for host in matches:
        if host.lifecycle not in {
            HostLifecycle.DECOMMISSIONED,
            HostLifecycle.QUARANTINED,
        }:
            registry.transition(host.host_id, HostLifecycle.QUARANTINED)

    # Older standalone operator databases have no canonical Cognition schema.
    # They still receive identity/endpoint/grant and OPS quarantine above.
    with closing(sqlite3.connect(path, timeout=10)) as db:
        has_evidence = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='cognition_v2_evidence'"
        ).fetchone() is not None
    if not has_evidence:
        return ()
    return FleetCognitiveEvidenceBridge(
        CognitiveEvidenceLedger(path)
    ).revoke_node(
        node_id=str(node_id),
        reason="durable Fleet enrollment retired",
        source_ref=f"fleet-retirement:{node_id}",
        now=now,
    )
