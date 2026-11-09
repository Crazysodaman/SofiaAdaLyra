"""D028 one-Hub-per-Platform lifecycle and STOP/lease teardown contract.

The disposable lifecycle double tests test service ownership and closure;
they deliberately do not assert a real Hub may open without owner grants.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sofia.platform.ops.library_chunk_receiver import ChunkTransferRejected
from sofia.platform.run.library_host_service import HostedLibraryHub
from sofia.platform.run.platform_service import PlatformServiceSession
from test.test_platform_service_session import provision


def test_platform_session_owns_only_one_explicit_hub_and_closes_before_lease_release(
    tmp_path, monkeypatch,
):
    import sofia.platform.run.library_host_service as source
    records = []

    class FakeHub:
        def __init__(self, *, service, **source_configuration):
            records.append(("construct", service.lease is not None))
            self._closed = False
            self.service = service

        def close(self):
            if not self._closed:
                records.append(("close", self.service.lease is not None))
                self._closed = True

    monkeypatch.setattr(source, "HostedLibraryHub", FakeHub)
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        # Ordinary status and management readiness do not start a Hub.
        assert service.status()["management_listening"] is True
        assert records == []
        opened = service.open_owner_approved_library_hub()
        with pytest.raises(PermissionError, match="single owner-selected"):
            service.open_owner_approved_library_hub()
        opened.close()
        replaced = service.open_owner_approved_library_hub()
        assert replaced is not opened
    assert records == [
        ("construct", True), ("close", True),
        ("construct", True), ("close", True),
    ]


def test_hosted_hub_stop_revocation_closes_listener_without_serving(tmp_path):
    # Unit-level STOP check, NOT owner enrollment or mTLS evidence.
    class FakeListener:
        closed = False
        served = False

        def serve_once(self):
            self.served = True
            return 1

        def close(self):
            self.closed = True

    hub = object.__new__(HostedLibraryHub)
    listener = FakeListener()
    hub._closed = False
    hub._hub = listener
    hub._hub_grant = lambda: False
    hub._current_publisher = lambda _: True
    hub.transfer = object()
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        hub.serve_once()
    assert listener.closed is True
    assert listener.served is False


def test_closed_hub_is_never_reused_for_another_run_generation():
    class FakeListener:
        def __init__(self):
            self.count = 0
        def close(self):
            self.count += 1

    hub = object.__new__(HostedLibraryHub)
    listener = FakeListener()
    hub._closed = False
    hub._hub = listener
    hub._hub_grant = lambda: True
    hub._current_publisher = lambda _: True
    hub.transfer = object()
    hub.close()
    hub.close()
    assert listener.count == 1
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        hub.serve_once()
