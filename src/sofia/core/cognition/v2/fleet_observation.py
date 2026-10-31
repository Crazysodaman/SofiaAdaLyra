"""Bridge verified Fleet resource observations into canonical V2 evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json

from sofia.platform.resources import ResourceSupply
from sofia.platform.ops.model import FleetHost, HostLifecycle

from .contracts import AcquisitionState, EpistemicState, EvidenceAtom, EvidenceNeed
from .evidence import CognitiveEvidenceLedger


_PREDICATES = {
    "os.family": "machine.os",
    "cpu.arch": "machine.architecture",
    "cpu.utilization_percent": "ops.cpu_percent",
    "memory.allocatable_bytes": "machine.memory_allocatable_bytes",
    "gpu.utilization_percent": "ops.gpu_percent",
    "gpu.vram.allocatable_bytes": "machine.gpu_vram_allocatable_bytes",
    "storage.allocatable_bytes": "machine.storage_allocatable_bytes",
    "health.temperature_c": "ops.temperature_c",
    "health.throttled": "ops.throttled",
    "health.power_limited": "ops.power_limited",
    "runtime.sofia_agent.version": "machine.agent_version",
}


class FleetObservationRejected(PermissionError):
    """The Fleet observation cannot cross the Core evidence boundary."""


class FleetCognitiveEvidenceBridge:
    """Admit only fresh, enrolled and independently verified Fleet facts.

    The bridge grants no authority. It preserves the HNF source reference,
    inventory revision, resource identity, unit and expiry in each atom and
    writes through the existing canonical V2 ledger.
    """

    def __init__(self, ledger: CognitiveEvidenceLedger) -> None:
        if not isinstance(ledger, CognitiveEvidenceLedger):
            raise TypeError("ledger must be CognitiveEvidenceLedger")
        self.ledger = ledger

    def ingest(
        self,
        supply: ResourceSupply,
        *,
        host: FleetHost,
        scope_id: str,
        now: datetime,
    ) -> tuple[EvidenceAtom, ...]:
        if not isinstance(supply, ResourceSupply):
            raise TypeError("supply must be ResourceSupply")
        if not isinstance(host, FleetHost):
            raise TypeError("host must be FleetHost")
        if host.host_id != supply.host_id:
            raise FleetObservationRejected("Fleet observation belongs to a different host")
        if (
            not supply.enrolled
            or not supply.trusted
            or not host.trusted
            or host.node_id is None
            or host.lifecycle not in {
                HostLifecycle.ENROLLED,
                HostLifecycle.HEALTHY,
                HostLifecycle.DEGRADED,
                HostLifecycle.MAINTENANCE,
            }
        ):
            raise FleetObservationRejected("Fleet host is not actively enrolled and trusted")
        if not isinstance(scope_id, str) or not scope_id.strip():
            raise ValueError("scope_id is required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        node_id = str(host.node_id)
        subject_id = f"fleet-node:{node_id}"
        atoms = []
        for fact in supply.facts:
            predicate = _PREDICATES.get(fact.key)
            if predicate is None:
                continue
            if not fact.verified:
                continue
            if not fact.fresh(moment):
                continue
            value = {
                "value": fact.value,
                "unit": fact.unit,
                "host_id": supply.host_id,
                "resource_id": fact.resource_id,
                "source_ref": fact.source_ref,
                "inventory_revision": supply.inventory_revision,
                "node_id": node_id,
            }
            canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
            identity = json.dumps(
                {
                    "subject": subject_id,
                    "predicate": predicate,
                    "scope": scope_id,
                    "observed_at": fact.observed_at.isoformat(),
                    "expires_at": None if fact.expires_at is None else fact.expires_at.isoformat(),
                    "value": value,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            digest = sha256(identity.encode("utf-8")).hexdigest()
            atom = EvidenceAtom(
                evidence_id=f"evidence:fleet:{digest}",
                subject_id=subject_id,
                predicate=predicate,
                value_json=canonical,
                source_id=f"capability:fleet:{digest[:24]}",
                observed_at=fact.observed_at,
                expires_at=fact.expires_at,
                scope_id=scope_id,
                trust=0.98,
                epistemic_state=EpistemicState.OBSERVED,
                acquisition_state=AcquisitionState.CURRENT,
            )
            atoms.append(self.ledger.append(atom))
        if not atoms:
            raise FleetObservationRejected("no fresh verified Fleet facts were available")
        return tuple(atoms)

    def revoke(
        self,
        *,
        node_id: str,
        scope_id: str,
        reason: str,
        source_ref: str,
        now: datetime,
    ) -> tuple[str, ...]:
        """Revoke every current V2 fact for an explicitly revoked enrollment."""
        prefix = f"fleet-node:{node_id}"
        revoked = []
        for predicate in _PREDICATES.values():
            need = EvidenceNeed(
                need_id=f"need:revoke:{sha256((prefix + predicate + scope_id).encode()).hexdigest()[:24]}",
                subject_id=prefix,
                predicate=predicate,
                scope_id=scope_id,
            )
            for atom in self.ledger.matching(need):
                if atom.acquisition_state is not AcquisitionState.CURRENT:
                    continue
                self.ledger.record_status(
                    atom.evidence_id,
                    AcquisitionState.REVOKED,
                    reason=reason,
                    source_ref=source_ref,
                    changed_at=now,
                )
                revoked.append(atom.evidence_id)
        return tuple(revoked)
