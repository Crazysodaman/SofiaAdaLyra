"""Governed installed Platform release lifecycle: select, install, activate.

STAGE already happened in platform_release_staging: it copies verified bytes
into a fresh private candidate tree and never selects, installs or activates.
This module consumes such a staged candidate and provides:

* select:   independently re-verify a staged candidate (signature, digests,
            wheel dependency inventory and the requested revision floor)
            before anything is installed.
* install:  journal a crash-safe attempt, publish independently re-verified
            bytes into an isolated owner-private target, record a durable
            installation receipt and advance the durable anti-rollback
            checkpoint. Activation is deliberately out of scope here and a
            fresh partial failure never touches the destination.
* activate: require a fresh, exact, single-use owner approval plus operator
            STOP fencing, then start the real local service adapter, verify
            real service health and record a durable activation receipt.

The canonical Core state file (sofia.db) stays owned by its existing
authorities: activation consumes approvals only through the existing
ExecutionApprovalVerifier on the canonical state path. Installation and
activation receipts live in a platform-owned SQLite store plus owner-private
JSON receipts. No second canonical writer is created and no Core, LLM or
GPU is required.
"""
from __future__ import annotations

from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from queue import Empty, Queue
from threading import Thread
from uuid import uuid4

from sofia.platform.ops.platform_release import PlatformReleaseRejected, PlatformReleaseVerifier
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier, execution_fingerprint
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
    ensure_owner_private_directory, restrict_new_owner_private_path,
)
from sofia.platform.verify.python_runtime import materialize_python_runtime
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget

INSTALLATION_SCHEMA = 'aegis.platform.installation.v1'
STAGE_SCHEMA = 'aegis.platform.code-stage.v1'
ACTIVATION_SCHEMA = 'aegis.platform.code-activation.v1'
SERVICE_SCHEMA = 'aegis.platform.service-control.v1'
ACTIVATION_CAPABILITY = 'platform.activate_release'
ROLLBACK_CAPABILITY = 'platform.rollback_release'
INSTALL = 'install'
ROLLBACK = 'rollback'
SUCCEEDED = 'SUCCEEDED'
_FAILED = 'FAILED'


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _decode_private_json(path: Path):
    size = path.stat(follow_symlinks=False).st_size
    return loads_strict_model_json(
        read_artifact_file(path, size, include_data=True)[1].decode('utf-8'))


