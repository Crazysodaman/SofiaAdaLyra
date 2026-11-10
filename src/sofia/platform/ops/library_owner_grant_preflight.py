"""Private single-owner Library grant preflight for the existing SAFE CLI.

An owner should not hand-type current RUN generations or a privileged OS
principal into JSON. This module derives them from canonical installed state
and the executing local OS identity; it only prints a reviewed scope suitable
for the existing owner-authenticated PermissionStore grant workflow.

No signing key, user secret, SAFE approval, grant, listener, Core, model or
other host state is created here. The actual effectful SAFE CLI MUST still
authenticate the owner and consume a separate one-use approval.
"""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
import json
import os
from pathlib import Path
from typing import Callable

from sofia.platform.run.lease import LocalRunLeaseStore
from sofia.platform.run.library_source_gate import (
    HUB_CAPABILITY, selected_hub_grant_scope,
)
from sofia.platform.run.library_read_authority import (
    LIBRARY_READ_CAPABILITY, CATALOG_OPERATION,
)
from sofia.platform.run.library_owner_trust import OwnerLibraryTrustStore


class OwnerLibraryPreflightDenied(PermissionError):
    """No current canonical single-owner Platform state for a scope."""


def _current(store: OwnerLibraryTrustStore, *, now: datetime | None) -> tuple[str, int]:
    if not isinstance(store, OwnerLibraryTrustStore):
        raise OwnerLibraryPreflightDenied("canonical installed single-owner store required")
    instant = datetime.now(timezone.utc) if now is None else now
    if not isinstance(instant, datetime) or instant.utcoffset() is None:
        raise OwnerLibraryPreflightDenied("trusted aware current clock required")
    if store.stop.current().active:
        raise OwnerLibraryPreflightDenied("operator STOP blocks new Library grants")
    # LocalRunLeaseStore.__init__ normally initializes its own tables.
    # A read-only preflight must never create even those tables on an
    # uncommissioned host. Require the canonical lease schema to exist first.
    store.state.validate()
    with closing(store.state.connect()) as connection:
        existing = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='run_local_lease'"
        ).fetchone()
    if existing is None:
        raise OwnerLibraryPreflightDenied(
            "installed Platform RUN lease is not initialized"
        )
    current = LocalRunLeaseStore(
        store.path, lease_key="platform-service",
    ).current(now=instant)
    if current is None:
        raise OwnerLibraryPreflightDenied("installed Platform RUN is not current")
    return store.platform_id, current.epoch


def _preview(*, platform_id: str, generation: int, capability: str,
             scope: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "aegis.library.personal-owner-standing-scope-preview.v1",
        "owner_mode": "SINGLE_OWNER_PRIVATE",
        "platform_id": platform_id,
        "run_generation": generation,
        "capability": capability,
        "scope": scope,
        "scope_json": json.dumps(
            scope, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ),
        "max_grant_minutes": 60,
        "suggested_grant_minutes": 10,
        "authorization_required": "EXISTING_OWNER_SAFE_ONE_USE",
        "owner_proof_consumed": False,
        "grant_created": False,
        "listener_started": False,
        "core_activated": False,
    }


def preview_personal_hub_grant(
    *, store: OwnerLibraryTrustStore, bind_host: str,
    bind_port: int, now: datetime | None = None,
) -> dict[str, object]:
    platform_id, generation = _current(store, now=now)
    scope = selected_hub_grant_scope(
        source_platform_id=platform_id, source_generation=generation,
        bind_host=bind_host, bind_port=bind_port,
    )
    return _preview(
        platform_id=platform_id, generation=generation,
        capability=HUB_CAPABILITY, scope=scope,
    )


def preview_personal_local_read_grant(
    *, store: OwnerLibraryTrustStore, now: datetime | None = None,
    native_peer: Callable[[], str] | None = None,
) -> dict[str, object]:
    platform_id, generation = _current(store, now=now)
    if native_peer is None:
        if os.name == "nt":
            # Existing verified attended Windows-owner path, not a claimed SID
            # or a Hub-provided identity. Do not read or expose owner secrets.
            from sofia.platform.safe.owner_secret import (
                require_venus_interactive_windows,
            )
            peer = "windows:sid:" + require_venus_interactive_windows(
                require_terminal=True,
            )
        elif os.name == "posix":
            peer = f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
        else:
            raise OwnerLibraryPreflightDenied("unsupported local operator OS")
    else:
        # Dependency injection for disposable tests only. Real commissioning
        # CLI NEVER accepts arbitrary user-supplied OS peer identifiers.
        if not callable(native_peer):
            raise OwnerLibraryPreflightDenied("native peer reader required")
        peer = native_peer()
    if (type(peer) is not str or len(peer) > 160
            or not (peer.startswith("unix:uid:") or peer.startswith("windows:sid:"))):
        raise OwnerLibraryPreflightDenied("exact local OS operator identity required")
    scope = {
        "platform_id": platform_id,
        "peer": peer,
        "operation": CATALOG_OPERATION,
    }
    return _preview(
        platform_id=platform_id, generation=generation,
        capability=LIBRARY_READ_CAPABILITY, scope=scope,
    )
