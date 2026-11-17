"""MOD-IT-BACKUP-DR: bounded supplied backup/restore plan and evidence review.

No backup is produced, no restore is attempted, no repository is mounted and no
canonical SofA-a state is inspected. A supplied restore-drill result remains an
unverified claim, never proof that a restore would succeed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import MODULE_ID

CAPABILITY_ID = 'it.backup_dr.validate_recovery_plan.v1'
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'dataset_ref', 'plan_ref',
                     'backup_interval_seconds', 'retention_seconds',
                     'rpo_seconds', 'rto_seconds', 'targets', 'evidence'})
_TARGET_FIELDS = frozenset({'target_ref', 'storage_ref', 'encrypted_reported',
                            'offsite_reported'})
_EVIDENCE_FIELDS = frozenset({'last_backup_at', 'backup_state', 'integrity_check',
                              'restore_drill', 'restore_duration_seconds'})
_MAX_SECONDS = 31_536_000


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


def _seconds(value: object, label: str) -> int:
    if type(value) is not int or not 1 <= value <= _MAX_SECONDS:
        raise ValueError(f'invalid {label}')
    return value


def validate_recovery_plan(plan: Mapping[str, object], *, now: datetime,
                           max_age_seconds: int = 300) -> dict[str, object]:
    """Validate plan coherence and supplied evidence; never execute recovery."""
    if not isinstance(plan, Mapping) or set(plan) != _FIELDS:
        raise ValueError('recovery plan requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source = _ref(plan['source_ref'], 'source_ref')
    dataset = _ref(plan['dataset_ref'], 'dataset_ref')
    plan_ref = _ref(plan['plan_ref'], 'plan_ref')
    interval = _seconds(plan['backup_interval_seconds'], 'backup_interval_seconds')
    retention = _seconds(plan['retention_seconds'], 'retention_seconds')
    rpo = _seconds(plan['rpo_seconds'], 'rpo_seconds')
    rto = _seconds(plan['rto_seconds'], 'rto_seconds')
    observed = _aware(plan['observed_at'], 'observed_at')
    now = now.astimezone(timezone.utc)

    raw_targets = plan['targets']
    if type(raw_targets) is not list or not 1 <= len(raw_targets) <= 32:
        raise ValueError('targets must contain 1..32 items')
    targets = []
    seen_targets: set[str] = set()
    for item in raw_targets:
        if not isinstance(item, Mapping) or set(item) != _TARGET_FIELDS:
            raise ValueError('invalid backup target fields')
        target_ref = _ref(item['target_ref'], 'target_ref')
        if target_ref in seen_targets:
            raise ValueError('duplicate target_ref')
        seen_targets.add(target_ref)
        storage_ref = _ref(item['storage_ref'], 'storage_ref')
        if type(item['encrypted_reported']) is not bool or type(item['offsite_reported']) is not bool:
            raise ValueError('target flags must be boolean')
        targets.append((target_ref, storage_ref,
                        item['encrypted_reported'], item['offsite_reported']))

    evidence = plan['evidence']
    if not isinstance(evidence, Mapping) or set(evidence) != _EVIDENCE_FIELDS:
        raise ValueError('invalid evidence fields')
    backup_state = evidence['backup_state']
    if not isinstance(backup_state, str) or backup_state not in {'completed', 'failed', 'unknown'}:
        raise ValueError('invalid backup_state')
    integrity = evidence['integrity_check']
    if not isinstance(integrity, str) or integrity not in {'passed', 'failed', 'not_run'}:
        raise ValueError('invalid integrity_check')
    drill = evidence['restore_drill']
    if not isinstance(drill, str) or drill not in {'passed', 'failed', 'not_run'}:
        raise ValueError('invalid restore_drill')
    duration = evidence['restore_duration_seconds']
    if duration is not None and (type(duration) is not int or not 0 <= duration <= _MAX_SECONDS):
        raise ValueError('invalid restore_duration_seconds')
    if (drill == 'not_run' and duration is not None) or (drill == 'passed' and duration is None):
        raise ValueError('restore drill duration evidence mismatch')
    last_backup = evidence['last_backup_at']
    backup_at = None if last_backup is None else _aware(last_backup, 'last_backup_at')
    if backup_at is not None and backup_at > observed:
        raise ValueError('backup cannot occur after observation')

    base = {
        'schema': 'sofia.it.backup_dr.recovery_plan_validation.v1',
        'module_id': MODULE_ID,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source,
        'dataset_ref': dataset,
        'plan_ref': plan_ref,
        'observed_at': observed.isoformat(),
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'backup_created': False,
        'restore_performed': False,
        'restore_independently_verified': False,
        'canonical_state_inspected': False,
    }
    age = (now - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base |= {'freshness': freshness}
    if freshness != 'fresh':
        return base | {
            'status': 'unknown',
            'target_count': None,
            'last_backup_age_seconds': None,
            'restore_claim': 'not_verified',
            'findings': ['snapshot_timestamp_invalid'],
            'targets': [],
        }

    findings: list[str] = []
    if retention < interval:
        findings.append('retention_shorter_than_backup_interval')
    if interval > rpo:
        findings.append('backup_interval_exceeds_rpo')
    if len(targets) == 1:
        findings.append('single_backup_target_reported')
    if any(not encrypted for _, _, encrypted, _ in targets):
        findings.append('target_encryption_unconfirmed')
    if any(not offsite for _, _, _, offsite in targets):
        findings.append('target_offsite_unconfirmed')

    backup_age = None
    if backup_state == 'failed':
        findings.append('backup_failure_reported')
    elif backup_state == 'unknown':
        findings.append('backup_completion_unknown')
    if backup_at is None:
        findings.append('last_backup_unknown')
    else:
        backup_age = max(0, round((now - backup_at).total_seconds()))
        if backup_age > rpo:
            findings.append('rpo_exceeded')
    if integrity == 'failed':
        findings.append('integrity_failure_reported')
    elif integrity == 'not_run':
        findings.append('integrity_not_verified')
    if drill == 'failed':
        findings.append('restore_drill_failure_reported')
    elif drill == 'not_run':
        findings.append('restore_not_verified')
    elif duration is not None and duration > rto:
        findings.append('rto_exceeded_in_drill')

    rows = [{
        'target_ref': target_ref,
        'storage_ref': storage_ref,
        'encrypted_reported': encrypted,
        'offsite_reported': offsite,
    } for target_ref, storage_ref, encrypted, offsite in targets]
    return base | {
        'status': 'validated_with_findings' if findings else 'validated_consistent',
        'target_count': len(rows),
        'backup_interval_seconds': interval,
        'retention_seconds': retention,
        'rpo_seconds': rpo,
        'rto_seconds': rto,
        'last_backup_age_seconds': backup_age,
        'restore_claim': 'supplied_pass' if drill == 'passed' else 'not_verified',
        'findings': sorted(set(findings)),
        'targets': sorted(rows, key=lambda row: row['target_ref']),
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate a supplied recovery plan and evidence without backup or restore effects.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'plan'}):
            raise ValueError('invalid recovery plan validation request')
        return validate_recovery_plan(request.parameters['plan'],
                                      now=datetime.now(timezone.utc))

    return ((capability, handler),)
