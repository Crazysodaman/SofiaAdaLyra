"""Command-line construction, verification and signing of release evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import platform
import sys

from sofia.package_metadata import application_version
from sofia.config.model import CURRENT_CONFIGURATION_SCHEMA_VERSION
from sofia.dev.release_signing import sign_manifest_file
from sofia.dev.supply_chain import (
    construct_release_evidence,
    verify_release_evidence,
)
from sofia.distributed.version import CURRENT_FLEET_PROTOCOL_VERSION
from sofia.state.sqlite_plane import SQLiteStatePlane


def _read_digest(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if len(value) != 64:
        raise ValueError(f"{path} does not contain a 64-character SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(
            f"{path} does not contain a hexadecimal SHA-256 digest"
        ) from exc
    return value.casefold()


def _construct(args) -> int:
    version = application_version()
    release_id = args.release_id or (
        f"sofia-{version}-{args.git_revision[:12]}"
    )
    result = construct_release_evidence(
        release_id=release_id,
        git_revision=args.git_revision,
        application_version=version,
        python_version=platform.python_version(),
        dependency_lock_path=Path(args.lock),
        wheel_path=Path(args.wheel),
        source_dir=Path(args.source),
        constitution_sha256=_read_digest(
            Path(args.constitution_hash)
        ),
        state_schema_min=SQLiteStatePlane.SCHEMA_REVISION,
        state_schema_max=SQLiteStatePlane.SCHEMA_REVISION,
        fleet_protocol_version=str(
            CURRENT_FLEET_PROTOCOL_VERSION
        ),
        fleet_agent_version=version,
        configuration_schema_version=(
            CURRENT_CONFIGURATION_SCHEMA_VERSION
        ),
        output_dir=Path(args.output),
        created_at=datetime.now(timezone.utc),
        parent_release_id=args.parent_release_id,
        parent_manifest_sha256=args.parent_manifest_sha256,
    )
    print(
        f"release evidence created: {result.manifest.release_id} "
        f"manifest_sha256={result.manifest.manifest_sha256}"
    )
    return 0


def _verify(args) -> int:
    manifest = verify_release_evidence(Path(args.release_dir))
    print(
        f"release evidence verified: {manifest.release_id} "
        f"manifest_sha256={manifest.manifest_sha256}"
    )
    return 0


def _sign(args) -> int:
    password = (
        None
        if args.password_env is None
        else __import__("os").environ.get(args.password_env, "").encode()
    )
    if args.password_env is not None and not password:
        raise ValueError(
            f"password environment variable {args.password_env!r} is empty"
        )
    signature = sign_manifest_file(
        Path(args.manifest),
        private_key_path=Path(args.private_key),
        signature_path=Path(args.signature),
        password=password,
    )
    print(
        f"release manifest signed: {args.signature} "
        f"bytes={len(signature)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.dev.release_cli"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    construct = sub.add_parser("construct")
    construct.add_argument("--git-revision", required=True)
    construct.add_argument("--lock", required=True)
    construct.add_argument("--wheel", required=True)
    construct.add_argument("--source", required=True)
    construct.add_argument("--constitution-hash", required=True)
    construct.add_argument("--output", required=True)
    construct.add_argument("--release-id")
    construct.add_argument("--parent-release-id")
    construct.add_argument("--parent-manifest-sha256")
    construct.set_defaults(handler=_construct)

    verify = sub.add_parser("verify")
    verify.add_argument("--release-dir", required=True)
    verify.set_defaults(handler=_verify)

    sign = sub.add_parser("sign")
    sign.add_argument("--manifest", required=True)
    sign.add_argument("--private-key", required=True)
    sign.add_argument("--signature", required=True)
    sign.add_argument("--password-env")
    sign.set_defaults(handler=_sign)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except Exception as exc:
        print(
            f"release command failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
