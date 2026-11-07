"""Disposable installer-cache regressions; artifact metadata grants no authority."""
from hashlib import sha256
import os
import subprocess

import pytest

from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact, PlatformKind

pytestmark = pytest.mark.pkg_ops


def artifact(data):
    return PlatformArtifact('synthetic', '1.0.0', PlatformKind.LINUX, 'x86_64',
        sha256(data).hexdigest(), 'disposable-release-key', True, 'fixture')


def redirect(link, target):
    if os.name == 'nt':
        subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],check=True,capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def test_reimport_must_not_report_success_for_corrupted_existing_cache(tmp_path):
    source=tmp_path/'source.whl'
    source.write_bytes(b'authenticated bytes fixture')
    value=artifact(source.read_bytes())
    cache=OfflineArtifactCache(tmp_path/'cache')
    stored=cache.import_artifact(value,source)
    stored.write_bytes(b'corrupted prior cache')
    with pytest.raises((OSError,ValueError,RuntimeError)):
        cache.import_artifact(value,source)
    assert stored.read_bytes()==b'corrupted prior cache'


def test_source_ancestor_redirect_is_rejected_before_cache_publication(tmp_path):
    actual=tmp_path/'actual'
    actual.mkdir()
    source=actual/'source.whl'
    source.write_bytes(b'fixture')
    link=tmp_path/'redirect'
    redirect(link,actual)
    cache=OfflineArtifactCache(tmp_path/'cache')
    with pytest.raises((OSError,ValueError,RuntimeError)):
        cache.import_artifact(artifact(b'fixture'),link/'source.whl')
    assert not list(cache.root.iterdir())


def test_redirected_cache_ancestor_cannot_be_created_or_adopted(tmp_path):
    actual=tmp_path/'actual'
    actual.mkdir()
    link=tmp_path/'redirect'
    redirect(link,actual)
    with pytest.raises((OSError,ValueError,RuntimeError)):
        OfflineArtifactCache(link/'cache')
    assert not (actual/'cache').exists()


def test_publication_failure_keeps_existing_data_and_removes_own_partial(tmp_path, monkeypatch):
    import sofia.platform.ops.platform_install as installation
    source=tmp_path/'source.whl'
    source.write_bytes(b'fixture')
    value=artifact(b'fixture')
    cache=OfflineArtifactCache(tmp_path/'cache')
    destination=cache.root/value.sha256
    def fail(source, target):
        target.write_bytes(b'concurrent data must survive')
        raise FileExistsError('injected competing publication')
    monkeypatch.setattr(installation.os, 'link', fail)
    with pytest.raises(FileExistsError):
        cache.import_artifact(value,source)
    assert destination.read_bytes()==b'concurrent data must survive'
    assert not list(cache.root.glob('.artifact-*'))


def test_write_failure_never_publishes_success_or_leaves_partial(tmp_path, monkeypatch):
    import sofia.platform.ops.platform_install as installation
    source=tmp_path/'source.whl'
    source.write_bytes(b'fixture')
    cache=OfflineArtifactCache(tmp_path/'cache')
    def fail(*args):
        raise OSError('injected disk failure')
    monkeypatch.setattr(installation.os, 'fsync', fail)
    with pytest.raises(OSError):
        cache.import_artifact(artifact(b'fixture'),source)
    assert not (cache.root/artifact(b'fixture').sha256).exists()
    assert not list(cache.root.glob('.artifact-*'))


def test_separate_process_cannot_enter_cache_while_import_lock_is_owned(tmp_path):
    from pathlib import Path
    import sys
    from sofia.platform.run.process_lock import StateProcessLock
    cache=OfflineArtifactCache(tmp_path/'cache')
    lock=StateProcessLock(cache.root/'cache',resource='platform-cache',lock_directory=cache.root)
    environment={'PATH':os.defpath,'PYTHONPATH':str(Path(__file__).parents[1]/'src')}
    for name in ('SystemRoot','WINDIR','TEMP','TMP'):
        if name in os.environ: environment[name]=os.environ[name]
    code='''import sys
from pathlib import Path
from sofia.platform.run.process_lock import StateProcessLock
root=Path(sys.argv[1])
lock=StateProcessLock(root/'cache',resource='platform-cache',lock_directory=root)
try:
    lock.acquire()
except RuntimeError:
    print('BLOCKED')
else:
    lock.release()
    print('ACQUIRED')
'''
    def run():
        return subprocess.run([sys.executable,'-c',code,str(cache.root)],env=environment,
            capture_output=True,text=True,check=True,timeout=15).stdout.strip()
    with lock:
        assert run()=='BLOCKED'
    assert run()=='ACQUIRED'


@pytest.mark.skipif(os.name!='posix',reason='POSIX mode compatibility; Windows uses owner DACL contract')
def test_unsafe_existing_cache_is_rejected_without_changing_permissions(tmp_path):
    root=tmp_path/'cache'
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(PermissionError):
        OfflineArtifactCache(root)
    assert root.stat().st_mode & 0o777==0o755
