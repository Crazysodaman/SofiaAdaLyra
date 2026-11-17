"""Offline validation tests for supplied container stack/image/config safety.

No Docker socket, Portainer API, registry, pull, start, restart or config write.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.it_containers.stack_validation import (
    capability_registrations as stack_regs,
    validate_stack_config,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
DIGEST = 'a' * 64


def at(seconds: int = 0) -> str:
    return (NOW + timedelta(seconds=seconds)).isoformat()


def service(**extra):
    return {
        'service_ref': 'service:web',
        'image_ref': 'registry.example/app',
        'image_digest': DIGEST,
        'image_tag': 'v1.2.3',
        'privileged': False,
        'read_only_root': True,
        'host_network': False,
        'environment_keys': ['APP_MODE'],
        'mount_refs': ['mount:data'],
        'published_ports': [],
    } | extra


def stack(**extra):
    return {
        'source_ref': 'portainer:stack',
        'observed_at': at(),
        'stack_ref': 'stack:app',
        'services': [service()],
    } | extra


def test_stack_consistent_projection_is_effect_free():
    result = validate_stack_config(stack(), now=NOW)
    assert result['status'] == 'validated_consistent'
    assert result['findings'] == []
    assert result['service_count'] == 1
    assert result['effect'] == 'none'
    assert result['docker_contacted'] is False
    assert result['portainer_contacted'] is False
    assert result['registry_contacted'] is False
    assert result['containers_started'] is False
    assert result['config_applied'] is False
    assert result['runtime_health'] == 'UNKNOWN'
    assert result['deployment_verified'] is False


def test_stack_unsafe_config_is_reported_without_repair():
    result = validate_stack_config(
        stack(services=[service(
            image_digest=None, image_tag='latest', privileged=True,
            read_only_root=False, host_network=True,
            environment_keys=['DB_PASSWORD', 'API_TOKEN'],
            published_ports=[80, 8443],
        )]),
        now=NOW,
    )
    assert result['status'] == 'validated_with_findings'
    assert set(result['findings']) == {
        'image_digest_absent',
        'mutable_latest_tag',
        'privileged_mode_reported',
        'writable_root_filesystem_reported',
        'host_network_reported',
        'secret_like_environment_key_reported',
        'host_port_published',
        'privileged_host_port_published',
    }
    assert result['containers_started'] is False


def test_stack_environment_values_and_paths_are_not_projected():
    result = validate_stack_config(
        stack(services=[service(
            environment_keys=['DB_PASSWORD', 'APP_MODE'],
            mount_refs=['mount:data', 'mount:config'],
        )]),
        now=NOW,
    )
    encoded = json.dumps(result)
    assert 'DB_PASSWORD' not in encoded
    assert 'mount:data' not in encoded
    assert 'mount:config' not in encoded
    assert result['services'][0]['secret_like_environment_key_count'] == 1
    assert result['services'][0]['mount_ref_count'] == 2
    assert result['environment_values_exposed'] is False
    assert result['host_paths_exposed'] is False


def test_stack_stale_snapshot_is_unknown():
    result = validate_stack_config(stack(observed_at=at(-3600)), now=NOW)
    assert result['status'] == 'unknown'
    assert result['service_count'] is None
    assert result['services'] == []
    assert result['findings'] == ['snapshot_timestamp_invalid']


@pytest.mark.parametrize('change', [
    {'services': []},
    {'services': [service(service_ref=f'service:{n}') for n in range(65)]},
    {'services': [service(), service()]},
    {'services': [service(image_digest='xyz')]},
    {'services': [service(image_digest='A' * 64)]},
    {'services': [service(image_tag='bad tag')]},
    {'services': [service(image_tag='')]},
    {'services': [service(privileged='false')]},
    {'services': [service(read_only_root=0)]},
    {'services': [service(host_network=None)]},
    {'services': [service(environment_keys=['bad key'])]},
    {'services': [service(environment_keys=['APP_MODE', 'APP_MODE'])]},
    {'services': [service(environment_keys=[f'KEY_{n}' for n in range(33)])]},
    {'services': [service(mount_refs=['mount:a', 'mount:a'])]},
    {'services': [service(mount_refs=[f'mount:{n}' for n in range(33)])]},
    {'services': [service(mount_refs=['../etc'])]},
    {'services': [service(published_ports=[0])]},
    {'services': [service(published_ports=[65536])]},
    {'services': [service(published_ports=[True])]},
    {'services': [service(published_ports=[80, 80])]},
    {'source_ref': 'portainer\nstack'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'services': [service() | {'docker_socket': '/var/run/docker.sock'}]},
    {'execute': True},
])
def test_stack_rejects_malformed_or_oversized(change):
    with pytest.raises(ValueError):
        validate_stack_config(stack(**change), now=NOW)


@pytest.mark.parametrize('bad_ref', ['../etc/passwd', '/var/run/docker.sock',
                                     'registry\\secret', 'registry/../app'])
def test_stack_rejects_path_like_references(bad_ref):
    with pytest.raises(ValueError):
        validate_stack_config(stack(source_ref=bad_ref), now=NOW)
    with pytest.raises(ValueError):
        validate_stack_config(stack(stack_ref=bad_ref), now=NOW)
    with pytest.raises(ValueError):
        validate_stack_config(stack(services=[service(image_ref=bad_ref)]), now=NOW)


def test_stack_registration_is_inert_and_identity_checked():
    (capability, handler), = stack_regs()
    assert isinstance(capability, Capability)
    assert capability.name == 'it.containers.validate_stack_config.v1'
    live = stack(observed_at=datetime.now(timezone.utc).isoformat())
    result = handler(CapabilityRequest(capability, {'stack': live},
                                      None, 'offline stack review'))
    assert result['effect'] == 'none'
    assert result['docker_contacted'] is False
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'stack': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'stack': live, 'deploy': True},
                                  None, 'invalid'))
