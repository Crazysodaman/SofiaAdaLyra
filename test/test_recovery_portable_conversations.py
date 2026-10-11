"""Deferred independent recovery export and privacy evidence tests.

No runtime, LLM, live database or real backup is required for source tests.
The encrypted CLI route is a separate composition contract.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3

import pytest

from sofia.conversation.lifelong import LifelongThreadStore
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.ops.recovery_export import export_portable_conversations
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.store import SocialSessionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


def _fixture(tmp_path):
    root = tmp_path / "offline-restored-home"
    root.mkdir()
    state = bootstrap_canonical_sqlite(root / "sofia.db")
    conversation = ConversationStore(state)
    social = SocialSessionStore(state)
    threads = LifelongThreadStore(state)
    owner = PrincipalContext(
        principal_id="owner:synthetic", audience_id="local:text",
        audience_kind=AudienceKind.PRIVATE, display_name="Owner",
    )
    session = conversation.create_session()
    social.bind(session_id=session.id, principal=owner)
    message = ConversationMessage(
        id="original:one", session_id=session.id,
        role=ConversationRole.USER, content="Gaia: violet sensor 🌌",
        created_at=datetime(2026, 10, 11, 12, tzinfo=timezone.utc),
    )
    conversation.save(message)
    project = threads.get_or_create(
        owner=owner, kind="project", name="Gaia",
    )
    threads.link_message(
        thread_id=project.thread_id, source_message_id=message.id,
        principal=owner,
    )
    conversation.close()
    output_root = tmp_path / "owner-export"
    output_root.mkdir()
    return state, output_root / "all-audiences.jsonl", project.thread_id


def _load_lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_portable_export_contains_originals_scopes_and_links_not_shadow_text(tmp_path):
    state, output, thread = _fixture(tmp_path)
    report = export_portable_conversations(
        state_path=state, destination=output,
        approve_sensitive_plaintext=True,
    )
    assert report.message_count == 1
    assert report.thread_count == 1
    assert report.link_count == 1
    records = _load_lines(output)
    assert [x["record_type"] for x in records] == [
        "header", "original_message", "thread", "thread_source_link", "footer",
    ]
    original = records[1]
    assert original["content"] == "Gaia: violet sensor 🌌"
    assert original["audience_id"] == "local:text"
    assert original["audience_kind"] == "private"
    assert original["binding"] == "currently_bound"
    assert records[2]["thread_id"] == thread
    assert records[3]["current_original_available"] is True
    assert records[3]["current_source_audience_matches"] is True
    assert records[4]["preceding_lines_sha256"] == sha256(
        b"".join(output.read_bytes().splitlines(keepends=True)[:-1])
    ).hexdigest()
    assert report.content_sha256 == records[4]["preceding_lines_sha256"]


def test_dangling_source_link_is_evidence_not_a_restored_authority(tmp_path):
    state, output, thread = _fixture(tmp_path)
    with sqlite3.connect(state) as db:
        db.execute("DELETE FROM conversation_messages WHERE id='original:one'")
    report = export_portable_conversations(
        state_path=state, destination=output,
        approve_sensitive_plaintext=True,
    )
    rows = _load_lines(output)
    assert report.message_count == 0
    assert rows[2]["record_type"] == "thread_source_link"
    assert rows[2]["current_original_available"] is False
    assert rows[2]["current_source_audience_matches"] is False


def test_sensitive_plaintext_export_requires_explicit_approval(tmp_path):
    state, output, _ = _fixture(tmp_path)
    with pytest.raises(PermissionError, match="explicit plaintext"):
        export_portable_conversations(
            state_path=state, destination=output,
            approve_sensitive_plaintext=False,
        )
    assert not output.exists()


def test_portable_export_does_not_overwrite_owner_file(tmp_path):
    state, output, _ = _fixture(tmp_path)
    output.write_bytes(b"owner-owned-file")
    with pytest.raises(FileExistsError, match="overwrite"):
        export_portable_conversations(
            state_path=state, destination=output,
            approve_sensitive_plaintext=True,
        )
    assert output.read_bytes() == b"owner-owned-file"


def test_portable_export_rejects_redirects_and_unverified_remote_storage(
    tmp_path, monkeypatch,
):
    state, output, _ = _fixture(tmp_path)
    external = tmp_path / "unrelated"
    external.mkdir()
    redirect = tmp_path / "redirect"
    try:
        redirect.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("OS refuses symlink fixture")
    with pytest.raises(PermissionError, match="symlinks or junctions"):
        export_portable_conversations(
            state_path=state, destination=redirect / "out.jsonl",
            approve_sensitive_plaintext=True,
        )
    monkeypatch.setattr(
        "sofia.ops.recovery_export._filesystem_kind",
        lambda _path: "remote",
    )
    with pytest.raises(PermissionError, match="proven local storage"):
        export_portable_conversations(
            state_path=state, destination=output,
            approve_sensitive_plaintext=True,
        )


def test_source_export_is_streamed_across_page_boundaries(tmp_path):
    state, output, _ = _fixture(tmp_path)
    with sqlite3.connect(state) as db:
        for index in range(300):
            db.execute(
                "INSERT INTO conversation_messages "
                "(id,session_id,role,content,created_at) VALUES(?,?,?,?,?)",
                (
                    f"bulk-{index}", "synthetic-unbound-session", "user",
                    f"exact original {index}",
                    "2026-10-11T12:00:00+00:00",
                ),
            )
    report = export_portable_conversations(
        state_path=state, destination=output,
        approve_sensitive_plaintext=True,
    )
    assert report.message_count == 301
    rows = _load_lines(output)
    assert sum(x["record_type"] == "original_message" for x in rows) == 301
    assert any(
        x.get("binding") == "unbound_not_authorized"
        for x in rows
    )
