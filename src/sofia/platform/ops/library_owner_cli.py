"""Personal-use Project Aegis owner Library CLI (Core-free, headless).

Local state belongs to ONE installed Platform and ONE human owner. No tenant,
commercial CA, web service, third-party account, automatic publisher trust,
model download or Core startup. This tool CANNOT create a SAFE approval.

Usage:
  python -m sofia.platform.ops.library_owner_cli --state STATE --platform-id ID status
  python -m sofia.platform.ops.library_owner_cli --state STATE --platform-id ID prepare-enroll --source-platform-id HUB --public-key KEY --catalog-generation 1 --minimum-revision 1
  python -m sofia.platform.ops.library_owner_cli --state STATE --platform-id ID enroll --source-platform-id HUB --public-key KEY --catalog-generation 1 --minimum-revision 1 --approval-id ID
  python -m sofia.platform.ops.library_owner_cli --state STATE --platform-id ID import-index --file SIGNED_INDEX
  python -m sofia.platform.ops.library_owner_cli --state STATE --platform-id ID prepare-revoke
  python -m sofia.platform.ops.library_owner_cli --state STATE --platform-id ID revoke --approval-id ID

A separate attended owner-secret/WebAuthn workflow must record the exact
approval fingerprint returned by prepare-enroll/prepare-revoke before the
effectful command can consume it. Never paste your owner secret here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

from sofia.platform.run.library_owner_trust import (
    ENROLL_CAPABILITY, REVOKE_CAPABILITY, OwnerLibraryTrustDenied,
    OwnerLibraryTrustStore, enrollment_parameters, revocation_parameters,
)
from sofia.platform.safe.execution_approval import execution_fingerprint
from sofia.platform.state.private_file import assert_no_redirected_components


def _read_bounded_file(path: Path | str, *, max_bytes: int, exact: int | None = None) -> bytes:
    file = Path(path).absolute()
    assert_no_redirected_components(file, include_leaf=True)
    before = file.stat(follow_symlinks=False)
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 1 <= before.st_size <= max_bytes
            or (exact is not None and before.st_size != exact)):
        raise OwnerLibraryTrustDenied("reviewed bounded owner-selected file required")
    fd = os.open(
        file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        opened = os.fstat(fd)
        before_id = (
            before.st_dev, before.st_ino, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns,
        )
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino, opened.st_size,
                    opened.st_mtime_ns, opened.st_ctime_ns) != before_id):
            raise OwnerLibraryTrustDenied("selected publisher file changed during open")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            data = handle.read(max_bytes + 1)
        after = os.fstat(fd)
        assert_no_redirected_components(file, include_leaf=True)
        last = file.stat(follow_symlinks=False)
        if (len(data) != before.st_size
                or (after.st_dev, after.st_ino, after.st_size,
                    after.st_mtime_ns, after.st_ctime_ns) != before_id
                or (last.st_dev, last.st_ino, last.st_size,
                    last.st_mtime_ns, last.st_ctime_ns) != before_id):
            raise OwnerLibraryTrustDenied("owner-selected publisher file changed during read")
        return data
    finally:
        os.close(fd)


def _result(payload: dict[str, object]) -> None:
    print(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ), flush=True)


def _approval_preview(
    *, capability: str, parameters: dict[str, object],
) -> dict[str, object]:
    return {
        "schema": "aegis.library.personal-owner-approval-preview.v1",
        "capability": capability,
        "request_fingerprint": execution_fingerprint(capability, parameters),
        "parameters": parameters,
        "owner_approval_recorded": False,
        "effect_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True,
                        help="already initialized canonical Platform-local SQLite")
    parser.add_argument("--platform-id", required=True,
                        help="the installed immutable Platform ID, not a new name")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("status")
    for name in ("prepare-enroll", "enroll"):
        command = actions.add_parser(name)
        command.add_argument("--source-platform-id", required=True)
        command.add_argument("--public-key", type=Path, required=True)
        command.add_argument("--catalog-generation", type=int, required=True)
        command.add_argument("--minimum-revision", type=int, required=True)
        if name == "enroll":
            command.add_argument("--approval-id", required=True)
    actions.add_parser("prepare-revoke")
    command = actions.add_parser("revoke")
    command.add_argument("--approval-id", required=True)
    command = actions.add_parser("import-index")
    command.add_argument("--file", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        store = OwnerLibraryTrustStore(
            args.state, platform_id=args.platform_id,
        )
        if args.action == "status":
            pin = store.current()
            if pin is None:
                state, last_revision = "UNENROLLED", None
            elif not pin.active:
                state, last_revision = "REVOKED", None
            else:
                try:
                    signed = store()
                    state = "SIGNED_INDEX_CURRENT" if signed else "INDEX_UNAVAILABLE"
                    last_revision = (
                        None if signed is None
                        else json.loads(signed.raw_signed_index)["catalog_revision"]
                    )
                except (ValueError, PermissionError, RuntimeError, OSError):
                    state, last_revision = "SIGNED_INDEX_UNAVAILABLE_OR_STALE", None
            _result({
                "schema": "aegis.library.personal-owner-status.v1",
                "platform_id": store.platform_id,
                "owner_mode": "SINGLE_OWNER_PRIVATE",
                "publisher_state": state,
                "source_platform_id": None if pin is None else pin.source_platform_id,
                "publisher_key_sha256": None if pin is None else pin.public_key_sha256,
                "trust_generation": None if pin is None else pin.trust_generation,
                "minimum_catalog_revision": None if pin is None else pin.minimum_catalog_revision,
                "verified_catalog_revision": last_revision,
                "install_executed": False, "core_activated": False,
            })
            return 0
        if args.action in {"prepare-enroll", "enroll"}:
            public = _read_bounded_file(args.public_key, max_bytes=32, exact=32)
            previous = store.current()
            generation = 0 if previous is None else previous.trust_generation
            params = enrollment_parameters(
                state_path=store.path, platform_id=store.platform_id,
                source_platform_id=args.source_platform_id,
                public_key=public,
                catalog_generation=args.catalog_generation,
                minimum_catalog_revision=args.minimum_revision,
                previous_trust_generation=generation,
            )
            if args.action == "prepare-enroll":
                _result(_approval_preview(
                    capability=ENROLL_CAPABILITY, parameters=params,
                ))
            else:
                pin = store.enroll(
                    source_platform_id=args.source_platform_id,
                    public_key=public,
                    catalog_generation=args.catalog_generation,
                    minimum_catalog_revision=args.minimum_revision,
                    approval_id=args.approval_id,
                )
                _result({
                    "schema": "aegis.library.personal-owner-effect.v1",
                    "result": "OWNER_PUBLISHER_ENROLLED",
                    "publisher_key_sha256": pin.public_key_sha256,
                    "trust_generation": pin.trust_generation,
                    "signed_catalog_available": False,
                    "install_executed": False,
                })
            return 0
        if args.action in {"prepare-revoke", "revoke"}:
            pin = store.current()
            if pin is None or not pin.active:
                raise OwnerLibraryTrustDenied("no active owner publisher root")
            params = revocation_parameters(state_path=store.path, pin=pin)
            if args.action == "prepare-revoke":
                _result(_approval_preview(
                    capability=REVOKE_CAPABILITY, parameters=params,
                ))
            else:
                result = store.revoke(approval_id=args.approval_id)
                _result({
                    "schema": "aegis.library.personal-owner-effect.v1",
                    "result": "OWNER_PUBLISHER_REVOKED",
                    "trust_generation": result.trust_generation,
                    "install_executed": False,
                })
            return 0
        if args.action == "import-index":
            signed = _read_bounded_file(args.file, max_bytes=65536)
            digest = store.accept_signed_catalog(signed)
            _result({
                "schema": "aegis.library.personal-owner-effect.v1",
                "result": "SIGNED_CATALOG_CACHED",
                "signed_index_sha256": digest,
                "install_executed": False, "core_activated": False,
            })
            return 0
        raise OwnerLibraryTrustDenied("unknown owner Library operation")
    except (
        OwnerLibraryTrustDenied, PermissionError, RuntimeError,
        ValueError, TypeError, OSError, sqlite3.Error,
    ) as exc:
        print(
            "Aegis owner Library operation refused (" + type(exc).__name__ + ")",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
