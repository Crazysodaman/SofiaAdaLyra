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
from sofia.core.social.principals import local_sparks_principal
from sofia.core.goals.evidence import GoalEvidenceIndex, GoalEvidenceLedger


NOW = datetime.now(timezone.utc).replace(microsecond=0)
NODE = "11111111-2222-3333-4444-555555555555"
SCOPE = "local:text"


def _fact(
    value="linux", *, key="os.family", unit=None, verified=True,
    observed_at=NOW, expires_at=None,
):
    return CapabilityFact(
        key, value, unit, "artemis", "host:artemis",
        EvidenceClass.OBSERVED, "fleet-discovery:mtls-agent-discovery",
        observed_at, expires_at or observed_at + timedelta(hours=1), verified,
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
    return path, ledger, FleetCognitiveEvidenceBridge(
        ledger, goal_evidence=GoalEvidenceLedger(path)
    )


def test_authenticated_fleet_observation_becomes_scoped_core_evidence(tmp_path):
    _, ledger, bridge = _bridge(tmp_path)
    atoms = bridge.ingest(
        _supply(), host=_host(), principal=local_sparks_principal(), now=NOW
    )

    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.subject_id == f"fleet-node:{NODE}"
    assert atom.source_id.startswith("capability:fleet:")
    assert '"source_ref":"fleet-discovery:mtls-agent-discovery"' in atom.value_json
    assert EvidenceGraph(ledger).resolve(_need(), now=NOW).atoms == atoms
    goal_record = GoalEvidenceIndex(ledger.path).lookup(
        atom.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
    )
    assert goal_record is not None
    assert goal_record.kind == "external_observation"
    assert goal_record.principal_id == "person:sparks"
    assert goal_record.audience == "private:local:text"


def test_each_eligible_fact_projects_its_own_canonical_predicate(tmp_path):
    path, _ledger, bridge = _bridge(tmp_path)
    facts = (
        _fact("linux", key="os.family"),
        _fact("amd64", key="cpu.arch"),
        _fact(42.5, key="cpu.utilization_percent", unit="percent"),
        _fact(8192, key="memory.allocatable_bytes", unit="bytes", verified=False),
        _fact("ignored", key="vendor.unsupported"),
    )

    atoms = bridge.ingest(
        _supply(*facts), host=_host(),
        principal=local_sparks_principal(), now=NOW,
    )

    assert {atom.predicate for atom in atoms} == {
        "machine.os", "machine.architecture", "ops.cpu_percent",
    }
    index = GoalEvidenceIndex(path)
    for atom in atoms:
        record = index.lookup(
            atom.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
        )
        assert record is not None
        assert record.assertion == atom.predicate


def test_duplicate_reordered_facts_keep_stable_atom_predicate_links(tmp_path):
    path, ledger, bridge = _bridge(tmp_path)
    facts = (
        _fact("linux", key="os.family"),
        _fact("amd64", key="cpu.arch"),
        _fact(42.5, key="cpu.utilization_percent", unit="percent"),
    )
    first = bridge.ingest(
        _supply(*facts), host=_host(),
        principal=local_sparks_principal(), now=NOW,
    )
    reordered = bridge.ingest(
        _supply(*reversed(facts)), host=_host(),
        principal=local_sparks_principal(), now=NOW,
    )

    assert set(reordered) == set(first)
    index = GoalEvidenceIndex(path)
    for atom in ledger.subject_atoms(f"fleet-node:{NODE}"):
        record = index.lookup(
            atom.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
        )
        assert record is not None
        assert record.assertion == atom.predicate


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
        bridge.ingest(
            supply, host=_host(), principal=local_sparks_principal(), now=NOW
        )
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
        bridge.ingest(
            _supply(), host=host, principal=local_sparks_principal(), now=NOW
        )
    assert ledger.matching(_need()) == ()


def test_conflicting_authenticated_observations_remain_contradicted(tmp_path):
    _, ledger, bridge = _bridge(tmp_path)
    first = bridge.ingest(
        _supply(_fact("linux")), host=_host(),
        principal=local_sparks_principal(), now=NOW,
    )[0]
    second = bridge.ingest(
        _supply(_fact("windows", observed_at=NOW + timedelta(seconds=1)), revision=2),
        host=_host(),
        principal=local_sparks_principal(),
        now=NOW + timedelta(seconds=1),
    )[0]

    resolution = EvidenceGraph(ledger).resolve(
        _need(), now=NOW + timedelta(seconds=1)
    )
    assert resolution.acquisition_state is AcquisitionState.CONTRADICTED
    assert resolution.atoms == ()
    assert len(ledger.matching(_need())) == 2
    index = GoalEvidenceIndex(ledger.path)
    assert index.lookup(
        first.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
    ) is None
    assert index.lookup(
        second.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
    ) is None


def test_revoked_enrollment_invalidates_evidence_across_restart(tmp_path):
    path, ledger, bridge = _bridge(tmp_path)
    atom = bridge.ingest(
        _supply(), host=_host(), principal=local_sparks_principal(), now=NOW
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
    assert GoalEvidenceIndex(path).lookup(
        atom.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
    ) is None


def test_duplicate_observation_is_idempotent(tmp_path):
    _, ledger, bridge = _bridge(tmp_path)
    first = bridge.ingest(
        _supply(), host=_host(), principal=local_sparks_principal(), now=NOW
    )
    second = bridge.ingest(
        _supply(), host=_host(), principal=local_sparks_principal(), now=NOW
    )
    assert second == first
    assert ledger.matching(_need()) == first


def test_expired_cognitive_atom_invalidates_goals_projection(tmp_path):
    path, _ledger, bridge = _bridge(tmp_path)
    observed = NOW - timedelta(seconds=1)
    atom = bridge.ingest(
        _supply(_fact(
            observed_at=observed,
            expires_at=observed + timedelta(milliseconds=500),
        )),
        host=_host(), principal=local_sparks_principal(), now=observed,
    )[0]
    assert GoalEvidenceIndex(path).lookup(
        atom.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
    ) is None


def test_observation_fact_without_source_ref_is_unconstructable():
    with pytest.raises(ValueError, match="source_ref"):
        CapabilityFact(
            "os.family", "linux", None, "artemis", "host:artemis",
            EvidenceClass.OBSERVED, "",
            NOW, NOW + timedelta(hours=1), True,
        )


def test_supply_rejects_facts_from_other_hosts():
    forged = CapabilityFact(
        "os.family", "linux", None, "venus", "host:venus",
        EvidenceClass.OBSERVED, "fleet-discovery:mtls-agent-discovery",
        NOW, NOW + timedelta(hours=1), True,
    )
    with pytest.raises(ValueError, match="supply host"):
        _supply(forged)


def test_fleet_observations_are_scoped_to_the_receiving_audience(tmp_path):
    path, ledger, bridge = _bridge(tmp_path)
    other_principal = local_sparks_principal(audience_id="remote-chat:owner-key")
    private = bridge.ingest(
        _supply(), host=_host(),
        principal=local_sparks_principal(), now=NOW,
    )[0]
    remote = bridge.ingest(
        _supply(_fact("windows", observed_at=NOW + timedelta(seconds=1))),
        host=_host(),
        principal=other_principal, now=NOW + timedelta(seconds=1),
    )[0]

    assert private.scope_id != remote.scope_id
    assert EvidenceGraph(ledger).resolve(
        _need(), now=NOW + timedelta(seconds=2),
    ).atoms == (private,)
    other_need = EvidenceNeed(
        "need:artemis-os-remote", f"fleet-node:{NODE}", "machine.os",
        remote.scope_id, max_age_seconds=120, minimum_trust=0.9,
    )
    assert EvidenceGraph(ledger).resolve(
        other_need, now=NOW + timedelta(seconds=2),
    ).atoms == (remote,)
    index = GoalEvidenceIndex(path)
    private_record = index.lookup(
        private.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
    )
    remote_record = index.lookup(
        remote.evidence_id.replace("evidence:fleet:", "goal-evidence:fleet:")
    )
    assert private_record is not None
    assert private_record.audience == f"private:{local_sparks_principal().audience_id}"
    assert remote_record is not None
    assert remote_record.audience == f"private:{other_principal.audience_id}"
