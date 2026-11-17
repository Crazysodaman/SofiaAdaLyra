"""Offline validation tests for supplied credential-exposure findings.

No scanner, log reader, secret store or network request is used, and raw
evidence text is redacted before it is projected.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.it_security.exposure import (
    capability_registrations as exposure_regs,
    review_credential_exposure,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
SECRET_TEXT = (
    'password=Hunter2 token: abcdef123456 '
    'C:\\Users\\bob\\secret.txt /home/bob/.ssh/id_rsa '
    'Bearer abcdefghij'
)


def at(seconds: int = 0) -> str:
    return (NOW + timedelta(seconds=seconds)).isoformat()


def finding(**extra):
    return {
        'finding_ref': 'finding:a',
        'asset_ref': 'host:a',
        'credential_class': 'password',
        'exposure_state': 'exposed',
        'severity': 'high',
        'evidence_text': SECRET_TEXT,
    } | extra


def report(**extra):
    return {
        'source_ref': 'security:report',
        'observed_at': at(),
        'findings': [finding()],
    } | extra


def test_exposure_review_is_effect_free_and_redacted():
    result = review_credential_exposure(report(), now=NOW)
    assert result['status'] == 'reviewed_with_findings'
    assert result['highest_reported_severity'] == 'high'
    assert result['summary'] == 'reported_exposure_needs_review'
    assert result['effect'] == 'none'
    assert result['scanner_invoked'] is False
    assert result['external_requests_sent'] is False
    assert result['raw_evidence_returned'] is False
    assert result['secrets_redacted_before_output'] is True
    assert result['findings_detail'][0]['redaction_count'] > 0
    encoded = json.dumps(result)
    for leaked in ('Hunter2', 'abcdef123456', 'C:\\\\Users', '/home/bob',
                   'Bearer', 'id_rsa', 'secret.txt'):
        assert leaked not in encoded


def test_exposure_excerpt_is_bounded_and_never_raw():
    result = review_credential_exposure(
        report(findings=[finding(evidence_text=SECRET_TEXT + ' ' + 'x' * 1500)]),
        now=NOW,
    )
    row = result['findings_detail'][0]
    assert 'evidence_text' not in row
    assert len(row['redacted_excerpt']) <= 160
    assert set(row).issuperset({'finding_ref', 'asset_ref', 'credential_class',
                                'reported_exposure_state', 'reported_severity',
                                'redacted_excerpt', 'redaction_count'})


def test_exposure_not_exposed_and_revoked_do_not_trigger_rotation():
    clean = review_credential_exposure(
        report(findings=[finding(exposure_state='not_exposed')]), now=NOW)
    assert clean['summary'] == 'no_current_exposure_reported'
    assert clean['highest_reported_severity'] is None
    revoked = review_credential_exposure(
        report(findings=[finding(exposure_state='revoked')]), now=NOW)
    assert 'credential_revocation_reported' in revoked['findings']
    assert revoked['highest_reported_severity'] is None


def test_exposure_unknown_state_stays_unknown():
    result = review_credential_exposure(
        report(findings=[finding(exposure_state='unknown')]), now=NOW)
    assert result['summary'] == 'unknown'
    assert result['findings_detail'][0]['classification'] == 'unknown'
    assert result['highest_reported_severity'] is None


def test_exposure_stale_report_never_leaks_evidence():
    result = review_credential_exposure(
        report(observed_at=at(-3600)), now=NOW)
    assert result['status'] == 'unknown'
    assert result['finding_count'] is None
    assert result['findings'] == []
    assert result['highest_reported_severity'] is None
    assert result['summary'] == 'unknown'
    assert 'Hunter2' not in json.dumps(result)


@pytest.mark.parametrize('change', [
    {'findings': []},
    {'findings': [finding(finding_ref=f'finding:{n}') for n in range(65)]},
    {'findings': [finding(), finding()]},
    {'findings': [finding(credential_class='bank_account')]},
    {'findings': [finding(exposure_state='maybe')]},
    {'findings': [finding(severity='system')]},
    {'findings': [finding(evidence_text=123)]},
    {'findings': [finding(evidence_text='x' * 2001)]},
    {'findings': [finding(evidence_text='password=ok\x00hidden')]},
    {'findings': [finding() | {'scan_now': True}]},
    {'source_ref': 'security\nreport'},
    {'source_ref': '../private'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'scan': True},
])
def test_exposure_rejects_malformed_or_oversized(change):
    with pytest.raises(ValueError):
        review_credential_exposure(report(**change), now=NOW)


@pytest.mark.parametrize('bad_ref', ['../etc/shadow', '/etc/shadow',
                                     'host\\private', 'host/../asset'])
def test_exposure_rejects_path_like_references(bad_ref):
    with pytest.raises(ValueError):
        review_credential_exposure(report(source_ref=bad_ref), now=NOW)
    with pytest.raises(ValueError):
        review_credential_exposure(
            report(findings=[finding(finding_ref=bad_ref)]), now=NOW)
    with pytest.raises(ValueError):
        review_credential_exposure(
            report(findings=[finding(asset_ref=bad_ref)]), now=NOW)


def test_exposure_registration_is_inert_and_identity_checked():
    (capability, handler), = exposure_regs()
    assert isinstance(capability, Capability)
    assert capability.name == 'it.security.review_credential_exposure.v1'
    live = report(observed_at=datetime.now(timezone.utc).isoformat())
    result = handler(CapabilityRequest(capability, {'report': live},
                                      None, 'offline exposure review'))
    assert result['effect'] == 'none'
    assert result['raw_evidence_returned'] is False
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'report': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'report': live, 'scan': True},
                                  None, 'invalid'))
