"""D028-03 guarded owner-selected LAN Hub listener for approved byte reads.

This component runs only when invoked by the canonical Platform service after
verified host enrollment, current owner SAFE authorization, publisher trust and
service readiness. Importing the module starts no service and grants nothing.
No public/wildcard listener, installer, writer, signing keys or personal Core
storage are exposed. All chunk decisions remain delegated to the canonical
service and rechecked by library_tls_chunk_transport.
"""
from __future__ import annotations

import ipaddress
import socket
import ssl
from pathlib import Path
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_tls_chunk_transport import serve_one_chunk


_LAN_V4 = tuple(ipaddress.ip_network(prefix) for prefix in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8",
))
_LAN_V6 = (ipaddress.ip_network("fc00::/7"), ipaddress.ip_network("::1/128"))


def _private_bind(host: str) -> tuple[int, str]:
    if (type(host) is not str or not host or len(host) > 64
            or "%" in host):
        # IPv6 zone/interface suffixes are not part of the exact
        # owner-reviewed numeric Hub bind and can select another interface.
        raise ChunkTransferRejected("explicit numeric private-LAN bind required")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ChunkTransferRejected("DNS, wildcard and nonnumeric binds forbidden") from exc
    if (address.is_unspecified or address.is_multicast
            or address.is_link_local or (address.is_reserved and not address.is_loopback)
            or not any(address in net for net in (_LAN_V4 if address.version == 4 else _LAN_V6))):
        raise ChunkTransferRejected("public or unreviewed network exposure forbidden")
    return (socket.AF_INET if address.version == 4 else socket.AF_INET6), str(address)


class ApprovedLibraryHub:
    """One explicitly enabled mTLS listener; callers own service lifecycle.

    owner_enabled must read current, service-backed SAFE/STOP, identity and Hub
    role state. authorize_peer must bind the peer certificate to an enrolled
    principal, exact artifact scope, current generation and revocation.
    resolve_verified_cache must ONLY resolve the independently verified CAS;
    network input never specifies a filesystem path.
    """

    def __init__(
        self, *, bind_host: str, port: int, tls_context: ssl.SSLContext,
        owner_enabled: Callable[[], bool],
        lookup_transfer: Callable[[str], PinnedChunkTransfer],
        authorize_peer: Callable,
        publisher_current: Callable[[PinnedChunkTransfer], bool],
        resolve_verified_cache: Callable[[PinnedChunkTransfer], Path],
        timeout_seconds: int = 10,
    ) -> None:
        family, host = _private_bind(bind_host)
        if type(port) is not int or not 0 <= port <= 65535:
            raise ChunkTransferRejected("explicit bounded Hub port required")
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
            raise ChunkTransferRejected("bounded Hub deadline required")
        if (not isinstance(tls_context, ssl.SSLContext)
                or tls_context.protocol != ssl.PROTOCOL_TLS_SERVER
                or tls_context.verify_mode != ssl.CERT_REQUIRED
                or tls_context.minimum_version < ssl.TLSVersion.TLSv1_3):
            raise ChunkTransferRejected("server-side mutual TLS1.3 context required")
        if not all(callable(x) for x in (
            owner_enabled, lookup_transfer, authorize_peer,
            publisher_current, resolve_verified_cache,
        )):
            raise ChunkTransferRejected("canonical service authority callbacks required")
        if owner_enabled() is not True:
            raise ChunkTransferRejected("Hub role not currently owner-approved")
        self._family = family
        self._host = host
        self._port = port
        self._context = tls_context
        self._owner_enabled = owner_enabled
        self._lookup = lookup_transfer
        self._authorize = authorize_peer
        self._publisher = publisher_current
        self._resolver = resolve_verified_cache
        self._timeout = timeout_seconds
        self._listener: socket.socket | None = None

    def open(self) -> tuple[str, int]:
        if self._listener is not None:
            raise ChunkTransferRejected("Hub listener already active")
        if self._owner_enabled() is not True:
            raise ChunkTransferRejected("Hub role revoked before bind")
        sock = socket.socket(self._family, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if self._family == socket.AF_INET6:
                sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            sock.bind((self._host, self._port))
            sock.listen(4)
            sock.settimeout(self._timeout)
            if self._owner_enabled() is not True:
                raise ChunkTransferRejected("Hub role revoked during bind")
            self._listener = sock
            endpoint = sock.getsockname()
            return str(endpoint[0]), int(endpoint[1])
        except BaseException:
            sock.close()
            raise

    def serve_once(self) -> int:
        if self._listener is None:
            raise ChunkTransferRejected("Hub was not explicitly opened")
        if self._owner_enabled() is not True:
            raise ChunkTransferRejected("Hub STOP or owner revocation")
        try:
            peer, _address = self._listener.accept()
        except (socket.timeout, TimeoutError) as exc:
            # A bounded idle poll lets the owner-controlled worker recheck
            # RUN generation and STOP without treating absence of peers
            # as a security incident.
            raise ChunkTransferRejected("bounded Hub accept unavailable") from exc
        except OSError as exc:
            # EBADF / revoked descriptor / listener failure is NOT idle.
            # The owner supervisor must account for a broken Hub socket.
            raise ChunkTransferRejected("Hub listener failed") from exc
        with peer:
            peer.settimeout(self._timeout)
            if self._owner_enabled() is not True:
                raise ChunkTransferRejected("Hub STOP or owner revocation at accept")
            try:
                with self._context.wrap_socket(peer, server_side=True) as secured:
                    secured.settimeout(self._timeout)
                    if self._owner_enabled() is not True:
                        raise ChunkTransferRejected("Hub STOP or owner revocation after mTLS")
                    return serve_one_chunk(
                        secured, lookup_transfer=self._lookup,
                        authorize_peer=self._authorize,
                        publisher_current=self._publisher,
                        resolve_verified_cache=self._resolver,
                    )
            except (OSError, ssl.SSLError, TimeoutError) as exc:
                raise ChunkTransferRejected("mutual TLS Hub connection unavailable") from exc

    def serve_bounded(self, *, max_connections: int) -> int:
        """Serve a bounded number of separately authorized mTLS chunks.

        The canonical Platform service controls the event loop and cancellation.
        Each reconnect calls serve_once, which rechecks the owner Hub role at
        accept, TLS establishment, and within its per-chunk authorization.
        No background daemon or implicit retry is created.
        """
        if type(max_connections) is not int or not 1 <= max_connections <= 10000:
            raise ChunkTransferRejected("bounded Hub connection budget required")
        if self._listener is None:
            raise ChunkTransferRejected("Hub was not explicitly opened")
        total_bytes = 0
        for _ in range(max_connections):
            if self._owner_enabled() is not True:
                raise ChunkTransferRejected("Hub role revoked between chunks")
            total_bytes += self.serve_once()
        return total_bytes

    def close(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()
