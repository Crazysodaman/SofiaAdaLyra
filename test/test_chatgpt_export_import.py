from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from zipfile import ZipFile

from sofia.memory.chatgpt_export import parse_chatgpt_export_archive
from sofia.memory.chatgpt_export_store import ChatGPTExportEvidenceStore
from sofia.memory.import_chatgpt import main as import_chatgpt_main
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.social.principals import SPARKS_PRINCIPAL_ID


NOW = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)


def _message(message_id, role, content, create_time, *, content_type="text"):
    return {
        "id": message_id,
        "author": {"role": role},
        "create_time": create_time,
        "content": {
            "content_type": content_type,
            "parts": [content],
        },
    }


def _write_export(path: Path) -> None:
    eligible = {
        "id": "conversation-1",
        "conversation_id": "conversation-1",
        "title": "Sofía project",
        "create_time": 1790611200.0,
        "update_time": 1790614800.0,
        "current_node": "assistant-1",
        "is_do_not_remember": False,
        "is_archived": False,
        "memory_scope": "global_enabled",
        "mapping": {
            "user-1": {
                "id": "user-1",
                "parent": None,
                "children": ["assistant-thought"],
                "message": {
                    **_message(
                        "user-message-1",
                        "user",
                        "Sparks prefers evidence-first imports.",
                        1790611200.0,
                        content_type="multimodal_text",
                    ),
                    "content": {
                        "content_type": "multimodal_text",
                        "parts": [
                            "Sparks prefers evidence-first imports.",
                            {
                                "content_type": "image_asset_pointer",
                                "asset_pointer": "sediment://file_asset_1",
                            },
                        ],
                    },
                },
            },
            "assistant-thought": {
                "id": "assistant-thought",
                "parent": "user-1",
                "children": ["assistant-1"],
                "message": _message(
                    "thought-1",
                    "assistant",
                    "private reasoning must not be imported",
                    1790611210.0,
                    content_type="thoughts",
                ),
            },
            "assistant-1": {
                "id": "assistant-1",
                "parent": "assistant-thought",
                "children": [],
                "message": _message(
                    "assistant-message-1",
                    "assistant",
                    "Visible assistant reply.",
                    1790611220.0,
                ),
            },
            "alternate": {
                "id": "alternate",
                "parent": "user-1",
                "children": [],
                "message": _message(
                    "alternate-message",
                    "assistant",
                    "Inactive branch must not be imported.",
                    1790611230.0,
                ),
            },
        },
    }
    memory_disabled = {
        "id": "conversation-disabled",
        "conversation_id": "conversation-disabled",
        "title": "Memory disabled",
        "current_node": "disabled-user",
        "is_do_not_remember": False,
        "memory_scope": "global_disabled",
        "mapping": {
            "disabled-user": {
                "id": "disabled-user",
                "parent": None,
                "children": [],
                "message": _message(
                    "disabled-message",
                    "user",
                    "This scope must be skipped.",
                    1790611350.0,
                ),
            },
        },
    }
    do_not_remember = {
        "id": "conversation-private",
        "conversation_id": "conversation-private",
        "title": "Do not remember",
        "current_node": "private-user",
        "is_do_not_remember": True,
        "memory_scope": "global_enabled",
        "mapping": {
            "private-user": {
                "id": "private-user",
                "parent": None,
                "children": [],
                "message": _message(
                    "private-message",
                    "user",
                    "This must be skipped.",
                    1790611300.0,
                ),
            },
        },
    }
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "export_manifest.json",
            json.dumps({"version": 1}),
        )
        archive.writestr(
            "conversation_asset_file_names.json",
            json.dumps({"file_asset_1": "reference.png"}),
        )
        archive.writestr(
            "conversations-000.json",
            json.dumps([eligible, do_not_remember, memory_disabled]),
        )


def test_full_export_parser_keeps_only_visible_active_branch_and_honors_do_not_remember(
    tmp_path: Path,
):
    source = tmp_path / "export.zip"
    _write_export(source)

    batch = parse_chatgpt_export_archive(
        source.read_bytes(),
        observed_at=NOW,
    )

    assert len(batch.conversations) == 1
    assert batch.skipped_do_not_remember == 1
    assert batch.skipped_memory_disabled == 1
    assert batch.message_count == 2
    assert batch.attachment_count == 1
    conversation = batch.conversations[0]
    assert conversation.conversation_id == "conversation-1"
    assert conversation.memory_scope == "global_enabled"
    assert [(item.role, item.content) for item in conversation.messages] == [
        ("user", "Sparks prefers evidence-first imports."),
        ("assistant", "Visible assistant reply."),
    ]
    assert conversation.messages[0].attachments[0].asset_id == "file_asset_1"
    assert conversation.messages[0].attachments[0].file_name == "reference.png"
    assert all("private reasoning" not in item.content for item in conversation.messages)
    assert all("Inactive branch" not in item.content for item in conversation.messages)


