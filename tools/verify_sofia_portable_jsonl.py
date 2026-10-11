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
    with path.open("rb") as source:
        for line_number, raw in enumerate(source, start=1):
            if len(raw) > _MAX_LINE_BYTES:
                raise ValueError(f"line {line_number} exceeds safety limit")
            if not raw.endswith(b"\n"):
                raise ValueError(f"line {line_number} missing newline terminator")
            try:
                record = json.loads(raw.decode("utf-8"))
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
                if kind == "original_message":
                    if not all(
                        isinstance(record.get(field), str)
                        for field in (
                            "message_id", "session_id", "role", "content",
                            "created_at", "binding",
                        )
                    ):
                        raise ValueError(f"line {line_number} has invalid original")
                elif kind == "thread":
                    if not all(
                        isinstance(record.get(field), str)
                        for field in ("thread_id", "owner_principal_id", "kind", "name")
                    ):
                        raise ValueError(f"line {line_number} has invalid thread")
                else:
                    if not all(
                        isinstance(record.get(field), str)
                        for field in (
                            "thread_id", "source_message_id",
                            "source_session_id", "visibility",
                        )
                    ):
                        raise ValueError(f"line {line_number} has invalid source link")
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
