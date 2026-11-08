"""Privileged, DISPOSABLE Linux process/UID tests, not signed B1 or SAFE.

Run only on a disposable root Linux lab. The test-only policy in the server
is NOT canonical SAFE and never obtains or consumes an owner approval.
"""
from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile

import pytest

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import make_response

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or os.geteuid() != 0,
    reason="disposable Linux root account-namespace prerequisite",
)

SVC_UID, SVC_GID = 31041, 31041
OP_UID, OP_GID = 31042, 31042
DENIED_UID, DENIED_GID = 31043, 31043
MGMT_GID = 31044


def _serve(path: str, ready, stopped, revoked, generation):
    # Run the server under a genuine different kernel UID and supplementary GID.
    os.setgroups([MGMT_GID])
    os.setgid(SVC_GID)
    os.setuid(SVC_UID)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        prev = os.umask(0o117)
        try:
            sock.bind(path)
        finally:
            os.umask(prev)
        os.chown(path, SVC_UID, MGMT_GID)
        os.chmod(path, 0o660)
        sock.listen(5)
        sock.settimeout(0.2)
        ready.set()
        while stopped.value != 1:
            try:
                conn, _ = sock.accept()
            except socket.timeout:
                continue
            with conn:
                conn.settimeout(1)
                pid, uid, gid = struct.unpack(
                    '3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
                )
                if uid != OP_UID or gid != OP_GID or revoked.value:
                    continue  # Unknown or revoked peer receives EOF, not identity disclosure.
                raw = b''
                while not raw.endswith(b'\n'):
                    chunk = conn.recv(4096)
                    if not chunk or len(raw) + len(chunk) > 65536:
                        break
                    raw += chunk
                if not raw.endswith(b'\n'):
                    continue
                try:
                    req = UntrustedManagementRead.parse(raw[:-1], now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc))
                    if revoked.value:
                        continue
                    if stopped.value == 2:
                        reply = make_response(req, observed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc), denial_code='STOPPED')
                    elif req.expected_generation != generation.value:
                        reply = make_response(req, observed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc), denial_code='STALE_GENERATION')
                    else:
                        reply = make_response(req, observed_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc), data={
                            'platform_id':req.target_platform_id,
                            'generation':req.expected_generation,
                            'core_started':False,
                            'operator_stop':False,
                        })
                    conn.sendall(json.dumps(reply, separators=(',', ':')).encode()+b'\n')
                except (PermissionError, ValueError, BrokenPipeError, OSError):
                    pass
    finally:
        sock.close()
        try: os.unlink(path)
        except FileNotFoundError: pass


def _as_uid(uid: int, gid: int, groups: list[int], path: Path,
            service_pid: int, generation: int, socket_group: int | None = MGMT_GID):
    def drop():
        os.setgroups(groups)
        os.setgid(gid)
        os.setuid(uid)
    args={
        'socket_path':str(path), 'expected_platform_id':'platform:alpha',
        'expected_generation':generation, 'installed_service_uid':SVC_UID,
        'installed_service_gid':SVC_GID, 'installed_service_pid':service_pid,
        'installed_socket_group_gid':socket_group,
    }
    script = '''import json,sys\nfrom pathlib import Path\nfrom sofia.sdk.platform_management_client import read_linux_platform_status\na=json.loads(sys.argv[1]);a['socket_path']=Path(a['socket_path'])\ntry:\n x=read_linux_platform_status(**a)\n print(json.dumps({'result':'OK' if x.outcome=='OK' else 'DENIED','code':x.denial_code,'gen':x.generation,'id':x.request_id,'data':x.data}))\nexcept Exception as e:\n print(json.dumps({'result':'REFUSED','exception':type(e).__name__}))\n'''
    env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
    p=subprocess.run([sys.executable, '-c', script, json.dumps(args)],
                     text=True,capture_output=True,timeout=5,preexec_fn=drop,env=env)
    assert p.returncode==0,(p.returncode,p.stderr)
    return json.loads(p.stdout)


