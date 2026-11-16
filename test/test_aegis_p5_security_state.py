"""Aegis P5 durable-store privacy, redirect fencing and stale-writer regressions.

All stores are disposable SQLite files under pytest temporary directories.  No
canonical ``sofia.db``, Core identity, Constitution or protected memory is read
or written by any path exercised here.
"""
from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path
import stat
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.ops.component_install import (
    CoreComponentInstaller, CoreComponentRegistry,
    Ed25519ComponentSignatureVerifier,
)
from sofia.platform.ops.library_primary_lease import (
    LibraryPrimaryDenied, LibraryPrimaryLeaseStore,
)
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.ops.synthetic_core_lifecycle import (
    CoreProcessObservation, SyntheticCoreLifecycle, SyntheticCoreLifecycleConflict,
    SyntheticCoreLifecycleStore,
)
from sofia.platform.run.management_mutation_store import (
    ManagementMutationReceiptStore,
)
from sofia.platform.state.canonical_sqlite import CanonicalStateUnavailable
from sofia.platform.state.local_store import PlatformLocalStore, LocalStateUnavailable
from sofia.platform.state.private_file import assert_owner_private_path
from test.aegis_p5_security_support import (
    NOW, approved_request, compose, make_directory_redirect,
    recording_registry,
)

OWNER = "owner:p5-security"
SHA = "a" * 64


def _local_store(root: Path, host: str = "p5-host") -> PlatformLocalStore:
    return PlatformLocalStore(
        root / "local.db",
        roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
        host_identity=host,
    )


class FakeBackend:
    def __init__(self) -> None:
        self.running: dict[str, int] = {}
        self.start_calls = 0
        self.stop_calls = 0

    def start(self, *, core_id: str, lineage_id: str, generation: int):
        self.start_calls += 1
        self.running[core_id] = generation
        return CoreProcessObservation.RUNNING

    def stop(self, *, core_id: str, lineage_id: str, generation: int):
        self.stop_calls += 1
        self.running.pop(core_id, None)
        return CoreProcessObservation.STOPPED

    def observe(self, *, core_id: str, lineage_id: str, generation: int):
        return (
            CoreProcessObservation.RUNNING
            if core_id in self.running else CoreProcessObservation.STOPPED
        )


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls: list[tuple[str, str, int]] = []

    def __call__(self, operation: str, fingerprint: str, generation: int) -> bool:
        self.calls.append((operation, fingerprint, generation))
        return self.allowed


def _synthetic_lifecycle(
    tmp_path: Path, backend: FakeBackend, *,
    authorizer: Authorizer | None = None,
    freshness: list[bool] | None = None,
) -> SyntheticCoreLifecycle:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    installer = CoreComponentInstaller(
        CoreComponentRegistry(tmp_path / "component-registry.sqlite"),
        Ed25519ComponentSignatureVerifier({"p5-disposable-key": public}),
        installation_root=tmp_path / "component-install-root",
        authorization_check=lambda *_args: True,
    )
    auth = authorizer or Authorizer()
    fresh = freshness if freshness is not None else [True]
    return SyntheticCoreLifecycle(
        store_path=tmp_path / "synthetic-bindings.sqlite",
        platform_id=str(uuid4()),
        installer=installer,
        backend=backend,
        authorization=auth,
        freshness=lambda: fresh[0],
        platform_health_check=lambda: True,
        clock=lambda: NOW,
    )


def _bind_installed(lifecycle: SyntheticCoreLifecycle) -> tuple[str, str]:
    core_id, lineage_id = str(uuid4()), str(uuid4())
    lifecycle.store.path.parent.mkdir(parents=True, exist_ok=True)
    with lifecycle.store.transaction() as db:
        db.execute(
            "INSERT INTO ops_synthetic_core_binding("
            "owner_id,core_id,lineage_id,generation,state,artifact_sha256,"
            "version,installed_at,updated_at,last_operation,last_outcome,detail"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                OWNER, core_id, lineage_id, 0, "installed", SHA, "0.1.0",
                NOW.isoformat(), NOW.isoformat(), "install", "SUCCEEDED", "",
            ),
        )
    return core_id, lineage_id


def _assert_private_file(path: Path) -> None:
    assert path.is_file()
    assert_owner_private_path(path, directory=False)
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0


def test_synthetic_core_store_is_owner_private_and_rejects_redirects(tmp_path):
    store = SyntheticCoreLifecycleStore(tmp_path / "private" / "bindings.sqlite")
    _assert_private_file(store.path)
    assert_owner_private_path(store.path.parent, directory=True)

    actual = tmp_path / "actual"
    actual.mkdir()
    redirected = tmp_path / "redirected"
    make_directory_redirect(redirected, actual)
    with pytest.raises(PermissionError, match="redirection"):
        SyntheticCoreLifecycleStore(redirected / "bindings.sqlite")
    assert not (actual / "bindings.sqlite").exists()


@pytest.mark.parametrize(
    "name", ["sofia.db", "SOFIA.DB", "sofia.db-wal", "Sofia.db-shm"],
)
def test_synthetic_core_store_never_joins_protected_core_state(tmp_path, name):
    path = tmp_path / name
    with pytest.raises(PermissionError, match="protected"):
        SyntheticCoreLifecycleStore(path)
    assert not path.exists()


def test_installer_store_never_joins_protected_core_state(tmp_path):
    for name in ("sofia.db", "SOFIA.DB", "sofia.db-journal"):
        path = tmp_path / name
        with pytest.raises(PermissionError, match="protected"):
            PlatformInstallationStore(path)
        assert not path.exists()


