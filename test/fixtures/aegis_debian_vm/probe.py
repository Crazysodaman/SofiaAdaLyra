"""Offline disposable-VM receipt; never a release or production authorization."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

SOURCE=json.loads(Path('/opt/aegis/test-inputs.json').read_text())['source_sha']
UNIT='aegis-platform.service'

def command(*args):
    value=subprocess.run(args,check=True,capture_output=True,text=True,timeout=40)
    return value.stdout

def ready(previous=None):
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        values=dict(line.split('=',1) for line in command('systemctl','show',UNIT,'--property=ActiveState,SubState,MainPID').splitlines())
        pid=int(values.get('MainPID','0'))
        if values.get('ActiveState')=='active' and values.get('SubState')=='running' and pid and pid!=previous:
            for line in reversed(command('journalctl','-u',UNIT,'-o','cat','--no-pager','-n','40').splitlines()):
                if line.startswith('{'):
                    row=json.loads(line)
                    if row.get('phase')=='ready' and row.get('supervisor_pid')==pid:
                        return row
        time.sleep(.1)
    raise AssertionError('VM service readiness deadline')

def stop(row):
    command('systemctl','stop',UNIT)
    values=dict(line.split('=',1) for line in command('systemctl','show',UNIT,'--property=ActiveState,Result,ExecMainStatus').splitlines())
    assert values=={'ActiveState':'inactive','Result':'success','ExecMainStatus':'0'},values
    assert all(not Path('/proc',str(row[key])).exists() for key in ('supervisor_pid','worker_pid'))

try:
    assert Path('/proc/1/comm').read_text().strip()=='systemd'
    assert 'VERSION_ID="12"' in Path('/etc/os-release').read_text()
    assert sys.version_info[:2]==(3,12)
    assert importlib.util.find_spec('sofia.core') is None
    assert importlib.util.find_spec('ollama') is None
    public=json.loads(Path('/opt/aegis/identity-reference.json').read_text())
    first=ready()
    duplicate=subprocess.run(['runuser','-u','aegis','--','/opt/aegis/bin/aegis-platform-service',
        '--python','/usr/local/bin/python3.12','--identity-home','/var/lib/aegis/identity',
        '--state','/var/lib/aegis/platform.db','--platform-id',public['identity']['uuid'],
        '--public-key-sha256',public['public_key_sha256']],capture_output=True,text=True,timeout=15)
    assert duplicate.returncode==2 and not duplicate.stdout
    assert ready()['supervisor_pid']==first['supervisor_pid']
    stop(first)
    command('systemctl','start',UNIT)
    second=ready(first['supervisor_pid'])
    command('systemctl','kill','--kill-whom=main','--signal=SIGKILL',UNIT)
    third=ready(second['supervisor_pid'])
    stop(third)
    assert first['generation']<second['generation']<third['generation']
    assert all(row['platform_id']==public['identity']['uuid'] for row in (first,second,third))
    restored=json.loads(command('runuser','-u','aegis','--','/usr/local/bin/python3.12','-I','-c',
        'import json; from pathlib import Path; from sofia.platform.state.installation_identity import InstallationIdentityStore; print(json.dumps(InstallationIdentityStore(Path("/var/lib/aegis/identity")).load().to_payload()))'))
    assert restored==public
    assert not list(Path('/var/lib/aegis').rglob('sofia.db'))
    receipt=dict(schema='aegis.disposable.debian12-vm.v1',result='PASS',source_sha=SOURCE,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        platform_id=public['identity']['uuid'],public_key_sha256=public['public_key_sha256'],
        generations=[row['generation'] for row in (first,second,third)],
        python=sys.version.split()[0],kernel=command('uname','-r').strip(),pid1='systemd',os_version='12',core_installed=False,ollama_installed=False,
        graceful_stops=2,crash_recovered=True,duplicate_denied=True,production_authorized=False,release_accepted=False)
except Exception as error:
    receipt=dict(schema='aegis.disposable.debian12-vm.v1',result='FAIL',error_type=type(error).__name__,
        source_sha=SOURCE,production_authorized=False,release_accepted=False)
print('AEGIS_VM_RESULT '+json.dumps(receipt,sort_keys=True),flush=True)
subprocess.run(['systemctl','poweroff'],check=True,timeout=30)
