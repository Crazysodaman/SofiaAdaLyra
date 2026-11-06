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
from pathlib import Path
import sys
from uuid import uuid4

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.run.lease import LocalRunLeaseStore
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.state.private_file import assert_owner_private_path
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
        try:
            self.leases = LocalRunLeaseStore(state_path, lease_key='platform-service')
            self.stop = OperatorStopStore(state_path)
            result = self.leases.acquire(owner_id='platform-service:'+uuid4().hex,
                now=datetime.now(timezone.utc), ttl_seconds=15)
            if result.lease is None:
                raise RuntimeError('Platform service lease unavailable')
            self.lease = result.lease
        except BaseException:
            self.lock.release()
            raise

    def status(self):
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
        return dict(platform_id=self.identity.identity.canonical_uuid,
            public_key_sha256=self.identity.public_key_sha256,
            serial=self.identity.identity.serial, generation=self.lease.epoch,
            core_started=False, operator_stop=self.stop.current().active)

    def close(self):
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
