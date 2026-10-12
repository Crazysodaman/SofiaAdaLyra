"""Deferred stdlib-only portable JSONL verifier compatibility contracts."""
from pathlib import Path
import json
import runpy

import pytest

from sofia.ops.recovery_export import export_portable_conversations
from test.test_recovery_portable_conversations import _fixture

@pytest.fixture(autouse=True)
def _synthetic_verified_local_media(monkeypatch):
    # Docker/CI tmp_path may be overlayfs, which is deliberately NOT
    # authorized as a durable production home. These tests exercise JSONL
    # behavior in isolated synthetic paths, not actual host disk admission.
    monkeypatch.setattr(
        "sofia.ops.recovery_export._filesystem_kind",
        lambda _path: "local",
    )





def _verifier():
    path = Path(__file__).resolve().parents[1] / "tools" / (
        "verify_sofia_portable_jsonl.py"
    )
    namespace = runpy.run_path(str(path))
    return namespace["verify"]


def test_standalone_verifier_accepts_original_export_without_sofia_runtime(tmp_path):
    state, path, _ = _fixture(tmp_path)
    export_portable_conversations(
        state_path=state, destination=path,
        approve_sensitive_plaintext=True,
    )
    summary = _verifier()(path)
    assert summary["original_message"] == 1
    assert summary["thread"] == 1
    assert summary["thread_source_link"] == 1


def test_standalone_verifier_denies_modified_source_content(tmp_path):
    state, path, _ = _fixture(tmp_path)
    export_portable_conversations(
        state_path=state, destination=path,
        approve_sensitive_plaintext=True,
    )
    original = path.read_text(encoding="utf-8")
    assert "violet sensor" in original
    path.write_text(
        original.replace("violet sensor", "fabricated sensor"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _verifier()(path)


def test_standalone_verifier_denies_missing_footer_and_extra_records(tmp_path):
    state, path, _ = _fixture(tmp_path)
    export_portable_conversations(
        state_path=state, destination=path,
        approve_sensitive_plaintext=True,
    )
    body = path.read_bytes()
    path.write_bytes(b"".join(body.splitlines(keepends=True)[:-1]))
    with pytest.raises(ValueError, match="missing required header or footer"):
        _verifier()(path)

    path.write_bytes(body + b'{"record_type":"thread"}\n')
    with pytest.raises(ValueError, match="after integrity footer"):
        _verifier()(path)


def test_standalone_verifier_does_not_trust_footer_counts(tmp_path):
    state, path, _ = _fixture(tmp_path)
    export_portable_conversations(
        state_path=state, destination=path,
        approve_sensitive_plaintext=True,
    )
    # Preserve the exact body bytes on Windows, where read_text/write_text
    # newline round trips can otherwise invalidate the SHA-256 before the
    # verifier reaches the independent footer count check.
    lines = path.read_bytes().splitlines(keepends=True)
    footer = json.loads(lines[-1].decode("utf-8"))
    footer["original_message_count"] = 42
    lines[-1] = (json.dumps(footer, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(b"".join(lines))
    with pytest.raises(ValueError, match="footer original_message_count"):
        _verifier()(path)
