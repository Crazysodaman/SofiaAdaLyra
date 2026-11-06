"""Bounded read-only status admission from the existing Platform binding owner.

This local adapter returns routing metadata, not credentials or owner authority.
Rust invokes the installed module through a trusted isolated Python executable;
no UI-provided program, enrollment flag or cached snapshot substitutes for it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from sofia.platform.core_link.binding import CoreLinkBindingStore, CoreLinkBindingState
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION

SCHEMA = 'aegis.platform.core-link-status-authority.v1'
MAX_REPLY_BYTES = 16 * 1024


def status_admission(
    store: CoreLinkBindingStore, *, request_id: str,
    minimum_store_revision: int = 1, binding_id: str | None = None,
    expected_binding_revision: int | None = None,
) -> dict[str, object]:
    """Re-read owner selection and status scope; never activate or select it."""
    if not isinstance(request_id, str) or re.fullmatch('[0-9a-f]{64}', request_id) is None:
        raise ValueError('invalid authority request correlation')
    if type(minimum_store_revision) is not int or minimum_store_revision < 1:
        raise ValueError('positive minimum store revision required')
    if (binding_id is None) != (expected_binding_revision is None):
        raise ValueError('binding identity and revision must be supplied together')
    if expected_binding_revision is not None and (
        type(expected_binding_revision) is not int or expected_binding_revision < 1
    ):
        raise ValueError('positive binding revision required')
    snapshot = store.load()

    def denied(revision: int) -> dict[str, object]:
        return dict(schema=SCHEMA, request_id=request_id, store_revision=revision,
                    admission='denied', binding=None)

    selected = snapshot.selected()
    if snapshot.revision < minimum_store_revision or selected is None:
        return denied(snapshot.revision)
    if binding_id is not None and (
        selected.binding_id != binding_id or selected.revision != expected_binding_revision
    ):
        return denied(snapshot.revision)
    try:
        selected, revision = store.require_current_selected(
            binding_id=selected.binding_id, expected_binding_revision=selected.revision,
            minimum_store_revision=max(snapshot.revision, minimum_store_revision),
        )
    except PermissionError:
        return denied(store.load().revision)
    if (selected.state is not CoreLinkBindingState.ACTIVE
            or 'status.read' not in selected.granted_scopes
            or selected.protocol_version != SDK_PROTOCOL_VERSION):
        return denied(revision)
    return dict(schema=SCHEMA, request_id=request_id, store_revision=revision,
                admission='allowed', binding=selected.to_payload())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Read current Core Link status admission')
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--minimum-store-revision', type=int, default=1)
    parser.add_argument('--binding-id')
    parser.add_argument('--binding-revision', type=int)
    args = parser.parse_args(argv)
    try:
        result = status_admission(
            CoreLinkBindingStore(args.store), request_id=args.request_id,
            minimum_store_revision=args.minimum_store_revision, binding_id=args.binding_id,
            expected_binding_revision=args.binding_revision,
        )
        encoded = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(encoded.encode('utf-8')) > MAX_REPLY_BYTES:
            raise ValueError('authority reply exceeds contract')
    except (OSError, RuntimeError, ValueError, TypeError):
        print('Core Link authority unavailable', file=sys.stderr)
        return 2
    print(encoded)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
