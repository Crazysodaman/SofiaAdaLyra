from datetime import datetime, timedelta, timezone

import pytest

from sofia.core.cognition.v2 import (
    AcquisitionState,
    CognitiveEvidenceLedger,
    EvidenceGraph,
    EvidenceNeed,
    FleetCognitiveEvidenceBridge,
    FleetObservationRejected,
)
from sofia.platform.resources import CapabilityFact, EvidenceClass, ResourceSupply
from sofia.platform.ops.model import FleetHost, HostLifecycle
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)
NODE = "11111111-2222-3333-4444-555555555555"
SCOPE = "private:sparks"


def _fact(value="linux", *, verified=True, observed_at=NOW, expires_at=None):
    return CapabilityFact(
        "os.family", value, None, "artemis", "host:artemis",
        EvidenceClass.OBSERVED, "fleet-discovery:mtls-agent-discovery",
        observed_at, expires_at or observed_at + timedelta(minutes=2), verified,
    )


def _supply(*facts, enrolled=True, trusted=True, revision=1):
    return ResourceSupply(
        "artemis", enrolled, trusted, revision, tuple(facts or (_fact(),)),
    )


def _host(*, host_id="artemis", trusted=True, node_id=NODE,
          lifecycle=HostLifecycle.ENROLLED):
    from uuid import UUID
    return FleetHost(
        host_id, "linux", "amd64", lifecycle, trusted,
        node_id=None if node_id is None else UUID(node_id),
    )


def _need():
    return EvidenceNeed(
        "need:artemis-os", f"fleet-node:{NODE}", "machine.os", SCOPE,
        max_age_seconds=120, minimum_trust=0.9,
    )


def _bridge(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    ledger = CognitiveEvidenceLedger(path)
    return path, ledger, FleetCognitiveEvidenceBridge(ledger)


def test_authenticated_fleet_observation_becomes_scoped_core_evidence(tmp_path):
    _, ledger, bridge = _bridge(tmp_path)
    atoms = bridge.ingest(_supply(), host=_host(), scope_id=SCOPE, now=NOW)

    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.subject_id == f"fleet-node:{NODE}"
    assert atom.source_id.startswith("capability:fleet:")
    assert '"source_ref":"fleet-discovery:mtls-agent-discovery"' in atom.value_json
    assert EvidenceGraph(ledger).resolve(_need(), now=NOW).atoms == atoms


@pytest.mark.parametrize(
    "supply, message",
    [
        (_supply(enrolled=False), "enrolled"),
        (_supply(trusted=False), "enrolled"),
        (_supply(_fact(verified=False)), "fresh verified"),
        (_supply(_fact(observed_at=NOW - timedelta(minutes=5), expires_at=NOW - timedelta(minutes=1))), "fresh verified"),
    ],
)
def test_unauthorized_unverified_and_stale_observations_are_rejected(
    tmp_path, supply, message
):
    _, ledger, bridge = _bridge(tmp_path)
    with pytest.raises(FleetObservationRejected, match=message):
        bridge.ingest(supply, host=_host(), scope_id=SCOPE, now=NOW)
    assert ledger.matching(_need()) == ()


@pytest.mark.parametrize(
    "host",
    [
        _host(host_id="venus"),
        _host(trusted=False),
        _host(node_id=None),
        _host(lifecycle=HostLifecycle.QUARANTINED),
    ],
)
def test_invalid_or_revoked_fleet_identity_is_rejected(tmp_path, host):
    _, ledger, bridge = _bridge(tmp_path)
    with pytest.raises(FleetObservationRejected):
        bridge.ingest(_supply(), host=host, scope_id=SCOPE, now=NOW)
    assert ledger.matching(_need()) == ()


def test_conflicting_authenticated_observations_remain_contradicted(tmp_path):
    _, ledger, bridge = _bridge(tmp_path)
    bridge.ingest(_supply(_fact("linux")), host=_host(), scope_id=SCOPE, now=NOW)
    bridge.ingest(
        _supply(_fact("windows", observed_at=NOW + timedelta(seconds=1)), revision=2),
        host=_host(),
        scope_id=SCOPE,
        now=NOW + timedelta(seconds=1),
    )

    resolution = EvidenceGraph(ledger).resolve(
        _need(), now=NOW + timedelta(seconds=1)
    )
    assert resolution.acquisition_state is AcquisitionState.CONTRADICTED
    assert resolution.atoms == ()
    assert len(ledger.matching(_need())) == 2


def test_revoked_enrollment_invalidates_evidence_across_restart(tmp_path):
    path, ledger, bridge = _bridge(tmp_path)
    atom = bridge.ingest(
        _supply(), host=_host(), scope_id=SCOPE, now=NOW
    )[0]

    assert bridge.revoke(
        node_id=NODE,
        scope_id=SCOPE,
        reason="Fleet enrollment was explicitly revoked",
        source_ref="fleet-enrollment:revocation",
        now=NOW + timedelta(seconds=1),
    ) == (atom.evidence_id,)

    restarted = CognitiveEvidenceLedger(path)
    resolution = EvidenceGraph(restarted).resolve(
        _need(), now=NOW + timedelta(seconds=2)
    )
    assert resolution.acquisition_state is AcquisitionState.REVOKED
    assert resolution.atoms == ()
    assert restarted.get(atom.evidence_id).acquisition_state is AcquisitionState.REVOKED


def test_duplicate_observation_is_idempotent(tmp_path):
    _, ledger, bridge = _bridge(tmp_path)
    first = bridge.ingest(_supply(), host=_host(), scope_id=SCOPE, now=NOW)
    second = bridge.ingest(_supply(), host=_host(), scope_id=SCOPE, now=NOW)
    assert second == first
    assert ledger.matching(_need()) == first
