"""Deferred pure-standard-library verification of owner JSONL recovery export.

Synthetic records only. No original user conversations, live files, tests or
CI are used during source authoring.
"""
from hashlib import sha256
import json

import pytest

from scripts.verify_sofia_portable_export import (
    main, verify_portable_export,
)


def _line(record):
    return (
        json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ) + "\n"
    ).encode("utf-8")


def _document(*, one_original=True):
    header = {
        "record_type": "header", "schema": "sofia.portable-conversations.v1",
        "created_at": "2026-10-11T18:00:00+00:00",
        "privacy": "ALL_AUDIENCES_SENSITIVE_PLAINTEXT",
        "authority": "offline_operator_export_not_a_channel_grant",
        "source": "verified_offline_canonical_sqlite",
    }
    originals = [{
        "record_type": "original_message", "message_id": "synthetic:message:1",
        "session_id": "synthetic:session:1", "role": "user",
        "content": "Entirely invented data for export verification",
        "created_at": "2026-10-11T18:00:00+00:00",
        "binding": "currently_bound", "principal_id": "person:synthetic",
        "audience_id": "private:synthetic", "audience_kind": "private",
    }] if one_original else []
    content = b"".join(map(_line, [header, *originals]))
    footer = {
        "record_type": "footer", "schema": "sofia.portable-conversations.v1",
        "original_message_count": len(originals),
        "thread_count": 0, "thread_source_link_count": 0,
        "preceding_lines_sha256": sha256(content).hexdigest(),
    }
    return content + _line(footer)


def test_valid_export_reports_only_counts_and_exact_raw_sha256(tmp_path, capsys):
    path = tmp_path / "synthetic.jsonl"
    path.write_bytes(_document())
    receipt = verify_portable_export(path)
    assert (receipt.message_count, receipt.thread_count, receipt.link_count) == (
        1, 0, 0,
    )
    assert main([str(path)]) == 0
    output = capsys.readouterr().out
    assert "NOT cryptographic authenticity" in output
    assert "invented data for export" not in output


def test_tampered_original_content_is_detected_without_disclosing_text(tmp_path):
    path = tmp_path / "tampered.jsonl"
    raw = _document()
    assert b"invented" in raw
    path.write_bytes(raw.replace(b"invented", b"altered!"))
    with pytest.raises(ValueError, match="content hash mismatch"):
        verify_portable_export(path)


@pytest.mark.parametrize("alter", (
    lambda raw: raw[:-1],
    lambda raw: raw + b"{}\n",
    lambda raw: raw.replace(
        b'"original_message_count":1', b'"original_message_count":2',
    ),
    lambda raw: raw.replace(
        b'"privacy":"ALL_AUDIENCES_SENSITIVE_PLAINTEXT"',
        b'"privacy":"PUBLIC"',
    ),
))
def test_partial_forged_or_trailing_exports_fail_closed(tmp_path, alter):
    path = tmp_path / "malformed.jsonl"
    path.write_bytes(alter(_document()))
    with pytest.raises(ValueError):
        verify_portable_export(path)


def test_capped_line_read_refuses_unbounded_content(tmp_path):
    path = tmp_path / "oversized.jsonl"
    path.write_bytes(_document())
    with pytest.raises(ValueError, match="maximum size"):
        verify_portable_export(path, max_line_bytes=1024)
