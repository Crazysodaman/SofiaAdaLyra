"""Local orchestration races; fake transport does not certify network security."""
from datetime import timedelta

import pytest

from test.test_distributed_operations import NOW, fixture
from test.distributed_support import remote_authorization
from sofia.platform.distributed.operations import RemoteOperationDenied, RemoteOperationUncertain


@pytest.mark.parametrize("phase", ["discover", "execute"])
def test_revocation_during_transport_prevents_dispatch_or_result_release(remote_authorization, phase):
    enrollment, request, transport, gateway = fixture(remote_authorization)
    original = getattr(transport, phase)

    def revoke_then_return(*args):
        value = original(*args)
        remote_authorization.revoke(request.grant_id)
        return value

    setattr(transport, phase, revoke_then_return)
    error = RemoteOperationDenied if phase == "discover" else RemoteOperationUncertain
    with pytest.raises(error, match="grant"):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls.count("execute") == (phase == "execute")
    with pytest.raises(RemoteOperationDenied, match="Duplicate"):
        gateway.invoke(enrollment, request, now=NOW)


@pytest.mark.parametrize("phase", ["discover", "execute"])
def test_grant_expiry_advances_during_transport(remote_authorization, monkeypatch, phase):
    enrollment, request, transport, gateway = fixture(remote_authorization)
    # Inventory remains current while the two-minute grant expires.
    gateway._max_age = timedelta(minutes=10)
    elapsed = [10.0]
    monkeypatch.setattr("sofia.platform.distributed.operations.monotonic", lambda: elapsed[0])
    original = getattr(transport, phase)

    def delay_then_return(*args):
        value = original(*args)
        elapsed[0] += 121
        return value

    setattr(transport, phase, delay_then_return)
    error = RemoteOperationDenied if phase == "discover" else RemoteOperationUncertain
    with pytest.raises(error, match="grant"):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls.count("execute") == (phase == "execute")


@pytest.mark.parametrize("phase", ["discover", "execute"])
def test_revocation_outcome_persists_and_cannot_replay_after_restart(tmp_path, phase):
    from test.test_distributed_durable import setup, grant_for
    from sofia.platform.distributed.durable import (
        DurableDistributedGateway, DurableRemoteAuthorization, DurableRemoteLedger,
    )

    database, enrollment, request, auth, ledger, transport, gateway = setup(tmp_path)
    auth.add_approved_grant(grant_for(request))
    original = getattr(transport, phase)

    def revoke_then_return(*args):
        value = original(*args)
        auth.revoke(request.grant_id)
        return value

    setattr(transport, phase, revoke_then_return)
    error = RemoteOperationDenied if phase == "discover" else RemoteOperationUncertain
    with pytest.raises(error):
        gateway.invoke(enrollment, request, now=NOW)
    expected = "denied_after_reserve" if phase == "discover" else "uncertain"
    assert ledger.status(request.request_id) == expected
    auth.close()
    ledger.close()
    auth = DurableRemoteAuthorization(database)
    ledger = DurableRemoteLedger(database)
    try:
        restarted = DurableDistributedGateway(
            transport, auth, ledger, max_inventory_age=timedelta(minutes=1))
        with pytest.raises(RemoteOperationDenied):
            restarted.invoke(enrollment, request, now=NOW)
        assert ledger.status(request.request_id) == expected
        assert transport.calls.count("execute") == (phase == "execute")
    finally:
        auth.close()
        ledger.close()


@pytest.mark.parametrize("phase", ["discover", "execute"])
def test_failed_authority_recheck_does_not_dispatch_or_release(remote_authorization, monkeypatch, phase):
    enrollment, request, transport, gateway = fixture(remote_authorization)
    original = getattr(transport, phase)

    def fail_recheck(*args):
        value = original(*args)

        def unavailable(*args, **kwargs):
            raise OSError("authority store unavailable")

        monkeypatch.setattr(type(remote_authorization), "permits", unavailable)
        return value

    setattr(transport, phase, fail_recheck)
    error = RemoteOperationDenied if phase == "discover" else RemoteOperationUncertain
    with pytest.raises(error):
        gateway.invoke(enrollment, request, now=NOW)
    assert transport.calls.count("execute") == (phase == "execute")
