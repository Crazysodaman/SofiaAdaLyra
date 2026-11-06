"""Explicit privileged disposable Fleet state setup, never production admission."""
from dataclasses import replace
from datetime import datetime, timezone


def fixture_host(registry, host):
    from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
    from sofia.platform.state.model import StateClass, StateKey, StateRecord
    if isinstance(registry, StatePlaneFleetRegistry):
        key = StateKey(namespace=registry.NAMESPACE, key=host.host_id)
        current = registry.state_plane.read(key)
        registry.state_plane.write(StateRecord(key=key, state_class=StateClass.SHARED_AUTHORITATIVE,
            revision=1 if current is None else current.revision+1,
            value=registry._encode(host), updated_at=datetime.now(timezone.utc), source='test-fixture:fleet'),
            expected_revision=None if current is None else current.revision)
        registry._load()
    else:
        registry._hosts[host.host_id] = host
    return host


def fixture_authenticate(registry, host_id, node_id):
    return fixture_host(registry, replace(registry.host(host_id), trusted=True, node_id=node_id))


def register_fixture_candidate(registry, host):
    from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
    from sofia.platform.ops.model import HostLifecycle
    if isinstance(registry, StatePlaneFleetRegistry) and (host.trusted or host.node_id is not None):
        assert host.lifecycle is HostLifecycle.CANDIDATE, 'fixture starts from a candidate'
        assert registry.host(host.host_id) in (None, host), 'fixture identity must not conflict'
        return fixture_host(registry, host)
    return registry.register_candidate(host)


def authenticate_fixture_candidate(registry, host_id, node_id):
    from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
    if isinstance(registry, StatePlaneFleetRegistry):
        return fixture_authenticate(registry, host_id, node_id)
    return registry.authenticate_candidate(host_id, node_id)
