"""Disposable AF_UNIX test listener: NOT a signed installed B1 service."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import socket
import threading
import sys
import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux SO_PEERCRED IPC")

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import make_response
from sofia.sdk.platform_management_client import read_linux_platform_status

@contextmanager
def synthetic_service(tmp_path, mode='OK'):
    home=tmp_path/'private';home.mkdir(mode=0o700);home.chmod(0o700)
    path=home/'mgmt-3.sock'
    listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    old=os.umask(0o077)
    try: listener.bind(str(path))
    finally: os.umask(old)
    path.chmod(0o600)  # Production ManagementUnixListener applies 0600 after bind.
    listener.listen(1)
    listener.settimeout(2)
    obs=[]
    ready=threading.Event()
    def serve():
        ready.set()
        try:
            connection,_=listener.accept()
            with connection:
                if mode=='EOF':return
                raw=b''
                while not raw.endswith(b'\n'):
                    block=connection.recv(4096)
                    if not block:return
                    raw+=block
                req=UntrustedManagementRead.parse(raw[:-1],now=datetime.now(timezone.utc))
                obs.append(req)
                now=datetime.now(timezone.utc)
                if mode=='STOPPED':body=make_response(req,observed_at=now,denial_code='STOPPED')
                else:
                    body=make_response(req,observed_at=now,data=dict(platform_id=req.target_platform_id,generation=req.expected_generation,operator_stop=False,core_started=False))
                if mode=='FORGED_GENERATION': body['platform_generation']=8
                if mode=='EXTRA_REPLY':connection.sendall(json.dumps(body).encode()+b'\n{}\n');return
                connection.sendall(json.dumps(body).encode()+b'\n')
        except OSError:pass
    thread=threading.Thread(target=serve,daemon=True)
    thread.start();ready.wait(2)
    try: yield path,obs
    finally:
        listener.close();thread.join(timeout=3)
        path.unlink(missing_ok=True)


def query(path,**changes):
    kw=dict(socket_path=path,expected_platform_id='platform:alpha',expected_generation=3,installed_service_uid=os.getuid(),installed_service_gid=os.getgid(),installed_service_pid=os.getpid())
    kw.update(changes)
    return read_linux_platform_status(**kw)

def test_live_native_status_over_kernel_authenticated_socket(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        got=query(path)
        assert got.outcome=='OK' and got.data['generation']==3
        assert got.data['operator_stop'] is False and got.data['core_started'] is False
        assert len(observed)==1 and observed[0].operation=='platform.status'
        assert observed[0].request_id.startswith('req:')

def test_live_native_typed_stop_no_status_claim(tmp_path):
    with synthetic_service(tmp_path,'STOPPED') as (path,_):
        got=query(path)
        assert got.outcome=='DENIED' and got.denial_code=='STOPPED' and got.data is None

def test_native_revoke_like_EOF_fails_closed(tmp_path):
    with synthetic_service(tmp_path,'EOF') as (path,_):
        with pytest.raises(PermissionError,match='refused|unavailable'):
            query(path)

def test_native_wrong_signed_uid_denied_before_request(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        with pytest.raises(PermissionError,match='directory'):
            query(path,installed_service_uid=os.getuid()+10000)
        assert not observed

def test_native_wrong_signed_gid_denied_before_request(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        with pytest.raises(PermissionError,match='directory'):
            query(path,installed_service_gid=os.getgid()+10000)
        assert not observed

def test_native_wrong_signed_server_pid_denied_before_request(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        with pytest.raises(PermissionError,match='OS identity'):
            query(path,installed_service_pid=os.getpid()+10000)
        assert not observed

def test_native_forged_generation_is_not_live_status(tmp_path):
    with synthetic_service(tmp_path,'FORGED_GENERATION') as (path,_):
        with pytest.raises(PermissionError,match='uncorrelated'):
            query(path)

def test_native_unsafe_world_access_denied_before_request(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        path.chmod(0o666)
        with pytest.raises(PermissionError,match='socket inode'):
            query(path)
        assert not observed

def test_native_runtime_mode_does_not_widen(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        path.parent.chmod(0o755)
        with pytest.raises(PermissionError,match='runtime directory'):
            query(path)
        assert not observed

def test_native_socket_symlink_rejected_without_connect(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        alias=path.parent/'alias.sock'
        alias.symlink_to(path)
        with pytest.raises(PermissionError,match='redirection'):
            query(alias)
        assert not observed

def test_native_unsupported_mutation_request_is_not_emitted(tmp_path):
    with synthetic_service(tmp_path) as (path,observed):
        got=query(path)
        assert got.operation=='platform.status'
        assert len(observed)==1

def test_native_socket_absent_fails_closed(tmp_path):
    with pytest.raises((PermissionError,FileNotFoundError)):
        query(tmp_path/'does-not-exist'/'mgmt.sock')
