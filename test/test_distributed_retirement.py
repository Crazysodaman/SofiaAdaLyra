from test.fleet_state_fixture import register_fixture_candidate, authenticate_fixture_candidate
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sofia.platform.distributed.model import ApprovedEndpoint
from sofia.platform.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.platform.distributed.model import NodeEnrollment
from sofia.platform.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.platform.distributed.model import DistributedNode, NodeEndpoint, NodeTransport
from sofia.platform.distributed.operator import retire_node
from sofia.platform.ops.model import FleetHost, HostLifecycle
from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.core.cognition.v2 import (
    AcquisitionState, CognitiveEvidenceLedger, EpistemicState, EvidenceAtom,
)


def test_retirement_disables_identity_and_endpoint(tmp_path):
    node=DistributedNode(uuid4(),"Artemis")
    enrollment=NodeEnrollment(node,sha256(b"k").hexdigest(),datetime.now(timezone.utc),"Sparks")
    endpoint=NodeEndpoint("artemis.local",443,NodeTransport.HTTPS)
    state_path=tmp_path/"sofia.db"
    ids=DurableNodeIdentityRegistry(state_path); eps=DurableEndpointPolicy(state_path)
    ids.enroll(enrollment); eps.approve(ApprovedEndpoint(node.node_id,endpoint,"Sparks"))
    retire_node(state_path,node.node_id)
    assert ids.get(node.node_id) is None
    assert eps.permits(node.node_id,endpoint) is False
    ids.close(); eps.close()


def test_retirement_quarantines_host_and_revokes_cognitive_evidence(tmp_path):
    now = datetime.now(timezone.utc)
    state_path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    node = DistributedNode(uuid4(), "Artemis")
    enrollment = NodeEnrollment(
        node, sha256(b"artemis-key").hexdigest(), now, "Sparks",
    )
    endpoint = NodeEndpoint("artemis.local", 7443, NodeTransport.HTTPS)
    identities = DurableNodeIdentityRegistry(state_path)
    endpoints = DurableEndpointPolicy(state_path)
    identities.enroll(enrollment)
    endpoints.approve(ApprovedEndpoint(node.node_id, endpoint, "Sparks"))
    identities.close()
    endpoints.close()

    registry = StatePlaneFleetRegistry(SQLiteStatePlane(state_path))
    register_fixture_candidate(registry, FleetHost(
        "Artemis", "linux", "amd64", HostLifecycle.CANDIDATE, False,
    ))
    authenticate_fixture_candidate(registry, "Artemis", node.node_id)
    registry.transition("Artemis", HostLifecycle.ENROLLED)
    evidence = CognitiveEvidenceLedger(state_path)
    atom = evidence.append(EvidenceAtom(
        evidence_id="evidence:fleet:retirement-case",
        subject_id=f"fleet-node:{node.node_id}",
        predicate="machine.os", value_json='"linux"',
        source_id="capability:fleet:retirement-case",
        observed_at=now, expires_at=now + timedelta(hours=1),
        scope_id="local:text", trust=0.98,
        epistemic_state=EpistemicState.OBSERVED,
        acquisition_state=AcquisitionState.CURRENT,
    ))

    retire_node(state_path, node.node_id)
    retire_node(state_path, node.node_id)

    restarted = StatePlaneFleetRegistry(SQLiteStatePlane(state_path))
    host = restarted.host("Artemis")
    assert host is not None
    assert host.lifecycle is HostLifecycle.QUARANTINED
    assert CognitiveEvidenceLedger(state_path).get(
        atom.evidence_id
    ).acquisition_state is AcquisitionState.REVOKED
