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
from threading import Event, RLock, Thread
import sys
from uuid import uuid4

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.run.lease import LocalRunLeaseStore
from sofia.platform.run.management_read import ManagementReadDispatcher
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


class PlatformServiceSession:
    """Hold existing local RUN authority plus an OS lifetime lock, never a Core lease."""

    def __init__(self, identity_home: Path, state_path: Path, expected_id: str,
                 expected_public_key_sha256: str):
        self.identity_store = InstallationIdentityStore(identity_home)
        self.identity = self.identity_store.load()
        if (self.identity.identity.canonical_uuid != expected_id
                or self.identity.public_key_sha256 != expected_public_key_sha256):
            raise PermissionError('service installation identity differs')
        assert_owner_private_path(state_path.parent, directory=True)
        assert_owner_private_path(state_path, directory=False)
        self.storage = PlatformLocalStore(state_path, create=False,
            roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)), host_identity=expected_id)
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
        )
        if os.name == "nt":
            name = "AegisPlatform-" + platform_id.replace("-", "") + "-" + str(self.lease.epoch)
            listener = ManagementWindowsPipeListener(
                name, dispatch=dispatcher.dispatch,
                enrolled_operator_sid=current_peer.enrolled_windows_operator_sid(),
            )
            self._management_endpoint = listener.name
        elif sys.platform == "linux":
            runtime = os.environ.get("RUNTIME_DIRECTORY")
            if runtime is not None:
                # Trust only the exact, signed-systemd configured runtime
                # directory. Never adopt /tmp, HOME, colon lists or a caller's
                # arbitrary environment path as an external IPC endpoint.
                if runtime != "/run/aegis-platform":
                    raise PermissionError("unreviewed systemd runtime directory")
                home = Path(runtime)
                assert_no_redirected_components(home, include_leaf=True)
                parent = home.stat(follow_symlinks=False)
                if (not stat.S_ISDIR(parent.st_mode)
                        or parent.st_uid != os.geteuid()
                        or parent.st_gid != os.getegid()
                        or stat.S_IMODE(parent.st_mode) != 0o750):
                    raise PermissionError("systemd runtime directory not governed")
                # Epoch-fenced path avoids adopting a socket abandoned by a
                # forced kill; old paths stay non-authoritative and offline.
                socket_path = home / ("mgmt-" + str(self.lease.epoch) + ".sock")
                listener = ManagementUnixListener(
                    socket_path, dispatch=dispatcher.dispatch,
                    operator_group_gid=os.getegid(),
                )
            else:
                # Explicit developer fallback: owner-only, no external users.
                # Installed Debian service MUST use RuntimeDirectory rather
                # than claiming external connectivity through PrivateTmp.
                home = Path(tempfile.mkdtemp(prefix="aegis-mgmt-"))
                home.chmod(0o700)
                self._management_home = home
                listener = ManagementUnixListener(
                    home / "management.sock", dispatch=dispatcher.dispatch,
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

    def close(self):
        try:
            self._stop_management()
        finally:
            with self._status_lock:
                try:
                    if self.lease is not None:
                        self.leases.release(self.lease, now=datetime.now(timezone.utc))
                        self.lease = None
                finally:
                    self.lock.release()

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
