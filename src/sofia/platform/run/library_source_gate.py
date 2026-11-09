"""D028 source-Hub authority: current source generation and recipient TLS peer.

Recipient RUN generation and source Hub RUN generation are independent. The
transport's PinnedChunkTransfer.generation is bound to the recipient, not
silently compared to the source listener's RUN lease. This gate refuses any
source whose own owner-approved Hub lease, STOP, enrollment, publisher trust,
peer grant or selected signed transfer is no longer current.

No listener is created, no peer enrolled, no owner approval generated, no
package signed, no Core activated. The one-use authenticated owner approval
remains in the canonical PermissionStore grant workflow.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import re
import ssl

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_tls_hub import _private_bind
from sofia.platform.run.library_peer_gate import (
    CAPABILITY as PEER_CAPABILITY,
    _require_verified_tls13_peer, _SCOPE as PEER_SCOPE, _MAX_CHUNK,
)
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.safe.operator_stop import OperatorStopStore

HUB_CAPABILITY = "platform.library.hub.serve"
HUB_PROTOCOL = "aegis.library.tls.chunk.v1"
HUB_SCOPE = frozenset({
    "platform_id", "source_generation", "bind_host", "bind_port", "protocol",
})
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_INT = 2**53 - 1


def selected_hub_grant_scope(
    *, source_platform_id: str, source_generation: int,
    bind_host: str, bind_port: int,
) -> dict[str, object]:
    """Create scope to request from owner; this is NEVER a grant."""
    if (type(source_platform_id) is not str
            or _ID.fullmatch(source_platform_id) is None
            or type(source_generation) is not int
            or not 1 <= source_generation <= _MAX_INT
            or type(bind_port) is not int or not 1 <= bind_port <= 65535):
        raise PermissionError("explicit source identity, RUN epoch and listening port required")
    _, canonical = _private_bind(bind_host)
    if canonical != bind_host:
        raise PermissionError("owner Hub authorization requires canonical numeric IP")
    return {
        "platform_id": source_platform_id,
        "source_generation": source_generation,
        "bind_host": canonical,
        "bind_port": bind_port,
        "protocol": HUB_PROTOCOL,
    }


class CurrentLibraryHubAuthority:
    """Explicit source-side SAFE grant; independent of destination generation."""

    def __init__(
        self, *, permissions: PermissionStore, stop: OperatorStopStore,
        current_status: Callable[[], Mapping[str, object]],
        source_platform_id: str, source_generation: int,
        bind_host: str, bind_port: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(permissions, PermissionStore) or not isinstance(stop, OperatorStopStore):
            raise TypeError("real current SAFE/STOP owner stores required")
        if not callable(current_status):
            raise TypeError("source Platform service status reader required")
        if clock is not None and not callable(clock):
            raise TypeError("source service clock required")
        self.scope = selected_hub_grant_scope(
            source_platform_id=source_platform_id,
            source_generation=source_generation,
            bind_host=bind_host, bind_port=bind_port,
        )
        self.permissions = permissions
        self.stop = stop
        self.status = current_status
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def __call__(self) -> bool:
        instant = self.clock()
        if not isinstance(instant, datetime) or instant.utcoffset() is None:
            return False
        state = self.status()
        if (not isinstance(state, Mapping)
                or state.get("platform_id") != self.scope["platform_id"]
                or type(state.get("generation")) is not int
                or state["generation"] != self.scope["source_generation"]
                or state.get("operator_stop") is not False
                or self.stop.current().active):
            return False
        for grant in self.permissions.grants(active_only=False):
            if (grant.capability == HUB_CAPABILITY
                    and type(grant.scope) is dict
                    and set(grant.scope) == HUB_SCOPE
                    and grant.matches(self.scope, now=instant)):
                return True
        return False


class CurrentLibrarySourcePeerAuthorizer:
    """Verify current recipient certificate and exact owner peer scope at source."""

    def __init__(
        self, *, permissions: PermissionStore,
        hub_enabled: CurrentLibraryHubAuthority,
        signed_transfer: PinnedChunkTransfer,
        expected_recipient_certificate_sha256: str,
        publisher_current: Callable[[PinnedChunkTransfer], bool],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(permissions, PermissionStore):
            raise TypeError("real SAFE PermissionStore required")
        if not isinstance(hub_enabled, CurrentLibraryHubAuthority):
            raise TypeError("real source Platform Hub authority required")
        if not isinstance(signed_transfer, PinnedChunkTransfer):
            raise TypeError("independently selected signed transfer required")
        if (type(expected_recipient_certificate_sha256) is not str
                or _SHA.fullmatch(expected_recipient_certificate_sha256) is None):
            raise PermissionError("independently pinned recipient TLS certificate required")
        if not callable(publisher_current):
            raise PermissionError("independently verified publisher revocation required")
        if clock is not None and not callable(clock):
            raise TypeError("trusted source current clock required")
        if signed_transfer.source_platform_id != hub_enabled.scope["platform_id"]:
            raise PermissionError("Hub is not the transfer's signed source Platform")
        if signed_transfer.target_platform_id == signed_transfer.source_platform_id:
            raise PermissionError("peer serving requires distinct enrolled recipient")
        self.permissions = permissions
        self.hub = hub_enabled
        self.transfer = signed_transfer
        self.certificate_sha256 = expected_recipient_certificate_sha256
        self.publisher_current = publisher_current
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def __call__(
        self, tls_socket: ssl.SSLSocket, peer_fingerprint: str,
        transfer: PinnedChunkTransfer, offset: int, length: int,
    ) -> bool:
        if (transfer != self.transfer
                or type(offset) is not int or type(length) is not int
                or offset < 0 or not 1 <= length <= _MAX_CHUNK
                or offset > transfer.size_bytes - length):
            raise PermissionError("source-side peer request differs from signed selected transfer")
        fingerprint = _require_verified_tls13_peer(tls_socket)
        if (type(peer_fingerprint) is not str or fingerprint != peer_fingerprint
                or fingerprint != self.certificate_sha256):
            raise PermissionError("source-side mTLS recipient certificate differs from owner enrollment")

        def current() -> bool:
            now = self.clock()
            if not isinstance(now, datetime) or now.utcoffset() is None:
                return False
            if (self.hub() is not True
                    or self.publisher_current(transfer) is not True):
                return False
            expected = {
                "source_platform_id": transfer.source_platform_id,
                "target_platform_id": transfer.target_platform_id,
                "certificate_sha256": fingerprint,
                "manifest_digest": transfer.manifest_sha256,
                "content_digest": transfer.content_sha256,
                "artifact_kind": transfer.artifact_kind,
                "catalog_revision": transfer.catalog_revision,
                "data_class": transfer.data_class,
                "license_distribution": transfer.license_distribution,
            }
            for grant in self.permissions.grants(active_only=False):
                scope = grant.scope
                if (grant.capability != PEER_CAPABILITY
                        or type(scope) is not dict or set(scope) != PEER_SCOPE):
                    continue
                chunk_cap, total_cap = scope["max_chunk_bytes"], scope["max_total_bytes"]
                if (type(chunk_cap) is not int or not 1 <= chunk_cap <= _MAX_CHUNK
                        or type(total_cap) is not int or not 1 <= total_cap <= _MAX_INT
                        or length > chunk_cap or transfer.size_bytes > total_cap):
                    continue
                if grant.matches(
                    {**expected, "max_chunk_bytes": chunk_cap,
                     "max_total_bytes": total_cap}, now=now,
                ):
                    return True
            return False

        if current() is not True or current() is not True:
            raise PermissionError("current owner-approved source Hub or recipient peer grant unavailable")
        return True
