"""D028-03/04 guarded mTLS peer admission, no new owner authority.

THIS IS NOT A LIVE HUB. It opens no socket, issues no cert, streams no bytes
and never approves a grant. Only the existing Rust-owned Platform service
may pass a real SSL socket created by an independently reviewed CERT_REQUIRED
TLS 1.3 context and current local service/STOP and SAFE backing objects.

Until owner enrollment and the dedicated grant capability are formally
approved, library.peer.fetch remains a protected unknown capability and
this gate refuses every real peer. This is deliberately NOT a Hub signoff.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from hashlib import sha256
import re
import ssl

from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.safe.operator_stop import OperatorStopStore

CAPABILITY = "library.peer.fetch"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PEER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}$")
_SCOPE = frozenset({
    "source_platform_id", "target_platform_id", "certificate_sha256",
    "manifest_digest", "content_digest", "artifact_kind",
    "catalog_revision", "data_class", "license_distribution",
    "max_chunk_bytes", "max_total_bytes",
})
_MAX_CHUNK = 1024 * 1024
_MAX_INTEGER = 2**53 - 1


def _require_verified_tls13_peer(socket: ssl.SSLSocket) -> str:
    """Certificate hash from real mutually verified TLS, never peer JSON."""
    if not isinstance(socket, ssl.SSLSocket):
        raise PermissionError("real OS TLS socket required")
    context = socket.context
    if (context is None or context.verify_mode != ssl.CERT_REQUIRED
            or socket.version() != "TLSv1.3"):
        raise PermissionError("mutually authenticated TLS1.3 required")
    peer = socket.getpeercert(binary_form=True)
    if not isinstance(peer, bytes) or not 1 <= len(peer) <= 64 * 1024:
        raise PermissionError("verified peer certificate absent or unbounded")
    return sha256(peer).hexdigest()


def admit_owner_enrolled_library_chunk(
    *,
    tls_socket: ssl.SSLSocket,
    permissions: PermissionStore,
    stop: OperatorStopStore,
    current_status: Callable[[], Mapping[str, object]],
    source_platform_id: str,
    target_platform_id: str,
    expected_generation: int,
    catalog_revision: int,
    manifest_digest: str,
    content_digest: str,
    artifact_kind: str,
    offset: int,
    length: int,
    total_bytes: int,
    now: datetime | None = None,
) -> str:
    """Fail-closed peer read checkpoint; caller must repeat **per chunk**.

    The values must originate from the service's enrolled/signed catalog
    and pinned request, never from an untrusted Hub self-claim. The result
    is a *peer fingerprint*, not permission to install, activate or persist
    any contents. With no existing owner-approved SAFE grant, always deny.
    """
    if not isinstance(permissions, PermissionStore) or not isinstance(stop, OperatorStopStore):
        raise TypeError("canonical SAFE and STOP stores required")
    if not callable(current_status):
        raise TypeError("service-owned current status required")
    for identity in (source_platform_id, target_platform_id):
        if type(identity) is not str or _PEER_ID.fullmatch(identity) is None:
            raise ValueError("pinned Platform identity required")
    for digest in (manifest_digest, content_digest):
        if type(digest) is not str or _SHA256.fullmatch(digest) is None:
            raise ValueError("signed pinned digest required")
    if artifact_kind not in {"platform_release", "sdk", "core_runtime",
                             "core_definition", "module", "model", "asset", "rollback"}:
        raise ValueError("reviewed artifact class required")
    for number in (expected_generation, catalog_revision, offset, length, total_bytes):
        if type(number) is not int or number < 0 or number > _MAX_INTEGER:
            raise ValueError("bounded transfer revision and offsets required")
    if (expected_generation < 1 or not 1 <= length <= _MAX_CHUNK
            or total_bytes < 1 or offset > total_bytes - length):
        raise ValueError("transfer chunk out of declared bounds")
    moment = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(moment, datetime) or moment.utcoffset() is None:
        raise PermissionError("trusted aware service clock required")
    fingerprint = _require_verified_tls13_peer(tls_socket)
    expected = {
        "source_platform_id": source_platform_id,
        "target_platform_id": target_platform_id,
        "certificate_sha256": fingerprint,
        "manifest_digest": manifest_digest,
        "content_digest": content_digest,
        "artifact_kind": artifact_kind,
        "catalog_revision": catalog_revision,
        "data_class": "public",
        "license_distribution": "permitted",
        "max_chunk_bytes": length,
        "max_total_bytes": total_bytes,
    }

    def checked() -> bool:
        state = current_status()
        if (type(state) is not dict
                or state.get("platform_id") != target_platform_id
                or type(state.get("generation")) is not int
                or state["generation"] != expected_generation
                or state.get("operator_stop") is not False
                or state.get("core_started") is not False
                or stop.current().active):
            return False
        # This read re-joins one-use owner proof with current credential
        # version; a rotated secret, revoked grant or expired grant disappears.
        # The scope also binds one SOURCE peer and one TARGET Platform.
        for grant in permissions.grants(active_only=False):
            if (grant.capability == CAPABILITY
                    and isinstance(grant.scope, dict)
                    and set(grant.scope) == _SCOPE
                    and grant.matches(expected, now=moment)):
                # A smaller chunk is permitted only if scope exactly matches;
                # no broad wildcard or silent scope expansion is authorized.
                return True
        return False

    if not checked() or not checked():
        raise PermissionError("current authenticated Library peer grant unavailable")
    return fingerprint
