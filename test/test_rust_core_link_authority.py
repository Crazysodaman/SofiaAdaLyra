"""Real mTLS dispatch through installed Core-free canonical Platform authority."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import threading

import pytest

from sofia.platform.core_link import CoreLinkBindingState
from sofia.platform.core_link.transport import CoreLinkServer, CoreLinkServerConfiguration
from sofia.platform.distributed.tls import public_key_fingerprint_from_pem_certificate
from sofia.sdk.core_link import CoreLinkResponse, CoreLinkResponseStatus
from test.test_core_link_binding import store, binding, NOW
from test.test_core_link_conversation import tls_material
from test.test_component_install_production import component_wheels, production_venv

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def authority_probe():
    subprocess.run(['cargo','build','--locked','-p','sofia-core-link','--features','diagnostic-probe',
                    '--bin','r2_platform_status_probe'],cwd=ROOT,check=True,capture_output=True,text=True,timeout=300)
    target = Path(os.environ.get('CARGO_TARGET_DIR', ROOT/'target'))
    return target/'debug'/('r2_platform_status_probe.exe' if os.name == 'nt' else 'r2_platform_status_probe')


def active_store(tmp_path, pin, scopes=('status.read',)):
    registry = store(tmp_path)
    record = binding(trust_anchor_ref='sha256:'+pin, granted_scopes=scopes)
    registry.add_pending(record, expected_store_revision=0)
    registry.transition(record.binding_id, expected_binding_revision=1, expected_store_revision=1,
        state=CoreLinkBindingState.VERIFYING, at=NOW+timedelta(seconds=1))
    current = registry.reconcile_contact(record.binding_id, expected_binding_revision=2,
        expected_store_revision=2, remote_platform_id=record.remote_platform_id,
        remote_core_identity_id=record.remote_core_identity_id, remote_core_generation=record.remote_core_generation,
        endpoint_id=record.endpoint_id, trust_anchor_ref=record.trust_anchor_ref, at=NOW+timedelta(seconds=2))
    return registry, registry.select(record.binding_id, expected_store_revision=current.revision)


@pytest.mark.parametrize('mode', ['active','revoked','offline','missing_scope','bad_pin','inflight_revoke','revocation_cycle'])
def test_installed_authority_fences_real_rust_dispatch(tmp_path, authority_probe, production_venv, mode):
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)
    pin = public_key_fingerprint_from_pem_certificate(server_cert)
    registry, selected = active_store(tmp_path, '0'*64 if mode == 'bad_pin' else pin,
        ('conversation.read',) if mode == 'missing_scope' else ('status.read',))
    assert 'core-absent' in production_venv['run'](['-I','-c',
        "import importlib.util; assert importlib.util.find_spec('sofia.core') is None; print('core-absent')"])
    selected_binding = selected.selected()
    if mode in {'revoked','offline'}:
        registry.transition(selected_binding.binding_id, expected_binding_revision=selected_binding.revision,
            expected_store_revision=selected.revision,
            state=CoreLinkBindingState.REVOKED if mode == 'revoked' else CoreLinkBindingState.OFFLINE,
            at=NOW+timedelta(seconds=3))

    class Gateway:
        count = 0
        completed = 0
        def dispatch(self, *, certificate_public_key_sha256, request):
            self.count += 1
            assert certificate_public_key_sha256 == public_key_fingerprint_from_pem_certificate(client_cert)
            assert request.operation == 'status'
            assert request.local_platform_id == selected_binding.local_platform_id
            assert request.remote_platform_id == selected_binding.remote_platform_id
            assert request.remote_core_identity_id == selected_binding.remote_core_identity_id
            if mode == 'inflight_revoke':
                registry.transition(selected_binding.binding_id, expected_binding_revision=selected_binding.revision,
                    expected_store_revision=selected.revision, state=CoreLinkBindingState.REVOKED,
                    at=NOW+timedelta(seconds=3))
            self.completed += 1
            return CoreLinkResponse(request.request_id, CoreLinkResponseStatus.COMPLETED,
                {'ready':True,'generation':7,'private':'PRIVATE_STATUS_DO_NOT_LOG'},datetime.now(timezone.utc))
        def close(self): pass

    gateway = Gateway()
    server = CoreLinkServer(CoreLinkServerConfiguration('127.0.0.1',0,server_cert,server_key,ca,socket_timeout_seconds=3),gateway)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        key_path = client_key if mode in {'active','bad_pin','inflight_revoke','revocation_cycle'} else tmp_path/'must-not-resolve-key.pem'
        args = [str(authority_probe),str(production_venv['python']),str(registry.path),str(selected.revision),
            selected_binding.endpoint_id,selected_binding.credential_ref,
            f'https://localhost:{server.address[1]}/v1/core-link',str(ca),str(client_cert),str(key_path)]
        if mode == 'revocation_cycle':
            import queue
            def line(stream):
                messages = queue.Queue()
                threading.Thread(target=lambda: messages.put(stream.readline()),daemon=True).start()
                return json.loads(messages.get(timeout=15))
            child = subprocess.Popen(args+['revocation-cycle'],cwd=production_venv['venv_root'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                assert line(child.stdout) == {'operation':'status','status':'completed'}
                original = registry.path.read_bytes()
                registry.transition(selected_binding.binding_id,expected_binding_revision=selected_binding.revision,
                    expected_store_revision=selected.revision,state=CoreLinkBindingState.REVOKED,
                    at=NOW+timedelta(seconds=3))
                child.stdin.write('x'); child.stdin.flush()
                assert line(child.stdout) == {'phase':'denied'}
                # Roll back disposable metadata after the client observed revocation.
                registry.path.write_bytes(original)
                out, err = child.communicate(input='x',timeout=15)
                assert child.returncode == 0, err
                assert json.loads(out) == {'phase':'rollback-denied'}
                assert gateway.count == gateway.completed == 1
                assert 'PRIVATE_STATUS_DO_NOT_LOG' not in out+err
            finally:
                if child.poll() is None: child.kill()
                child.wait(timeout=5)
            return
        result = subprocess.run(args,
            cwd=production_venv['venv_root'],capture_output=True,text=True,timeout=20)
        if mode == 'active':
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout) == {'operation':'status','status':'completed'}
        else:
            assert result.returncode != 0
            assert result.stdout == ''
            assert 'fixture key unavailable' not in result.stderr
        assert gateway.count == (1 if mode in {'active','inflight_revoke'} else 0)
        assert gateway.completed == gateway.count
        if mode == 'inflight_revoke':
            assert registry.load().selected() is None
            assert registry.load().bindings[0].state is CoreLinkBindingState.REVOKED
        assert 'PRIVATE_STATUS_DO_NOT_LOG' not in result.stdout + result.stderr
    finally:
        server.close()
        thread.join(timeout=3)
