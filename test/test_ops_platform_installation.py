"""Owned release installation lifecycle: durable receipts, anti-rollback,
anti-replay owner activation and real installed service health."""
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from email.parser import BytesParser
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.platform_installation import (
    ACTIVATION_CAPABILITY, INSTALL, ROLLBACK, PlatformInstallationDenied,
    PlatformInstallationStore, PythonPlatformServiceLauncher,
    activate_installed_release, install_staged_release,
    platform_activation_request, platform_rollback_request, verify_installed,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.ops.platform_release_staging import stage_platform_release
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import ensure_owner_private_directory
from sofia.platform.verify.python_runtime import build_python_runtime
from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.platform_release import (
    PlatformReleaseAsset, PlatformReleaseManifest, PlatformReleaseTarget,
)
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_platform_release_verifier import platform_wheels
from test.test_platform_service_session import provision
from test.test_python_runtime_artifacts import fake_prefix

pytestmark = pytest.mark.pkg_ops


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _wheel_identity(wheel):
    with zipfile.ZipFile(io.BytesIO(Path(wheel).read_bytes())) as archive:
        metadata = [item.filename for item in archive.infolist()
                    if item.filename.endswith('.dist-info/METADATA')]
        assert len(metadata) == 1
        details = BytesParser().parsebytes(archive.read(metadata[0]))
    return details.get('Name'), details.get('Version')


def _normalised(name):
    return re.sub('[-_.]+', '-', name).lower()


class SignedReleaseBuilder:
    """Disposable in-memory signer staging genuine Platform release trees.

    The generated key is never persisted and is not an owner principal or a
    production trust root. asset/digest bindings rely on the real Platform
    manifest, verifier and staging contracts.
    """

    def __init__(self, root, wheels):
        self.root = Path(root)
        self.wheels = wheels
        ensure_owner_private_directory(self.root)
        self._key = Ed25519PrivateKey.generate()
        public = self._key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo)
        self.verifier = PlatformReleaseVerifier({'disposable-test-signer': public})
        self.signer_key_id = 'disposable-test-signer'
        self._prefix = None

    def stage(self, *, release_id='disposable-vm-release', revision=1,
              python_version='3.12.16'):
        safe_name = re.sub('[^a-z0-9-]+', '-', release_id.lower()).strip('-')[:32]
        build = self.root / f'assets-{safe_name}-r{revision}'
        build.mkdir(exist_ok=True)
        if self._prefix is None:
            self._prefix = fake_prefix(self.root)
        prefix = self._prefix
        service = build / 'aegis-platform-service'
        service.write_bytes((prefix / 'bin/python3.12').read_bytes())
        contents = {}
        for kind, wheel in self.wheels.items():
            contents[wheel.name] = (kind, wheel.read_bytes())
        contents['aegis-platform-service'] = ('service', service.read_bytes())
        runtime = build_python_runtime(prefix, build / 'python-runtime.zip',
            target=PlatformReleaseTarget.DEBIAN12_X86_64,
            python_version=python_version)
        contents[runtime.reference.path] = ('python-runtime',
                                            Path(build / 'python-runtime.zip').read_bytes())
        observed = []
        for kind, wheel in self.wheels.items():
            name, version = _wheel_identity(wheel)
            observed.append(dict(distribution=name, version=version,
                artifact=wheel.name))
        contents['dependency-index.json'] = ('dependency-lock', _json(dict(
            schema='aegis.disposable.vm.dependency-index.v1', wheels=observed,
            production_authorized=False)))
        contents['observed-sbom.json'] = ('sbom', _json(dict(
            schema='aegis.disposable.vm.sbom.v1', packages=observed,
            python_version=python_version, standards_compliance_claimed=False)))
        contents['assembly-provenance.json'] = ('provenance', _json(dict(
            schema='aegis.disposable.vm.provenance.v1',
            observed_source_sha='a' * 40, base_image='pinned-test-image',
            artifact_hashes=dict((name, sha256(data).hexdigest())
                                 for name, (_, data) in contents.items()),
            production_release_attested=False)))
        assets = []
        for name, (kind, data) in sorted(contents.items()):
            (build / name).write_bytes(data)
            assets.append(PlatformReleaseAsset(kind, ArtifactReference(
                name, sha256(data).hexdigest(), len(data))))
        manifest = PlatformReleaseManifest(
            release_id, '0.1.0', int(revision), 'a' * 40,
            PlatformReleaseTarget.DEBIAN12_X86_64, SDK_PROTOCOL_VERSION,
            python_version, tuple(assets))
        signature = b64encode(self._key.sign(manifest.digest.encode('ascii'))).decode('ascii')
        destination = self.root / f'staged-{safe_name}-r{revision}'
        receipt = stage_platform_release(
            verifier=self.verifier, payload=manifest.to_payload(),
            signature_b64=signature, signer_key_id=self.signer_key_id,
            assets_root=build, destination=destination,
            expected_source_sha='a' * 40, expected_target=manifest.target,
            minimum_revision=1)
        return destination, manifest, receipt


