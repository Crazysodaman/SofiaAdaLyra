"""MOD-IT-CONTAINERS: bounded supplied stack/image/config safety review.

No Docker socket, Portainer API, registry call, container start/restart, image
pull or configuration write occurs. Environment values and filesystem paths are
never accepted; only opaque references and counts are projected.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import MODULE_ID

CAPABILITY_ID = 'it.containers.validate_stack_config.v1'
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_TAG = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$')
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_ENV_KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'stack_ref', 'services'})
_SERVICE_FIELDS = frozenset({'service_ref', 'image_ref', 'image_digest',
                             'image_tag', 'privileged', 'read_only_root',
                             'host_network', 'environment_keys', 'mount_refs',
                             'published_ports'})
_SECRET_KEY_HINTS = ('password', 'passwd', 'secret', 'token', 'api_key',
                     'apikey', 'private_key', 'credential')


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ValueError(f'invalid {label}')
    if value.startswith('/') or '\\' in value or '..' in value.split('/'):
        raise ValueError(f'unsafe {label}')
    return value


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f'invalid {label}')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'invalid {label}') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f'{label} requires timezone')
    return parsed.astimezone(timezone.utc)


def validate_stack_config(stack: Mapping[str, object], *, now: datetime,
                          max_age_seconds: int = 300) -> dict[str, object]:
    """Validate one bounded supplied stack projection; never contact runtime."""
    if not isinstance(stack, Mapping) or set(stack) != _FIELDS:
        raise ValueError('stack snapshot requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source = _ref(stack['source_ref'], 'source_ref')
    stack_ref = _ref(stack['stack_ref'], 'stack_ref')
    observed = _aware(stack['observed_at'], 'observed_at')
    now = now.astimezone(timezone.utc)

    services = stack['services']
    if type(services) is not list or not 1 <= len(services) <= 64:
        raise ValueError('services must contain 1..64 items')
    parsed = []
    seen_services: set[str] = set()
    for item in services:
        if not isinstance(item, Mapping) or set(item) != _SERVICE_FIELDS:
            raise ValueError('invalid service fields')
        service_ref = _ref(item['service_ref'], 'service_ref')
        if service_ref in seen_services:
            raise ValueError('duplicate service_ref')
        seen_services.add(service_ref)
        image_ref = _ref(item['image_ref'], 'image_ref')
        digest = item['image_digest']
        if digest is not None and (not isinstance(digest, str)
                                   or _DIGEST.fullmatch(digest) is None):
            raise ValueError('invalid image_digest')
        tag = item['image_tag']
        if tag is not None and (not isinstance(tag, str) or _TAG.fullmatch(tag) is None):
            raise ValueError('invalid image_tag')
        for field in ('privileged', 'read_only_root', 'host_network'):
            if type(item[field]) is not bool:
                raise ValueError(f'invalid {field}')

        raw_keys = item['environment_keys']
        if type(raw_keys) is not list or len(raw_keys) > 32:
            raise ValueError('environment_keys must be a bounded list')
        if any(not isinstance(key, str) or _ENV_KEY.fullmatch(key) is None
               for key in raw_keys):
            raise ValueError('invalid environment key')
        if len(set(raw_keys)) != len(raw_keys):
            raise ValueError('duplicate environment key')

        raw_mounts = item['mount_refs']
        if type(raw_mounts) is not list or len(raw_mounts) > 32:
            raise ValueError('mount_refs must be a bounded list')
        mount_refs = [_ref(value, 'mount_ref') for value in raw_mounts]
        if len(set(mount_refs)) != len(mount_refs):
            raise ValueError('duplicate mount_ref')

        raw_ports = item['published_ports']
        if type(raw_ports) is not list or len(raw_ports) > 64:
            raise ValueError('published_ports must be a bounded list')
        if any(type(port) is not int or not 1 <= port <= 65535 for port in raw_ports):
            raise ValueError('invalid published port')
        if len(set(raw_ports)) != len(raw_ports):
            raise ValueError('duplicate published port')

        secret_like = sum(
            1 for key in raw_keys
            if any(hint in key.lower() for hint in _SECRET_KEY_HINTS)
        )
        parsed.append((service_ref, image_ref, digest, tag,
                       item['privileged'], item['read_only_root'],
                       item['host_network'], len(raw_keys), secret_like,
                       len(mount_refs), sorted(raw_ports)))

    base = {
        'schema': 'sofia.it.containers.stack_config_validation.v1',
        'module_id': MODULE_ID,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source,
        'stack_ref': stack_ref,
        'observed_at': observed.isoformat(),
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'docker_contacted': False,
        'portainer_contacted': False,
        'registry_contacted': False,
        'containers_started': False,
        'config_applied': False,
        'runtime_health': 'UNKNOWN',
        'deployment_verified': False,
        'environment_values_exposed': False,
        'host_paths_exposed': False,
    }
    age = (now - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base |= {'freshness': freshness}
    if freshness != 'fresh':
        return base | {
            'status': 'unknown',
            'service_count': None,
            'findings': ['snapshot_timestamp_invalid'],
            'services': [],
        }

    findings: list[str] = []
    rows = []
    for (service_ref, image_ref, digest, tag, privileged, read_only_root,
         host_network, env_count, secret_like, mount_count, ports) in parsed:
        if digest is None:
            findings.append('image_digest_absent')
        if tag == 'latest':
            findings.append('mutable_latest_tag')
        if privileged:
            findings.append('privileged_mode_reported')
        if not read_only_root:
            findings.append('writable_root_filesystem_reported')
        if host_network:
            findings.append('host_network_reported')
        if secret_like:
            findings.append('secret_like_environment_key_reported')
        if ports:
            findings.append('host_port_published')
        if any(port < 1024 for port in ports):
            findings.append('privileged_host_port_published')
        rows.append({
            'service_ref': service_ref,
            'image_ref': image_ref,
            'image_digest_pinned': digest is not None,
            'image_tag': tag,
            'privileged': privileged,
            'read_only_root': read_only_root,
            'host_network': host_network,
            'environment_key_count': env_count,
            'secret_like_environment_key_count': secret_like,
            'mount_ref_count': mount_count,
            'published_ports': ports,
        })
    return base | {
        'status': 'validated_with_findings' if findings else 'validated_consistent',
        'service_count': len(rows),
        'findings': sorted(set(findings)),
        'services': sorted(rows, key=lambda row: row['service_ref']),
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Review a supplied container stack projection without contacting Docker or Portainer.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'stack'}):
            raise ValueError('invalid stack validation request')
        return validate_stack_config(request.parameters['stack'],
                                     now=datetime.now(timezone.utc))

    return ((capability, handler),)
