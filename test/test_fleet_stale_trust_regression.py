from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
from sofia.platform.ops.model import FleetHost, HostLifecycle, HostTelemetry
from sofia.platform.ops.fleet import FleetRemovalApproval
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.plane import StatePlaneConflictError
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint
from test.owner_auth_fixture import record_verified_owner_approval
from test.fleet_state_fixture import fixture_host


@pytest.mark.parametrize('write', ['telemetry', 'lifecycle'])
def test_stale_telemetry_cannot_resurrect_decommissioned_trust(canonical_state_path, write):
    first = StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path))
    fixture_host(first, FleetHost('worker', 'linux', 'x86_64', HostLifecycle.DRAINING, True, node_id=uuid4()))
    stale = StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path))
    now = datetime.now(timezone.utc)
    parameters = first.removal_parameters('worker', proposal_revision='removal')
    approval = ExecutionApproval('removal', 'fleet.decommission', execution_fingerprint('fleet.decommission', parameters),
        'person:sparks', now, now+timedelta(minutes=5))
    record_verified_owner_approval(ExecutionApprovalVerifier(canonical_state_path), approval)
    first.decommission('worker', proposal_revision='removal', approval=FleetRemovalApproval('removal', 'worker', 'removal', 'label', now))
    with pytest.raises(StatePlaneConflictError):
        if write == 'telemetry':
            stale.update_telemetry('worker', HostTelemetry(now, cpu_percent=1))
        else:
            stale.transition('worker', HostLifecycle.MAINTENANCE)
    persisted = StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path)).host('worker')
    assert persisted.lifecycle is HostLifecycle.DECOMMISSIONED and not persisted.trusted


def test_durable_internal_authentication_cannot_promote_trust(canonical_state_path):
    registry = StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path))
    registry.register_candidate(FleetHost('worker', 'linux', 'x86_64', HostLifecycle.CANDIDATE, False))
    with pytest.raises(PermissionError): registry.authenticate_candidate('worker', uuid4())
    assert not StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path)).host('worker').trusted


def test_registration_cannot_inject_trusted_durable_candidate(canonical_state_path):
    registry = StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path))
    with pytest.raises(PermissionError):
        registry.register_candidate(FleetHost('worker', 'linux', 'x86_64', HostLifecycle.CANDIDATE, True))
    assert registry.host('worker') is None


def test_legacy_json_cannot_restore_retired_trust(canonical_state_path, tmp_path):
    import json
    registry = StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path))
    host = FleetHost('retired', 'linux', 'x86_64', HostLifecycle.CANDIDATE, True, node_id=uuid4())
    legacy = tmp_path / 'legacy-fleet.json'
    legacy.write_text(json.dumps({'hosts':[json.loads(registry._encode(host))]}))
    with pytest.raises(PermissionError):
        StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path), legacy_path=legacy)
    assert legacy.exists()
    assert StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path)).host('retired') is None


def test_in_memory_base_promotion_cannot_leak_into_durable_telemetry(canonical_state_path):
    from sofia.platform.ops.fleet import FleetRegistry
    registry = StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path))
    registry.register_candidate(FleetHost('worker', 'linux', 'x86_64', HostLifecycle.CANDIDATE, False))
    FleetRegistry.authenticate_candidate(registry, 'worker', uuid4())
    with pytest.raises(PermissionError):
        registry.update_telemetry('worker', HostTelemetry(datetime.now(timezone.utc), cpu_percent=1))
    assert not StatePlaneFleetRegistry(SQLiteStatePlane(canonical_state_path)).host('worker').trusted
