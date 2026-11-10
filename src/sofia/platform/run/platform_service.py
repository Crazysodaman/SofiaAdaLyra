"""Core-free canonical state adapter for a Rust-owned Platform service.

Only the owning supervisor's inherited anonymous pipes are used. This is not
an external management endpoint or an owner approval/enrollment authority.
It does not start Cores, load personal state or grant module capabilities.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sqlite3
import stat
import tempfile
from pathlib import Path
from threading import Event, Lock, RLock, Thread
import sys
from uuid import uuid4

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.run.lease import LocalRunLeaseStore
from sofia.platform.run.management_read import ManagementReadDispatcher
from sofia.platform.run.library_read_authority import CurrentLibraryReadPeerAuthority
from sofia.platform.run.library_read_dispatch import (
    LibraryReadDispatcher, LocalReadMultiplexer,
)
from sofia.platform.run.management_peer_authority import CurrentManagementPeerAuthority
from sofia.platform.run.management_unix_listener import ManagementUnixListener
from sofia.platform.run.management_windows_pipe import ManagementWindowsPipeListener
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
)
from sofia.sdk.cognition_json import loads_strict_model_json

SCHEMA = 'aegis.platform.service-control.v1'


def systemd_management_operator_group(
    runtime: str, parent, *, service_uid: int, service_gid: int,
    service_groups: tuple[int, ...] = (),
) -> int | None:
    """Read installer-owned 0700 private or 0750 dedicated operator group.

    No OS ACL mutation, SAFE enrollment, or other authority is created here.
    """
    if runtime not in {"/run/aegis", "/run/aegis-platform"}:
        raise PermissionError("unreviewed systemd runtime directory")
    if (not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != service_uid):
        raise PermissionError("systemd runtime directory not governed")
    mode = stat.S_IMODE(parent.st_mode)
    if mode == 0o700:
        if parent.st_gid != service_gid:
            raise PermissionError("private service runtime group differs")
        return None
    if runtime == "/run/aegis-platform" and mode == 0o750:
        import grp
        try:
            gid = grp.getgrnam("aegis-mgmt").gr_gid
        except KeyError as exc:
            raise PermissionError("dedicated management group missing") from exc
        if (parent.st_gid != gid
                or gid not in (service_gid, *service_groups)):
            raise PermissionError("installed management group differs")
        return gid
    raise PermissionError("unexpected systemd runtime directory mode")

def select_enrolled_windows_pipe_sid(
    management_sid: str | None, library_sid: str | None,
) -> str | None:
    """One current individual operator across both separately SAFE-granted reads.

    This is an ACL selector only. Real Windows requires SID account-type
    verification at native pipe construction and current SAFE on every read.
    A group, service SID, or conflicting individually enrolled user is not a
    shortcut to local Platform authority.
    """
    import re
    candidates = {sid for sid in (management_sid, library_sid) if sid is not None}
    if len(candidates) > 1:
        raise PermissionError("distinct owner-enrolled Windows operators require explicit installer policy")
    for sid in candidates:
        if (type(sid) is not str
                or re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", sid) is None):
            raise PermissionError("unsupported Windows individual operator SID")
    return next(iter(candidates), None)


class PlatformServiceSession:
    """Hold existing local RUN authority plus an OS lifetime lock, never a Core lease."""

    def __init__(self, identity_home: Path, state_path: Path, expected_id: str,
                 expected_public_key_sha256: str, *,
                 installed_signed_catalog=None):
        # B1/owner enrollment supplies a separately pinned, read-only profile
        # provider. Stock Core-free installation has none and reports
        # UNAVAILABLE, not a self-signed publisher or synthetic "healthy".
        if installed_signed_catalog is not None and not callable(installed_signed_catalog):
            raise TypeError("canonical installed Library catalog provider required")
        self._installed_signed_catalog = installed_signed_catalog
        self.identity_store = InstallationIdentityStore(identity_home)
        self.identity = self.identity_store.load()
        if (self.identity.identity.canonical_uuid != expected_id
                or self.identity.public_key_sha256 != expected_public_key_sha256):
            raise PermissionError('service installation identity differs')
        assert_owner_private_path(state_path.parent, directory=True)
        assert_owner_private_path(state_path, directory=False)
        self.storage = PlatformLocalStore(state_path, create=False,
            roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)), host_identity=expected_id)
        if installed_signed_catalog is None:
            # Single-owner default. The existing identity-pinned local SQLite
            # holds an exact owner-authenticated signing root, if enrolled.
            # A fresh install has no pin: catalog reads remain UNAVAILABLE.
            # There is no public CA, tenant registry, TOFU or new daemon.
            from sofia.platform.run.library_owner_trust import OwnerLibraryTrustStore
            self._installed_signed_catalog = OwnerLibraryTrustStore(
                state_path, platform_id=expected_id,
            )
        self.lock = StateProcessLock(state_path, resource='platform-service', owner_label='Platform service',
            lock_directory=state_path.parent)
        self.lock.acquire()
        self.lease = None
        self._status_lock = RLock()
        self._management_stop = Event()
        self._management_listener = None
        self._management_thread = None
        self._management_home = None
        self._management_endpoint = None
        # One owner-approved private signed Library Hub per current RUN
        # service. Explicitly opened children are closed BEFORE lease release.
        self._hosted_library_hubs = []
        self._closing = False
        self._closed = False
        # Recipient's quarantine is single-writer even across repeated
        # foreground resumptions. A second simultaneous acquire is refused.
        self._recipient_transfer_lock = Lock()
        try:
            self.leases = LocalRunLeaseStore(state_path, lease_key='platform-service')
            self.stop = OperatorStopStore(state_path)
            result = self.leases.acquire(owner_id='platform-service:'+uuid4().hex,
                now=datetime.now(timezone.utc), ttl_seconds=15)
            if result.lease is None:
                raise RuntimeError('Platform service lease unavailable')
            self.lease = result.lease
            self._start_management(state_path, expected_id)
        except BaseException:
            self._stop_management()
            if self.lease is not None:
                self.leases.release(self.lease, now=datetime.now(timezone.utc))
                self.lease = None
            self.lock.release()
            raise

    def _start_management(self, state_path: Path, platform_id: str) -> None:
        """Bind native IPC before readiness; current SAFE proof remains mandatory.

        The runtime owns the socket/pipe and dies if the endpoint disappears.
        No GUI, module, Core or owner enrollment is started from this path.
        """
        if self.lease is None:
            raise RuntimeError("management requires active Platform lease")
        permissions = PermissionStore(state_path)
        current_peer = CurrentManagementPeerAuthority(
            permissions, platform_id=platform_id,
        )
        dispatcher = ManagementReadDispatcher(
            current_status=self.status,
            authorize=current_peer,
            read_settings=lambda _scopes: (_ for _ in ()).throw(
                PermissionError("Platform-local settings reader not approved")
            ),
            enrolled_denial_responses=True,
        )
        # Same verified local OS peer path, distinct owner enrollment.
        # No independently configured publisher index exists in the stock
        # installed profile yet. A catalog read therefore says UNAVAILABLE,
        # never fabricates trust, catalog data or installed status.
        library_peer = CurrentLibraryReadPeerAuthority(
            permissions, platform_id=platform_id,
        )
        def read_owner_sources():
            # Only this already-authenticated installed Platform service may
            # supply live local Hub status and the canonical SQLite owner root.
            # No UI/HUB callback can inject a publisher readiness assertion.
            from sofia.platform.run.library_owner_trust import OwnerLibraryTrustStore
            from sofia.platform.run.library_owner_sources import owner_library_source_status
            with self._status_lock:
                current = self.status()
                last_hub = (
                    self._hosted_library_hubs[-1]
                    if self._hosted_library_hubs else None
                )
                owner = (
                    self._installed_signed_catalog
                    if isinstance(self._installed_signed_catalog, OwnerLibraryTrustStore)
                    else None
                )
                return owner_library_source_status(
                    status=current, owner_trust=owner,
                    hosted_hub=last_hub,
                )

        library_dispatcher = LibraryReadDispatcher(
            current_status=self.status,
            authorize_os_peer=library_peer,
            installed_signed_catalog=(
                self._installed_signed_catalog if self._installed_signed_catalog
                is not None else lambda: None
            ),
            read_owner_sources=read_owner_sources,
        )
        read_mux = LocalReadMultiplexer(
            management=dispatcher, library=library_dispatcher,
        )
        if os.name == "nt":
            # A single native pipe serves BOTH separately owner-enrolled read
            # protocols. Union only if all current owner grants resolve to
            # one and the same individually verified Windows user SID.
            management_sid = current_peer.enrolled_windows_operator_sid()
            library_sid = library_peer.enrolled_windows_operator_sid()
            selected_sid = select_enrolled_windows_pipe_sid(
                management_sid, library_sid,
            )
            name = "AegisPlatform-" + platform_id.replace("-", "") + "-" + str(self.lease.epoch)
            listener = ManagementWindowsPipeListener(
                name, dispatch=read_mux.dispatch,
                enrolled_operator_sid=selected_sid,
            )
            self._management_endpoint = listener.name
        elif sys.platform == "linux":
            runtime = os.environ.get("RUNTIME_DIRECTORY")
            if runtime is not None:
                # Trust only the exact, signed-systemd configured runtime
                # directory. Never adopt /tmp, HOME, colon lists or a caller's
                # arbitrary environment path as an external IPC endpoint.
                home = Path(runtime)
                assert_no_redirected_components(home, include_leaf=True)
                parent = home.stat(follow_symlinks=False)
                group_gid = systemd_management_operator_group(
                    runtime, parent,
                    service_uid=os.geteuid(), service_gid=os.getegid(),
                    service_groups=tuple(os.getgroups()),
                )
                # Epoch-fenced path avoids adopting a socket abandoned by a
                # forced kill; old paths stay non-authoritative and offline.
                socket_path = home / ("mgmt-" + str(self.lease.epoch) + ".sock")
                listener = ManagementUnixListener(
                    socket_path, dispatch=read_mux.dispatch,
                    operator_group_gid=group_gid,
                )
            else:
                # Explicit developer fallback: owner-only, no external users.
                # Installed Debian service MUST use RuntimeDirectory rather
                # than claiming external connectivity through PrivateTmp.
                home = Path(tempfile.mkdtemp(prefix="aegis-mgmt-"))
                home.chmod(0o700)
                self._management_home = home
                listener = ManagementUnixListener(
                    home / "management.sock", dispatch=read_mux.dispatch,
                )
            self._management_endpoint = str(listener.path)
        else:
            raise PermissionError("no native authenticated management transport")
        listener.open()
        self._management_listener = listener
        self._management_thread = Thread(
            target=listener.serve_until, args=(self._management_stop,),
            name="AegisPlatformManagement", daemon=True,
        )
        self._management_thread.start()

    def _stop_management(self) -> None:
        self._management_stop.set()
        listener = self._management_listener
        if listener is not None:
            listener.close()
            self._management_listener = None
        thread = self._management_thread
        if thread is not None:
            thread.join(timeout=3)
            self._management_thread = None
            if thread.is_alive():
                raise RuntimeError("management IPC did not drain")
        home = self._management_home
        if home is not None:
            home.rmdir()
            self._management_home = None

    def status(self):
        with self._status_lock:
            if self._closing or self._closed:
                raise RuntimeError("Platform service shutdown has begun")
            if self.lease is None or self.identity_store.load() != self.identity:
                raise RuntimeError('Platform service identity unavailable')
            self.storage.validate()
            now = datetime.now(timezone.utc)
            if not self.leases.holds(self.lease, now=now):
                raise RuntimeError('Platform service generation expired')
            result = self.leases.renew(self.lease, now=now, ttl_seconds=15)
            if result.lease is None:
                raise RuntimeError('Platform service generation lost')
            self.lease = result.lease
            listener = self._management_listener
            thread = self._management_thread
            if listener is None or thread is None or not thread.is_alive():
                raise RuntimeError("Platform management listener lost")
            return dict(platform_id=self.identity.identity.canonical_uuid,
                public_key_sha256=self.identity.public_key_sha256,
                serial=self.identity.identity.serial, generation=self.lease.epoch,
                core_started=False, operator_stop=self.stop.current().active,
                management_listening=True,
                management_endpoint=self._management_endpoint)

    def accept_installed_signed_library_catalog(self, signed_index: bytes) -> str:
        """Store bounded signed metadata after current owner-root verification.

        Internal B1/Fleet caller ONLY, never management IPC, UI, Core or a
        remote Hub command. A signed fresh index is not an install grant.
        The existing Platform-local SQLite holds the index and owner pin,
        so personal homelab operation needs no cloud catalog daemon.
        """
        from sofia.platform.run.library_owner_trust import OwnerLibraryTrustStore
        with self._status_lock:
            if self.status()["operator_stop"] is not False:
                raise PermissionError("operator STOP prevents signed catalog acceptance")
            if not isinstance(self._installed_signed_catalog, OwnerLibraryTrustStore):
                raise PermissionError("custom installed catalog does not own local publisher trust")
            return self._installed_signed_catalog.accept_signed_catalog(signed_index)

    def open_owner_approved_library_hub(self, **installed_trusted_configuration):
        """Explicit private Hub start, never automatic from service readiness.

        The caller must be the trusted B1/Fleet service composition, not
        untrusted native JSON or a Core. The HostedLibraryHub constructor
        checks current SAFE, STOP, signed publisher and enrolled recipient.
        """
        from sofia.platform.run.library_host_service import HostedLibraryHub
        with self._status_lock:
            if self._closing or self._closed:
                raise RuntimeError("cannot start Hub while Platform is stopping")
            self.status()
            if any(not child._closed for child in self._hosted_library_hubs):
                raise PermissionError("single owner-selected Library Hub already serving")
            instance = HostedLibraryHub(
                service=self, **installed_trusted_configuration,
            )
            self._hosted_library_hubs = [instance]
            return instance

    def acquire_owner_approved_library_asset(
        self, *, approval_id: str, start_offset: int = 0,
        chunk_bytes: int = 1024 * 1024, max_chunks: int = 128,
        **installed_trusted_configuration,
    ) -> dict[str, object]:
        """One foreground D028 recipient acquisition on this RUN service.

        No GUI/IPC effect route is exposed until D028-00 is frozen. The
        installed B1/Fleet composition must pass independently provisioned
        publisher key, enrolled TLS connector, exact signed index, real cache,
        quarantine and independent package verifier. The current SAFE owner
        grants are always read from this service's original canonical state.
        """
        from sofia.platform.run.library_recipient_service import HostedLibraryRecipient
        if not self._recipient_transfer_lock.acquire(blocking=False):
            raise PermissionError("another installed recipient transfer is active")
        try:
            status = self.status()
            if status.get("operator_stop") is not False:
                raise PermissionError("operator STOP prevents recipient acquisition")
            # The canonical personal-owner SQLite already contains the
            # independently enrolled publisher root and signed current index.
            # Use it automatically instead of requiring redundant caller-
            # supplied key/profile configuration. This does NOT grant TLS
            # enrollment, package signer trust or cache import approval.
            config = dict(installed_trusted_configuration)
            if "signed_catalog_source" not in config:
                if not callable(self._installed_signed_catalog):
                    raise PermissionError("owner publisher catalog source unavailable")
                config["signed_catalog_source"] = self._installed_signed_catalog
            receiver = HostedLibraryRecipient(
                service=self, **config,
            )
            return receiver.acquire(
                approval_id=approval_id, start_offset=start_offset,
                chunk_bytes=chunk_bytes, max_chunks=max_chunks,
            )
        finally:
            self._recipient_transfer_lock.release()

    def acquire_owner_approved_library_sdk(
        self, *, approval_id: str,
        transfer, expected_artifact_id: str,
        receiver, cache, open_enrolled_tls,
        enrolled_source_certificate_sha256: str,
        signed_b1_sdk_envelope: bytes,
        b1_verifier, b1_installation,
        expected_source_sha: str, expected_target,
        trusted_signer_key_id: str, signer_current,
        start_offset: int = 0,
        chunk_bytes: int = 1024 * 1024, max_chunks: int = 128,
        signed_catalog_source=None, clock=None,
    ) -> dict[str, object]:
        """One private owner-approved SDK cache admission via REAL B1 trust.

        The caller supplies the installed B1 publisher verifier and original
        signed release envelope, NOT a Hub-supplied 'verified' boolean. The
        canonical SDK parser checks the selected wheel; separate SAFE owner
        proof, current enrolled TLS and cache import remain mandatory. No
        Platform installer, GUI action, Core activation or model loading.
        """
        from sofia.platform.ops.library_b1_sdk_publisher import (
            InstalledB1SignedSdkVerifier,
        )
        from sofia.platform.ops.library_chunk_receiver import (
            ChunkTransferRejected, PinnedChunkTransfer,
        )
        if (not isinstance(transfer, PinnedChunkTransfer)
                or transfer.artifact_kind != "sdk"):
            raise ChunkTransferRejected(
                "dedicated signed B1 SDK acquisition required"
            )
        publisher = InstalledB1SignedSdkVerifier(
            verifier=b1_verifier, installation=b1_installation,
            signed_envelope=signed_b1_sdk_envelope,
            expected_source_sha=expected_source_sha,
            expected_target=expected_target,
            trusted_signer_key_id=trusted_signer_key_id,
            signer_current=signer_current,
        )
        if (
            publisher.signed_manifest_sha256 != transfer.manifest_sha256
            or publisher._manifest.release_id != expected_artifact_id
        ):
            raise ChunkTransferRejected(
                "SDK signed B1 manifest or release differs from selected offer"
            )
        trusted = dict(
            transfer=transfer, expected_artifact_id=expected_artifact_id,
            receiver=receiver, cache=cache,
            open_enrolled_tls=open_enrolled_tls,
            enrolled_source_certificate_sha256=enrolled_source_certificate_sha256,
            verify_independent_package=publisher,
            package_signer_current=signer_current,
        )
        if signed_catalog_source is not None:
            trusted["signed_catalog_source"] = signed_catalog_source
        if clock is not None:
            trusted["clock"] = clock
        return self.acquire_owner_approved_library_asset(
            approval_id=approval_id, start_offset=start_offset,
            chunk_bytes=chunk_bytes, max_chunks=max_chunks, **trusted,
        )

    def close(self):
        """Drain child Hub and recipient work BEFORE relinquishing RUN authority.

        A second service must NEVER acquire a fresh generation while an
        older Hub worker can still emit signed bytes from the previous one.
        Close is idempotent on success; a failed drain keeps the original
        process/lease fence for explicit owner reconciliation.
        """
        with self._status_lock:
            if self._closed:
                return
            self._closing = True
            children = tuple(reversed(self._hosted_library_hubs))
        errors = []
        # No status lock while joining: a worker may be checking RUN/STOP
        # and must be able to finish rather than deadlocking on close().
        for hub in children:
            try:
                hub.close()
            except BaseException as exc:
                errors.append(exc)
        try:
            self._stop_management()
        except BaseException as exc:
            errors.append(exc)
        # A foreground recipient must finish its current bounded TLS read,
        # see service shutdown and refuse the next SAFE/cache effect. Do not
        # release RUN while any transfer still holds the owner session lock.
        if self._recipient_transfer_lock.acquire(timeout=30):
            self._recipient_transfer_lock.release()
        else:
            errors.append(RuntimeError("recipient acquisition did not drain"))
        if errors:
            raise RuntimeError(
                "Platform RUN lease retained because service work did not drain"
            ) from errors[0]
        with self._status_lock:
            self._hosted_library_hubs.clear()
            try:
                if self.lease is not None:
                    self.leases.release(
                        self.lease, now=datetime.now(timezone.utc),
                    )
                    self.lease = None
            finally:
                self.lock.release()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity-home', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--platform-id', required=True)
    parser.add_argument('--public-key-sha256', required=True)
    parser.add_argument('--supervisor-pid', type=int, required=True)
    args = parser.parse_args(argv)
    stage = 'parent'
    try:
        if args.supervisor_pid <= 0 or os.getppid() != args.supervisor_pid:
            raise PermissionError('service parent differs')
        stage = 'state'
        with PlatformServiceSession(args.identity_home, args.state, args.platform_id,
                                    args.public_key_sha256) as session:
            print(json.dumps(dict(schema=SCHEMA, phase='ready', pid=os.getpid(),
                supervisor_pid=os.getppid(), **session.status())), flush=True)
            sequence = 0
            stage = 'control'
            while True:
                raw = sys.stdin.buffer.readline(4097)
                if not raw:
                    return 0  # Supervisor lifetime ends; release rather than orphan.
                if len(raw) > 4096 or not raw.endswith(b'\n'):
                    raise ValueError('unbounded control request')
                request = loads_strict_model_json(raw.decode('utf-8'))
                if (not isinstance(request, dict) or set(request) != {'schema','sequence','generation','operation'}
                        or request['schema'] != SCHEMA or type(request['sequence']) is not int
                        or request['sequence'] != sequence+1 or type(request['generation']) is not int
                        or request['generation'] != session.lease.epoch
                        or request['operation'] not in {'status','shutdown'}):
                    raise PermissionError('stale or malformed service control')
                sequence += 1
                result = session.status()
                print(json.dumps(dict(schema=SCHEMA, sequence=sequence,
                    phase='stopped' if request['operation'] == 'shutdown' else 'healthy', **result)), flush=True)
                if request['operation'] == 'shutdown':
                    return 0
    except (OSError, RuntimeError, ValueError, TypeError, sqlite3.Error) as error:
        print(f'Platform service authority unavailable ({stage}: {type(error).__name__})', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
