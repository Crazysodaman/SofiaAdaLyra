"""Stable actor metadata must retain exact external-signature verification."""
from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from test.test_dev_approval_signatures import NOW, approval, key_material
from test.test_evolve_revision import MemoryAdapter, proposal
from sofia.platform.evolve.approval import ApprovalAction
from sofia.platform.evolve.revision import RevisionApproval, RevisionScope
from sofia.platform.safe.dev_approval import DevApprovalVerifier, dev_approval_signature_payload
from sofia.platform.safe.evolve_approval import DurableEvolutionApprovalVerifier, approval_signature_payload, revocation_signature_payload
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


@pytest.mark.parametrize('actor', ['person:sparks', 'Sparks'])
def test_dev_signed_owner_metadata_and_canonical_audit(tmp_path, actor):
    private, public = key_material()
    path = bootstrap_canonical_sqlite(tmp_path / 'state.db')
    verifier = DevApprovalVerifier(path, trusted_keys={'owner': public})
    item = replace(approval(), approved_by=actor)
    signature = private.sign(dev_approval_signature_payload(item))
    verifier.record(item, signer_key_id='owner', signature=signature)
    assert verifier.active_capabilities(now=NOW) == ('dev.apply',)
    consumed = verifier.consume(approval_id=item.approval_id, operation=item.operation,
        proposal_id=item.proposal_id, parameters={'proposal_id': item.proposal_id}, now=NOW)
    assert consumed == item  # retain original signed bytes, including legacy spelling
    assert verifier.active_capabilities(now=NOW) == ()
    with pytest.raises(PermissionError):
        verifier.consume(approval_id=item.approval_id, operation=item.operation,
            proposal_id=item.proposal_id, parameters={'proposal_id': item.proposal_id}, now=NOW)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT DISTINCT actor_id FROM safe_audit_event').fetchall() == [('person:sparks',)]
        assert db.execute('SELECT approved_by,signature FROM safe_dev_approval').fetchone() == (actor, signature)


@pytest.mark.parametrize('actor', ['person:sparks', 'Sparks'])
def test_evolve_signed_owner_metadata_verify_and_revoke(tmp_path, actor):
    private, public = key_material()
    path = bootstrap_canonical_sqlite(tmp_path / 'state.db')
    verifier = DurableEvolutionApprovalVerifier(path, trusted_keys={'owner': public})
    p = proposal(MemoryAdapter({(RevisionScope.PREFERENCE, 'response_style'): 'neutral'}))
    moment = p.created_at + timedelta(minutes=6)
    item = RevisionApproval(approval_id='revision-owner', proposal_id=p.proposal_id,
        proposal_fingerprint=p.fingerprint, action=ApprovalAction.APPLY,
        approved_by=actor, approved_at=moment-timedelta(minutes=1),
        expires_at=moment+timedelta(minutes=10), authority_reference='owner-session')
    signature = private.sign(approval_signature_payload(item))
    verifier.record_revision(item, signer_key_id='owner', signature=signature)
    assert verifier.verify(p, item, now=moment)
    assert verifier.active_capabilities(now=moment) == ('evolve.apply',)
    assert not verifier.verify(p, replace(item, approved_by='person:other'), now=moment)
    assert not verifier.verify(p, item, now=item.expires_at)
    payload = revocation_signature_payload(item.approval_id, revoked_at=moment, authority_reference='owner-session')
    verifier.revoke(item.approval_id, signer_key_id='owner', signature=private.sign(payload),
        revoked_at=moment, authority_reference='owner-session')
    assert not verifier.verify(p, item, now=moment)
    assert verifier.active_capabilities(now=moment) == ()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT DISTINCT actor_id FROM safe_audit_event').fetchall() == [('person:sparks',)]
        assert db.execute('SELECT approved_by,signature FROM safe_evolve_approval').fetchone() == (actor, signature)


@pytest.mark.parametrize('subsystem', ['dev', 'evolve'])
@pytest.mark.parametrize('defect', ['unknown_actor', 'wrong_signature', 'rewritten_alias', 'unknown_signer'])
def test_labels_never_replace_the_external_signature(tmp_path, subsystem, defect):
    private, public = key_material()
    path = bootstrap_canonical_sqlite(tmp_path / 'state.db')
    if subsystem == 'dev':
        verifier = DevApprovalVerifier(path, trusted_keys={'owner': public})
        item = replace(approval(), approved_by='person:sparks')
        sign_payload = dev_approval_signature_payload
        record = verifier.record
    else:
        verifier = DurableEvolutionApprovalVerifier(path, trusted_keys={'owner': public})
        item = RevisionApproval(approval_id='revision', proposal_id='proposal',
            proposal_fingerprint='a'*64, action=ApprovalAction.APPLY,
            approved_by='person:sparks', approved_at=NOW,
            expires_at=NOW+timedelta(minutes=10), authority_reference='owner-session')
        sign_payload = approval_signature_payload
        record = verifier.record_revision
    signed_item = item
    if defect == 'unknown_actor': item = signed_item = replace(item, approved_by='person:other')
    elif defect == 'rewritten_alias': signed_item = replace(item, approved_by='Sparks')
    signature = private.sign(sign_payload(signed_item))
    if defect == 'wrong_signature':
        wrong_private, _ = key_material()
        signature = wrong_private.sign(sign_payload(item))
    with pytest.raises(PermissionError):
        record(item, signer_key_id='unknown' if defect == 'unknown_signer' else 'owner', signature=signature)
    assert verifier.active_capabilities(now=NOW) == ()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM safe_audit_event').fetchone()[0] == 0


@pytest.mark.parametrize('actor', [None, 'Sparks'])
def test_dev_operator_cli_uses_stable_default_and_retains_legacy(tmp_path, capsys, actor):
    import json
    from cryptography.hazmat.primitives import serialization
    from sofia.platform.safe.dev_approve import main
    private, public = key_material()
    path = bootstrap_canonical_sqlite(tmp_path / 'state.db')
    private_path = tmp_path / 'disposable-owner.pem'
    private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    private_path.chmod(0o600)
    public_path = tmp_path / 'disposable-owner.pub'
    public_path.write_bytes(public)
    arguments = ['--state-path', str(path), '--operation', 'apply',
        '--proposal-id', 'code-1', '--parameters-json', '{"proposal_id":"code-1"}',
        '--private-key', str(private_path), '--trusted-public-key', str(public_path),
        '--signer-key-id', 'owner']
    if actor is not None: arguments += ['--approved-by', actor]
    assert main(arguments) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['approved_by'] == (actor or 'person:sparks')
    verifier = DevApprovalVerifier(path, trusted_keys={'owner': public})
    from datetime import datetime, timezone
    consumed = verifier.consume(approval_id=result['approval_id'], operation=approval().operation,
        proposal_id='code-1', parameters={'proposal_id': 'code-1'}, now=datetime.now(timezone.utc))
    assert consumed.approved_by == result['approved_by']
