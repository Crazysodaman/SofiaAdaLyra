"""Long installation paths must retain private, authenticated local worker IPC."""
from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.run import LocalRunLeaseStore, ComponentGenerationStore
from sofia.platform.core_worker.process import CoreWorkerController, CoreEngineProcessSpec


@pytest.mark.skipif(os.name=='nt',reason='AF_UNIX path-length and mode contract')
def test_long_runtime_path_uses_private_short_socket_and_cleans_it(tmp_path):
    platform_id,core_id=str(uuid4()),str(uuid4())
    state=tmp_path/'platform.db'
    PlatformLocalStore(state,roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),host_identity=platform_id)
    now=datetime.now(timezone.utc)
    leases=LocalRunLeaseStore(state,lease_key='component-core')
    lease=leases.acquire(owner_id='test:long-ipc',now=now,ttl_seconds=300).lease
    controller=CoreWorkerController(generations=ComponentGenerationStore(state_path=state,lease_store=leases),
        lease=lease,platform_instance_id=platform_id,core_identity_id=core_id,component_id='test.long-ipc',
        runtime_dir=tmp_path/('long-installed-path-'+'a'*90))
    socket=None
    try:
        health=controller.start(release_digest='a'*64,spec=CoreEngineProcessSpec('test'),now=now)
        assert health.ready
        socket=controller._active._socket_path
        assert len(os.fsencode(socket))<=100
        assert socket.parent.stat().st_mode & 0o077 == 0
        assert controller._active._lifetime_lock_path.parent == controller.runtime_dir
    finally:
        controller.shutdown(now=datetime.now(timezone.utc))
        leases.release(lease,now=datetime.now(timezone.utc))
    assert socket is not None and not socket.parent.exists()
    assert not list(tmp_path.rglob('sofia.db'))


@pytest.mark.skipif(os.name=='nt',reason='AF_UNIX ownership and cleanup contract')
def test_failed_spawn_cleans_owned_short_channel_without_touching_existing_socket(tmp_path,monkeypatch):
    from sofia.sdk import ComponentEndpoint, ComponentKind
    from sofia.platform.core_worker.process import _CoreWorkerProcess, CoreWorkerError
    import sofia.platform.core_worker.process as implementation
    endpoint=ComponentEndpoint('test.private-ipc',ComponentKind.CORE,'a'*64,1,str(uuid4()),str(uuid4()))
    worker=_CoreWorkerProcess(endpoint=endpoint,spec=CoreEngineProcessSpec('test'),
        runtime_dir=tmp_path/('long-runtime-'+'b'*90))
    context=implementation.multiprocessing.get_context('spawn')
    def failed(self): raise RuntimeError('injected spawn failure')
    monkeypatch.setattr(type(context.Process()),'start',failed)
    with pytest.raises(RuntimeError,match='injected spawn failure'):
        worker.start()
    assert worker._socket_directory is None
    assert worker._listener is None
    assert worker.terminate(force=True)

    with TemporaryDirectory(prefix="aegis-own-", dir="/tmp") as directory:
        short=_CoreWorkerProcess(endpoint=endpoint,spec=CoreEngineProcessSpec('test'),runtime_dir=Path(directory))
        # A pre-existing endpoint belongs to another owner and must survive cleanup.
        short._socket_path.write_bytes(b'not owned by this attempted launch')
        with pytest.raises(CoreWorkerError,match='already exists'):
            short.start()
        assert short.terminate(force=True)
        assert short._socket_path.read_bytes()==b'not owned by this attempted launch'
