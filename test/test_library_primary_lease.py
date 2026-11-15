"""D028 logical Library primary epoch, fencing and owner-approved promotion."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.ops.library_owner_cli import main
from sofia.platform.ops.library_primary_lease import (
    LibraryPrimaryDenied, LibraryPrimaryLeaseStore,
)
from sofia.platform.ops.library_replica import LibraryReplicaStateStore
from sofia.platform.state.local_store import PlatformLocalStore
from test.test_platform_service_session import provision

LIBRARY = "private-library-1"
HOST_A = "primary-host-a"
HOST_B = "replica-host-b"
PLATFORM_A = "platform-a"
PLATFORM_B = "platform-b"
NOW = datetime(2026, 11, 8, 22, 0, tzinfo=timezone.utc)


def _store(tmp_path) -> LibraryPrimaryLeaseStore:
    local = PlatformLocalStore(
        tmp_path / "platform.db",
        roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
        host_identity=HOST_A,
    )
    return LibraryPrimaryLeaseStore(local, logical_library_id=LIBRARY)


def test_valid_primary_epoch_and_lease_deny_dual_primary_claim(tmp_path):
    lease = _store(tmp_path)
    record, token = lease.claim_primary(
        host_identity=HOST_A, platform_id=PLATFORM_A, now=NOW,
    )
    assert record.primary_epoch == 1
    assert record.catalog_revision == 1
    assert record.read_only_replica is False
    assert record.is_primary is True

    with pytest.raises(LibraryPrimaryDenied, match="dual-primary"):
        lease.claim_primary(
            host_identity=HOST_B, platform_id=PLATFORM_B, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="writer token"):
        lease.claim_primary(
            host_identity=HOST_A, platform_id=PLATFORM_A, now=NOW,
        )

    renewed, same_token = lease.claim_primary(
        host_identity=HOST_A, platform_id=PLATFORM_A, now=NOW,
        writer_token=token,
    )
    assert same_token == token
    assert renewed.primary_epoch == record.primary_epoch
    assert lease.advance_catalog_revision(
        host_identity=HOST_A, platform_id=PLATFORM_A,
        epoch=record.primary_epoch, writer_token=token,
        expected_revision=1, now=NOW,
    ) == 2


def test_expired_lease_never_auto_promotes_a_second_host(tmp_path):
    lease = _store(tmp_path)
    record, token = lease.claim_primary(
        host_identity=HOST_A, platform_id=PLATFORM_A, now=NOW,
        lease_seconds=5,
    )
    with pytest.raises(LibraryPrimaryDenied, match="promotion"):
        lease.claim_primary(
            host_identity=HOST_B, platform_id=PLATFORM_B,
            now=NOW + timedelta(seconds=10),
        )
    with pytest.raises(LibraryPrimaryDenied, match="lease expired"):
        lease.require_writer(
            host_identity=HOST_A, platform_id=PLATFORM_A,
            epoch=record.primary_epoch, writer_token=token,
            now=NOW + timedelta(seconds=10),
        )


def test_fenced_epoch_cannot_write_index_mutations(tmp_path):
    lease = _store(tmp_path)
    record, token = lease.claim_primary(
        host_identity=HOST_A, platform_id=PLATFORM_A, now=NOW,
    )
    receipt = lease.fence_primary(
        host_identity=HOST_A, platform_id=PLATFORM_A,
        epoch=record.primary_epoch, writer_token=token, now=NOW,
    )
    assert receipt.old_primary_epoch == record.primary_epoch
    assert len(receipt.fingerprint) == 64

    with pytest.raises(LibraryPrimaryDenied, match="fenced"):
        lease.require_writer(
            host_identity=HOST_A, platform_id=PLATFORM_A,
            epoch=record.primary_epoch, writer_token=token, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied):
        lease.advance_catalog_revision(
            host_identity=HOST_A, platform_id=PLATFORM_A,
            epoch=record.primary_epoch, writer_token=token,
            expected_revision=1, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="fenced"):
        lease.claim_primary(
            host_identity=HOST_B, platform_id=PLATFORM_B, now=NOW,
        )


def test_promotion_requires_current_safe_callback_and_exact_fence(tmp_path):
    lease = _store(tmp_path)
    record, token = lease.claim_primary(
        host_identity=HOST_A, platform_id=PLATFORM_A, now=NOW,
    )
    receipt = lease.fence_primary(
        host_identity=HOST_A, platform_id=PLATFORM_A,
        epoch=record.primary_epoch, writer_token=token, now=NOW,
    )

    with pytest.raises(LibraryPrimaryDenied, match="SAFE"):
        lease.promote_read_only_replica(
            new_primary_host_id=HOST_B, new_primary_platform_id=PLATFORM_B,
            expected_old_epoch=record.primary_epoch,
            old_primary_fence_receipt=receipt,
            safe_authorization=None, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="SAFE"):
        lease.promote_read_only_replica(
            new_primary_host_id=HOST_B, new_primary_platform_id=PLATFORM_B,
            expected_old_epoch=record.primary_epoch,
            old_primary_fence_receipt=receipt,
            safe_authorization=lambda: False, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="fence receipt"):
        lease.promote_read_only_replica(
            new_primary_host_id=HOST_B, new_primary_platform_id=PLATFORM_B,
            expected_old_epoch=record.primary_epoch,
            old_primary_fence_receipt=None,
            safe_authorization=lambda: True, now=NOW,
        )
    with pytest.raises(LibraryPrimaryDenied, match="epoch"):
        lease.promote_read_only_replica(
            new_primary_host_id=HOST_B, new_primary_platform_id=PLATFORM_B,
            expected_old_epoch=record.primary_epoch + 1,
            old_primary_fence_receipt=receipt,
            safe_authorization=lambda: True, now=NOW,
        )

    promoted, new_token = lease.promote_read_only_replica(
        new_primary_host_id=HOST_B, new_primary_platform_id=PLATFORM_B,
        expected_old_epoch=record.primary_epoch,
        old_primary_fence_receipt=receipt,
        safe_authorization=lambda: True, now=NOW,
    )
    assert promoted.host_identity == HOST_B
    assert promoted.primary_platform_id == PLATFORM_B
    assert promoted.primary_epoch == record.primary_epoch + 1
    assert promoted.catalog_revision > record.catalog_revision
    assert promoted.read_only_replica is False
    assert new_token != token

    with pytest.raises(LibraryPrimaryDenied):
        lease.require_writer(
            host_identity=HOST_A, platform_id=PLATFORM_A,
            epoch=record.primary_epoch, writer_token=token, now=NOW,
        )
    assert lease.require_writer(
        host_identity=HOST_B, platform_id=PLATFORM_B,
        epoch=promoted.primary_epoch, writer_token=new_token, now=NOW,
    ).primary_platform_id == PLATFORM_B


def test_owner_cli_exposes_only_redacted_primary_and_replica_status(
    tmp_path, capsys,
):
    identity, current, state = provision(tmp_path)
    platform_id = current.identity.canonical_uuid
    local = PlatformLocalStore(
        state, create=False, host_identity=platform_id,
        roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
    )
    lease = LibraryPrimaryLeaseStore(local, logical_library_id=LIBRARY)
    record, token = lease.claim_primary(
        host_identity=platform_id, platform_id=platform_id,
        now=datetime.now(timezone.utc),
    )

    def call(*rest):
        return main([
            "--state", str(state), "--platform-id", platform_id, *rest,
        ])

    assert call("primary-status", "--logical-library-id", LIBRARY) == 0
    output = capsys.readouterr().out
    primary = json.loads(output)
    assert primary["schema"] == "aegis.library.primary-status.v1"
    assert primary["state"] == "PRIMARY"
    assert primary["primary_epoch"] == record.primary_epoch
    assert primary["read_only"] is False
    assert token not in output
    assert str(tmp_path) not in output

    assert call("replica-status", "--logical-library-id", LIBRARY) == 0
    output = capsys.readouterr().out
    replica = json.loads(output)
    assert replica["schema"] == "aegis.library.replica-status.v1"
    assert replica["state"] == "UNKNOWN"
    assert replica["read_only"] is True
    assert replica["replica_platform_id"] == platform_id
    assert token not in output
    assert str(tmp_path) not in output

    # Read-only status must not create a second writer or read-only replica.
    assert LibraryReplicaStateStore(
        local, logical_library_id=LIBRARY, replica_platform_id=platform_id,
    ).current() is None
