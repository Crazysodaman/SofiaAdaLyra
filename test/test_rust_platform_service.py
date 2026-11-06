"""Real Rust supervisor + actual installed Core-free Python state adapter."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading

import pytest

from test.test_component_install_production import component_wheels
from test.test_platform_service_session import provision

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def service_environment(tmp_path_factory, component_wheels):
    home = tmp_path_factory.mktemp('platform-service-venv')
    subprocess.run([sys.executable, '-m', 'venv', str(home)], check=True, capture_output=True)
    python = home / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    install = subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
        str(component_wheels['sdk']), str(component_wheels['platform'])],
        capture_output=True, text=True, timeout=300)
    assert install.returncode == 0, install.stderr
    verify = subprocess.run([str(python), '-I', '-c',
        "import importlib.util; assert importlib.util.find_spec('sofia.core') is None; assert importlib.util.find_spec('ollama') is None"],
        cwd=home, capture_output=True, text=True, timeout=30)
    assert verify.returncode == 0, verify.stderr
    subprocess.run(['cargo', 'build', '--locked', '-p', 'sofia-platform-lifecycle',
        '--bin', 'aegis-platform-service'], cwd=ROOT, check=True, capture_output=True, timeout=300)
    target = Path(os.environ.get('CARGO_TARGET_DIR', ROOT/'target'))
    return python, target/'debug'/('aegis-platform-service.exe' if os.name == 'nt' else 'aegis-platform-service')


def line(stream):
    replies = queue.Queue()
    threading.Thread(target=lambda: replies.put(stream.readline()), daemon=True).start()
    raw = replies.get(timeout=15)
    assert raw, 'supervisor exited before readiness'
    return json.loads(raw)


def arguments(service_environment, identity, current, state):
    python, binary = service_environment
    return [str(binary), '--python', str(python), '--identity-home', str(identity.home),
        '--state', str(state), '--platform-id', current.identity.canonical_uuid,
        '--public-key-sha256', current.public_key_sha256]


def test_installed_rust_service_stops_gracefully_and_excludes_duplicate(tmp_path, service_environment):
    identity, current, state = provision(tmp_path)
    args = arguments(service_environment, identity, current, state)
    child = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
    try:
        ready = line(child.stdout)
        assert ready['phase'] == 'ready'
        assert ready['supervisor_pid'] == child.pid
        assert ready['platform_id'] == current.identity.canonical_uuid
        duplicate = subprocess.run(args, capture_output=True, text=True, timeout=15)
        assert duplicate.returncode == 2
        assert duplicate.stdout == ''
        child.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGTERM)
        out, err = child.communicate(timeout=15)
        assert child.returncode == 0, err
        assert 'failed closed' not in out+err
        assert identity.load() == current
        assert not list(tmp_path.rglob('sofia.db'))
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_installed_rust_service_does_not_claim_ready_with_wrong_identity(tmp_path, service_environment):
    identity, current, state = provision(tmp_path)
    args = arguments(service_environment, identity, current, state)
    args[-1] = '0'*64
    result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert result.stdout == ''
    assert identity.load() == current


def test_abrupt_supervisor_exit_releases_adapter_and_allows_new_generation(tmp_path, service_environment):
    identity, current, state = provision(tmp_path)
    args = arguments(service_environment, identity, current, state)
    options = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
    child = subprocess.Popen(args, **options)
    try:
        first = line(child.stdout)
        child.kill()
        child.wait(timeout=5)
        # EOF releases the adapter's existing RUN lease and lifetime lock.
        import time
        from datetime import datetime, timezone
        from sofia.platform.run.lease import LocalRunLeaseStore
        leases = LocalRunLeaseStore(state, lease_key='platform-service')
        deadline = time.monotonic()+5
        while leases.current(now=datetime.now(timezone.utc)) is not None:
            assert time.monotonic() < deadline, 'orphaned service adapter retained authority'
            time.sleep(.02)
        replacement = subprocess.Popen(args, **options)
        try:
            second = line(replacement.stdout)
            assert second['generation'] > first['generation']
            replacement.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGTERM)
            _, err = replacement.communicate(timeout=15)
            assert replacement.returncode == 0, err
        finally:
            if replacement.poll() is None: replacement.kill()
            replacement.wait(timeout=5)
    finally:
        if child.poll() is None: child.kill()
        child.wait(timeout=5)


@pytest.mark.skipif(os.name == 'nt', reason='native Unix systemd notification socket')
def test_supervisor_notifies_ready_and_draining(tmp_path, service_environment):
    import socket
    identity, current, state = provision(tmp_path)
    path = str(tmp_path/'notify.sock')
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notify:
        notify.bind(path)
        notify.settimeout(15)
        env = os.environ.copy()
        env['NOTIFY_SOCKET'] = path
        child = subprocess.Popen(arguments(service_environment, identity, current, state),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            assert line(child.stdout)['phase'] == 'ready'
            assert notify.recv(4096).startswith(b'READY=1\n')
            child.send_signal(signal.SIGTERM)
            assert notify.recv(4096) == b'STOPPING=1'
            _, err = child.communicate(timeout=15)
            assert child.returncode == 0, err
        finally:
            if child.poll() is None: child.kill()
            child.wait(timeout=5)
