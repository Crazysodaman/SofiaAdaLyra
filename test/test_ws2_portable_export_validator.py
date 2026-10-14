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
    path.write_bytes(
        _document().replace(
            b"Entirely invented data for export verification",
            b"x" * 2048,
        )
    )
    with pytest.raises(ValueError, match="maximum size"):
        verify_portable_export(path, max_line_bytes=1024)


def _rewrite(records):
    """Build a self-consistent checksum for semantic forgery tests."""
    footer = records[-1].copy()
    body = b"".join(_line(item) for item in records[:-1])
    footer["preceding_lines_sha256"] = sha256(body).hexdigest()
    return body + _line(footer)


def test_duplicate_json_keys_rejected_before_footer_checksum(tmp_path):
    path = tmp_path / "duplicate.jsonl"
    path.write_bytes(_document().replace(
        b'"privacy":"ALL_AUDIENCES_SENSITIVE_PLAINTEXT"',
        b'"privacy":"ALL_AUDIENCES_SENSITIVE_PLAINTEXT","privacy":"PUBLIC"',
    ))
    with pytest.raises(ValueError, match="invalid UTF-8 JSON"):
        verify_portable_export(path)


@pytest.mark.parametrize("field,invalid", [
    ("authority", "unrestricted_channel_grant"),
    ("source", "unverified_legacy_database"),
])
def test_recomputed_checksum_cannot_forge_recovery_authority(
    tmp_path, field, invalid,
):
    records = [json.loads(line) for line in _document().splitlines()]
    records[0][field] = invalid
    path = tmp_path / "forged-label.jsonl"
    path.write_bytes(_rewrite(records))
    with pytest.raises(ValueError, match="authority/source"):
        verify_portable_export(path)


def test_unbound_message_cannot_carry_audience_grants_even_with_valid_hash(
    tmp_path,
):
    records = [json.loads(line) for line in _document().splitlines()]
    records[1]["binding"] = "unbound_not_authorized"
    path = tmp_path / "ambiguous-audience.jsonl"
    path.write_bytes(_rewrite(records))
    with pytest.raises(ValueError, match="unbound original"):
        verify_portable_export(path)


def test_bound_message_requires_original_audience_fields(tmp_path):
    records = [json.loads(line) for line in _document().splitlines()]
    records[1]["audience_id"] = None
    path = tmp_path / "missing-audience.jsonl"
    path.write_bytes(_rewrite(records))
    with pytest.raises(ValueError, match="missing audience_id"):
        verify_portable_export(path)


@pytest.mark.parametrize("kind,expected", [
    ("thread", "thread catalog access"),
    ("thread_source_link", "link access"),
    ("missing_original", "missing original"),
])
def test_thread_and_link_provenance_never_conveys_permission(
    tmp_path, kind, expected,
):
    records = [json.loads(line) for line in _document().splitlines()]
    thread = dict(
        record_type="thread", thread_id="synthetic:thread:1",
        owner_principal_id="person:synthetic", kind="main", name="Test",
        created_at="2026-10-11T18:00:00+00:00",
        access="catalog_not_a_cross_channel_grant",
    )
    link = dict(
        record_type="thread_source_link", thread_id="synthetic:thread:1",
        source_message_id="synthetic:message:1",
        source_session_id="synthetic:session:1",
        source_audience_id="private:synthetic", visibility="private",
        linked_at="2026-10-11T18:00:00+00:00",
        current_original_available=True,
        current_source_audience_matches=True,
        access="reference_only_not_an_authorization",
    )
    if kind == "thread":
        thread["access"] = "unrestricted"
    elif kind == "thread_source_link":
        link["access"] = "unrestricted"
    else:
        link["current_original_available"] = False
    records[1:1] = [thread, link] if not records[1:-1] else []
    # Original messages must precede the thread catalog.
    records = [records[0], *[r for r in records[1:-1] if r["record_type"] == "original_message"],
               thread, link, records[-1]]
    records[-1]["thread_count"] = 1
    records[-1]["thread_source_link_count"] = 1
    path = tmp_path / "invalid-provenance.jsonl"
    path.write_bytes(_rewrite(records))
    with pytest.raises(ValueError, match=expected):
        verify_portable_export(path)
