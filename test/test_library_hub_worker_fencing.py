"""D028 owner-only Hub worker is explicitly started and RUN-drained.

These unit tests exercise a real Platform local lease/process fence with
synthetic Hub workers. They do not claim signed installed-host or live
mTLS acceptance, and they do not create any production owner approval.
"""
from __future__ import annotations

from threading import Event, Lock, Thread
import time

import pytest

from sofia.platform.ops.library_chunk_receiver import ChunkTransferRejected
from sofia.platform.run.library_host_service import HostedLibraryHub
from sofia.platform.run.platform_service import PlatformServiceSession
from test.test_platform_service_session import provision


def _synthetic_worker(*, serve):
    class DummyListener:
        _timeout = 1
        closed = False

        def close(self):
            self.closed = True

    hub = object.__new__(HostedLibraryHub)
    hub._hub = DummyListener()
    hub._closed = False
    hub._serve_stop = Event()
    hub._serve_lock = Lock()
    hub._serve_thread = None
    hub._serve_successes = 0
    hub._serve_bytes = 0
    hub._serve_rejections = 0
    hub._serve_error = None
    hub._hub_grant = lambda: True
    hub._current_publisher = lambda _: True
    hub.transfer = object()
    hub.serve_once = serve
    return hub


def test_worker_requires_explicit_start_and_bounded_success_budget():
    hub = _synthetic_worker(serve=lambda: 131)
    assert hub.serving_status()["state"] == "OPEN_IDLE"
    assert hub._serve_thread is None
    hub.start_bounded_serving(max_connections=3)
    assert hub._serve_thread is not None
    hub._serve_thread.join(timeout=3)
    assert not hub._serve_thread.is_alive()
    snapshot = hub.serving_status()
    assert snapshot["state"] == "CLOSED"
    assert snapshot["served_chunks"] == 3
    assert snapshot["served_bytes"] == 393
    assert snapshot["rejected_connections"] == 0
    assert hub._hub.closed is True
    with pytest.raises(ChunkTransferRejected):
        hub.start_bounded_serving(max_connections=1)


def test_worker_bounds_bad_connections_without_exposing_peer_failures():
    hub = _synthetic_worker(
        serve=lambda: (_ for _ in ()).throw(
            ChunkTransferRejected("untrusted TLS credentials and user secret"),
        ),
    )
    hub.start_bounded_serving(max_connections=10, max_rejections=3)
    hub._serve_thread.join(timeout=3)
    state = hub.serving_status()
    assert state["state"] == "CLOSED"
    assert state["served_bytes"] == 0
    assert state["rejected_connections"] == 3
    assert state["last_failure_code"] == "REJECTION_BUDGET_EXHAUSTED"
    assert "secret" not in str(state)


def test_supervised_hub_closes_immediately_on_dead_listener():
    calls = []
    def dead():
        calls.append(True)
        raise ChunkTransferRejected("Hub listener failed")
    hub = _synthetic_worker(serve=dead)
    hub.start_bounded_serving(max_connections=1000, max_rejections=64)
    hub._serve_thread.join(timeout=3)
    assert not hub._serve_thread.is_alive()
    status = hub.serving_status()
    assert status["state"] == "CLOSED"
    assert status["last_failure_code"] == "LISTENER_UNAVAILABLE"
    assert status["rejected_connections"] == 0
    assert status["served_bytes"] == 0
    assert hub._hub.closed is True
    assert len(calls) == 1  # Do not spin on EBADF as if peers were absent.


def test_worker_poll_allows_revoke_without_serving_any_bytes():
    calls = []
    hub = _synthetic_worker(
        serve=lambda: (_ for _ in ()).throw(
            ChunkTransferRejected("bounded Hub accept unavailable"),
        ),
    )
    def now_current():
        calls.append(True)
        return len(calls) < 6
    hub._hub_grant = now_current
    hub.start_bounded_serving(max_connections=20, max_idle_seconds=3)
    hub._serve_thread.join(timeout=3)
    state = hub.serving_status()
    assert state["served_chunks"] == 0
    assert state["state"] == "CLOSED"
    assert state["last_failure_code"] == "OWNER_AUTHORITY_OR_HUB_UNAVAILABLE"


def test_session_drains_hub_worker_before_releasing_local_run_lease(
    tmp_path, monkeypatch,
):
    import sofia.platform.run.library_host_service as source

    events = []
    class Child:
        def __init__(self, *, service, **kwargs):
            self.service = service
            self._closed = False
            self._running = Event()
            self._stopping = Event()
            self.worker = Thread(target=self._serve, daemon=True)
            self.worker.start()
            assert self._running.wait(3)

        def _serve(self):
            self._running.set()
            self._stopping.wait()
            events.append(("worker-drained", self.service.lease is not None))

        def close(self):
            assert self.service.lease is not None
            self._stopping.set()
            self.worker.join(timeout=3)
            assert not self.worker.is_alive()
            self._closed = True
            events.append(("close", self.service.lease is not None))

    monkeypatch.setattr(source, "HostedLibraryHub", Child)
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        service.open_owner_approved_library_hub()
    assert events == [("worker-drained", True), ("close", True)]
    assert service.lease is None


def test_session_refuses_release_when_hub_still_has_active_worker(
    tmp_path, monkeypatch,
):
    import sofia.platform.run.library_host_service as source

    class Child:
        def __init__(self, *, service, **kwargs):
            self.service = service
            self._closed = False
            self.force_failure = True

        def close(self):
            if self.force_failure:
                raise RuntimeError("Hub worker cannot be drained")
            self._closed = True

    monkeypatch.setattr(source, "HostedLibraryHub", Child)
    identity, current, state = provision(tmp_path)
    service = PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    )
    hub = service.open_owner_approved_library_hub()
    try:
        with pytest.raises(RuntimeError, match="lease retained"):
            service.close()
        assert service.lease is not None
        assert service._closed is False
        assert service._closing is True
        # A replacement cannot quietly start against the old live socket.
        with pytest.raises(RuntimeError):
            PlatformServiceSession(
                identity.home, state, current.identity.canonical_uuid,
                current.public_key_sha256,
            )
    finally:
        hub.force_failure = False
        service.close()
    assert service.lease is None

def test_supervised_hub_rejects_concurrent_foreground_accept():
    started = Event()
    finish = Event()
    def occupied():
        started.set()
        finish.wait(timeout=3)
    worker = Thread(target=occupied, daemon=True)
    worker.start()
    assert started.wait(3)
    hub = object.__new__(HostedLibraryHub)
    hub._serve_thread = worker
    hub._closed = False
    try:
        with pytest.raises(ChunkTransferRejected, match="supervised serving worker"):
            HostedLibraryHub.serve_once(hub)
    finally:
        finish.set()
        worker.join(timeout=3)
    assert not worker.is_alive()
