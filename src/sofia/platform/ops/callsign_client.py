"""Explicit local authority client and read-only offline display projection.

A network transport is deliberately not invented here. Any later remote
adapter needs authenticated authority identity and response verification.
"""
import json
import sqlite3

from sofia.platform.ops.callsigns import CallsignAuthority, CallsignUnavailable, _uuid, canonical_json
from sofia.platform.state.private_file import atomic_write_private_text


class CallsignDisplayClient:
    def __init__(self, installation, authority_id, *, connect=None):
        self.installation = installation
        self.platform_id = installation.load().identity.canonical_uuid
        self.authority_id = _uuid(authority_id)
        self.connect = connect
        self.cache_path = installation.home / ('callsign-display-' + self.authority_id + '.json')
        self.cached = None
        if self.cache_path.exists() or self.cache_path.is_symlink():
            self.cached = json.loads(installation._read(self.cache_path, 8192))
            if (type(self.cached) is not dict or self.cached.get('authority_id') != self.authority_id or
                self.cached.get('platform_id') != self.platform_id or self.cached.get('status') != 'VERIFIED'):
                raise CallsignUnavailable('cached naming projection is invalid')

    def _authority(self):
        if self.connect is None:
            raise CallsignUnavailable('no designated authority connection')
        authority = self.connect()
        if not isinstance(authority, CallsignAuthority) or authority.authority_id != self.authority_id:
            raise CallsignUnavailable('designated authority differs')
        return authority

    def _remember(self, authority):
        snapshot = authority.snapshot(self.platform_id)
        if self.cached is not None and snapshot['revision'] < self.cached['revision']:
            raise CallsignUnavailable('authority projection moved backwards')
        atomic_write_private_text(self.cache_path, canonical_json(snapshot))
        self.cached = snapshot
        return snapshot

    def display(self):
        try:
            return self._remember(self._authority())
        except (OSError, sqlite3.Error, CallsignUnavailable, ConnectionError):
            return {**(self.cached or {'platform_id': self.platform_id, 'authority_id': self.authority_id,
                      'name': None, 'display': 'UNASSIGNED', 'revision': None}), 'status': 'CACHED' if self.cached else 'UNCONFIRMED'}

    def core_rename(self, request, signature):
        if request.get('platform_id') != self.platform_id:
            raise PermissionError('request is for another Platform')
        try:
            authority = self._authority()
            receipt = authority.core_rename(request, signature)
            self._remember(authority)
            return receipt
        except (OSError, sqlite3.Error, CallsignUnavailable, ConnectionError):
            return {'result': 'UNCONFIRMED', 'request_id': request.get('request_id'),
                    'last_verified': self.cached, 'authority_id': self.authority_id}
