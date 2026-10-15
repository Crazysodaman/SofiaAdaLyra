#!/usr/bin/env python3
"""Offline, stdlib-only integrity/structure verifier for Sofía JSONL v1.

Requires Python 3.10+ but NO Sofía package, Ollama, CUDA, network or secret.
This validates exported plaintext STRUCTURE and a footer checksum. It does
not authenticate the export's origin, restore an erased event, or grant a
channel permission. Authenticate encrypted archives with the backup key.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


SCHEMA = "sofia.portable-conversations.v1"
_MAX_LINE_BYTES = 16 * 1024 * 1024
_RECORD_ORDER = {"original_message": 1, "thread": 2, "thread_source_link": 3}


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("duplicate portable JSON key")
        record[key] = value
    return record


def _no_nonfinite(value: str) -> None:
    raise ValueError("nonfinite JSON number is forbidden")


def _required(record: dict, *fields: str) -> bool:
    return all(isinstance(record.get(key), str) and bool(record[key]) for key in fields)


def verify(path: Path) -> dict[str, int | str]:
    if not path.is_file():
        raise FileNotFoundError("portable JSONL file missing")
    counts = {
        "original_message": 0, "thread": 0,
        "thread_source_link": 0,
    }
    digest = sha256()
    footer = None
    header_seen = False
    phase = 0
    with path.open("rb") as source:
        line_number = 0
        while True:
            # Iterating a file in binary mode allocates an unbounded line
            # before a length check. Reject oversized hostile files first.
            raw = source.readline(_MAX_LINE_BYTES + 1)
            if not raw:
                break
            line_number += 1
            if len(raw) > _MAX_LINE_BYTES:
                raise ValueError(f"line {line_number} exceeds safety limit")
            if not raw.endswith(b"\n"):
                raise ValueError(f"line {line_number} missing newline terminator")
            try:
                record = json.loads(
                    raw.decode("utf-8"),
                    object_pairs_hook=_no_duplicate_keys,
                    parse_constant=_no_nonfinite,
                )
            except (UnicodeError, ValueError) as exc:
                raise ValueError(f"line {line_number} is not valid UTF-8 JSON") from exc
            if not isinstance(record, dict):
                raise ValueError(f"line {line_number} is not an object")
            kind = record.get("record_type")
            if footer is not None:
                raise ValueError("JSONL contains records after integrity footer")
            if not header_seen:
                if (
                    kind != "header" or record.get("schema") != SCHEMA
                    or record.get("privacy") != "ALL_AUDIENCES_SENSITIVE_PLAINTEXT"
                    or record.get("authority")
                        != "offline_operator_export_not_a_channel_grant"
                    or record.get("source") != "verified_offline_canonical_sqlite"
                    or not _required(record, "created_at")
                ):
                    raise ValueError("unknown or incomplete portable export header")
                header_seen = True
            elif kind == "footer":
                if record.get("schema") != SCHEMA:
                    raise ValueError("footer schema mismatch")
                if record.get("preceding_lines_sha256") != digest.hexdigest():
                    raise ValueError("portable export body SHA-256 mismatch")
                for key, value in (
                    ("original_message_count", counts["original_message"]),
                    ("thread_count", counts["thread"]),
                    ("thread_source_link_count", counts["thread_source_link"]),
                ):
                    if type(record.get(key)) is not int or record[key] != value:
                        raise ValueError(f"footer {key} disagrees with export records")
                footer = record
                continue
            elif kind in counts:
                next_phase = _RECORD_ORDER[kind]
                if next_phase < phase:
                    raise ValueError("portable record classes out of order")
                phase = next_phase
                if kind == "original_message":
                    if not _required(
                        record, "message_id", "session_id", "role", "created_at",
                    ) or not isinstance(record.get("content"), str):
                        raise ValueError(f"line {line_number} has invalid original")
                    if record.get("binding") == "currently_bound":
                        if not _required(record, "principal_id", "audience_id", "audience_kind"):
                            raise ValueError("bound original missing audience scope")
                    elif record.get("binding") == "unbound_not_authorized":
                        if any(
                            record.get(field) is not None
                            for field in ("principal_id", "audience_id", "audience_kind")
                        ):
                            raise ValueError("unbound original carries audience scope")
                    else:
                        raise ValueError("unknown original audience binding")
                elif kind == "thread":
                    if not _required(
                        record, "thread_id", "owner_principal_id", "kind",
                        "name", "created_at",
                    ) or record.get("access") != "catalog_not_a_cross_channel_grant":
                        raise ValueError(f"line {line_number} has invalid thread")
                else:
                    if not _required(
                        record, "thread_id", "source_message_id",
                        "source_session_id", "source_audience_id",
                        "visibility", "linked_at",
                    ) or record.get("access") != "reference_only_not_an_authorization":
                        raise ValueError(f"line {line_number} has invalid source link")
                    if any(
                        type(record.get(field)) is not bool
                        for field in (
                            "current_original_available",
                            "current_source_audience_matches",
                        )
                    ) or (
                        record["current_source_audience_matches"]
                        and not record["current_original_available"]
                    ):
                        raise ValueError("source link has impossible audience provenance")
                counts[kind] += 1
            else:
                raise ValueError(f"line {line_number} uses unknown record type")
            digest.update(raw)
    if not header_seen or footer is None:
        raise ValueError("portable export is missing required header or footer")
    return {"schema": SCHEMA, **counts, "body_sha256": digest.hexdigest()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify Sofía plain UTF-8 JSONL recovery export without Sofía."
    )
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = verify(args.file)
    except (OSError, ValueError) as exc:
        print(f"INVALID portable export: {exc}", file=sys.stderr)
        return 2
    print(
        "VALID STRUCTURE AND CHECKSUM (not origin authentication): "
        f"schema={summary['schema']} "
        f"messages={summary['original_message']} "
        f"threads={summary['thread']} "
        f"links={summary['thread_source_link']} "
        f"body_sha256={summary['body_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
