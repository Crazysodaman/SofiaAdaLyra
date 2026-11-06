"""Local authoritative callsign acceptance with real SAFE cryptographic proofs."""
from base64 import b64encode
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import multiprocessing
import sqlite3
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.sdk.identity import AegisIdentity, IdentityKind
from sofia.platform.ops.callsigns import (
    CallsignAuthority, CallsignUnavailable, CallsignRevisionConflict,
    SCHEMA, canonical_json, core_request_bytes, normalize_callsign,
)
from sofia.platform.ops.callsign_client import CallsignDisplayClient
from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard, bootstrap_canonical_sqlite
from sofia.platform.state.installation_identity import InstallationIdentityStore
from test.owner_auth_fixture import record_verified_owner_approval


def _proof(path, capability, parameters):
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(str(uuid4()), capability, execution_fingerprint(capability, parameters),
        'person:sparks', now-timedelta(seconds=1), now+timedelta(minutes=5))
    record_verified_owner_approval(ExecutionApprovalVerifier(path), approval)
    return approval.approval_id


class NamingFixture:
    def __init__(self, tmp_path):
        self.path = tmp_path / 'fleet.db'
        self.installation = InstallationIdentityStore(tmp_path / 'private' / 'authority')
        self.installation.initialize()
        from sofia.platform.state.local_store import PlatformLocalStore
        from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
        PlatformLocalStore(self.path, roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
            host_identity=self.installation.load().identity.canonical_uuid)
        identifier = str(uuid4())
        parameters = CallsignAuthority.initialize_parameters(self.path, self.installation, identifier)
        approval = _proof(self.path, 'fleet.callsign.authority.initialize', parameters)
        self.authority = CallsignAuthority.initialize(self.path, self.installation,
            authority_id=identifier, approval_id=approval)
        self.platforms = []
        for name in ('one', 'two'):
            store = InstallationIdentityStore(tmp_path / 'private' / name)
            identity = store.initialize()
            self.platforms.append(store)
            self.owner('register', identity.identity.canonical_uuid,
                {'identity': identity.identity.to_payload(), 'public_key_sha256': identity.public_key_sha256})
        self.first, self.second = [s.load().identity.canonical_uuid for s in self.platforms]

    def prepare(self, operation, platform, payload, *, revision=None, request_id=None):
        revision = self.authority.snapshot(platform)['revision'] if revision is None else revision
        request_id = request_id or str(uuid4())
        capability, parameters = self.authority.approval_parameters(operation, platform,
            expected_revision=revision, request_id=request_id, payload=payload)
        return {'expected_revision': revision, 'request_id': request_id, 'payload': payload,
                'approval_id': _proof(self.path, capability, parameters)}

    def owner(self, operation, platform, payload):
        return self.authority.owner_operation(operation, platform, **self.prepare(operation, platform, payload))

    def rename(self, platform, name, *, override=False):
        return self.owner('rename', platform, {'name': name, 'override_lock': override})

    def attach(self, platform=None, *, core=None, key=None, generation=1):
        platform = platform or self.first
        core, key = core or str(uuid4()), key or Ed25519PrivateKey.generate()
        der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.owner('attach', platform, {'core_identity': AegisIdentity.from_uuid_text(IdentityKind.CORE, core).to_payload(),
            'generation': generation, 'public_key_der': b64encode(der).decode('ascii')})
        return core, key

    def grant(self, platform=None, *, expires=None):
        identifier = str(uuid4())
        self.owner('grant', platform or self.first, {'grant_id': identifier,
            'expires_at': (expires or datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
        return identifier

    def request(self, grant, *, platform=None, name='Forward Unto Dawn'):
        platform = platform or self.first
        state = self.authority.snapshot(platform)
        now = datetime.now(timezone.utc)
        return {'schema': SCHEMA, 'authority_id': self.authority.authority_id,
            'platform_id': platform, 'core_id': state['core_id'], 'core_generation': state['core_generation'],
            'attachment_revision': state['attachment_revision'], 'grant_id': grant,
            'expected_revision': state['revision'], 'request_id': str(uuid4()), 'name': name,
            'issued_at': now.isoformat(), 'expires_at': (now+timedelta(minutes=2)).isoformat()}


@pytest.fixture
def naming(tmp_path):
    return NamingFixture(tmp_path)


def test_fresh_platform_unassigned_and_core_free(naming):
    for platform in (naming.first, naming.second):
        state = naming.authority.snapshot(platform)
        assert state['registered'] and state['display'] == 'UNASSIGNED'
        assert state['core_id'] is None and state['name'] is None


def test_owner_reserves_without_changing_installation_identity(naming):
    store = naming.platforms[0]
    identity = store.load()
    files = {p.name: p.read_bytes() for p in store.home.iterdir()}
    receipt = naming.rename(naming.first, 'Pillar of Autumn')
    assert receipt['result'] == 'COMMITTED'
    assert receipt['actor_id'] == 'person:sparks'
    assert naming.authority.snapshot(naming.first)['display'] == 'Pillar of Autumn'
    assert store.load() == identity and files == {p.name:p.read_bytes() for p in store.home.iterdir()}
    assert 'UNSC' not in receipt['name']


@pytest.mark.parametrize('first,second', [('Pillar of Autumn','PILLAR OF AUTUMN'), ('Café Dawn','Cafe\u0301 Dawn'), ('Straße Dawn','STRASSE DAWN')])
def test_atomic_unique_normalized_names_and_conflict_receipt(naming, first, second):
    naming.rename(naming.first, first)
    receipt = naming.rename(naming.second, second)
    assert receipt['result'] == 'CONFLICT' and receipt['name'] is None
    assert naming.authority.snapshot(naming.second)['display'] == 'UNASSIGNED'
    assert naming.authority.history(naming.second)[-1] == receipt


@pytest.mark.parametrize('name', ['', ' ', ' a', 'a ', 'a  b', 'a\n', 'a\x00', 'a\u200b', 'a\u202e', 'a\ufe0f', '\ud800', '\u0301a', 'a \u0301', 'Ａutumn', 'Pillаr', 'ΑΡΚ', 'x'*81, 'UNASSIGNED'])
def test_invalid_ambiguous_names_are_rejected(name):
    with pytest.raises((ValueError, UnicodeError)):
        normalize_callsign(name)


def test_owner_original_name_allowed(naming):
    assert naming.rename(naming.first, "Sofía's Quiet Reckoning")['result'] == 'COMMITTED'


def test_sqlite_constraint_independently_rejects_duplicate_ownership(naming):
    naming.rename(naming.first, 'In Amber Clad')
    with closing(sqlite3.connect(naming.path)) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE callsign_platform SET name='In Amber Clad',normalized_name='in amber clad' WHERE platform_id=?", (naming.second,))


def _compete(path, home, platform, arguments, barrier, queue):
    authority = CallsignAuthority(path, InstallationIdentityStore(home))
    barrier.wait(timeout=30)
    try:
        queue.put(authority.owner_operation('rename', platform, **arguments)['result'])
    except CallsignRevisionConflict:
        queue.put('STALE')


@pytest.mark.parametrize('same_platform', [False, True])
def test_separate_processes_one_committed_winner(naming, same_platform):
    one = naming.prepare('rename', naming.first, {'name':'Spirit of Fire','override_lock':False})
    other_platform = naming.first if same_platform else naming.second
    two = naming.prepare('rename', other_platform, {'name':'Spirit of Fire','override_lock':False})
    context = multiprocessing.get_context('spawn')
    barrier, queue = context.Barrier(3), context.Queue()
    processes = [context.Process(target=_compete, args=(naming.path, naming.installation.home, p, a, barrier, queue))
                 for p,a in ((naming.first,one),(other_platform,two))]
    try:
        for process in processes: process.start()
        barrier.wait(timeout=30)
        results = [queue.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
        assert sorted(results) == ['COMMITTED','STALE']
        with sqlite3.connect(naming.path) as db:
            assert db.execute("SELECT count(*) FROM callsign_platform WHERE normalized_name='spirit of fire'").fetchone()[0] == 1
    finally:
        for process in processes:
            if process.is_alive(): process.terminate(); process.join()
        queue.close()


def test_stale_revision_and_approval_replay_denied(naming):
    arguments = naming.prepare('rename', naming.first, {'name':'Autumn','override_lock':False})
    naming.authority.owner_operation('rename', naming.first, **arguments)
    with pytest.raises(CallsignRevisionConflict):
        naming.authority.owner_operation('rename', naming.first, **arguments)
    with sqlite3.connect(naming.path) as db:
        assert db.execute('SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?', (arguments['approval_id'],)).fetchone()[0]
    arguments['expected_revision'] += 1
    arguments['request_id'] = str(uuid4())
    with pytest.raises(PermissionError):
        naming.authority.owner_operation('rename', naming.first, **arguments)


@pytest.mark.parametrize('actor', ['Sparks', 'person:sparks'])
def test_forged_owner_display_metadata_denied(naming, actor):
    with pytest.raises(PermissionError):
        naming.authority.owner_operation('rename', naming.first, expected_revision=naming.authority.snapshot(naming.first)['revision'],
            request_id=str(uuid4()), payload={'name':'Stolen Dawn','override_lock':False}, approval_id=actor)
    assert naming.authority.snapshot(naming.first)['name'] is None


def test_restart_history_and_historical_name_reassignment(naming):
    naming.rename(naming.first, 'Autumn')
    naming.rename(naming.first, 'Dawn')
    naming.rename(naming.second, 'Autumn')
    restarted = CallsignAuthority(naming.path, InstallationIdentityStore(naming.installation.home))
    assert restarted.snapshot(naming.first)['name'] == 'Dawn'
    assert restarted.snapshot(naming.second)['name'] == 'Autumn'
    assert [r['name'] for r in restarted.history(naming.first)] == [None, 'Autumn','Dawn']


def test_core_with_correct_grant_and_signature_succeeds(naming):
    _, key = naming.attach()
    grant = naming.grant()
    request = naming.request(grant)
    result = naming.authority.core_rename(request, key.sign(core_request_bytes(request)))
    assert result['result'] == 'COMMITTED' and result['grant_id'] == grant
    assert result['actor_id'] == 'core:'+request['core_id']
    assert naming.authority.snapshot(naming.first)['name'] == request['name']
    with pytest.raises(CallsignRevisionConflict):
        naming.authority.core_rename(request, key.sign(core_request_bytes(request)))
    request['expected_revision'] = naming.authority.snapshot(naming.first)['revision']
    with pytest.raises(PermissionError, match='spent'):
        naming.authority.core_rename(request, key.sign(core_request_bytes(request)))


@pytest.mark.parametrize('defect', ['no_grant','wrong_key','wrong_core','wrong_platform','generation','attachment','expired_request','authority'])
def test_core_authority_is_exact_and_cryptographic(naming, defect):
    _, key = naming.attach()
    grant = naming.grant()
    request = naming.request(grant)
    if defect == 'no_grant': request['grant_id'] = str(uuid4())
    elif defect == 'wrong_key': key = Ed25519PrivateKey.generate()
    elif defect == 'wrong_core': request['core_id'] = str(uuid4())
    elif defect == 'wrong_platform': request['platform_id'] = naming.second
    elif defect == 'generation': request['core_generation'] += 1
    elif defect == 'attachment': request['attachment_revision'] += 1
    elif defect == 'authority': request['authority_id'] = str(uuid4())
    elif defect == 'expired_request':
        request['issued_at'] = (datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat()
        request['expires_at'] = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    with pytest.raises(PermissionError):
        naming.authority.core_rename(request, key.sign(core_request_bytes(request)))
    assert naming.authority.snapshot(naming.first)['name'] is None


def test_lock_unlock_and_explicit_owner_override(naming):
    _, key = naming.attach()
    grant = naming.grant()
    naming.owner('lock', naming.first, {})
    request = naming.request(grant)
    with pytest.raises(PermissionError): naming.authority.core_rename(request, key.sign(core_request_bytes(request)))
    with pytest.raises(PermissionError): naming.rename(naming.first, 'Owner Dawn')
    assert naming.rename(naming.first, 'Owner Dawn', override=True)['result'] == 'COMMITTED'
    assert naming.authority.snapshot(naming.first)['locked']
    naming.owner('unlock', naming.first, {})
    request = naming.request(grant)
    assert naming.authority.core_rename(request, key.sign(core_request_bytes(request)))['result'] == 'COMMITTED'


@pytest.mark.parametrize('mode', ['revoked', 'expired', 'swapped', 'detached', 'wrong_platform_grant'])
def test_grants_do_not_survive_revocation_or_attachment_changes(naming, mode):
    _, key = naming.attach()
    grant = naming.grant()
    old_request = naming.request(grant)
    if mode == 'revoked': naming.owner('revoke', naming.first, {'grant_id':grant})
    elif mode == 'expired': naming.authority.clock = lambda: datetime.now(timezone.utc)+timedelta(hours=2)
    elif mode == 'swapped': naming.attach()
    elif mode == 'detached': naming.owner('detach', naming.first, {})
    else:
        core, _ = naming.attach(naming.second, core=old_request['core_id'], key=key)
        old_request['platform_id'] = naming.second
        state = naming.authority.snapshot(naming.second)
        old_request['attachment_revision'] = state['attachment_revision']
    old_request['expected_revision'] = naming.authority.snapshot(naming.first)['revision']
    with pytest.raises(PermissionError):
        naming.authority.core_rename(old_request, key.sign(core_request_bytes(old_request)))


def test_expired_grant_denied_with_fresh_signed_request(naming):
    _, key = naming.attach()
    grant = naming.grant(expires=datetime.now(timezone.utc)+timedelta(seconds=30))
    later = datetime.now(timezone.utc)+timedelta(seconds=45)
    naming.authority.clock = lambda:later
    request = naming.request(grant)
    request.update(issued_at=later.isoformat(), expires_at=(later+timedelta(minutes=1)).isoformat())
    with pytest.raises(PermissionError): naming.authority.core_rename(request, key.sign(core_request_bytes(request)))


def test_detach_reattach_same_core_does_not_revive_grant_or_change_name(naming):
    naming.rename(naming.first, 'Spirit of Fire')
    core, key = naming.attach()
    grant = naming.grant()
    naming.owner('detach', naming.first, {})
    naming.attach(core=core, key=key)
    request = naming.request(grant)
    with pytest.raises(PermissionError): naming.authority.core_rename(request, key.sign(core_request_bytes(request)))
    assert naming.authority.snapshot(naming.first)['name'] == 'Spirit of Fire'


def test_audit_failure_rolls_back_name_revision_and_owner_proof(naming, monkeypatch):
    naming.rename(naming.first, 'Autumn')
    before = naming.authority.snapshot(naming.first)
    arguments = naming.prepare('rename', naming.first, {'name':'Dawn','override_lock':False})
    append = AuditChain.append_in_transaction
    def fail(self, db, **kwargs):
        append(self, db, **kwargs)
        if kwargs['event_type'] == 'fleet.callsign.rename': raise sqlite3.OperationalError('injected database failure')
    with monkeypatch.context() as patch:
        patch.setattr(AuditChain, 'append_in_transaction', fail)
        with pytest.raises(sqlite3.OperationalError): naming.authority.owner_operation('rename', naming.first, **arguments)
    assert naming.authority.snapshot(naming.first) == before
    with sqlite3.connect(naming.path) as db:
        assert db.execute('SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?', (arguments['approval_id'],)).fetchone()[0] is None
    assert naming.authority.owner_operation('rename', naming.first, **arguments)['result'] == 'COMMITTED'


def test_commit_failure_preserves_reservation_and_recovers_uncommitted_intent(naming, monkeypatch):
    before = naming.authority.snapshot(naming.first)
    arguments = naming.prepare('rename', naming.first, {'name':'Dawn','override_lock':False})
    class FailedCommit(sqlite3.Connection):
        def commit(self): raise sqlite3.OperationalError('injected commit failure')
    connect = CanonicalSQLiteGuard.connect
    def failing_connect(self, **kwargs):
        return connect(self, **{**kwargs, 'factory':FailedCommit})
    with monkeypatch.context() as patch:
        patch.setattr(CanonicalSQLiteGuard, 'connect', failing_connect)
        with pytest.raises(sqlite3.OperationalError): naming.authority.owner_operation('rename', naming.first, **arguments)
    assert naming.authority.snapshot(naming.first) == before
    assert json.loads(naming.authority.witness_path.read_text())['pending'] is None


def test_postcommit_confirmation_failure_is_uncertain_and_reconciles_once(naming, monkeypatch):
    import sofia.platform.ops.callsigns as module
    arguments = naming.prepare('rename', naming.first, {'name':'Dawn','override_lock':False})
    write = module.atomic_write_private_text
    calls = 0
    def fail_after_commit(path, content):
        nonlocal calls
        calls += 1
        if calls == 2: raise OSError('confirmation interrupted')
        return write(path, content)
    with monkeypatch.context() as patch:
        patch.setattr(module, 'atomic_write_private_text', fail_after_commit)
        with pytest.raises(OSError): naming.authority.owner_operation('rename', naming.first, **arguments)
    restarted = CallsignAuthority(naming.path, naming.installation)
    assert restarted.snapshot(naming.first)['name'] == 'Dawn'
    assert len([r for r in restarted.history(naming.first) if r['request_id'] == arguments['request_id']]) == 1


def test_acknowledged_database_rollback_and_loss_are_refused(naming, tmp_path):
    backup = tmp_path/'older.db'
    with closing(sqlite3.connect(naming.path)) as db, closing(sqlite3.connect(backup)) as target: db.backup(target)
    naming.rename(naming.first, 'Autumn')
    with closing(sqlite3.connect(backup)) as db, closing(sqlite3.connect(naming.path)) as target: db.backup(target)
    with pytest.raises(CallsignUnavailable): CallsignAuthority(naming.path, naming.installation)
    naming.path.unlink()
    with pytest.raises((OSError, CallsignUnavailable)): CallsignAuthority(naming.path, naming.installation)
    assert not naming.path.exists()


def test_offline_display_preserves_verified_name_without_local_authority(naming):
    naming.rename(naming.first, 'Autumn')
    client = CallsignDisplayClient(naming.platforms[0], naming.authority.authority_id, connect=lambda:naming.authority)
    assert client.display()['display'] == 'Autumn'
    client = CallsignDisplayClient(naming.platforms[0], naming.authority.authority_id)
    assert client.display()['display'] == 'Autumn' and client.display()['status'] == 'CACHED'
    _, key = naming.attach()
    request = naming.request(naming.grant(), name='Offline Claim')
    assert client.core_rename(request, key.sign(core_request_bytes(request)))['result'] == 'UNCONFIRMED'
    assert naming.authority.snapshot(naming.first)['name'] == 'Autumn'


def test_history_hashes_and_audit_match_committed_operations(naming):
    naming.rename(naming.first, 'Autumn')
    naming.rename(naming.second, 'AUTUMN')
    assert AuditChain(naming.path).verify() == (True, None)
    with sqlite3.connect(naming.path) as db:
        receipts = db.execute('SELECT receipt_json FROM callsign_event ORDER BY revision').fetchall()
        audits = db.execute("SELECT payload_json FROM safe_audit_event WHERE event_type='fleet.callsign.rename'").fetchall()
    assert len(audits) == 2
    previous = '0'*64
    for (raw,) in receipts:
        receipt = json.loads(raw)
        expected = receipt.pop('event_hash')
        assert receipt['previous_hash'] == previous
        assert sha256(canonical_json(receipt).encode()).hexdigest() == expected
        previous = expected


def test_cli_reviews_exact_owner_action_and_applies_only_verified_proof(naming, capsys):
    from sofia.platform.ops.callsign_cli import main
    revision = naming.authority.snapshot(naming.first)['revision']
    request = str(uuid4())
    common = ['--database',str(naming.path),'--installation-home',str(naming.installation.home)]
    fields = ['--operation','rename','--platform-id',naming.first,'--expected-revision',str(revision),
        '--request-id',request,'--payload-json','{"name":"Quiet Reckoning","override_lock":false}']
    assert main(common+['review']+fields) == 0
    review = json.loads(capsys.readouterr().out)
    assert review['parameters']['platform_id'] == naming.first
    assert main(common+['apply']+fields+['--approval-id','Sparks']) == 2
    assert json.loads(capsys.readouterr().out)['result'] == 'DENIED'
    approval = _proof(naming.path, review['capability'], review['parameters'])
    assert main(common+['apply']+fields+['--approval-id',approval]) == 0
    assert json.loads(capsys.readouterr().out)['result'] == 'COMMITTED'
    assert main(common+['apply']+fields+['--approval-id',approval]) == 3
    assert json.loads(capsys.readouterr().out)['result'] == 'STALE'


@pytest.mark.parametrize('damage', ['reservation','history','version'])
def test_partial_state_or_history_corruption_fails_closed(naming, damage):
    naming.rename(naming.first, 'Autumn')
    with sqlite3.connect(naming.path) as db:
        if damage == 'reservation':
            db.execute("UPDATE callsign_platform SET name='Forged',normalized_name='forged' WHERE platform_id=?", (naming.first,))
        elif damage == 'history':
            db.execute("UPDATE callsign_event SET receipt_json=replace(receipt_json,'Autumn','Forged')")
        else:
            db.execute("UPDATE callsign_meta SET canonicalization='unknown'")
    with pytest.raises(CallsignUnavailable): CallsignAuthority(naming.path, naming.installation)


@pytest.mark.parametrize('operation', ['grant','revoke'])
def test_permission_mutation_failure_rolls_back_with_registry(naming, monkeypatch, operation):
    naming.attach()
    grant = naming.grant() if operation == 'revoke' else str(uuid4())
    payload = {'grant_id':grant}
    if operation == 'grant': payload['expires_at'] = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    arguments = naming.prepare(operation, naming.first, payload)
    before = naming.authority.snapshot(naming.first)
    append = AuditChain.append_in_transaction
    def fail(self, db, **kwargs):
        result = append(self, db, **kwargs)
        if kwargs['event_type'] == 'fleet.callsign.'+operation: raise sqlite3.OperationalError('publication failed')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(AuditChain, 'append_in_transaction', fail)
        with pytest.raises(sqlite3.OperationalError): naming.authority.owner_operation(operation, naming.first, **arguments)
    assert naming.authority.snapshot(naming.first) == before
    with sqlite3.connect(naming.path) as db:
        row = db.execute('SELECT revoked_at FROM safe_permission_grant WHERE grant_id=?', (grant,)).fetchone()
        assert row is None if operation == 'grant' else row[0] is None
        assert db.execute('SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?', (arguments['approval_id'],)).fetchone()[0] is None
    assert naming.authority.owner_operation(operation, naming.first, **arguments)['result'] == 'COMMITTED'


def test_owner_authenticator_revocation_invalidates_derived_core_permission(naming):
    _, key = naming.attach()
    grant = naming.grant()
    with sqlite3.connect(naming.path) as db:
        db.execute('UPDATE safe_owner_credential SET revoked_at=?', (datetime.now(timezone.utc).isoformat(),))
    request = naming.request(grant)
    with pytest.raises(PermissionError): naming.authority.core_rename(request, key.sign(core_request_bytes(request)))


def test_host_display_and_core_selection_do_not_define_callsign(naming, monkeypatch):
    naming.rename(naming.first, 'Autumn')
    identity = naming.platforms[0].load()
    monkeypatch.setenv('HOSTNAME', 'ChangedHost')
    monkeypatch.setenv('COMPUTERNAME', 'AnotherHost')
    monkeypatch.setenv('SOFIA_CORE_IDENTITY_ID', 'UnrelatedCore')
    naming.attach()
    naming.owner('detach', naming.first, {})
    assert naming.authority.snapshot(naming.first)['name'] == 'Autumn'
    assert naming.platforms[0].load() == identity


def test_naming_bootstrap_refuses_core_canonical_state_without_writes(tmp_path):
    installation = InstallationIdentityStore(tmp_path / 'private' / 'installation')
    installation.initialize()
    core_path = bootstrap_canonical_sqlite(tmp_path/'sofia.db')
    before = core_path.read_bytes()
    with pytest.raises(CallsignUnavailable):
        CallsignAuthority.initialize(core_path, installation, authority_id=str(uuid4()), approval_id='not-authorized')
    assert core_path.read_bytes() == before
    assert not (installation.home/'callsign-authority.json').exists()


@pytest.mark.parametrize('change', ['name','target','operation','revision'])
def test_real_owner_proof_is_bound_to_exact_operation_target_and_revision(naming, change):
    arguments = naming.prepare('rename', naming.first, {'name':'Reviewed Dawn','override_lock':False})
    platform, operation = naming.first, 'rename'
    if change == 'name': arguments['payload'] = {'name':'Unreviewed Dawn','override_lock':False}
    elif change == 'target': platform = naming.second
    elif change == 'operation': operation, arguments['payload'] = 'lock', {}
    else: arguments['expected_revision'] += 1
    with pytest.raises((PermissionError, CallsignRevisionConflict)):
        naming.authority.owner_operation(operation, platform, **arguments)
    assert naming.authority.snapshot(naming.first)['name'] is None
    with sqlite3.connect(naming.path) as db:
        assert db.execute('SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?', (arguments['approval_id'],)).fetchone()[0] is None


def test_core_cannot_create_own_naming_grant(naming):
    core, _ = naming.attach()
    with pytest.raises(PermissionError):
        naming.authority.owner_operation('grant', naming.first,
            expected_revision=naming.authority.snapshot(naming.first)['revision'], request_id=str(uuid4()),
            payload={'grant_id':str(uuid4()),'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},
            approval_id=core)
    assert naming.authority.permissions.grants() == ()