@pytest.fixture
def builder(tmp_path, platform_wheels):
    return SignedReleaseBuilder(tmp_path / 'builder', platform_wheels)


@pytest.fixture(scope='module')
def service_python(tmp_path_factory, platform_wheels):
    """Real installed Core-free adapter environment built from release wheels."""
    home = tmp_path_factory.mktemp('installation-service-venv')
    subprocess.run([sys.executable, '-m', 'venv', str(home)], check=True,
                   capture_output=True)
    python = home / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    install = subprocess.run([str(python), '-m', 'pip', 'install',
        '--disable-pip-version-check', str(platform_wheels['sdk']),
        str(platform_wheels['platform'])], capture_output=True, text=True,
        timeout=600)
    assert install.returncode == 0, install.stderr
    probe = subprocess.run([str(python), '-I', '-c',
        "import importlib.util; assert importlib.util.find_spec('sofia.core') is None"
        "; assert importlib.util.find_spec('ollama') is None"],
        cwd=home, capture_output=True, text=True, timeout=30)
    assert probe.returncode == 0, probe.stderr
    return python


@pytest.fixture
def installed_release(tmp_path, builder):
    """A genuinely staged and installed release with its durable receipts."""
    staging, manifest, _receipt = builder.stage(revision=1)
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    destination = tmp_path / 'installed'
    install_staged_release(staging, destination, store=store, verifier=builder.verifier)
    return builder, store, destination


def _default_service_launcher(service_python, tmp_path):
    identity, current, state = provision(tmp_path / 'host')
    return identity, current, state, PythonPlatformServiceLauncher(
        service_python, identity.home, state,
        current.identity.canonical_uuid, current.public_key_sha256)


def _approve_dependency(canonical_state_path, tmp_path):
    approvals = ExecutionApprovalVerifier(canonical_state_path)
    return approvals


def test_install_records_durable_receipt_and_advances_checkpoint(installed_release):
    _builder, store, destination = installed_release
    receipt = store.receipt_for_release('disposable-vm-release')
    assert receipt['result'] == 'SUCCEEDED'
    assert receipt['operation'] == INSTALL
    assert bool(receipt['activated']) is False
    assert json.loads((destination / 'installation-receipt.json').read_text())[
        'activated'] is False
    checkpoint = store.checkpoint()
    assert checkpoint.minimum_accepted_revision == 1
    assert checkpoint.active_release_id is None
    assert not list(destination.rglob('sofia.db'))
    verify_installed(destination, store=store, verifier=_builder.verifier)
    assert len(store.history()) == 1


def test_installed_release_verifies_after_staging_directory_removed(installed_release):
    """Installed Platform verification must not require retained staging bytes."""
    builder, store, destination = installed_release
    receipt = store.receipt_for_release('disposable-vm-release')
    shutil.rmtree(Path(receipt['staging_path']))
    observed = verify_installed(destination, store=store, verifier=builder.verifier)
    assert observed['release_id'] == 'disposable-vm-release'
    assert observed['destination'] == str(destination)


