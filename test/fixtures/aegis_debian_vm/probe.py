"""Offline disposable-VM receipt; never a release or production authorization."""
from hashlib import sha256
import importlib.util
import zipfile
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

# Never power off or manage services outside the explicitly marked lab guest.
if sys.platform!='linux' or 'aegis.disposable_vm=1' not in Path('/proc/cmdline').read_text().split():
    raise SystemExit('explicit disposable VM kernel marker required')
INPUTS=json.loads(Path('/opt/aegis/test-inputs.json').read_text())
if INPUTS.get('production_authorized') is not False or INPUTS.get('release_accepted') is not False:
    raise SystemExit('disposable-only VM input scope required')
SOURCE=INPUTS['source_sha']
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
    # A missing restart is a real failure, not permission to extend the gate.
    # Report bounded systemd state (not journal payloads or private identity)
    # so we can distinguish start-limit, failed process, and stale observation.
    observed={}
    try:
        lines=command('systemctl','show',UNIT,
            '--property=ActiveState,SubState,Result,MainPID,NRestarts,ExecMainStatus,ExecMainCode').splitlines()
        for line in lines:
            if '=' not in line: continue
            key,value=line.split('=',1)
            if key in {'ActiveState','SubState','Result','MainPID','NRestarts','ExecMainStatus','ExecMainCode'}:
                observed[key]=value[:96]
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        observed={'observation':'unavailable'}
    # A bounded failure summary without service stdout, environment, tokens,
    # full journal messages or private identity. Never change the 45s deadline.
    try:
        status=command('systemctl','show',UNIT,
            '--property=LoadState,UnitFileState,ConditionResult,AssertResult,ActiveState,SubState,Result,MainPID,NRestarts,ExecMainStatus,ExecMainCode').splitlines()
        for line in status:
            if '=' not in line: continue
            key,value=line.split('=',1)
            if key in {'LoadState','UnitFileState','ConditionResult','AssertResult'}:
                observed[key]=value[:96]
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        observed['unit_metadata']='unavailable'
    # Does systemd think the service was ever activated? Count records
    # without including any journal payloads, which may include sensitive state.
    try:
        journal=command('journalctl','-u',UNIT,'--no-pager','-o','short-unix','-n','60')
        observed['journal_record_count']=len(journal.splitlines())
        observed['journal_has_ready_phase']=any(
            '"phase": "ready"' in line or '"phase":"ready"' in line
            for line in journal.splitlines())
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        observed['journal_observation']='unavailable'
    # Inspect only allowlisted class labels from Rust's bounded error line.
    # Never publish full guest journals, paths, environment or secrets.
    startup_classes=[]
    try:
        for line in command('journalctl','-u',UNIT,'-o','cat',
                            '--no-pager','-n','120').splitlines():
            if not line.startswith('Platform service failed closed:'):
                continue
            detail=line.split(':',1)[1].strip().lower()
            if 'timed out waiting on channel' in detail:
                label='worker_startup_deadline'
            elif 'abstract notify socket unsupported' in detail:
                label='unsupported_systemd_notify_address'
            elif 'canonical platform service unavailable' in detail:
                label='worker_process_unavailable'
            elif 'service lifetime binding differs' in detail:
                label='worker_lifetime_mismatch'
            elif 'service identity response differs' in detail:
                label='worker_identity_mismatch'
            elif 'no such file or directory' in detail:
                label='missing_installed_file'
            elif 'permission denied' in detail:
                label='service_permission_denied'
            else:
                label='other_supervisor_startup_failure'
            startup_classes.append(label)
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        startup_classes.append('service_journal_unavailable')
    raise AssertionError('VM service readiness deadline: '+json.dumps(
        {'previous_pid':previous,'systemd':observed,
         'startup_error_classes':startup_classes[-8:]},sort_keys=True))

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
    from sofia.platform.ops.platform_release import PlatformReleaseVerifier
    from sofia.platform.state.artifact_file import read_artifact_file
    from sofia.platform.verify.python_runtime import verify_python_runtime,probe_materialized_python
    from sofia.sdk.platform_release import PlatformReleaseTarget
    root=Path('/opt/aegis/staged-release')
    envelope=json.loads(Path('/opt/aegis/test-release-envelope.json').read_text())
    assert envelope['disposable_only'] is True
    manifest=PlatformReleaseVerifier({envelope['signer_key_id']:envelope['public_key_pem'].encode()}).verify(
        envelope['manifest'],signature_b64=envelope['signature_b64'],signer_key_id=envelope['signer_key_id'],
        assets_root=root/'assets',expected_source_sha=SOURCE,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,minimum_revision=1)
    runtime=next(item.reference for item in manifest.assets if item.kind=='python-runtime')
    inventory=verify_python_runtime(root/'assets'/runtime.path,expected=runtime,
        target=manifest.target,python_version=manifest.python_version)
    assert probe_materialized_python(root/'runtime',inventory)['result']=='VERIFIED_RELOCATED_RUNTIME_PROCESS'
    service=next(item.reference for item in manifest.assets if item.kind=='service')
    assert read_artifact_file(Path('/opt/aegis/bin/aegis-platform-service'),service.size_bytes)[0]==service.sha256
    # Pip rewrites RECORD; every other SDK/Platform wheel-owned file must be exact.
    import sofia
    site=Path(sofia.__file__).parent.parent
    installed_files=0
    for item in manifest.assets:
        if item.kind not in {'sdk','platform'}: continue
        with zipfile.ZipFile(root/'assets'/item.reference.path) as archive:
            for member in archive.infolist():
                if member.is_dir() or member.filename.endswith('.dist-info/RECORD'): continue
                expected=archive.read(member)
                assert read_artifact_file(site/member.filename,len(expected))[0]==sha256(expected).hexdigest()
                installed_files+=1
    assert installed_files>0
    public=json.loads(Path('/opt/aegis/identity-reference.json').read_text())
    assert Path(sys.base_prefix)==Path('/opt/aegis/staged-release/runtime/python')
    first=ready()
    assert Path('/proc',str(first['worker_pid']),'exe').resolve()==Path('/opt/aegis/staged-release/runtime/python/bin/python3.12')
    duplicate=subprocess.run(['runuser','-u','aegis','--','/opt/aegis/bin/aegis-platform-service',
        '--python','/opt/aegis/venv/bin/python','--identity-home','/var/lib/aegis/identity',
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
    restored=json.loads(command('runuser','-u','aegis','--','/usr/bin/env','LD_LIBRARY_PATH=/opt/aegis/staged-release/runtime/python/lib','/opt/aegis/venv/bin/python','-B','-I','-c',
        'import json; from pathlib import Path; from sofia.platform.state.installation_identity import InstallationIdentityStore; print(json.dumps(InstallationIdentityStore(Path("/var/lib/aegis/identity")).load().to_payload()))'))
    assert restored==public
    assert not list(Path('/var/lib/aegis').rglob('sofia.db'))
    receipt=dict(schema='aegis.disposable.debian12-vm.v3',result='PASS',source_sha=SOURCE,
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        platform_id=public['identity']['uuid'],public_key_sha256=public['public_key_sha256'],
        generations=[row['generation'] for row in (first,second,third)],
        python=sys.version.split()[0],kernel=command('uname','-r').strip(),pid1='systemd',os_version='12',core_installed=False,ollama_installed=False,
        bundled_runtime=True,verified_release_staged=True,release_manifest_sha256=manifest.digest,installed_component_files=installed_files,graceful_stops=2,crash_recovered=True,duplicate_denied=True,production_authorized=False,release_accepted=False)
except Exception as error:
    receipt=dict(schema='aegis.disposable.debian12-vm.v3',result='FAIL',error_type=type(error).__name__,
        source_sha=SOURCE,error_traceback=traceback.format_exc()[-4096:],production_authorized=False,release_accepted=False)
print('AEGIS_VM_RESULT '+json.dumps(receipt,sort_keys=True),flush=True)
subprocess.run(['systemctl','poweroff'],check=True,timeout=30)
