"""Actual SCM start/stop on disposable elevated Windows test runners only."""
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest

from test.test_rust_platform_service import service_environment
from test.test_component_install_production import component_wheels

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='native Windows SCM acceptance')


def wait_state(service, expected):
    import win32service
    deadline = time.monotonic()+20
    while win32service.QueryServiceStatus(service)[1] != expected:
        assert time.monotonic() < deadline, 'SCM transition exceeded deadline'
        time.sleep(.1)


def test_native_scm_core_free_start_stop(tmp_path, service_environment):
    import pywintypes
    import win32service
    python, binary = service_environment
    state_root = tmp_path/'system-owned'
    receipt = tmp_path/'public-bootstrap.json'
    bootstrap = tmp_path/'bootstrap.py'
    bootstrap.write_text('''
import importlib.util, json, sys
from pathlib import Path
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
assert importlib.util.find_spec('sofia.core') is None
assert importlib.util.find_spec('ollama') is None
root, receipt = map(Path, sys.argv[1:])
identity = InstallationIdentityStore(root/'identity').initialize()
PlatformLocalStore(root/'platform.db', roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
    host_identity=identity.identity.canonical_uuid)
receipt.write_text(json.dumps(identity.to_payload()))
''')
    task = 'Aegis-Test-'+uuid4().hex
    ps = tmp_path/'task.ps1'
    ps.write_text('''param($TaskName, $Python, $Arguments)
$ErrorActionPreference = 'Stop'
$action = New-ScheduledTaskAction -Execute $Python -Argument $Arguments
$principal = New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal | Out-Null
Start-ScheduledTask -TaskName $TaskName
''')
    manager = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
    service = None
    try:
        # Never stop, replace or adopt a service that this test did not create.
        try:
            existing = win32service.OpenService(manager, 'AegisPlatform', win32service.SERVICE_QUERY_STATUS)
        except pywintypes.error as error:
            assert error.winerror == 1060
        else:
            win32service.CloseServiceHandle(existing)
            pytest.fail('AegisPlatform already exists; refusing to modify it')
        arguments = subprocess.list2cmdline(['-I', str(bootstrap), str(state_root), str(receipt)])
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-File', str(ps),
            task, str(python), arguments], check=True, capture_output=True, text=True, timeout=30)
        deadline = time.monotonic()+30
        while not receipt.exists():
            assert time.monotonic() < deadline, 'SYSTEM fixture bootstrap did not finish'
            time.sleep(.1)
        public = json.loads(receipt.read_text())
        command = subprocess.list2cmdline([str(binary), '--scm', '--python', str(python),
            '--identity-home', str(state_root/'identity'), '--state', str(state_root/'platform.db'),
            '--platform-id', public['identity']['uuid'],
            '--public-key-sha256', public['public_key_sha256']])
        service = win32service.CreateService(manager, 'AegisPlatform', 'Aegis disposable SCM test',
            win32service.SERVICE_ALL_ACCESS, win32service.SERVICE_WIN32_OWN_PROCESS,
            win32service.SERVICE_DEMAND_START, win32service.SERVICE_ERROR_NORMAL, command)
        win32service.StartService(service, None)
        wait_state(service, win32service.SERVICE_RUNNING)
        win32service.ControlService(service, win32service.SERVICE_CONTROL_STOP)
        wait_state(service, win32service.SERVICE_STOPPED)
        assert win32service.QueryServiceStatus(service)[3] == 0
        # A second real SCM launch must reuse identity and advance durable lease.
        win32service.StartService(service, None)
        wait_state(service, win32service.SERVICE_RUNNING)
        win32service.ControlService(service, win32service.SERVICE_CONTROL_STOP)
        wait_state(service, win32service.SERVICE_STOPPED)
        assert win32service.QueryServiceStatus(service)[3] == 0
        assert not list(state_root.rglob('sofia.db'))
    finally:
        try:
            if service is not None:
                try:
                    if win32service.QueryServiceStatus(service)[1] != win32service.SERVICE_STOPPED:
                        win32service.ControlService(service, win32service.SERVICE_CONTROL_STOP)
                        wait_state(service, win32service.SERVICE_STOPPED)
                finally:
                    try:
                        win32service.DeleteService(service)
                    finally:
                        win32service.CloseServiceHandle(service)
        finally:
            win32service.CloseServiceHandle(manager)
            # Only the freshly generated disposable bootstrap task is stopped.
            cleanup = tmp_path/'cleanup.ps1'
            cleanup.write_text("param($TaskName)\nStop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue\nUnregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue\n")
            subprocess.run(['powershell','-NoProfile','-NonInteractive','-File',str(cleanup),task],
                capture_output=True, timeout=30)