def test_downgrade_after_reboot_refused_until_attested_rollback(
        tmp_path, builder, canonical_state_path):
    staging_one, _manifest, _sig = builder.stage(
        revision=1, release_id='release-one')
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    first = tmp_path / 'installed-one'
    install_staged_release(staging_one, first, store=store, verifier=builder.verifier)
    staging_two, _m2, _s2 = builder.stage(revision=2, release_id='release-two')
    install_staged_release(staging_two, tmp_path / 'installed-two', store=store,
                           verifier=builder.verifier)
    assert store.checkpoint().minimum_accepted_revision == 2
    # Reboot: a fresh store instance reads the same durable floor.
    rebooted = PlatformInstallationStore(tmp_path / 'installation.db')
    with pytest.raises(PlatformInstallationDenied, match='anti-rollback'):
        install_staged_release(staging_one, tmp_path / 'downgrade', store=rebooted,
                               verifier=builder.verifier)
    # Downgrade rollback is a protected operation, even when the signed bytes
    # are in local history. Reboots do not waive the exact one-use owner proof.
    target = tmp_path / 'rolled-back'
    with pytest.raises(PlatformInstallationDenied, match='owner approval'):
        install_staged_release(staging_one, target, store=rebooted,
            verifier=builder.verifier, operation=ROLLBACK)
    request = platform_rollback_request(
        staging_one, target, canonical_state_path, store=rebooted,
        verifier=builder.verifier)
    approvals = ExecutionApprovalVerifier(canonical_state_path)
    approval = ExecutionApproval(
        approval_id='approval:test-attested-rollback',
        capability=request['capability'],
        request_fingerprint=request['fingerprint'],
        approved_by='person:sparks',
        approved_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    record_verified_owner_approval(approvals, approval)
    rolled = install_staged_release(staging_one, target,
        store=rebooted, verifier=builder.verifier, operation=ROLLBACK,
        state_path=canonical_state_path, approval_id=approval.approval_id)
    assert rolled['operation'] == INSTALL
    with pytest.raises(PermissionError, match='already consumed'):
        install_staged_release(staging_one, target, store=rebooted,
            verifier=builder.verifier, operation=ROLLBACK,
            state_path=canonical_state_path, approval_id=approval.approval_id)
    assert rolled['destination'] == str(first)
    assert rebooted.checkpoint().minimum_accepted_revision == 2
    branch = builder.stage(revision=1, release_id='never-attested')
    with pytest.raises(PlatformInstallationDenied, match='attested'):
        install_staged_release(branch[0], tmp_path / 'impossible-roll', store=rebooted,
                               verifier=builder.verifier, operation=ROLLBACK)


def test_tampered_staged_asset_cannot_install(tmp_path, builder):
    staging, _manifest, _signature = builder.stage(revision=1)
    victim = next((staging / 'assets').glob('*platform*.whl'))
    victim_bytes = bytearray(victim.read_bytes())
    victim_path = Path(victim)
    with victim_path.open('r+b') as stream:
        stream.seek(len(victim_bytes) - 1)
        stream.write(bytes([victim_bytes[-1] ^ 0x01]))
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    destination = tmp_path / 'installed'
    with pytest.raises(Exception) as caught:
        install_staged_release(staging, destination, store=store,
                               verifier=builder.verifier)
    assert not destination.exists()
    assert list(store.pending_attempts()) == []


def test_unresolved_attempt_blocks_release_until_reviewed(tmp_path, builder):
    staging, _manifest, _signature = builder.stage(revision=1)
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    destination = tmp_path / 'installed'
    now = datetime.now(timezone.utc)
    store.begin_attempt('disposable-vm-release', 'b' * 64, destination, INSTALL, now)
    with pytest.raises(PlatformInstallationDenied, match='unresolved'):
        install_staged_release(staging, destination, store=store,
                               verifier=builder.verifier)
    (attempt,) = store.pending_attempts()
    store.finish_failed_attempt(attempt['attempt_id'], 'operator review', now)
    assert store.pending_attempts() == []
    install_staged_release(staging, destination, store=store, verifier=builder.verifier)
    verify_installed(destination, store=store, verifier=builder.verifier)


def test_publish_failure_records_failed_attempt_and_keeps_target_absent(
        tmp_path, builder, monkeypatch):
    import sofia.platform.ops.platform_installation as installation
    staging, _manifest, _signature = builder.stage(revision=1)
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    destination = tmp_path / 'installed'

    def explode(candidate, target, **_kwargs):
        raise RuntimeError('simulated host failure')

    monkeypatch.setattr(installation, '_publish_verified_tree', explode)
    with pytest.raises(RuntimeError, match='simulated host failure'):
        install_staged_release(staging, destination, store=store,
                               verifier=builder.verifier)
    (attempt,) = store.attempts()
    assert attempt['outcome'].startswith('reviewed: simulated host failure')
    assert store.pending_attempts() == []
    assert not destination.exists()
    assert list((tmp_path).glob('inbound-*')) == []
    monkeypatch.undo()
    install_staged_release(staging, destination, store=store, verifier=builder.verifier)
    verify_installed(destination, store=store, verifier=builder.verifier)


def test_store_refuses_canonical_core_state_file(tmp_path):
    with pytest.raises(PermissionError, match='canonical Core state'):
        PlatformInstallationStore(tmp_path / 'sofia.db')


def test_activation_consumes_exact_owner_approval_once(tmp_path, builder,
                                                       service_python,
                                                       canonical_state_path):
    identity, current, state = provision(tmp_path / 'host')
    staging, _manifest, _signature = builder.stage(revision=1)
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    destination = tmp_path / 'installed'
    install_staged_release(staging, destination, store=store, verifier=builder.verifier)
    request = platform_activation_request(destination, canonical_state_path, store=store)
    approvals = ExecutionApprovalVerifier(canonical_state_path)
    approval = ExecutionApproval(
        approval_id='approval:test-activation-once',
        capability=request['capability'],
        request_fingerprint=request['fingerprint'],
        approved_by='person:sparks',
        approved_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    record_verified_owner_approval(approvals, approval)
    runtime = PythonPlatformServiceLauncher(service_python, identity.home, state,
        current.identity.canonical_uuid, current.public_key_sha256)
    try:
        outcome = activate_installed_release(destination, store=store,
            state_path=canonical_state_path, verifier=builder.verifier,
            runtime=runtime, approval_id=approval.approval_id)
        assert outcome['health']['phase'] == 'ready'
        assert outcome['health']['core_started'] is False
        assert store.checkpoint().active_release_id == 'disposable-vm-release'
        activated = json.loads((destination / 'activation-receipt.json').read_text())
        assert activated['service_health_verified'] is True
    finally:
        runtime.close()
    with pytest.raises(PermissionError, match='already consumed'):
        approvals.consume(
            approval_id=approval.approval_id, capability=request['capability'],
            parameters=request['parameters'], now=datetime.now(timezone.utc))


def test_activation_denies_wrong_authority_and_stop(tmp_path, builder,
                                                    service_python,
                                                    canonical_state_path):
    identity, current, state = provision(tmp_path / 'host')
    staging, _manifest, _signature = builder.stage(revision=1)
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    destination = tmp_path / 'installed'
    install_staged_release(staging, destination, store=store, verifier=builder.verifier)
    request = platform_activation_request(destination, canonical_state_path, store=store)
    approvals = ExecutionApprovalVerifier(canonical_state_path)
    OperatorStopStore(canonical_state_path).set(
        active=True, updated_by='Sparks', at=datetime.now(timezone.utc),
        reason='shakedown fence')
    approval = ExecutionApproval(
        approval_id='approval:test-stop-fence',
        capability=request['capability'],
        request_fingerprint=request['fingerprint'],
        approved_by='person:sparks',
        approved_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    record_verified_owner_approval(approvals, approval)
    runtime = PythonPlatformServiceLauncher(service_python, identity.home, state,
        current.identity.canonical_uuid, current.public_key_sha256)
    with pytest.raises(PlatformInstallationDenied, match='STOP'):
        activate_installed_release(destination, store=store,
            state_path=canonical_state_path, verifier=builder.verifier,
            runtime=runtime, approval_id=approval.approval_id)
    runtime.close()
    with pytest.raises(PlatformInstallationDenied, match='only fully installed releases'):
        activate_installed_release(tmp_path / 'never-installed', store=store,
            state_path=canonical_state_path, verifier=builder.verifier,
            runtime=runtime, approval_id=approval.approval_id)


def test_activation_health_failure_records_failed_history(tmp_path, builder,
                                                          service_python,
                                                          canonical_state_path):
    identity, current, state = provision(tmp_path / 'host')
    staging, _manifest, _signature = builder.stage(revision=1)
    store = PlatformInstallationStore(tmp_path / 'installation.db')
    destination = tmp_path / 'installed'
    install_staged_release(staging, destination, store=store, verifier=builder.verifier)
    request = platform_activation_request(destination, canonical_state_path, store=store)
    approvals = ExecutionApprovalVerifier(canonical_state_path)
    approval = ExecutionApproval(
        approval_id='approval:test-health-fail',
        capability=request['capability'],
        request_fingerprint=request['fingerprint'],
        approved_by='person:sparks',
        approved_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    record_verified_owner_approval(approvals, approval)
    runtime = PythonPlatformServiceLauncher(service_python, identity.home, state,
        '0' * 64, current.public_key_sha256)
    with pytest.raises((RuntimeError, PermissionError)):
        activate_installed_release(destination, store=store,
            state_path=canonical_state_path, verifier=builder.verifier,
            runtime=runtime, approval_id=approval.approval_id)
    outcomes = [row['result'] for row in store.history()]
    assert any(value.startswith('FAILED:') for value in outcomes)
    assert store.checkpoint().active_release_id is None
    assert (destination / 'activation-receipt.json').exists() is False



def test_activation_state_write_failure_stops_started_service(
        tmp_path, installed_release, service_python, canonical_state_path, monkeypatch):
    """An activation DB error cannot leave a live unowned service child."""
    builder, store, destination = installed_release
    identity, current, state = provision(tmp_path / 'host')
    request = platform_activation_request(destination, canonical_state_path, store=store)
    approvals = ExecutionApprovalVerifier(canonical_state_path)
    approval = ExecutionApproval(
        approval_id='approval:test-install-state-failure',
        capability=request['capability'],
        request_fingerprint=request['fingerprint'],
        approved_by='person:sparks',
        approved_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    record_verified_owner_approval(approvals, approval)
    runtime = PythonPlatformServiceLauncher(service_python, identity.home, state,
        current.identity.canonical_uuid, current.public_key_sha256)

    def fail_state_write(*_args, **_kwargs):
        raise RuntimeError('simulated activation DB failure')

    monkeypatch.setattr(store, 'record_activated', fail_state_write)
    try:
        with pytest.raises(RuntimeError, match='activation DB failure'):
            activate_installed_release(destination, store=store,
                state_path=canonical_state_path, verifier=builder.verifier,
                runtime=runtime, approval_id=approval.approval_id)
        assert runtime._child is None
        assert store.checkpoint().active_release_id is None
    finally:
        runtime.close()


def test_activation_receipt_write_failure_requires_reconciliation(
        tmp_path, installed_release, service_python, canonical_state_path, monkeypatch):
    """DB success without an activation file must not be reported healthy."""
    import sofia.platform.ops.platform_installation as installation

    builder, store, destination = installed_release
    identity, current, state = provision(tmp_path / 'host')
    request = platform_activation_request(destination, canonical_state_path, store=store)
    approvals = ExecutionApprovalVerifier(canonical_state_path)
    approval = ExecutionApproval(
        approval_id='approval:test-install-receipt-failure',
        capability=request['capability'],
        request_fingerprint=request['fingerprint'],
        approved_by='person:sparks',
        approved_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
    record_verified_owner_approval(approvals, approval)
    runtime = PythonPlatformServiceLauncher(service_python, identity.home, state,
        current.identity.canonical_uuid, current.public_key_sha256)

    original_write = installation._write_new

    def fail_activation_receipt(path, data):
        if Path(path).name == 'activation-receipt.json':
            raise OSError('simulated activation receipt failure')
        return original_write(path, data)

    monkeypatch.setattr(installation, '_write_new', fail_activation_receipt)
    try:
        with pytest.raises(OSError, match='activation receipt failure'):
            activate_installed_release(destination, store=store,
                state_path=canonical_state_path, verifier=builder.verifier,
                runtime=runtime, approval_id=approval.approval_id)
        assert runtime._child is None
        assert store.checkpoint().active_release_id == 'disposable-vm-release'
        with pytest.raises(PlatformInstallationDenied, match='activation receipt'):
            verify_installed(destination, store=store, verifier=builder.verifier)
    finally:
        runtime.close()


def test_bounded_service_readiness_timeout_and_rejection():
    """A silent child must not block the Windows/Linux readiness path forever."""
    import threading
    import sofia.platform.ops.platform_installation as installation

    released = threading.Event()

    class SilentPipe:
        def readline(self):
            released.wait(timeout=1.0)
            return ''

    try:
        with pytest.raises(TimeoutError, match='service readiness deadline'):
            installation._bounded_readline(SilentPipe(), 0.02)
    finally:
        released.set()

    with pytest.raises(ValueError, match='readiness timeout'):
        installation._bounded_readline(SilentPipe(), 0)


def test_service_launcher_close_does_not_flush_closed_stdin():
    """EOF shutdown is idempotent on both Windows and Unix subprocess pipes."""
    child = subprocess.Popen(
        [sys.executable, '-c', 'import sys; sys.stdin.readline()'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)
    launcher = object.__new__(PythonPlatformServiceLauncher)
    launcher._child = child
    try:
        launcher.close()
        assert child.poll() == 0
        launcher.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