def _write_new(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    assert_no_redirected_components(path, include_leaf=True)
    descriptor = os.open(path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        restrict_new_owner_private_path(path, directory=False)
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def _sync_directories(destination):
    if os.name == 'nt':
        return
    directories = [item for item in destination.rglob('*') if item.is_dir()]
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        assert_no_redirected_components(path, include_leaf=True)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class PlatformInstallationDenied(PermissionError):
    """The release/authority/checkpoint contract refuses this lifecycle step."""


@dataclass(frozen=True, slots=True)
class VerifiedStagedRelease:
    release_id: str
    revision: int
    manifest_sha256: str
    source_sha: str
    signer_key_id: str
    staging_path: Path
    manifest: object


@dataclass(frozen=True, slots=True)
class InstallationCheckpoint:
    minimum_accepted_revision: int
    active_release_id: str | None
    active_installation_id: str | None
    generation: int


class PlatformInstallationStore:
    """Platform-owned SQLite receipts, attempts, history and anti-rollback floor.

    This store never owns canonical Core state: a file named sofia.db is
    refused outright and every transaction here is independent of it. History
    is append-only; the checkpoint row is the durable minimum-revision floor
    plus the exactly one active installation (or none).
    """

    def __init__(self, state_path):
        self.path = Path(state_path).absolute()
        if self.path.name == 'sofia.db':
            raise PermissionError('installation receipts never join canonical Core state')
        assert_no_redirected_components(self.path, include_leaf=True)
        ensure_owner_private_directory(self.path.parent)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('PRAGMA busy_timeout=10000')
            db.execute("""
                CREATE TABLE IF NOT EXISTS ops_platform_installation_checkpoint (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    minimum_accepted_revision INTEGER NOT NULL,
                    active_release_id TEXT,
                    active_installation_id TEXT,
                    generation INTEGER NOT NULL DEFAULT 0
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS ops_platform_installation_attempt (
                    attempt_id TEXT PRIMARY KEY,
                    release_id TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    outcome TEXT,
                    finished_at TEXT
                )
            """)
            db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS ops_platform_one_unresolved_attempt
                    ON ops_platform_installation_attempt(release_id)
                    WHERE outcome IS NULL
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS ops_platform_installation_receipt (
                    receipt_id TEXT PRIMARY KEY,
                    release_id TEXT NOT NULL UNIQUE,
                    operation TEXT NOT NULL,
                    result TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    staging_path TEXT NOT NULL,
                    destination TEXT NOT NULL UNIQUE,
                    installed_at TEXT NOT NULL,
                    activated INTEGER NOT NULL DEFAULT 0,
                    checkpoint_revision INTEGER NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS ops_platform_installation_history (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id TEXT NOT NULL,
                    release_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    result TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)

    def checkpoint(self):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                'SELECT minimum_accepted_revision, active_release_id,'
                ' active_installation_id, generation'
                ' FROM ops_platform_installation_checkpoint WHERE singleton=1'
            ).fetchone()
        return None if row is None else InstallationCheckpoint(*row)

    def revision_floor(self) -> int:
        current = self.checkpoint()
        return 0 if current is None else current.minimum_accepted_revision

    def receipt_for_release(self, release_id: str):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(
                'SELECT * FROM ops_platform_installation_receipt WHERE release_id=?',
                (release_id,)).fetchone()

    def receipt_for_destination(self, destination):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(
                'SELECT * FROM ops_platform_installation_receipt WHERE destination=?',
                (str(Path(destination).absolute()),)).fetchone()

    def pending_attempts(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(
                'SELECT * FROM ops_platform_installation_attempt'
                ' WHERE outcome IS NULL ORDER BY started_at').fetchall()

    def attempts(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(
                'SELECT * FROM ops_platform_installation_attempt ORDER BY started_at'
            ).fetchall()

    def history(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(
                'SELECT * FROM ops_platform_installation_history ORDER BY sequence'
            ).fetchall()

    def begin_attempt(self, release_id, manifest_sha256, destination, operation, now):
        target = str(Path(destination).absolute())
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            pending = db.execute(
                'SELECT attempt_id FROM ops_platform_installation_attempt'
                ' WHERE release_id=? AND outcome IS NULL', (release_id,)).fetchone()
            if pending is not None:
                raise PlatformInstallationDenied(
                    'release already has an unresolved installation attempt')
            attempt_id = 'attempt:' + uuid4().hex
            db.execute(
                'INSERT INTO ops_platform_installation_attempt'
                ' (attempt_id, release_id, manifest_sha256, destination, operation,'
                '  started_at) VALUES (?,?,?,?,?,?)',
                (attempt_id, release_id, manifest_sha256, target, operation,
                 now.isoformat()))
            db.commit()
        return attempt_id

    def finish_failed_attempt(self, attempt_id, error, now):
        if not (isinstance(error, str) and error.strip()):
            raise ValueError('failed attempt review requires an explicit reason')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute(
                'UPDATE ops_platform_installation_attempt'
                ' SET outcome=?, finished_at=? WHERE attempt_id=? AND outcome IS NULL',
                ('reviewed: ' + error.strip(), now.isoformat(), attempt_id)).rowcount
            if changed != 1:
                raise PlatformInstallationDenied(
                    'attempt unknown or already closed')
            db.commit()

    def _record_installed(self, db, *, receipt_id, release_id, operation, revision,
                          manifest_sha256, staging, destination, now, checkpoint_revision,
                          attempt_id):
        db.execute(
            'INSERT INTO ops_platform_installation_receipt'
            ' (receipt_id, release_id, operation, result, revision, manifest_sha256,'
            '  staging_path, destination, installed_at, activated, checkpoint_revision)'
            ' VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (receipt_id, release_id, operation, SUCCEEDED, revision, manifest_sha256,
             str(staging), str(destination), now.isoformat(), 0, checkpoint_revision))
        db.execute(
            'INSERT INTO ops_platform_installation_history'
            ' (receipt_id, release_id, operation, result, revision, manifest_sha256,'
            '  recorded_at) VALUES (?,?,?,?,?,?,?)',
            (receipt_id, release_id, operation, SUCCEEDED, revision, manifest_sha256,
             now.isoformat()))
        db.execute(
            'INSERT INTO ops_platform_installation_checkpoint'
            ' (singleton, minimum_accepted_revision, active_release_id,'
            '  active_installation_id, generation) VALUES (1,?,NULL,?,1)'
            ' ON CONFLICT(singleton) DO UPDATE SET'
            '  minimum_accepted_revision=excluded.minimum_accepted_revision,'
            '  active_installation_id=excluded.active_installation_id,'
            '  generation=ops_platform_installation_checkpoint.generation+1',
            (checkpoint_revision, receipt_id))
        db.execute(
            'UPDATE ops_platform_installation_attempt SET outcome=?, finished_at=?'
            ' WHERE attempt_id=? AND outcome IS NULL',
            ('completed', now.isoformat(), attempt_id))

    def record_activated(self, receipt_id, *, now) -> int:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute(
                'UPDATE ops_platform_installation_receipt SET activated=1'
                ' WHERE receipt_id=? AND activated=0', (receipt_id,)).rowcount
            if changed != 1:
                raise PlatformInstallationDenied(
                    'installation receipt unknown or already activated')
            active = db.execute(
                'SELECT release_id, revision, manifest_sha256 FROM'
                ' ops_platform_installation_receipt WHERE receipt_id=?',
                (receipt_id,)).fetchone()
            occupied = db.execute(
                'SELECT active_release_id FROM'
                ' ops_platform_installation_checkpoint WHERE singleton=1'
            ).fetchone()
            if occupied is None:
                raise PlatformInstallationDenied('installed lifecycle state missing')
            if occupied[0] is not None and occupied[0] != active[0]:
                raise PlatformInstallationDenied(
                    'another release is already active; owners must rollback first')
            db.execute(
                'UPDATE ops_platform_installation_checkpoint'
                ' SET active_release_id=?, active_installation_id=?, generation=generation+1'
                ' WHERE singleton=1', (active[0], receipt_id))
            db.execute(
                'INSERT INTO ops_platform_installation_history'
                ' (receipt_id, release_id, operation, result, revision, manifest_sha256,'
                '  recorded_at) VALUES (?,?,?,?,?,?,?)',
                (receipt_id, active[0], 'activate', SUCCEEDED, active[1], active[2],
                 now.isoformat()))
            generation = db.execute(
                'SELECT generation FROM ops_platform_installation_checkpoint'
                ' WHERE singleton=1').fetchone()[0]
            db.commit()
        return generation


def _verify_release_bytes(directory, *, verifier, minimum_revision, expected_source_sha):
    """Verify manifest, signature and asset digests rooted at one directory."""
    manifest_payload = _decode_private_json(directory / 'release-manifest.json')
    signature_document = _decode_private_json(directory / 'release-signature.json')
    scope = manifest_payload.get('target')
    return verifier.verify(
        manifest_payload, assets_root=directory / 'assets',
        signature_b64=signature_document.get('signature_b64'),
        signer_key_id=signature_document.get('signer_key_id'),
        expected_source_sha=expected_source_sha
        if expected_source_sha is not None else manifest_payload.get('source_sha'),
        expected_target=verifier_target(scope),
        minimum_revision=int(minimum_revision))


def verify_staged_release_candidate(staging_path, *, verifier, minimum_revision=0):
    """Re-verify a staged candidate independently of the staging-time result."""
    if not isinstance(verifier, PlatformReleaseVerifier):
        raise TypeError('configured Platform release verifier required')
    staging = Path(staging_path).absolute()
    assert_owner_private_path(staging, directory=True)
    receipt = _decode_private_json(staging / 'stage-receipt.json')
    if receipt.get('schema') != STAGE_SCHEMA:
        raise PlatformReleaseRejected('staged candidate carries a foreign stage schema')
    if receipt.get('result') != 'VERIFIED_PLATFORM_CODE_STAGED':
        raise PlatformReleaseRejected('staged candidate was never verified')
    if receipt.get('activated') is not False:
        raise PlatformReleaseRejected('staged candidate already claims activation')
    manifest = _verify_release_bytes(staging, verifier=verifier,
        minimum_revision=int(minimum_revision),
        expected_source_sha=receipt.get('source_sha'))
    if (manifest.release_id != receipt.get('release_id')
            or manifest.digest != receipt.get('manifest_sha256')):
        raise PlatformReleaseRejected('staged receipt does not match its release manifest')
    signature_document = _decode_private_json(staging / 'release-signature.json')
    return VerifiedStagedRelease(
        release_id=manifest.release_id, revision=manifest.revision,
        manifest_sha256=manifest.digest, source_sha=manifest.source_sha,
        signer_key_id=signature_document.get('signer_key_id'),
        staging_path=staging, manifest=manifest)


def verifier_target(value):
    if isinstance(value, PlatformReleaseTarget):
        return value
    return PlatformReleaseTarget(value)


def installed_release_id(release_id, manifest_sha256, destination) -> str:
    """Deterministic installation identity stable across the crash windows."""
    binding = f'{release_id}\n{manifest_sha256}\n{str(Path(destination).absolute())}'
    return 'installation:' + sha256(binding.encode('utf-8')).hexdigest()


def staging_asset_path(staging, relative):
    return staging / 'assets' / relative


def _publish_verified_tree(candidate, destination, *, verifier, operation, now,
                           installation_id):
    """Publish independently re-verified bytes into an absent private target.

    Every referenced asset is re-read through the bounded artifact reader,
    digest-compared against the verified manifest reference and written with
    exclusive creation; the copied bytes are verified again before the
    materialized runtime is derived. The destination never pre-exists.
    """
    manifest = candidate.manifest
    destination.mkdir(mode=0o700)
    restrict_new_owner_private_path(destination, directory=True)
    assets = destination / 'assets'
    assets.mkdir(mode=0o700)
    for asset in manifest.assets:
        reference = asset.reference
        source = staging_asset_path(candidate.staging_path, reference.path)
        size = source.stat(follow_symlinks=False).st_size
        digest, data = read_artifact_file(source, size, include_data=True)
        if digest != reference.sha256:
            raise PlatformReleaseRejected('staged source changed before installation')
        _write_new(assets.joinpath(*reference.path.split('/')), data)
    signature_document = _decode_private_json(
        candidate.staging_path / 'release-signature.json')
    verifier.verify(manifest.to_payload(), assets_root=assets,
        signature_b64=signature_document.get('signature_b64'),
        signer_key_id=candidate.signer_key_id,
        expected_source_sha=candidate.source_sha, expected_target=manifest.target,
        minimum_revision=candidate.revision)
    runtime = next(asset.reference for asset in manifest.assets
                   if asset.kind == 'python-runtime')
    materialize_python_runtime(assets.joinpath(*runtime.path.split('/')),
        destination / 'runtime', expected=runtime, target=manifest.target,
        python_version=manifest.python_version)
    _write_new(destination / 'release-manifest.json', manifest.canonical_bytes)
    _write_new(destination / 'release-signature.json', _json(signature_document))
    _write_new(destination / 'installation-receipt.json', _json(
        dict(schema=INSTALLATION_SCHEMA, result='PLATFORM_RELEASE_INSTALLED',
             installation_id=installation_id,
             release_id=candidate.release_id, revision=candidate.revision,
             manifest_sha256=candidate.manifest_sha256,
             source_sha=candidate.source_sha,
             signer_key_id=candidate.signer_key_id, operation=operation,
             activated=False, os_service_registered=False,
             state_initialized=False, service_health_verified=False)))


def platform_rollback_request(staging_path, destination, state_path, *, store, verifier):
    """Create a non-executable, checkpoint-bound owner rollback approval preview.

    The exact signed candidate, destination and current anti-rollback
    generation are included so a stale approval cannot authorize later work.
    """
    candidate = verify_staged_release_candidate(
        staging_path, verifier=verifier, minimum_revision=1)
    checkpoint = store.checkpoint()
    if checkpoint is None:
        raise PlatformInstallationDenied('rollback requires existing installation history')
    parameters = dict(
        release_id=candidate.release_id,
        manifest_sha256=candidate.manifest_sha256,
        revision=candidate.revision,
        staging_path=str(candidate.staging_path),
        destination=str(Path(destination).absolute()),
        state_path=str(Path(state_path).absolute()),
        checkpoint_revision=checkpoint.minimum_accepted_revision,
        checkpoint_generation=checkpoint.generation)
    return dict(capability=ROLLBACK_CAPABILITY, parameters=parameters,
                fingerprint=execution_fingerprint(ROLLBACK_CAPABILITY, parameters))


def install_staged_release(staging_path, destination, *, store, verifier,
                           minimum_revision=None, operation=INSTALL, now=None,
                           state_path=None, approval_id=None):
    """Publish an independently re-verified staged release into an owned target.

    No activation happens here. The durable anti-rollback checkpoint floors
    ordinary installs; downgrade only succeeds as an approved rollback of
    exactly previously attested bytes from this Platform's install history
    and it never lowers the floor. Interrupted attempts stay pending for
    operator review and block the same release until resolved.
    """
    now = now or datetime.now().astimezone()
    if operation not in (INSTALL, ROLLBACK):
        raise ValueError('unsupported installation operation')
    destination = Path(destination).absolute()
    ensure_owner_private_directory(destination.parent)
    requested_floor = (store.revision_floor() if minimum_revision is None
                       else int(minimum_revision))
    # The verifier only know its own manifest floor. The durable checkpoint
    # comparison below produces the explicit anti-rollback denial, so release
    # verification uses the bounded manifest floor alone.
    candidate = verify_staged_release_candidate(
        staging_path, verifier=verifier,
        minimum_revision=(max(1, int(minimum_revision)) if minimum_revision is not None
                          else 1))
    checkpoint = store.checkpoint()
    if checkpoint is not None and candidate.revision < checkpoint.minimum_accepted_revision:
        if operation != ROLLBACK:
            raise PlatformInstallationDenied(
                'release revision is below the durable anti-rollback checkpoint;'
                ' downgrade suppression requires an approved rollback of exactly'
                ' previously attested bytes')
        attested = [row for row in store.history()
                    if row['release_id'] == candidate.release_id
                    and row['manifest_sha256'] == candidate.manifest_sha256
                    and row['revision'] == candidate.revision
                    and row['result'] == SUCCEEDED]
        if not attested:
            raise PlatformInstallationDenied(
                'rollback target must be exact previously attested bytes from'
                ' this Platform install history')
    if operation == ROLLBACK:
        if state_path is None or not approval_id:
            raise PlatformInstallationDenied(
                'rollback requires fresh owner approval and canonical SAFE state')
        state_path = Path(state_path).absolute()
        if OperatorStopStore(state_path).current().active:
            raise PlatformInstallationDenied('operator STOP is engaged; rollback refused')
        request = platform_rollback_request(
            staging_path, destination, state_path, store=store, verifier=verifier)
        ExecutionApprovalVerifier(state_path).consume(
            approval_id=approval_id, capability=request['capability'],
            parameters=request['parameters'], now=now)
    receipt = store.receipt_for_release(candidate.release_id)
    if receipt is not None and receipt['result'] == SUCCEEDED:
        verify_installed(receipt['destination'], store=store, verifier=verifier)
        return installation_receipt(receipt)
    if store.pending_attempts():
        raise PlatformInstallationDenied(
            'an unresolved installation attempt must be reviewed first')
    attempt_id = store.begin_attempt(candidate.release_id, candidate.manifest_sha256,
                                     destination, operation, now)
    receipt_id = installed_release_id(candidate.release_id, candidate.manifest_sha256,
                                      destination)
    quarantine = destination.parent / ('inbound-' + uuid4().hex)
    try:
        if destination.exists():
            raise FileExistsError('installed release target must not replace existing data')
        _publish_verified_tree(candidate, quarantine, verifier=verifier,
                               operation=operation, now=now,
                               installation_id=receipt_id)
        _sync_directories(quarantine)
        assert_no_redirected_components(destination, include_leaf=True)
        os.replace(quarantine, destination)
    except BaseException as error:
        try:
            store.finish_failed_attempt(attempt_id, str(error) or type(error).__name__, now)
        finally:
            raise
    finally:
        if quarantine.exists():
            shutil.rmtree(quarantine, ignore_errors=True)
    floor = max(candidate.revision, (checkpoint.minimum_accepted_revision if checkpoint else 0))
    with closing(sqlite3.connect(store.path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        store._record_installed(db, receipt_id=receipt_id,
            release_id=candidate.release_id, operation=operation,
            revision=candidate.revision, manifest_sha256=candidate.manifest_sha256,
            staging=candidate.staging_path, destination=destination, now=now,
            checkpoint_revision=floor, attempt_id=attempt_id)
        db.commit()
    _sync_directories(destination)
    return installation_receipt(store.receipt_for_release(candidate.release_id))


def installation_receipt(row) -> dict:
    return dict(
        schema=INSTALLATION_SCHEMA, result='PLATFORM_RELEASE_INSTALLED',
        installation_id=row['receipt_id'], release_id=row['release_id'],
        revision=row['revision'], manifest_sha256=row['manifest_sha256'],
        operation=row['operation'], staged=row['staging_path'],
        destination=row['destination'], activated=bool(row['activated']),
        installed_at=row['installed_at'])


def verify_installed(destination, *, store, verifier, minimum_revision=0):
    """Read-only reconcile of an installed release with its durable receipts."""
    destination = Path(destination).absolute()
    row = store.receipt_for_destination(destination)
    if row is None:
        raise PlatformInstallationDenied('destination has no durable installation receipt')
    if store.pending_attempts():
        raise PlatformInstallationDenied(
            'an unresolved installation attempt must be reviewed first')
    installed = _decode_private_json(destination / 'installation-receipt.json')
    if installed.get('installation_id') != row['receipt_id']:
        raise PlatformInstallationDenied(
            'installation receipt disagrees with durable state; operator repair'
            ' judgment is required before anything else touches this target')
    if bool(row['activated']):
        try:
            activation = _decode_private_json(destination / 'activation-receipt.json')
        except (OSError, ValueError, UnicodeError) as error:
            raise PlatformInstallationDenied(
                'active release lacks valid activation receipt;'
                ' operator reconciliation required') from error
        if (activation.get('schema') != ACTIVATION_SCHEMA
                or activation.get('result') != 'PLATFORM_RELEASE_ACTIVATED'
                or activation.get('installation_id') != row['receipt_id']
                or activation.get('release_id') != row['release_id']
                or activation.get('manifest_sha256') != row['manifest_sha256']
                or activation.get('service_health_verified') is not True):
            raise PlatformInstallationDenied(
                'activation receipt conflicts with installed release;'
                ' operator reconciliation required')
    # Installed release trust comes from its own signed manifest and bytes.
    # Staging may be deleted after installation; it must not be a dependency.
    installed_manifest = _verify_release_bytes(
        destination, verifier=verifier,
        minimum_revision=max(1, int(minimum_revision), int(row['revision'])),
        expected_source_sha=None)
    if (installed_manifest.digest != row['manifest_sha256']
            or installed_manifest.release_id != row['release_id']
            or installed_manifest.revision != row['revision']):
        raise PlatformInstallationDenied('installed manifest drifted from durable state')
    for item in sorted(destination.rglob('*')):
        if item.is_file():
            read_artifact_file(item, item.stat(follow_symlinks=False).st_size)
    return installation_receipt(row)


def platform_activation_request(destination, state_path, *, store):
    """Show the exact capability parameters an owner must approve, up front."""
    destination = Path(destination).absolute()
    state_path = Path(state_path).absolute()
    row = store.receipt_for_destination(destination)
    if row is None:
        raise PlatformInstallationDenied('destination has no durable installation receipt')
    parameters = dict(
        release_id=row['release_id'], manifest_sha256=row['manifest_sha256'],
        revision=int(row['revision']), installation_id=row['receipt_id'],
        destination=str(destination), state_path=str(state_path))
    return dict(capability=ACTIVATION_CAPABILITY, parameters=parameters,
                fingerprint=execution_fingerprint(ACTIVATION_CAPABILITY, parameters))


def activate_installed_release(destination, *, store, state_path, verifier, runtime,
                               approval_id, now=None):
    """Consume the exact owner approval, start the real service, verify health.

    The approval must be fresh, unconsumed and bound to an exact fingerprint
    of this release selection; its consumption is single-use (anti-replay).
    Real health means a genuinely started local Platform service adapter
    reporting the expected schema, identity and Core-free status. A failed
    health check never marks anything active and records an explicit failed
    activation history entry without silently retrying.
    """
    now = now or datetime.now().astimezone()
    destination = Path(destination).absolute()
    state_path = Path(state_path).absolute()
    if not callable(getattr(runtime, 'start', None)) or not callable(getattr(runtime, 'close', None)):
        raise TypeError('real service runtime launcher with close required')
    receipt = store.receipt_for_destination(destination)
    if receipt is None or receipt['result'] != SUCCEEDED:
        raise PlatformInstallationDenied('only fully installed releases can activate')
    verify_installed(destination, store=store, verifier=verifier,
                     minimum_revision=int(receipt['revision']))
    if OperatorStopStore(state_path).current().active:
        raise PlatformInstallationDenied('operator STOP is engaged; activation refused')
    request = platform_activation_request(destination, state_path, store=store)
    approvals = ExecutionApprovalVerifier(state_path)
    approvals.consume(
        approval_id=approval_id, capability=request['capability'],
        parameters=request['parameters'], now=now)
    try:
        health = runtime.start()
    except BaseException as error:
        with suppress(Exception):
            runtime.close()
        with closing(sqlite3.connect(store.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute(
                'INSERT INTO ops_platform_installation_history'
                ' (receipt_id, release_id, operation, result, revision, manifest_sha256,'
                '  recorded_at) VALUES (?,?,?,?,?,?,?)',
                (receipt['receipt_id'], receipt['release_id'], 'activate',
                 _FAILED + ':' + (str(error).strip() or type(error).__name__),
                 receipt['revision'], receipt['manifest_sha256'], now.isoformat()))
            db.commit()
        raise
    if (not isinstance(health, dict) or health.get('schema') != SERVICE_SCHEMA
            or health.get('phase') != 'ready'
            or health.get('platform_id') != runtime.expected_platform_id
            or health.get('public_key_sha256') != runtime.expected_public_key_sha256
            or health.get('core_started') is not False):
        with suppress(Exception):
            runtime.close()
        with closing(sqlite3.connect(store.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute(
                'INSERT INTO ops_platform_installation_history'
                ' (receipt_id, release_id, operation, result, revision, manifest_sha256,'
                '  recorded_at) VALUES (?,?,?,?,?,?,?)',
                (receipt['receipt_id'], receipt['release_id'], 'activate',
                 _FAILED + ':service health verification failed', receipt['revision'],
                 receipt['manifest_sha256'], now.isoformat()))
            db.commit()
        raise RuntimeError('real service health verification failed')
    try:
        generation = store.record_activated(receipt['receipt_id'], now=now)
        _write_new(destination / 'activation-receipt.json', _json(
            dict(schema=ACTIVATION_SCHEMA, result='PLATFORM_RELEASE_ACTIVATED',
                 approval_id=approval_id, capability=ACTIVATION_CAPABILITY,
                 installation_id=receipt['receipt_id'], release_id=receipt['release_id'],
                 revision=receipt['revision'], manifest_sha256=receipt['manifest_sha256'],
                 activation_generation=generation, service_pid=health.get('pid'),
                 service_generation=health.get('generation'),
                 service_health_verified=True, activated_at=now.isoformat())))
    except BaseException:
        # Cross-store commit is not atomic. Close the started service and leave
        # the incomplete activation explicitly subject to operator recovery.
        with suppress(Exception):
            runtime.close()
        raise
    return dict(generation=generation, health=health)


def _bounded_readline(stream, timeout):
    """Read one child readiness line with a real wall-clock deadline.

    Windows anonymous pipes do not support POSIX selectors. The background
    reader is daemonized and the caller must terminate/close the child on a
    deadline failure so the pipe reader can finish.
    """
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 300):
        raise ValueError('service readiness timeout must be between 0 and 300 seconds')
    result = Queue(maxsize=1)

    def read_line():
        try:
            result.put((True, stream.readline()))
        except BaseException as error:
            result.put((False, error))

    Thread(target=read_line, daemon=True, name='aegis-readiness').start()
    try:
        success, payload = result.get(timeout=timeout)
    except Empty as error:
        raise TimeoutError('service readiness deadline expired') from error
    if not success:
        raise payload
    return payload


class PythonPlatformServiceLauncher:
    """Start the real installed Platform state adapter as a supervised child."""

    def __init__(self, python_executable, identity_home, state_path, expected_platform_id,
                 expected_public_key_sha256):
        self.python_executable = Path(python_executable)
        self.identity_home = Path(identity_home)
        self.state_path = Path(state_path).absolute()
        self.expected_platform_id = expected_platform_id
        self.expected_public_key_sha256 = expected_public_key_sha256
        self._child = None

    def start(self, *, timeout=30.0):
        environment = os.environ.copy()
        argv = [str(self.python_executable), '-I', '-m',
                'sofia.platform.run.platform_service',
                '--identity-home', str(self.identity_home),
                '--state', str(self.state_path),
                '--platform-id', self.expected_platform_id,
                '--public-key-sha256', self.expected_public_key_sha256,
                '--supervisor-pid', str(os.getpid())]
        if os.name == 'nt':
            base = subprocess.run(
                [str(self.python_executable), '-I', '-c',
                 'import sys; print(sys._base_executable)'],
                capture_output=True, text=True, check=True, timeout=15).stdout.strip()
            argv[0] = base
            environment['__PYVENV_LAUNCHER__'] = str(self.python_executable)
        self._child = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=environment,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
        try:
            line = _bounded_readline(self._child.stdout, timeout)
            if not line:
                error = self._child.stderr.read(4096)
                raise RuntimeError('service adapter exited before readiness: ' + error)
            health = loads_strict_model_json(line)
        except BaseException:
            self.close()
            raise
        return health

    def close(self):
        child = self._child
        self._child = None
        if child is None:
            return
        # EOF is the service's owned shutdown signal. Do not call communicate()
        # after closing stdin: Python tries flushing the already-closed pipe.
        try:
            if child.stdin is not None and not child.stdin.closed:
                child.stdin.close()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        finally:
            if child.poll() is None:
                with suppress(Exception):
                    child.kill()
                with suppress(Exception):
                    child.wait(timeout=5)
            for stream in (child.stdout, child.stderr):
                if stream is not None:
                    with suppress(Exception):
                        stream.close()
