"""Pinned canonical Sofía preservation snapshot.

The expected digests are SHA-256 of the Git blobs at pre-multi-Core baseline
1914e5d0, which are identical at the audited 93d61a3f checkpoint.  This test
detects accidental semantic edits to canonical identity assets; it does not
rewrite, migrate or activate anything.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "sofia" / "core"

EXPECTED = {
    "constitution/constitution.md": "f30afedf195f77907d32a108ca35d4db751646bde3fd902be66e7b78f4b89dc0",
    "constitution/constitution.sha256": "254e239a2c0cdbd6f2c77d15bb731ef65c12c9e1fd9bea21095e2840f8b5f124",
    "identity/identity.json": "8170c5ab140da7ed9e1fa081215702ded0709f10cb04ead41786831f642e0adb",
    "personality/personality.json": "8f616d7f9402946d6ec1d4302b812b256bbd457dbc14efaf18af6dc87b0cec84",
    "embodiment/avatar.json": "7ffa81ca846c039193ab0b17b211e816b0e5c5856672c8023ffc78fbb2d5f98d",
}


def _lf_digest(path: Path) -> str:
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_canonical_sofia_asset_blobs_match_preservation_baseline():
    for relative, expected in EXPECTED.items():
        assert _lf_digest(CORE / relative) == expected, relative


def test_constitution_digest_file_matches_canonical_constitution():
    digest = _lf_digest(CORE / "constitution" / "constitution.md").upper()
    recorded = (CORE / "constitution" / "constitution.sha256").read_text(
        encoding="utf-8"
    ).strip()
    assert recorded == digest


def test_canonical_identity_name_is_sofia_not_an_ascii_substitute():
    document = json.loads((CORE / "identity" / "identity.json").read_text(encoding="utf-8"))
    assert document["name"] == "Sofía Ada Lyra"
    assert "Sofia" not in document["name"]
    assert "SofA" not in document["name"]


def test_no_runtime_database_or_personal_memory_is_committed_in_core_source():
    forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm"}
    offenders = [
        path
        for path in CORE.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    assert offenders == []