def test_real_kernel_cross_uid_operator_socket_and_negative_policy():
    """Real separate Linux UIDs; synthetic local grant, not canonical SAFE."""
    ctx=multiprocessing.get_context('fork')
    root=Path(tempfile.mkdtemp(prefix='aegis-a010-', dir='/tmp'))
    runtime=root/'runtime'
    try:
        os.chmod(root,0o755)
        runtime.mkdir(mode=0o750)
        os.chown(runtime,SVC_UID,MGMT_GID)
        os.chmod(runtime,0o750)
        path=runtime/'mgmt.sock'
        ready=ctx.Event()
        stop=ctx.Value('i',0)
        revoke=ctx.Value('i',0)
        generation=ctx.Value('i',3)
        proc=ctx.Process(target=_serve,args=(str(path),ready,stop,revoke,generation))
        proc.start()
        assert ready.wait(4),'separate-UID service did not open socket'
        assert proc.is_alive()
        def call(uid=OP_UID,gid=OP_GID,groups=[MGMT_GID],gen=3,pid=None,group=MGMT_GID):
            return _as_uid(uid,gid,groups,path,proc.pid if pid is None else pid,gen,group)
        permitted=call()
        assert permitted['result']=='OK' and permitted['gen']==3 and permitted['data']['core_started'] is False
        # Group membership alone is NOT enrollment: server rejects this UID with EOF.
        wrong_group_member=call(uid=DENIED_UID,gid=DENIED_GID)
        assert wrong_group_member['result']=='REFUSED'
        # No group membership is rejected by OS before disclosing a reply.
        denied_os=call(uid=DENIED_UID,gid=DENIED_GID,groups=[])
        assert denied_os['result']=='REFUSED'
        wrong_group_pin=call(group=None)
        assert wrong_group_pin['result']=='REFUSED'
        revoke.value=1
        revoked=call()
        assert revoked['result']=='REFUSED'
        revoke.value=0
        stop.value=2
        stopped=call()
        assert stopped['result']=='DENIED' and stopped['code']=='STOPPED'
        stop.value=0
        generation.value=4
        stale=call()
        assert stale['result']=='DENIED' and stale['code']=='STALE_GENERATION'
        renewed=call(gen=4)
        assert renewed['result']=='OK'
        # Existing B owner-private runtime may never be silently shared.
        runtime.chmod(0o700)
        private_refused=call(gen=4)
        assert private_refused['result']=='REFUSED'
        runtime.chmod(0o750)
        assert call(gen=4)['result']=='OK'
        first_pid=proc.pid
        stop.value=1
        proc.join(timeout=3)
        assert proc.exitcode==0
        # Actual OS process restart with a NEW PID and RUN generation.
        ready=ctx.Event()
        stop=ctx.Value('i',0)
        generation=ctx.Value('i',5)
        proc=ctx.Process(target=_serve,args=(str(path),ready,stop,revoke,generation))
        proc.start()
        assert ready.wait(4) and proc.is_alive() and proc.pid!=first_pid
        old_pid_fenced=call(gen=5,pid=first_pid)
        assert old_pid_fenced['result']=='REFUSED'
        old_gen_fenced=call(gen=4)
        assert old_gen_fenced['result']=='DENIED' and old_gen_fenced['code']=='STALE_GENERATION'
        restarted=call(gen=5)
        assert restarted['result']=='OK' and restarted['gen']==5
        print('CROSS_UID',json.dumps({
            'service_pid':proc.pid,'service_uid':SVC_UID,'service_primary_gid':SVC_GID,
            'socket_group_gid':MGMT_GID,'operator_uid':OP_UID,'operator_gid':OP_GID,
            'private_0750_group_0660':True,'success':permitted,'wrong_uid':wrong_group_member,
            'outside_group':denied_os,'wrong_socket_pin':wrong_group_pin,
            'revoked':revoked,'stopped':stopped,'stale':stale,'renewed':renewed,
            'owner_private_refused':private_refused, 'old_pid_fenced':old_pid_fenced,
            'old_generation_after_restart':old_gen_fenced,'restarted':restarted,
        },sort_keys=True),flush=True)
        stop.value=1
        proc.join(timeout=3)
        assert proc.exitcode==0,proc.exitcode
    finally:
        if 'proc' in locals() and proc.is_alive():
            stop.value=1
            proc.terminate()
            proc.join(2)
        shutil.rmtree(root,ignore_errors=True)
