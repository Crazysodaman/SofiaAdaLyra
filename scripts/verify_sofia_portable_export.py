#!/usr/bin/env python3
"""Offline, read-only validator for Sofía's portable conversations JSONL v1.

Requires only Python's standard library. Does not import or start Sofía,
connect to SQLite, reveal message contents, write files or validate owner
authorization. JSONL footer SHA-256 is an accidental-corruption checksum;
the original encrypted backup manifest/HMAC remains the authenticated source.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sys


_SCHEMA = "sofia.portable-conversations.v1"
_MAX_LINE_BYTES = 64 * 1024 * 1024
_RECORD_PHASES = {
    "original_message": 1,
    "thread": 2,
    "thread_source_link": 3,
}


@dataclass(frozen=True)
class VerifiedPortableExport:
    message_count: int
    thread_count: int
    link_count: int
    preceding_lines_sha256: str


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-finite JSON number is forbidden")


def _unique_object_fields(pairs: list[tuple[str, object]]) -> dict:
    """Reject ambiguous JSON. Checksums do not establish field semantics."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate portable JSON field")
        result[key] = value
    return result


def _require_nonempty_text(item: dict, field: str) -> None:
    value = item.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"portable export missing {field}")


def verify_portable_export(
    path: Path, *, max_line_bytes: int = _MAX_LINE_BYTES,
) -> VerifiedPortableExport:
    """Validate a complete v1 JSONL export without retaining private text.

    Reads one capped line at a time. Authentication, audience consent,
    signature trust, erasure freshness and semantic truth MUST be verified
    separately against the original independently authenticated snapshot.
    """
    if not isinstance(path, Path) or not path.is_file():
        raise FileNotFoundError("existing portable JSONL file required")
    if type(max_line_bytes) is not int or not 1024 <= max_line_bytes <= _MAX_LINE_BYTES:
        raise ValueError("bounded maximum record bytes required")
    digest = sha256()
    counts = {"original_message": 0, "thread": 0, "thread_source_link": 0}
    line_number = 0
    phase = 0
    footer = None
    with path.open("rb") as source:
        while True:
            raw = source.readline(max_line_bytes + 1)
            if not raw:
                break
            line_number += 1
            if len(raw) > max_line_bytes:
                raise ValueError(
                    f"portable record {line_number} exceeds maximum size"
                )
            if not raw.endswith(b"\n"):
                raise ValueError(f"portable record {line_number} missing newline")
            try:
                record = json.loads(
                    raw.decode("utf-8"),
                    parse_constant=_reject_json_constant,
                    object_pairs_hook=_unique_object_fields,
                )
            except (UnicodeDecodeError, ValueError) as exc:
                raise ValueError(
                    f"invalid UTF-8 JSON at portable record {line_number}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError("portable records must be JSON objects")
            kind = record.get("record_type")
            if line_number == 1:
                if kind != "header" or record.get("schema") != _SCHEMA:
                    raise ValueError("missing exact portable export header/schema")
                if record.get("privacy") != "ALL_AUDIENCES_SENSITIVE_PLAINTEXT":
                    raise ValueError("portable export privacy label is missing")
                _require_nonempty_text(record, "created_at")
                if (
                    record.get("authority")
                    != "offline_operator_export_not_a_channel_grant"
                    or record.get("source")
                    != "verified_offline_canonical_sqlite"
                ):
                    raise ValueError("portable export authority/source labels invalid")
                digest.update(raw)
                continue
            if kind == "footer":
                if footer is not None:
                    raise ValueError("duplicate portable export footer")
                footer = record
                break
            if kind not in _RECORD_PHASES:
                raise ValueError(f"unknown portable record type at line {line_number}")
            next_phase = _RECORD_PHASES[kind]
            if next_phase < phase:
                raise ValueError("portable record classes are out of order")
            phase = next_phase
            if kind == "original_message":
                for field in ("message_id", "session_id", "role", "created_at"):
                    _require_nonempty_text(record, field)
                if not isinstance(record.get("content"), str):
                    raise ValueError("original content must be present as exact text")
                if record.get("binding") not in (
                    "currently_bound", "unbound_not_authorized",
                ):
                    raise ValueError("unknown original binding classification")
                binding_fields = ("principal_id", "audience_id", "audience_kind")
                if record["binding"] == "currently_bound":
                    for field in binding_fields:
                        _require_nonempty_text(record, field)
                elif any(record.get(field) is not None for field in binding_fields):
                    raise ValueError("unbound original has audience credentials")
            elif kind == "thread":
                for field in (
                    "thread_id", "owner_principal_id", "kind", "name", "created_at",
                ):
                    _require_nonempty_text(record, field)
                if record.get("access") != "catalog_not_a_cross_channel_grant":
                    raise ValueError("portable thread catalog access label invalid")
            elif kind == "thread_source_link":
                for field in (
                    "thread_id", "source_message_id", "source_session_id",
                    "source_audience_id", "visibility", "linked_at",
                ):
                    _require_nonempty_text(record, field)
                for field in (
                    "current_original_available",
                    "current_source_audience_matches",
                ):
                    if type(record.get(field)) is not bool:
                        raise ValueError("source availability labels must be booleans")
                if record.get("access") != "reference_only_not_an_authorization":
                    raise ValueError("portable link access label invalid")
                if (
                    record["current_source_audience_matches"]
                    and not record["current_original_available"]
                ):
                    raise ValueError("missing original cannot match source audience")
            counts[kind] += 1
            digest.update(raw)
        if footer is None:
            raise ValueError("portable export missing footer")
        if source.read(1):
            raise ValueError("portable export contains trailing records after footer")
    if footer.get("schema") != _SCHEMA:
        raise ValueError("footer schema disagrees with portable header")
    expected = footer.get("preceding_lines_sha256")
    if (
        not isinstance(expected, str) or len(expected) != 64
        or expected != digest.hexdigest()
    ):
        raise ValueError("portable JSONL content hash mismatch")
    for key, count in (
        ("original_message_count", counts["original_message"]),
        ("thread_count", counts["thread"]),
        ("thread_source_link_count", counts["thread_source_link"]),
    ):
        if type(footer.get(key)) is not int or footer[key] != count:
            raise ValueError(f"portable footer {key} disagrees with records")
    return VerifiedPortableExport(
        message_count=counts["original_message"],
        thread_count=counts["thread"],
        link_count=counts["thread_source_link"],
        preceding_lines_sha256=digest.hexdigest(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only SHA-256/structure check for Sofía conversation JSONL."
    )
    parser.add_argument("export", type=Path, help="owner-approved plaintext JSONL")
    args = parser.parse_args(argv)
    try:
        receipt = verify_portable_export(args.export)
    except (OSError, ValueError) as exc:
        print(f"portable export INVALID: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        "portable export structure/checksum valid (NOT cryptographic authenticity): "
        f"messages={receipt.message_count} threads={receipt.thread_count} "
        f"links={receipt.link_count} sha256={receipt.preceding_lines_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
