"""Local designated Fleet naming authority, independent of any Core.

A SQLite transaction owns reservations, SAFE permissions and audit. An
installation-private revision witness detects acknowledged database rollback.
No network enrollment or remote transport is provided by this module.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import time
import unicodedata
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.sdk.identity import AegisIdentity, IdentityKind
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.state.local_store import PlatformLocalStore, LocalStateUnavailable, LOCAL_STATE_APPLICATION_ID
from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier, OWNER_PRINCIPAL_ID
from sofia.platform.safe.permissions import PermissionStore, standing_grant_parameters
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.platform.state.installation_identity import InstallationIdentityStore, InstallationIdentityUnavailable
from sofia.platform.state.private_file import atomic_write_private_text

SCHEMA = 'aegis.fleet.callsigns.v1'
CANONICALIZATION = 'nfc-nfkc-casefold-latin-v1:ucd-' + unicodedata.unidata_version
CORE_CAPABILITY = 'fleet.callsign.core.rename'
GENESIS = '0' * 64
_DOMAIN = b'aegis.fleet.callsign.request.v1\x00'
_OPERATIONS = frozenset({'register', 'rename', 'lock', 'unlock', 'attach', 'detach', 'grant', 'revoke'})


class CallsignUnavailable(RuntimeError):
    """No current authoritative result can be confirmed."""


class CallsignRevisionConflict(RuntimeError):
    pass


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _uuid(value):
    identity = AegisIdentity.from_uuid_text(IdentityKind.PLATFORM, value)
    if identity.identity_id.int == 0:
        raise ValueError('null identity is not allowed')
    return identity.canonical_uuid


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('invalid revision or generation')
    return value


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('aware UTC timestamp required')
    return value.astimezone(timezone.utc)


def normalize_callsign(value):
    """NFC display; NFKC/casefold/NFKC uniqueness key, Unicode 14+ categories.

    Permit Latin letters, attached marks, ASCII digits/spaces and ship-name
    punctuation. Reject compatibility presentation, mixed-script confusables,
    combining-only words and non-ASCII punctuation/separators. No name list.
    """
    if not isinstance(value, str) or not 1 <= len(value) <= 80:
        raise ValueError('callsign must contain 1..80 Unicode code points')
    value.encode('utf-8', errors='strict')
    display = unicodedata.normalize('NFC', value)
    if display != display.strip(' ') or '  ' in display or not display.strip(' '):
        raise ValueError('ambiguous callsign spacing')
    letters = []
    preceding_letter = False
    marks = 0
    for character in display:
        category = unicodedata.category(character)
        if category[0] in {'L', 'N'}:
            if category[0] == 'L' and not unicodedata.name(character, '').startswith('LATIN '):
                raise ValueError('callsign letters must use the unambiguous Latin display alphabet')
            if category[0] == 'N' and character not in '0123456789':
                raise ValueError('ambiguous numeric presentation')
            letters.append(character)
            preceding_letter = category[0] == 'L'
            marks = 0
        elif category[0] == 'M':
            marks += 1
            if not preceding_letter or not unicodedata.combining(character) or marks > 2:
                raise ValueError('unattached, invisible or excessive combining mark')
        elif character not in " '-.,:&()":
            raise ValueError('invisible, control or unsupported callsign character')
        else:
            preceding_letter = False
            marks = 0
    if not letters or len(display.encode('utf-8')) > 240:
        raise ValueError('callsign requires visible letters/numbers within 240 bytes')
    # Reject formatting compatibility glyphs (full-width/mathematical/ligatures)
    # rather than presenting a different visible spelling for the same name.
    if unicodedata.normalize('NFKC', display) != display:
        raise ValueError('ambiguous compatibility presentation')
    scripts = {unicodedata.name(c, '').split(' ')[0] for c in letters if unicodedata.category(c).startswith('L')}
    if len(scripts & {'LATIN', 'GREEK', 'CYRILLIC'}) > 1:
        raise ValueError('ambiguous mixed-script callsign')
    key = unicodedata.normalize('NFKC', unicodedata.normalize('NFKC', display).casefold())
    if key == 'unassigned':
        raise ValueError('UNASSIGNED is a state, not a reservable name')
    return display, key


def core_request_bytes(request):
    """Public signing contract. Constructing it does not authenticate a Core."""
    fields = {'schema', 'authority_id', 'platform_id', 'core_id', 'core_generation',
              'attachment_revision', 'grant_id', 'expected_revision', 'request_id',
              'name', 'issued_at', 'expires_at'}
    if type(request) is not dict or set(request) != fields or request['schema'] != SCHEMA:
        raise ValueError('unsupported Core naming request')
    for name in ('authority_id', 'platform_id', 'core_id', 'request_id', 'grant_id'):
        if _uuid(request[name]) != request[name]:
            raise ValueError('canonical UUID required')
    for name in ('core_generation', 'attachment_revision'):
        _integer(request[name], 1)
    _integer(request['expected_revision'])
    normalize_callsign(request['name'])
    start, end = (_utc(datetime.fromisoformat(request[name])) for name in ('issued_at', 'expires_at'))
    if not timedelta(0) < end-start <= timedelta(minutes=5):
        raise ValueError('Core request lifetime must be positive and at most five minutes')
    encoded = canonical_json(request).encode('utf-8')
    if len(encoded) > 4096:
        raise ValueError('Core naming request is too large')
    return _DOMAIN + encoded


def _publish_witness(installation, path, value):
    """Durable secure rename, retaining the shared private-file implementation."""
    staging = path.with_name(path.name + '.next')
    installation._private(path.parent, directory=True)
    if path.exists() or path.is_symlink():
        installation._private(path, directory=False)
    atomic_write_private_text(staging, canonical_json(value))
    installation._private(staging, directory=False)
    if os.name == 'nt':
        import win32file
        import win32con
        win32file.MoveFileEx(str(staging), str(path),
            win32con.MOVEFILE_REPLACE_EXISTING | win32con.MOVEFILE_WRITE_THROUGH)
    else:
        os.replace(staging, path)
        descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    installation._private(path, directory=False)


def _existing_local_store(path, installation):
    try:
        installation._private(Path(path).absolute().parent, directory=True)
        installation._private(Path(path).absolute(), directory=False)
        store = PlatformLocalStore(path, roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
            host_identity=installation.load().identity.canonical_uuid, create=False)
        if store.binding.core_identity is not None:
            raise CallsignUnavailable('naming authority cannot use a Core-bound state file')
        return store
    except (LocalStateUnavailable, InstallationIdentityUnavailable, OSError) as exc:
        raise CallsignUnavailable('authority requires existing independent Platform-local state') from exc


class CallsignAuthority:
    """Open a designated local authority; ordinary open never bootstraps state.

    The installation is the authority host from PR #192. Target Platforms and
    attached Cores have their own distinct UUIDs. Attachments here are the
    authoritative naming bindings, not an implicit Core Link enrollment.
    """

    def __init__(self, path: Path, installation: InstallationIdentityStore, *, clock=None):
        self.path = Path(path).absolute()
        self.installation = installation
        self.host = installation.load()
        self.storage = _existing_local_store(self.path, installation)
        self.witness_path = installation.home / 'callsign-authority.json'
        self.guard = CanonicalSQLiteGuard(self.path)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with self._locked(), closing(self.guard.connect()) as db:
            db.row_factory = sqlite3.Row
            self._reconcile(db)
        # The schema check above refuses lost authority or authorization tables
        # before generic SAFE stores can initialize their shared schemas.
        self.approvals = ExecutionApprovalVerifier(self.path)
        self.permissions = PermissionStore(self.path)
        self.audit = AuditChain(self.path)

    @staticmethod
    def initialize_parameters(path, installation, authority_id):
        _existing_local_store(path, installation)
        return {'schema': SCHEMA, 'canonicalization': CANONICALIZATION, 'operation': 'initialize', 'authority_id': _uuid(authority_id),
                'authority_platform_id': installation.load().identity.canonical_uuid,
                'database_path': str(Path(path).absolute()), 'expected_revision': 0}

    @classmethod
    def initialize(cls, path, installation, *, authority_id, approval_id):
        parameters = cls.initialize_parameters(path, installation, authority_id)
        guard = CanonicalSQLiteGuard(path)
        verifier = ExecutionApprovalVerifier(path)
        PermissionStore(path)
        witness_path = installation.home / 'callsign-authority.json'
        with StateProcessLock(path, resource='fleet-callsign'), closing(guard.connect()) as db, db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN IMMEDIATE')
            if witness_path.exists() or witness_path.is_symlink() or db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='callsign_meta'"
            ).fetchone():
                raise CallsignUnavailable('authority already established or bootstrap interrupted')
            now = datetime.now(timezone.utc)
            verified = verifier.consume(approval_id=approval_id, capability='fleet.callsign.authority.initialize',
                parameters=parameters, now=now, _transaction_db=db)
            definitions = [
                'CREATE TABLE callsign_meta (singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema TEXT NOT NULL, canonicalization TEXT NOT NULL, authority_id TEXT NOT NULL, authority_platform_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=0), head_hash TEXT NOT NULL, last_time TEXT NOT NULL)',
                'CREATE TABLE callsign_platform (platform_id TEXT PRIMARY KEY, public_key_sha256 TEXT NOT NULL UNIQUE, name TEXT, normalized_name TEXT UNIQUE, locked INTEGER NOT NULL DEFAULT 0 CHECK(locked IN (0,1)), core_id TEXT, core_generation INTEGER, core_public_key_der BLOB, attachment_revision INTEGER NOT NULL DEFAULT 0, CHECK((name IS NULL)=(normalized_name IS NULL)))',
                'CREATE TABLE callsign_grant (grant_id TEXT PRIMARY KEY, platform_id TEXT NOT NULL REFERENCES callsign_platform(platform_id), scope_json TEXT NOT NULL, issued_revision INTEGER NOT NULL)',
                'CREATE TABLE callsign_event (revision INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, platform_id TEXT NOT NULL, actor_id TEXT NOT NULL, grant_id TEXT, operation TEXT NOT NULL, occurred_at TEXT NOT NULL, previous_name TEXT, new_name TEXT, result TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE, receipt_json TEXT NOT NULL)',
            ]
            for statement in definitions:
                db.execute(statement)
            db.execute('INSERT INTO callsign_meta VALUES (1,?,?,?,?,?,?,?)',
                (SCHEMA, CANONICALIZATION, parameters['authority_id'], parameters['authority_platform_id'], 0, GENESIS, now.isoformat()))
            verifier.audit.append_in_transaction(db, actor_id=verified.principal_id,
                event_type='fleet.callsign.authority.initialized', payload=parameters, occurred_at=now)
            witness = {**parameters, 'installation_key_sha256': installation.load().public_key_sha256,
                       'revision': 0, 'head_hash': GENESIS, 'last_time': now.isoformat(), 'pending': None}
            # A partial bootstrap is retained and refused, never auto-recreated.
            _publish_witness(installation, witness_path, witness)
        return cls(path, installation)

    @contextmanager
    def _locked(self):
        lock = StateProcessLock(self.path, resource='fleet-callsign')
        deadline = time.monotonic() + 10
        while True:
            try:
                lock.acquire()
                break
            except RuntimeError as exc:
                if time.monotonic() >= deadline:
                    raise CallsignUnavailable('authority is busy; no operation confirmed') from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            lock.release()

    def _witness(self):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate authority witness field')
                result[key] = value
            return result
        self.installation.load()
        raw = json.loads(self.installation._read(self.witness_path, 8192), object_pairs_hook=unique)
        expected = {'schema', 'canonicalization', 'operation', 'authority_id', 'authority_platform_id', 'database_path',
                    'expected_revision', 'installation_key_sha256', 'revision', 'head_hash', 'last_time', 'pending'}
        if type(raw) is not dict or set(raw) != expected or raw['schema'] != SCHEMA or raw['operation'] != 'initialize':
            raise CallsignUnavailable('unknown authority witness')
        if (raw['authority_platform_id'] != self.host.identity.canonical_uuid or
            raw['installation_key_sha256'] != self.host.public_key_sha256 or raw['database_path'] != str(self.path)):
            raise CallsignUnavailable('authority host/path binding differs')
        if raw['canonicalization'] != CANONICALIZATION or type(raw['expected_revision']) is not int or raw['expected_revision'] != 0:
            raise CallsignUnavailable('canonicalization policy requires explicit migration')
        _uuid(raw['authority_id']); _integer(raw['revision'])
        states = [{k: raw[k] for k in ('revision', 'head_hash', 'last_time')}]
        if raw['pending'] is not None:
            states.append(raw['pending'])
        for state in states:
            if type(state) is not dict or set(state) != {'revision', 'head_hash', 'last_time'}:
                raise CallsignUnavailable('invalid authority intent')
            _integer(state['revision'])
            head = state['head_hash']
            if not isinstance(head, str) or len(head) != 64 or any(c not in '0123456789abcdef' for c in head):
                raise CallsignUnavailable('invalid authority history hash')
            _utc(datetime.fromisoformat(state['last_time']))
        if raw['pending'] is not None and raw['pending']['revision'] != raw['revision']+1:
            raise CallsignUnavailable('invalid authority intent revision')
        return raw

    def _reconcile(self, db):
        try:
            witness = self._witness()
            binding = db.execute('SELECT host_identity,roles_json,core_identity FROM platform_local_host_binding WHERE singleton=1').fetchone()
            if (db.execute('PRAGMA application_id').fetchone()[0] != LOCAL_STATE_APPLICATION_ID or
                binding is None or binding[0] != self.host.identity.canonical_uuid or
                json.loads(binding[1]) != ['MODULE_HOST'] or binding[2] is not None):
                raise CallsignUnavailable('authority Platform-local storage binding differs')
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required = {'platform_local_host_binding', 'callsign_meta', 'callsign_platform', 'callsign_grant', 'callsign_event',
                        'safe_audit_event', 'safe_permission_grant', 'safe_permission_owner_auth_binding',
                        'safe_execution_approval', 'safe_execution_owner_auth_binding'}
            if not required <= tables:
                raise CallsignUnavailable('authority schema is incomplete; approved recovery required')
            meta = dict(db.execute('SELECT * FROM callsign_meta WHERE singleton=1').fetchone())
            if meta['schema'] != SCHEMA or meta['canonicalization'] != CANONICALIZATION or meta['authority_id'] != witness['authority_id'] or meta['authority_platform_id'] != witness['authority_platform_id']:
                raise CallsignUnavailable('authority identity/schema differs')
            current = {key: meta[key] for key in ('revision', 'head_hash', 'last_time')}
            committed = {key: witness[key] for key in current}
            had_pending = witness['pending'] is not None
            if had_pending:
                # An interrupted commit has exactly two legitimate outcomes.
                # No result was acknowledged while this intent was pending.
                if current not in (committed, witness['pending']):
                    raise CallsignUnavailable('authority intent differs from durable state')
                witness.update(current, pending=None)
            elif current != committed:
                raise CallsignUnavailable('authority rollback/replacement detected')
            previous = GENESIS
            last_receipt = None
            for index, row in enumerate(db.execute('SELECT * FROM callsign_event ORDER BY revision'), 1):
                receipt = json.loads(row['receipt_json'])
                if (row['revision'] != index or receipt.get('revision') != index or
                    receipt.get('previous_hash') != previous or row['previous_hash'] != previous):
                    raise CallsignUnavailable('authority history sequence differs')
                head = receipt.pop('event_hash')
                if sha256(canonical_json(receipt).encode('utf-8')).hexdigest() != head or row['event_hash'] != head:
                    raise CallsignUnavailable('authority history receipt differs')
                for key in ('request_id', 'platform_id', 'actor_id', 'grant_id', 'operation', 'occurred_at', 'result'):
                    if row[key] != receipt[key]:
                        raise CallsignUnavailable('authority history index differs')
                if row['previous_name'] != receipt['previous_name'] or row['new_name'] != receipt['name']:
                    raise CallsignUnavailable('authority history ownership differs')
                previous, last_receipt = head, receipt
            if meta['head_hash'] != previous or meta['revision'] != (0 if last_receipt is None else last_receipt['revision']):
                raise CallsignUnavailable('authority history differs from its head')
            if last_receipt is None:
                if db.execute('SELECT count(*) FROM callsign_platform').fetchone()[0] or db.execute('SELECT count(*) FROM callsign_grant').fetchone()[0]:
                    raise CallsignUnavailable('authority bootstrap contains unexplained ownership')
            elif last_receipt['state_sha256'] != self._state_hash(db) or last_receipt['occurred_at'] != meta['last_time']:
                raise CallsignUnavailable('authority state differs from acknowledged history')
            if had_pending:
                _publish_witness(self.installation, self.witness_path, witness)
            self.authority_id = meta['authority_id']
            return meta, witness
        except CallsignUnavailable:
            raise
        except Exception as exc:
            raise CallsignUnavailable('authority unavailable; no automatic recovery') from exc

    @staticmethod
    def _state_hash(db):
        state = {}
        for table, key in (('callsign_platform', 'platform_id'), ('callsign_grant', 'grant_id')):
            rows = []
            for row in db.execute(f'SELECT * FROM {table} ORDER BY {key}'):
                rows.append({name: (b64encode(value).decode('ascii') if isinstance(value, bytes) else value)
                             for name, value in dict(row).items()})
            state[table] = rows
        return sha256(canonical_json(state).encode('utf-8')).hexdigest()

    def _now(self, meta):
        now = _utc(self.clock())
        if now < _utc(datetime.fromisoformat(meta['last_time'])):
            raise CallsignUnavailable('authority host clock moved backwards')
        return now

    @staticmethod
    def _target(db, platform_id):
        row = db.execute('SELECT * FROM callsign_platform WHERE platform_id=?', (platform_id,)).fetchone()
        if row is None:
            raise PermissionError('Platform is not registered with this naming authority')
        return row

    def _context(self, operation, platform_id, expected_revision, request_id, payload):
        if operation not in _OPERATIONS or type(payload) is not dict:
            raise ValueError('unsupported naming operation')
        if len(canonical_json(payload).encode('utf-8')) > 16_384:
            raise ValueError('naming payload exceeds 16-KiB bound')
        return {'schema': SCHEMA, 'authority_id': self.authority_id, 'operation': operation,
                'platform_id': _uuid(platform_id), 'expected_revision': _integer(expected_revision),
                'request_id': _uuid(request_id), 'payload': json.loads(canonical_json(payload))}

    def _grant_scope(self, db, context):
        target = self._target(db, context['platform_id'])
        if target['core_id'] is None:
            raise PermissionError('naming grant requires a current attachment')
        return {**context, 'core_id': target['core_id'], 'core_generation': target['core_generation'],
                'attachment_revision': target['attachment_revision'], 'action': 'rename'}

    def approval_parameters(self, operation, platform_id, *, expected_revision, request_id, payload):
        """Inert exact review document; it supplies no authority or credentials."""
        context = self._context(operation, platform_id, expected_revision, request_id, payload)
        with self._locked(), closing(self.guard.connect()) as db:
            db.row_factory = sqlite3.Row
            meta, _ = self._reconcile(db)
            if meta['revision'] != expected_revision:
                raise CallsignRevisionConflict('stale naming revision')
            if operation == 'grant':
                scope = self._grant_scope(db, context)
                expires = _utc(datetime.fromisoformat(payload['expires_at']))
                return 'safe.permission.standing.grant', standing_grant_parameters(CORE_CAPABILITY,
                    scope=scope, grant_id=_uuid(payload['grant_id']), expires_at=expires)
            if operation == 'revoke':
                return 'safe.permission.standing.revoke', {'grant_id': _uuid(payload['grant_id']), 'authority_context': context}
        return 'fleet.callsign.' + operation, context

    def _core_authorization(self, db, request, signature, now):
        encoded = core_request_bytes(request)
        if request['authority_id'] != self.authority_id:
            raise PermissionError('wrong naming authority')
        start, end = (_utc(datetime.fromisoformat(request[k])) for k in ('issued_at', 'expires_at'))
        if not start <= now < end:
            raise PermissionError('Core naming request expired or not active')
        target = self._target(db, request['platform_id'])
        if target['locked'] or any(target[k] != request[k] for k in ('core_id', 'core_generation', 'attachment_revision')):
            raise PermissionError('owner lock or Core attachment fence denies naming')
        try:
            key = serialization.load_der_public_key(target['core_public_key_der'])
            if not isinstance(key, Ed25519PublicKey) or not isinstance(signature, bytes) or len(signature) != 64:
                raise ValueError('Ed25519 Core proof required')
            key.verify(signature, encoded)
        except Exception as exc:
            raise PermissionError('Core naming signature is invalid') from exc
        link = db.execute('SELECT * FROM callsign_grant WHERE grant_id=? AND platform_id=?',
                          (request['grant_id'], request['platform_id'])).fetchone()
        if link is None:
            raise PermissionError('no registry-issued naming grant')
        scope = json.loads(link['scope_json'])
        actual_scope = {**scope, **{k: request[k] for k in ('authority_id', 'platform_id', 'core_id', 'core_generation', 'attachment_revision')}}
        grants = self.permissions.grants(_transaction_db=db)
        if not any(g.grant_id == request['grant_id'] and g.capability == CORE_CAPABILITY and
                   g.scope == scope and g.matches(actual_scope, now=now) for g in grants):
            raise PermissionError('naming grant is expired, revoked or unauthenticated')
        return target, 'core:' + request['core_id']

    def _change_name(self, db, platform_id, name):
        display, normalized = normalize_callsign(name)
        try:
            db.execute('UPDATE callsign_platform SET name=?,normalized_name=? WHERE platform_id=?',
                       (display, normalized, platform_id))
            return 'COMMITTED', display
        except sqlite3.IntegrityError as exc:
            # Only an actual normalized-name uniqueness collision is a conflict.
            # Other integrity/database failures roll back the entire request.
            if exc.sqlite_errorcode != sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                raise
            owner = db.execute('SELECT platform_id FROM callsign_platform WHERE normalized_name=?', (normalized,)).fetchone()
            if owner is None or owner[0] == platform_id:
                raise
            return 'CONFLICT', self._target(db, platform_id)['name']

    def _owner_change(self, db, context, approval_id, now):
        operation, payload, platform_id = context['operation'], context['payload'], context['platform_id']
        if operation == 'grant':
            if set(payload) != {'grant_id', 'expires_at'}:
                raise ValueError('grant requires exactly grant_id and expires_at')
            scope = self._grant_scope(db, context)
            expires = _utc(datetime.fromisoformat(payload['expires_at']))
            grant = self.permissions.grant(CORE_CAPABILITY, scope=scope, grant_id=_uuid(payload['grant_id']),
                expires_at=expires, approval_id=approval_id, now=now, _transaction_db=db)
            db.execute('INSERT INTO callsign_grant VALUES(?,?,?,?)',
                (grant.grant_id, platform_id, canonical_json(scope), context['expected_revision']+1))
            return grant.granted_by, grant.grant_id, 'COMMITTED'
        if operation == 'revoke':
            if set(payload) != {'grant_id'}:
                raise ValueError('revocation requires exactly grant_id')
            grant_id = _uuid(payload['grant_id'])
            if db.execute('SELECT 1 FROM callsign_grant WHERE grant_id=? AND platform_id=?', (grant_id, platform_id)).fetchone() is None:
                raise PermissionError('grant belongs to another Platform')
            self.permissions.revoke(grant_id, approval_id=approval_id, now=now,
                authority_context=context, _transaction_db=db)
            return OWNER_PRINCIPAL_ID, grant_id, 'COMMITTED'
        verified = self.approvals.consume(approval_id=approval_id, capability='fleet.callsign.'+operation,
            parameters=context, now=now, _transaction_db=db)
        if operation == 'register':
            if set(payload) != {'identity', 'public_key_sha256'}:
                raise ValueError('registration requires the existing installation identity')
            identity = AegisIdentity.from_payload(payload['identity'])
            if identity.kind is not IdentityKind.PLATFORM or identity.canonical_uuid != platform_id:
                raise PermissionError('Platform identity differs')
            pin = payload['public_key_sha256']
            if not isinstance(pin, str) or len(pin) != 64 or any(c not in '0123456789abcdef' for c in pin):
                raise ValueError('invalid installation key fingerprint')
            try:
                db.execute('INSERT INTO callsign_platform(platform_id,public_key_sha256) VALUES(?,?)', (platform_id, pin))
            except sqlite3.IntegrityError as exc:
                raise PermissionError('Platform UUID/key binding already exists and cannot be replaced') from exc
        else:
            target = self._target(db, platform_id)
            if operation == 'rename':
                if set(payload) != {'name', 'override_lock'} or type(payload['override_lock']) is not bool:
                    raise ValueError('rename requires a name and explicit boolean lock override')
                if target['locked'] and not payload['override_lock']:
                    raise PermissionError('owner must explicitly approve lock override')
                result, _ = self._change_name(db, platform_id, payload['name'])
                return verified.principal_id, None, result
            elif operation in {'lock', 'unlock', 'detach'}:
                if payload:
                    raise ValueError('operation requires empty payload')
                if operation == 'detach':
                    db.execute('UPDATE callsign_platform SET core_id=NULL,core_generation=NULL,core_public_key_der=NULL,attachment_revision=attachment_revision+1 WHERE platform_id=?', (platform_id,))
                else:
                    db.execute('UPDATE callsign_platform SET locked=? WHERE platform_id=?', (int(operation == 'lock'), platform_id))
            elif operation == 'attach':
                if set(payload) != {'core_identity', 'generation', 'public_key_der'}:
                    raise ValueError('attachment requires exact Core identity, generation and public key')
                core = AegisIdentity.from_payload(payload['core_identity'])
                if core.kind is not IdentityKind.CORE or core.identity_id.int == 0:
                    raise ValueError('non-null Core identity required')
                generation = _integer(payload['generation'], 1)
                raw_key = b64decode(payload['public_key_der'], validate=True)
                if len(raw_key) != 44 or not isinstance(serialization.load_der_public_key(raw_key), Ed25519PublicKey):
                    raise ValueError('Ed25519 Core public key required')
                db.execute('UPDATE callsign_platform SET core_id=?,core_generation=?,core_public_key_der=?,attachment_revision=attachment_revision+1 WHERE platform_id=?',
                    (core.canonical_uuid, generation, raw_key, platform_id))
        return verified.principal_id, None, 'COMMITTED'

    def owner_operation(self, operation, platform_id, *, expected_revision, request_id, payload, approval_id):
        if not isinstance(approval_id, str) or not 1 <= len(approval_id) <= 160:
            raise ValueError('bounded owner approval reference required')
        context = self._context(operation, platform_id, expected_revision, request_id, payload)
        return self._execute(context, approval_id=approval_id)

    def core_rename(self, request, signature):
        core_request_bytes(request)
        context = self._context('rename', request['platform_id'], request['expected_revision'],
            request['request_id'], {'name': request['name'], 'override_lock': False})
        return self._execute(context, core_request=request, signature=signature)

    def _execute(self, context, *, approval_id=None, core_request=None, signature=None):
        with self._locked(), closing(self.guard.connect()) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            try:
                meta, witness = self._reconcile(db)
                if meta['revision'] != context['expected_revision']:
                    raise CallsignRevisionConflict('stale registry revision; old reservation preserved')
                if db.execute('SELECT 1 FROM callsign_event WHERE request_id=?', (context['request_id'],)).fetchone():
                    raise PermissionError('naming request already spent')
                now = self._now(meta)
                before = db.execute('SELECT name FROM callsign_platform WHERE platform_id=?', (context['platform_id'],)).fetchone()
                if core_request is not None:
                    _, actor = self._core_authorization(db, core_request, signature, now)
                    grant_id = core_request['grant_id']
                    result, _ = self._change_name(db, context['platform_id'], core_request['name'])
                else:
                    actor, grant_id, result = self._owner_change(db, context, approval_id, now)
                current = self._target(db, context['platform_id'])
                now = self._now(meta)
                if core_request is not None:
                    self._core_authorization(db, core_request, signature, now)
                else:
                    proof = db.execute('SELECT approved_at,expires_at FROM safe_execution_approval WHERE approval_id=?', (approval_id,)).fetchone()
                    if proof is None or not _utc(datetime.fromisoformat(proof[0])) <= now < _utc(datetime.fromisoformat(proof[1])):
                        raise PermissionError('owner approval expired before naming publication')
                revision = meta['revision']+1
                receipt = {'schema': SCHEMA, 'authority_id': self.authority_id, 'revision': revision,
                    'request_id': context['request_id'], 'platform_id': context['platform_id'],
                    'operation': context['operation'], 'actor_id': actor, 'grant_id': grant_id,
                    'owner_approval_id': None if core_request is not None else approval_id,
                    'previous_name': None if before is None else before[0], 'name': current['name'],
                    'result': result, 'occurred_at': now.isoformat(), 'parameters': context,
                    'previous_hash': meta['head_hash'], 'state_sha256': self._state_hash(db)}
                head = sha256(canonical_json(receipt).encode('utf-8')).hexdigest()
                receipt['event_hash'] = head
                db.execute('INSERT INTO callsign_event VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (revision, context['request_id'], context['platform_id'], actor, grant_id, context['operation'],
                     now.isoformat(), receipt['previous_name'], receipt['name'], result, meta['head_hash'], head, canonical_json(receipt)))
                self.audit.append_in_transaction(db, actor_id=actor, event_type='fleet.callsign.'+context['operation'],
                    payload=receipt, occurred_at=now, event_id='callsign:'+context['request_id'])
                changed = db.execute('UPDATE callsign_meta SET revision=?,head_hash=?,last_time=? WHERE singleton=1 AND revision=?',
                    (revision, head, now.isoformat(), meta['revision']))
                if changed.rowcount != 1:
                    raise CallsignRevisionConflict('registry compare-and-swap failed')
                next_state = {'revision': revision, 'head_hash': head, 'last_time': now.isoformat()}
                # Publish a bounded intent before SQLite commit, then confirm it.
                # All reads/writes share this cross-process witness lock.
                witness['pending'] = next_state
                _publish_witness(self.installation, self.witness_path, witness)
                db.commit()
                witness.update(next_state, pending=None)
                _publish_witness(self.installation, self.witness_path, witness)
                self.guard.validate()
                return receipt  # only after DB + witness are durably published
            except BaseException:
                db.rollback()
                raise

    def snapshot(self, platform_id):
        platform_id = _uuid(platform_id)
        with self._locked(), closing(self.guard.connect()) as db:
            db.row_factory = sqlite3.Row
            meta, _ = self._reconcile(db)
            row = db.execute('SELECT * FROM callsign_platform WHERE platform_id=?', (platform_id,)).fetchone()
            return {'schema': SCHEMA, 'authority_id': self.authority_id, 'platform_id': platform_id,
                'revision': meta['revision'], 'name': None if row is None else row['name'],
                'display': 'UNASSIGNED' if row is None or row['name'] is None else row['name'],
                'registered': row is not None, 'locked': False if row is None else bool(row['locked']),
                'core_id': None if row is None else row['core_id'],
                'core_generation': None if row is None else row['core_generation'],
                'attachment_revision': 0 if row is None else row['attachment_revision'], 'status': 'VERIFIED'}

    def history(self, platform_id):
        with self._locked(), closing(self.guard.connect()) as db:
            db.row_factory = sqlite3.Row
            self._reconcile(db)
            return tuple(json.loads(r[0]) for r in db.execute('SELECT receipt_json FROM callsign_event WHERE platform_id=? ORDER BY revision', (_uuid(platform_id),)))
