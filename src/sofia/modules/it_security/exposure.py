"""MOD-IT-SECURITY: bounded supplied credential-exposure review with redaction.

No vulnerability scanner, log reader, secret store, endpoint or network access
occurs. Supplied evidence text is treated as untrusted data, redacted before it
is projected, and never returned raw. A report is not proof of compromise.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import MODULE_ID

CAPABILITY_ID = 'it.security.review_credential_exposure.v1'
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'findings'})
_FINDING_FIELDS = frozenset({'finding_ref', 'asset_ref', 'credential_class',
                             'exposure_state', 'severity', 'evidence_text'})
_CLASSES = frozenset({'password', 'api_token', 'private_key', 'session_cookie',
                      'connection_string', 'unknown'})
_EXPOSURE = frozenset({'exposed', 'not_exposed', 'revoked', 'unknown'})
_SEVERITY = frozenset({'low', 'medium', 'high', 'critical', 'unknown'})
_ORDER = {'unknown': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
_MAX_EVIDENCE = 2000
_MAX_EXCERPT = 160
_REDACTIONS = (
    (re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?'
                r'-----END [A-Z0-9 ]*PRIVATE KEY-----', re.S), 'private_key'),
    (re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|"
                r"access[_-]?key|client[_-]?secret)\b\s*[:=]\s*"
                r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"), 'credential_assignment'),
    (re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{6,}'), 'bearer_token'),
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), 'aws_access_key_id'),
    (re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'), 'github_token'),
    (re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b'), 'slack_token'),
    (re.compile(r'\b[A-Za-z0-9._%+-]+:[^@\s/:\'"]+@[A-Za-z0-9.-]+\b'), 'userinfo_url'),
    (re.compile(r'\b[A-Za-z]:\\[^\s<>|]+'), 'windows_path'),
    (re.compile(r'\\\\[^\s<>|]+'), 'unc_path'),
    (re.compile(r'(?<![\w.-])/(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*'), 'unix_path'),
)


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


def _redact(text: str) -> tuple[str, int]:
    redacted = text
    count = 0
    for pattern, label in _REDACTIONS:
        redacted, hits = pattern.subn(f'[REDACTED:{label}]', redacted)
        count += hits
    compact = ' '.join(redacted.split())
    if len(compact) > _MAX_EXCERPT:
        compact = compact[:_MAX_EXCERPT - 3] + '...'
    return compact, count


def review_credential_exposure(report: Mapping[str, object], *, now: datetime,
                               max_age_seconds: int = 300) -> dict[str, object]:
    """Review bounded supplied findings; redact secrets and paths."""
    if not isinstance(report, Mapping) or set(report) != _FIELDS:
        raise ValueError('credential exposure report requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source = _ref(report['source_ref'], 'source_ref')
    observed = _aware(report['observed_at'], 'observed_at')
    now = now.astimezone(timezone.utc)

    raw_findings = report['findings']
    if type(raw_findings) is not list or not 1 <= len(raw_findings) <= 64:
        raise ValueError('findings must contain 1..64 items')
    parsed = []
    seen: set[str] = set()
    for item in raw_findings:
        if not isinstance(item, Mapping) or set(item) != _FINDING_FIELDS:
            raise ValueError('invalid exposure finding fields')
        finding_ref = _ref(item['finding_ref'], 'finding_ref')
        if finding_ref in seen:
            raise ValueError('duplicate finding_ref')
        seen.add(finding_ref)
        asset_ref = _ref(item['asset_ref'], 'asset_ref')
        credential_class = item['credential_class']
        if not isinstance(credential_class, str) or credential_class not in _CLASSES:
            raise ValueError('invalid credential_class')
        exposure_state = item['exposure_state']
        if not isinstance(exposure_state, str) or exposure_state not in _EXPOSURE:
            raise ValueError('invalid exposure_state')
        severity = item['severity']
        if not isinstance(severity, str) or severity not in _SEVERITY:
            raise ValueError('invalid severity')
        evidence = item['evidence_text']
        if not isinstance(evidence, str) or len(evidence) > _MAX_EVIDENCE:
            raise ValueError('invalid evidence_text')
        if any(ord(char) == 0 or (ord(char) < 32 and char not in '\n\t\r') or ord(char) == 127
               for char in evidence):
            raise ValueError('unsafe control character in evidence_text')
        parsed.append((finding_ref, asset_ref, credential_class,
                       exposure_state, severity, evidence))

    base = {
        'schema': 'sofia.it.security.credential_exposure_review.v1',
        'module_id': MODULE_ID,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source,
        'observed_at': observed.isoformat(),
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'scanner_invoked': False,
        'external_requests_sent': False,
        'raw_evidence_returned': False,
        'secrets_redacted_before_output': True,
    }
    age = (now - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base |= {'freshness': freshness}
    if freshness != 'fresh':
        return base | {
            'status': 'unknown',
            'finding_count': None,
            'highest_reported_severity': None,
            'summary': 'unknown',
            'findings': [],
        }

    rows = []
    findings: list[str] = []
    active_severities: list[str] = []
    unknown_state = False
    for (finding_ref, asset_ref, credential_class,
         exposure_state, severity, evidence) in parsed:
        excerpt, redaction_count = _redact(evidence)
        if exposure_state == 'exposed':
            findings.append('credential_exposure_reported')
            if severity != 'unknown':
                active_severities.append(severity)
            classification = 'reported_exposed'
        elif exposure_state == 'revoked':
            findings.append('credential_revocation_reported')
            classification = 'reported_revoked'
        elif exposure_state == 'unknown':
            findings.append('exposure_state_unknown')
            unknown_state = True
            classification = 'unknown'
        else:
            classification = 'reported_not_exposed'
        rows.append({
            'finding_ref': finding_ref,
            'asset_ref': asset_ref,
            'credential_class': credential_class,
            'reported_exposure_state': exposure_state,
            'reported_severity': severity,
            'classification': classification,
            'redacted_excerpt': excerpt,
            'redaction_count': redaction_count,
        })

    highest = max(active_severities, key=lambda value: _ORDER[value], default=None)
    summary = ('reported_exposure_needs_review' if active_severities
               else 'unknown' if unknown_state
               else 'no_current_exposure_reported')
    if active_severities:
        # Advisory next checks only; no rotation or revocation is performed here.
        guidance = 'Rotate through the approved secret-management workflow and review scope.'
        for row in rows:
            if row['classification'] == 'reported_exposed':
                row['next_check'] = guidance
    return base | {
        'status': 'reviewed_with_findings' if active_severities else 'reviewed',
        'finding_count': len(rows),
        'highest_reported_severity': highest,
        'summary': summary,
        'findings': sorted(set(findings)),
        'findings_detail': sorted(rows, key=lambda row: row['finding_ref']),
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Review supplied credential-exposure findings with secret and path redaction.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'report'}):
            raise ValueError('invalid credential exposure review request')
        return review_credential_exposure(request.parameters['report'],
                                          now=datetime.now(timezone.utc))

    return ((capability, handler),)