def test_management_receipts_reject_redirected_canonical_parent(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    bootstrap_canonical_sqlite(state / "platform.db")
    redirected = actual / "redirected"
    make_directory_redirect(redirected, state)
    with pytest.raises(CanonicalStateUnavailable):
        ManagementMutationReceiptStore(redirected / "platform.db")


def test_library_local_store_rejects_redirected_parent(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    store = _local_store(actual)
    assert store.path.is_file()
    redirected = tmp_path / "redirected"
    make_directory_redirect(redirected, actual)
    with pytest.raises(LocalStateUnavailable, match="redirect"):
        PlatformLocalStore(
            redirected / "local.db",
            roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
            host_identity="p5-host",
        )


def test_management_and_library_backing_files_are_owner_private(tmp_path):
    from sofia.platform.ops.library_replica import LibraryReplicaStateStore
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

    management = tmp_path / "management"
    management.mkdir()
    canonical = bootstrap_canonical_sqlite(management / "platform.db")
    ManagementMutationReceiptStore(canonical)
    _assert_private_file(canonical)

    storage = _local_store(tmp_path / "library", "p5-private-host")
    lease = LibraryPrimaryLeaseStore(
        storage, logical_library_id="p5-private-library",
    )
    lease.claim_primary(
        host_identity="p5-private-host", platform_id="platform:private",
        now=NOW,
    )
    replica = LibraryReplicaStateStore(
        storage, logical_library_id="p5-private-library",
        replica_platform_id="platform:replica",
        primary_platform_id="platform:primary",
    )
    replica.record_state(state="UNKNOWN", now=NOW)
    _assert_private_file(storage.path)


def test_new_p5_stores_do_not_create_or_touch_sofia_db(tmp_path):
    _local_store(tmp_path, "p5-no-canonical")
    PlatformInstallationStore(tmp_path / "b1" / "install.db")
    SyntheticCoreLifecycleStore(tmp_path / "synthetic" / "bindings.sqlite")
    state = tmp_path / "management"
    state.mkdir()
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    bootstrap_canonical_sqlite(state / "platform.db")
    ManagementMutationReceiptStore(state / "platform.db")
    assert not (tmp_path / "sofia.db").exists()
    assert not (tmp_path / "synthetic" / "sofia.db").exists()


def test_management_stale_generation_and_revision_are_fenced(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    canonical = bootstrap_canonical_sqlite(state / "platform.db")
    calls: list = []
    dispatcher, approvals, _ = compose(canonical, recording_registry(calls))
    for index, (changes, code) in enumerate((
        ({"expected_generation": 2}, "STALE_GENERATION"),
        ({"expected_revision": 4}, "STALE_REVISION"),
    )):
        document = approved_request(
            approvals, idempotency_key=f"idempotency:stale-{index}", **changes,
        )
        reply = dispatcher.dispatch(document, authenticated_peer="unix:uid:1000:gid:1000", now=NOW)
        assert reply["outcome"] == "DENIED"
        assert reply["error_code"] == code
    assert calls == []


def test_library_stale_writer_epoch_token_and_fence_are_refused(tmp_path):
    storage = _local_store(tmp_path, "p5-library-host")
    lease = LibraryPrimaryLeaseStore(storage, logical_library_id="p5-library")
    record, token = lease.claim_primary(
        host_identity="p5-library-host", platform_id="platform:library",
        now=NOW,
    )
    later = NOW + timedelta(seconds=61)
    with pytest.raises(LibraryPrimaryDenied, match="expired"):
        lease.require_writer(
            host_identity="p5-library-host", platform_id="platform:library",
            epoch=record.primary_epoch, writer_token=token, now=later,
        )
    renewed, token2 = lease.claim_primary(
        host_identity="p5-library-host", platform_id="platform:library",
        now=later,
    )
    assert renewed.primary_epoch == record.primary_epoch + 1
    with pytest.raises(LibraryPrimaryDenied, match="stale"):
        lease.require_writer(
            host_identity="p5-library-host", platform_id="platform:library",
            epoch=record.primary_epoch, writer_token=token, now=later,
        )
    with pytest.raises(LibraryPrimaryDenied, match="stale"):
        lease.advance_catalog_revision(
            host_identity="p5-library-host", platform_id="platform:library",
            epoch=renewed.primary_epoch, writer_token=token2,
            expected_revision=record.catalog_revision + 1, now=later,
        )
    receipt = lease.fence_primary(
        host_identity="p5-library-host", platform_id="platform:library",
        epoch=renewed.primary_epoch, writer_token=token2, now=later,
    )
    assert receipt.old_primary_epoch == renewed.primary_epoch
    with pytest.raises(LibraryPrimaryDenied, match="fenced"):
        lease.require_writer(
            host_identity="p5-library-host", platform_id="platform:library",
            epoch=renewed.primary_epoch, writer_token=token2, now=later,
        )


def test_synthetic_core_stale_generation_and_revocation_are_fenced(tmp_path):
    backend = FakeBackend()
    authorizer = Authorizer()
    lifecycle = _synthetic_lifecycle(tmp_path, backend, authorizer=authorizer)
    core_id, _lineage = _bind_installed(lifecycle)

    started = lifecycle.start(
        owner_id=OWNER, core_id=core_id, expected_generation=0,
    )
    assert started.generation == 1
    assert backend.start_calls == 1

    with pytest.raises(SyntheticCoreLifecycleConflict):
        lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=0)
    assert backend.start_calls == 1

    authorizer.allowed = False
    with pytest.raises(PermissionError):
        lifecycle.stop(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert backend.stop_calls == 0
    assert lifecycle.store.binding(OWNER, core_id).state.value == "active"

    authorizer.allowed = True
    stopped = lifecycle.stop(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert stopped.state.value == "stopped"
    assert backend.stop_calls == 1
