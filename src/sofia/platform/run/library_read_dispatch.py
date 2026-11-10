"""Read-only D028 catalog over the existing canonical Platform OS IPC.

The caller is a kernel verified Unix UID or Windows pipe SID, checked against
a distinct current one-hour, owner-authenticated SAFE standing grant. The
sender-signed index is then re-verified using a public key supplied by the
*installed service*, never by a peer request. No new listener, local grant,
network client, unsigned catalog fallback, UI-owned authority, or cache writer.

Unconfigured trusted publisher catalog -> typed UNAVAILABLE for an enrolled
operator; unknown/revoked OS caller -> EOF. Only the exact one-page, unfiltered
catalog projection is currently enabled. Other D028 read projections must be
frozen with the Rust consumer before returning successful data.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json

from sofia.platform.ops.library_signed_index import (
    VerifiedLibraryIndex, verify_signed_library_index,
)
from sofia.platform.run.library_read_authority import (
    CATALOG_OPERATION, SOURCES_OPERATION,
)
from sofia.sdk.platform_library import (
    LIBRARY_PROTOCOL, LIBRARY_RESPONSE_SCHEMA,
    UntrustedLibraryRequest, UntrustedLibraryResponse,
)

_MAX_RESPONSE_BYTES = 32768


@dataclass(frozen=True, slots=True)
class InstalledSignedCatalogSource:
    """Trusted service configuration, not network-supplied publisher data."""

    raw_signed_index: bytes
    trusted_publisher_public_key: bytes
    expected_publisher_key_sha256: str
    expected_source_platform_id: str
    expected_catalog_generation: int
    minimum_catalog_revision: int
    publisher_key_current: Callable[[str], bool]


class LibraryReadDispatcher:
    def __init__(
        self, *,
        current_status: Callable[[], Mapping[str, object]],
        authorize_os_peer: Callable[[str, str], bool],
        installed_signed_catalog: Callable[[], InstalledSignedCatalogSource | None],
        read_owner_sources: Callable[[], dict[str, object]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        for callback in (current_status, authorize_os_peer, installed_signed_catalog):
            if not callable(callback):
                raise TypeError("real installed Platform reader authority required")
        self._status = current_status
        self._authorize = authorize_os_peer
        self._catalog = installed_signed_catalog
        if read_owner_sources is not None and not callable(read_owner_sources):
            raise TypeError("canonical owner Library source status callback required")
        self._sources = read_owner_sources
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _status_current(
        status: Mapping[str, object], request: UntrustedLibraryRequest,
    ) -> bool:
        return (isinstance(status, Mapping)
                and status.get("platform_id") == request.target_platform_id
                and type(status.get("generation")) is int
                and status["generation"] == request.expected_generation
                and status.get("operator_stop") is False)

    @staticmethod
    def _reply(
        request: UntrustedLibraryRequest, *, observed: datetime,
        data: dict | None = None, denial: str | None = None,
    ) -> dict[str, object]:
        if (data is None) == (denial is None):
            raise ValueError("one verified catalog or one denial required")
        doc = {
            "schema": LIBRARY_RESPONSE_SCHEMA,
            "protocol": LIBRARY_PROTOCOL,
            "request_id": request.request_id,
            "correlation_id": request.correlation_id,
            "operation": request.operation,
            "platform_id": request.target_platform_id,
            "platform_generation": request.expected_generation,
            "state_revision": request.expected_revision,
            "observed_at": observed.astimezone(timezone.utc).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
            "outcome": "DENIED" if denial is not None else "OK",
            "data": data,
            "denial": None if denial is None else {"code": denial},
        }
        raw = json.dumps(
            doc, sort_keys=True, separators=(",", ":"),
            allow_nan=False, ensure_ascii=False,
        ).encode("utf-8")
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise PermissionError("bounded signed Library catalog response exceeded")
        # Do not send a projection that the client SDK would reject.
        UntrustedLibraryResponse.parse(raw, expected=request, now=observed)
        return doc

    def dispatch(
        self, raw: bytes, *, authenticated_peer: str, now: datetime,
    ) -> dict[str, object]:
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise PermissionError("trusted current service time required")
        if type(authenticated_peer) is not str or not authenticated_peer:
            raise PermissionError("kernel verified OS peer required")
        status = self._status()
        if not isinstance(status, Mapping) or type(status.get("platform_id")) is not str:
            raise PermissionError("canonical Platform identity unavailable")
        request = UntrustedLibraryRequest.parse(
            raw, now=now,
            expected_target_platform_id=status["platform_id"],
        )
        # An unknown operator gets EOF. Never return typed denial before
        # independently validated current owner enrollment.
        if self._authorize(authenticated_peer, request.operation) is not True:
            raise PermissionError("no current owner-enrolled Library read permission")

        def recheck() -> None:
            if (self._authorize(authenticated_peer, request.operation) is not True
                    or not self._status_current(self._status(), request)):
                raise PermissionError("Library read owner enrollment, RUN or STOP changed")

        def deny(code: str) -> dict[str, object]:
            if self._authorize(authenticated_peer, request.operation) is not True:
                raise PermissionError("Library operator revoked before denial")
            observed = self._clock()
            if not isinstance(observed, datetime) or observed.utcoffset() is None:
                raise PermissionError("signed Library observation clock unavailable")
            return self._reply(request, observed=observed, denial=code)

        if status.get("operator_stop") is True:
            return deny("STOPPED")
        if status.get("generation") != request.expected_generation:
            return deny("STALE_GENERATION")
        if not self._status_current(status, request):
            raise PermissionError("Library current Platform service unavailable")
        if request.operation == SOURCES_OPERATION:
            if request.expected_revision != 0:
                return deny("STALE_GENERATION")
            if self._sources is None:
                return deny("UNAVAILABLE")
            snapshot = self._sources()
            if type(snapshot) is not dict:
                raise PermissionError("owner-only Library source status unavailable")
            recheck()
            observed = self._clock()
            if (not isinstance(observed, datetime)
                    or observed.utcoffset() is None):
                raise PermissionError("trusted source observation clock required")
            recheck()
            return self._reply(request, observed=observed, data=snapshot)
        if request.operation != CATALOG_OPERATION:
            return deny("NOT_PERMITTED")
        source = self._catalog()
        if source is None:
            return deny("UNAVAILABLE")
        if not isinstance(source, InstalledSignedCatalogSource):
            raise PermissionError("untrusted Library catalog source implementation")
        verified: VerifiedLibraryIndex = verify_signed_library_index(
            source.raw_signed_index,
            trusted_publisher_public_key=source.trusted_publisher_public_key,
            expected_publisher_key_sha256=source.expected_publisher_key_sha256,
            expected_source_platform_id=source.expected_source_platform_id,
            expected_target_platform_id=request.target_platform_id,
            expected_catalog_generation=source.expected_catalog_generation,
            minimum_catalog_revision=source.minimum_catalog_revision,
            now=now, publisher_key_current=source.publisher_key_current,
        )
        if not verified.matches(verified.catalog):
            raise PermissionError("signed Library catalog mutated during review")
        # No unsanctioned re-pagination or content transformation: the
        # installed service only supplies the exact signed first page.
        document = json.loads(raw)
        params = document["parameters"]
        if (params["cursor"] is not None or params["kinds"]
                or len(verified.catalog["items"]) > params["limit"]
                or verified.catalog["page"]["next_cursor"] is not None
                or verified.catalog["page"]["cursor_state"] != "CURRENT"):
            return deny("NOT_PERMITTED")
        if (verified.catalog_revision != request.expected_revision
                or (status.get("library_revision") is not None
                    and (type(status["library_revision"]) is not int
                         or status["library_revision"] != verified.catalog_revision))):
            return deny("STALE_GENERATION")
        recheck()
        later_revision = self._status().get("library_revision")
        if later_revision is not None and later_revision != verified.catalog_revision:
            raise PermissionError("Library catalog revision changed during observation")
        if source.publisher_key_current(source.expected_publisher_key_sha256) is not True:
            raise PermissionError("publisher revoked during Library catalog observation")
        observed = self._clock()
        if (not isinstance(observed, datetime) or observed.utcoffset() is None
                or observed.astimezone(timezone.utc) >= verified.expires_at
                or not verified.matches(verified.catalog)):
            raise PermissionError("signed Library catalog expired before response")
        recheck()
        final_revision = self._status().get("library_revision")
        if final_revision is not None and final_revision != verified.catalog_revision:
            raise PermissionError("Library catalog revision changed before response")
        return self._reply(
            request, observed=observed, data=verified.catalog,
        )


class LocalReadMultiplexer:
    """Route strict v1 envelopes over the *existing* OS-authenticated socket.

    The routing schema never confers authority. Both dispatchers independently
    authorize exact current OS caller, RUN generation, STOP and operation.
    """
    def __init__(self, *, management, library: LibraryReadDispatcher) -> None:
        if not callable(getattr(management, "dispatch", None)):
            raise TypeError("existing canonical management dispatcher required")
        if not isinstance(library, LibraryReadDispatcher):
            raise TypeError("separate canonical Library read dispatcher required")
        self.management = management
        self.library = library

    def dispatch(
        self, raw: bytes, *, authenticated_peer: str, now: datetime,
    ) -> dict[str, object]:
        if type(raw) is not bytes or not 1 <= len(raw) <= 32768:
            raise PermissionError("bounded local Platform read required")
        try:
            document = json.loads(raw)
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise PermissionError("invalid Platform read envelope") from exc
        if type(document) is not dict:
            raise PermissionError("typed Platform read envelope required")
        if document.get("schema") == "aegis.platform.library.request.v1":
            return self.library.dispatch(
                raw, authenticated_peer=authenticated_peer, now=now,
            )
        return self.management.dispatch(
            raw, authenticated_peer=authenticated_peer, now=now,
        )
