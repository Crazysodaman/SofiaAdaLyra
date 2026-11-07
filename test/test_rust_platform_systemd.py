"""Real systemd contract on an explicitly opted-in disposable Linux CI host.

Ordinary test runs must never provision accounts/services on a developer host.
The native CI job opts in and fails, rather than skips, if its OS is unavailable.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest

from test.test_rust_platform_service import service_environment
from test.test_component_install_production import component_wheels

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.environ.get('AEGIS_REQUIRE_SYSTEMD_ACCEPTANCE') != '1',
    reason='requires explicitly opted-in disposable systemd CI host')


def root_command(*arguments, check=True):
    result = subprocess.run(['sudo', '-n', *map(str, arguments)], check=False,
        capture_output=True, text=True, timeout=45)
    if check:
        assert result.returncode == 0, result.stderr[:4096]
    return result


def properties(unit):
    response = root_command('systemctl', 'show', unit, '--property=ActiveState,SubState,MainPID,ExecMainStatus,Result')
    return dict(line.split('=', 1) for line in response.stdout.splitlines() if '=' in line)


def ready_receipt(unit, previous_pid=None):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        current = properties(unit)
        if current.get('ActiveState') == 'active' and current.get('SubState') == 'running':
            pid = int(current['MainPID'])
            if pid > 0 and pid != previous_pid:
                journal = root_command('journalctl', '--unit', unit, '--output=cat', '--no-pager', '-n', '50')
                for line in reversed(journal.stdout.splitlines()):
                    if line.startswith('{'):
                        value = json.loads(line)
                        if value.get('phase') == 'ready' and value.get('supervisor_pid') == pid:
                            return value
        time.sleep(.1)
    pytest.fail('systemd did not publish verified readiness within deadline')


def assert_stopped(unit, receipt):
    root_command('systemctl', 'stop', unit)
    current = properties(unit)
    assert current['ActiveState'] == 'inactive', current
    assert current['Result'] == 'success', current
    assert current['ExecMainStatus'] == '0', current
    for field in ('supervisor_pid', 'worker_pid'):
        assert not Path('/proc', str(receipt[field])).exists(), f'{field} survived graceful stop'


def test_native_systemd_core_free_stop_restart_and_crash_recovery(tmp_path, service_environment):
    if os.environ.get('AEGIS_REQUIRE_SYSTEMD_ACCEPTANCE') != '1':
        pytest.skip('requires explicitly opted-in disposable systemd CI host')
    assert os.name == 'posix' and Path('/proc/1/comm').read_text().strip() == 'systemd', 'native systemd host required'
    assert root_command('true', check=False).returncode == 0, 'noninteractive test-host administration required'
    python, binary = service_environment
    token = uuid4().hex
    account = 'aegis-t-' + token[:12]
    name = 'aegis-test-' + token
    unit = name + '.service'
    runtime = Path('/opt') / name
    state = Path('/var/lib') / name
    config = Path('/etc') / name
    unit_path = Path('/etc/systemd/system') / unit
    # All names are generated here. Never adopt an existing account, service or path.
    assert root_command('getent', 'passwd', account, check=False).returncode == 2
    for target in (runtime, state, config, unit_path):
        assert root_command('test', '-e', target, check=False).returncode == 1
        assert root_command('test', '-L', target, check=False).returncode == 1
    account_created = unit_created = False
    forced_cleanup = False
    roots_created = []
    try:
        root_command('useradd', '--system', '--user-group', '--no-create-home', '--home-dir', state,
            '--shell', '/usr/sbin/nologin', account)
        account_created = True
        for directory in (runtime, state, config):
            root_command('install', '-d', '-m', '0755' if directory == runtime else '0700', directory)
            roots_created.append(directory)
        root_command('chown', account + ':' + account, state)
        # Copy only the independently installed SDK/Platform environment; no Core.
        root_command('cp', '-a', python.parent.parent, runtime / 'runtime')
        root_command('chmod', '-R', 'a+rX', runtime / 'runtime')
        root_command('install', '-m', '0755', binary, runtime / 'aegis-platform-service')
        installed_python = runtime / 'runtime/bin/python'
        bootstrap = tmp_path / 'bootstrap.py'
        bootstrap.write_text('''
import importlib.util, json, sys
from pathlib import Path
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
assert importlib.util.find_spec('sofia.core') is None
assert importlib.util.find_spec('ollama') is None
root = Path(sys.argv[1])
identity = InstallationIdentityStore(root/'identity').initialize()
PlatformLocalStore(root/'platform.db', roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
    host_identity=identity.identity.canonical_uuid)
print(json.dumps(identity.to_payload()))
''')
        root_command('install', '-m', '0644', bootstrap, runtime / 'bootstrap.py')
        public = json.loads(root_command('runuser', '-u', account, '--', installed_python,
            '-I', runtime / 'bootstrap.py', state).stdout)
        # Public metadata only; no private Platform key or owner secret is exported.
        platform_id = public['identity']['uuid']
        environment = tmp_path / 'service.env'
        environment.write_text('\n'.join((
            f'AEGIS_PYTHON={installed_python}', f'AEGIS_IDENTITY_HOME={state}/identity',
            f'AEGIS_LOCAL_STATE={state}/platform.db', f'AEGIS_PLATFORM_ID={platform_id}',
            f"AEGIS_PUBLIC_KEY_SHA256={public['public_key_sha256']}", '')))
        root_command('install', '-m', '0600', environment, config / 'service.env')
        source = (ROOT / 'packaging/services/aegis-platform.service').read_text()
        for before, after in (
            ('/etc/aegis/platform-service.env', str(config / 'service.env')),
            ('/var/lib/aegis', str(state)),
            ('/opt/aegis/bin/aegis-platform-service', str(runtime / 'aegis-platform-service')),
            ('User=aegis\n', f'User={account}\n'), ('Group=aegis\n', f'Group={account}\n'),
            ('StateDirectory=aegis\n', f'StateDirectory={name}\n'),
            ('RuntimeDirectory=aegis\n', f'RuntimeDirectory={name}\n')):
            assert before in source
            source = source.replace(before, after)
        candidate = tmp_path / unit
        candidate.write_text(source)
        root_command('install', '-m', '0644', candidate, unit_path)
        unit_created = True
        root_command('systemctl', 'daemon-reload')
        root_command('systemctl', 'start', unit)
        first = ready_receipt(unit)
        assert first['platform_id'] == platform_id
        assert_stopped(unit, first)
        root_command('systemctl', 'start', unit)
        second = ready_receipt(unit, first['supervisor_pid'])
        assert second['generation'] > first['generation']
        # Crash only this owned unit; systemd's production Restart policy must recover.
        root_command('systemctl', 'kill', '--kill-whom=main', '--signal=SIGKILL', unit)
        third = ready_receipt(unit, second['supervisor_pid'])
        assert third['platform_id'] == platform_id
        assert third['generation'] > second['generation']
        assert_stopped(unit, third)
        reloaded = root_command('runuser', '-u', account, '--', installed_python, '-I', '-c',
            'import json,sys; from sofia.platform.state.installation_identity import InstallationIdentityStore; print(json.dumps(InstallationIdentityStore(sys.argv[1]).load().to_payload()))',
            state / 'identity')
        assert json.loads(reloaded.stdout) == public
        assert not root_command('find', state, '-name', 'sofia.db', '-print').stdout.strip()
    finally:
        if unit_created:
            stopped = root_command('systemctl', 'stop', unit, check=False)
            if stopped.returncode:
                forced_cleanup = True
                # Failed acceptance may need bounded cleanup; this never counts as a pass.
                root_command('systemctl', 'kill', '--kill-whom=all', '--signal=SIGKILL', unit, check=False)
                root_command('systemctl', 'stop', unit, check=False)
            root_command('rm', '--', unit_path)
            root_command('systemctl', 'daemon-reload')
            root_command('systemctl', 'reset-failed', unit, check=False)
        for directory in reversed(roots_created):
            root_command('rm', '-rf', '--', directory)
        if account_created:
            root_command('userdel', account)
            if root_command('getent', 'group', account, check=False).returncode == 0:
                root_command('groupdel', account)
        assert not forced_cleanup, 'acceptance required forced cleanup and cannot pass'