def test_full_export_evidence_is_principal_bound_and_idempotent(tmp_path: Path):
    source = tmp_path / "export.zip"
    _write_export(source)
    batch = parse_chatgpt_export_archive(source.read_bytes(), observed_at=NOW)
    state_path = tmp_path / "sofia.db"
    store = ChatGPTExportEvidenceStore(state_path)

    assert store.save(batch) is True
    assert store.save(batch) is False
    assert store.counts(batch.source_digest) == (1, 2, 1, 1, 1)

    with __import__("sqlite3").connect(state_path) as db:
        principal = db.execute(
            "SELECT principal_id FROM chatgpt_export_batch "
            "WHERE source_digest=?",
            (batch.source_digest,),
        ).fetchone()[0]
    assert principal == SPARKS_PRINCIPAL_ID

    assert store.attachments_for_message(
        batch.source_digest,
        "conversation-1",
        "user-message-1",
    ) == (
        ("file_asset_1", "reference.png", "image_asset_pointer"),
    )

    recalled = store.search_relevant(
        "evidence imports",
        principal_id=SPARKS_PRINCIPAL_ID,
    )
    assert len(recalled) == 1
    assert recalled[0].role == "user"
    assert recalled[0].content == "Sparks prefers evidence-first imports."
    assert recalled[0].title == "Sofía project"

    assert store.search_relevant(
        "evidence imports",
        principal_id="person:someone-else",
    ) == ()


def test_full_export_cli_imports_evidence_without_creating_memory_candidates(
    tmp_path: Path,
    capsys,
):
    source = tmp_path / "export.zip"
    _write_export(source)
    state_path = tmp_path / "sofia.db"

    assert import_chatgpt_main(
        [str(source), "--state-path", str(state_path), "--dry-run"]
    ) == 0
    assert state_path.exists() is False

    assert import_chatgpt_main(
        [str(source), "--state-path", str(state_path)]
    ) == 0

    candidates = DurableMemoryCandidateStore(state_path)
    try:
        assert candidates.list_ids(status=CandidateStatus.PROPOSED) == ()
        assert candidates.list_ids(status=CandidateStatus.PROMOTED) == ()
    finally:
        candidates.close()

    output = capsys.readouterr().out
    assert "memory_status=evidence_only" in output


def test_full_export_cli_refuses_blind_bulk_promotion(tmp_path: Path, capsys):
    source = tmp_path / "export.zip"
    _write_export(source)

    assert import_chatgpt_main(
        [
            str(source),
            "--state-path",
            str(tmp_path / "sofia.db"),
            "--promote-all",
            "--approved-by",
            "Sparks",
        ]
    ) == 2

    assert "blind --promote-all is not allowed" in capsys.readouterr().err


def test_full_export_parser_retains_attachment_only_visible_message(tmp_path: Path):
    source = tmp_path / "attachment-only.zip"
    conversation = {
        "id": "conversation-image",
        "conversation_id": "conversation-image",
        "title": "Image only",
        "current_node": "image-node",
        "is_do_not_remember": False,
        "memory_scope": "global_enabled",
        "mapping": {
            "image-node": {
                "id": "image-node",
                "parent": None,
                "children": [],
                "message": {
                    "id": "image-message",
                    "author": {"role": "user"},
                    "create_time": 1790611400.0,
                    "content": {
                        "content_type": "multimodal_text",
                        "parts": [
                            {
                                "content_type": "image_asset_pointer",
                                "asset_pointer": "sediment://file_image_only",
                            }
                        ],
                    },
                },
            },
        },
    }
    with ZipFile(source, "w") as archive:
        archive.writestr("export_manifest.json", json.dumps({"version": 1}))
        archive.writestr(
            "conversation_asset_file_names.json",
            json.dumps({"file_image_only": "image-only.png"}),
        )
        archive.writestr(
            "conversations-000.json",
            json.dumps([conversation]),
        )

    batch = parse_chatgpt_export_archive(
        source.read_bytes(),
        observed_at=NOW,
    )

    assert batch.message_count == 1
    assert batch.attachment_count == 1
    message = batch.conversations[0].messages[0]
    assert message.content == ""
    assert message.attachments[0].file_name == "image-only.png"
