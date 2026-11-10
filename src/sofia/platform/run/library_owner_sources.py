"""Read-only single-owner Artifact Library status from canonical Platform state.

This is local OS-authenticated service evidence, NOT a signed publisher
package, owner grant, model readiness, Fleet heartbeat or installation
receipt. Only the installed Platform service supplies the store and its own
child Hub. Unknown/revoked values must not be promoted to healthy in UI.
No paths, credentials, keys, certificate identities or private Core data are
returned to clients.
"""
from __future__ import annotations

from collections.abc import Mapping

from sofia.platform.run.library_owner_trust import (
    OwnerLibraryTrustDenied, OwnerLibraryTrustStore,
)
from sofia.platform.run.library_read_dispatch import InstalledSignedCatalogSource
from sofia.platform.ops.library_signed_index import SignedLibraryIndexRejected
from sofia.sdk.platform_library import SOURCES_STATUS_SCHEMA

_MAX = 2**53 - 1


def owner_library_source_status(
    *,
    status: Mapping[str, object],
    owner_trust: OwnerLibraryTrustStore | None,
    hosted_hub: object | None,
) -> dict[str, object]:
    """Construct exact approved owner-only read projection.

    Caller must have already verified the native OS principal, the exact
    standing read grant, current RUN generation and STOP before calling.
    """
    if (not isinstance(status, Mapping)
            or type(status.get("platform_id")) is not str
            or type(status.get("generation")) is not int
            or not 1 <= status["generation"] <= _MAX
            or status.get("operator_stop") is not False):
        raise PermissionError("current STOP-free Platform status required")
    if owner_trust is not None and not isinstance(owner_trust, OwnerLibraryTrustStore):
        raise PermissionError("canonical personal owner publisher store required")

    source_platform_id = None
    publisher_state = "UNKNOWN"
    catalog_state = "UNAVAILABLE"
    if owner_trust is not None:
        if owner_trust.platform_id != status["platform_id"]:
            raise PermissionError("owner publisher pin belongs to another Platform")
        pin = owner_trust.current()
        if pin is None:
            publisher_state = "UNENROLLED"
        else:
            source_platform_id = pin.source_platform_id
            if not pin.active:
                publisher_state = "REVOKED"
            elif owner_trust.publisher_current(
                pin.public_key_sha256, pin.trust_generation,
            ) is True:
                publisher_state = "CURRENT"
                try:
                    reviewed = owner_trust()
                except (OwnerLibraryTrustDenied, SignedLibraryIndexRejected):
                    # A corrupt/expired signed page is NOT an absent clean
                    # Library. This status cannot confer any trust.
                    catalog_state = "UNVERIFIED"
                else:
                    if reviewed is not None:
                        if not isinstance(reviewed, InstalledSignedCatalogSource):
                            raise PermissionError("owner Library signed profile type changed")
                        catalog_state = "CURRENT"
            else:
                publisher_state = "UNKNOWN"

    hub_state = "CLOSED"
    served_chunks = 0
    served_bytes = 0
    if hosted_hub is not None:
        if not callable(getattr(hosted_hub, "serving_status", None)):
            raise PermissionError("unrecognized installed Hub child")
        snapshot = hosted_hub.serving_status()
        if (type(snapshot) is not dict
                or snapshot.get("schema") != "aegis.platform.library.hub-worker.v1"):
            raise PermissionError("Hub worker status is not canonical")
        hub_state = snapshot.get("state")
        served_chunks = snapshot.get("served_chunks")
        served_bytes = snapshot.get("served_bytes")
        if (hub_state not in {"CLOSED", "OPEN_IDLE", "SERVING"}
                or type(served_chunks) is not int
                or type(served_bytes) is not int
                or not 0 <= served_chunks <= _MAX
                or not 0 <= served_bytes <= _MAX):
            raise PermissionError("unbounded or unverifiable local Hub observation")
        # Alive thread alone is not current owner authority. A revoked
        # session can be draining and must not appear as serving READY.
        if hub_state == "SERVING":
            if not callable(getattr(hosted_hub, "_hub_grant", None)):
                raise PermissionError("missing current owner Hub grant reader")
            if hosted_hub._hub_grant() is not True:
                hub_state = "UNKNOWN"

    return {
        "schema": SOURCES_STATUS_SCHEMA,
        "owner_mode": "SINGLE_OWNER_PRIVATE",
        "source_platform_id": source_platform_id,
        "publisher_state": publisher_state,
        "catalog_state": catalog_state,
        "hub_state": hub_state,
        "served_chunks": served_chunks,
        "served_bytes": served_bytes,
    }
