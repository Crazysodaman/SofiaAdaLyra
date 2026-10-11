"""Deferred privacy contract for raw imported conversation evidence egress.

Promoted memories follow their independently reviewed audience grants. A
private transport alone never authorizes original ChatGPT archive exposure.
"""
from datetime import datetime, timezone

from sofia.memory.chatgpt_export import parse_chatgpt_export_archive
from sofia.memory.chatgpt_export_store import ChatGPTExportEvidenceStore
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.system import MemorySystem
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import (
    SPARKS_PRINCIPAL_ID,
    discord_sparks_principal,
    local_sparks_principal,
)
from test.test_chatgpt_export_import import _write_export


def test_raw_chatgpt_history_does_not_cross_authenticated_local_audience(tmp_path):
    source = tmp_path / "chatgpt.zip"
    _write_export(source)
    state = tmp_path / "sofia.db"
    originals = ChatGPTExportEvidenceStore(state)
    batch = parse_chatgpt_export_archive(
        source.read_bytes(), observed_at=datetime.now(timezone.utc),
    )
    assert originals.save(batch)
    candidates = DurableMemoryCandidateStore(state)
    memory = MemorySystem(candidates, originals)
    try:
        local = memory.recall_historical_evidence(
            "evidence imports", principal=local_sparks_principal(),
        )
        assert len(local) == 1
        assert "evidence-first imports" in local[0].content
        assert len(memory.recall_historical_evidence(
            "evidence imports",
            principal=local_sparks_principal("local:terminal"),
        )) == 1

        private_remote_audiences = (
            discord_sparks_principal(12345),
            PrincipalContext(
                principal_id=SPARKS_PRINCIPAL_ID,
                audience_id="mobile:private:device-a",
                audience_kind=AudienceKind.PRIVATE,
            ),
            PrincipalContext(
                principal_id=SPARKS_PRINCIPAL_ID,
                audience_id="mobile:private:device-a:g2",
                audience_kind=AudienceKind.PRIVATE,
            ),
            PrincipalContext(
                principal_id=SPARKS_PRINCIPAL_ID,
                audience_id="remote-chat:123456789abcdef0",
                audience_kind=AudienceKind.PRIVATE,
            ),
            PrincipalContext(
                principal_id=SPARKS_PRINCIPAL_ID,
                audience_id="local:unapproved",
                audience_kind=AudienceKind.PRIVATE,
            ),
        )
        for remote in private_remote_audiences:
            assert memory.recall_historical_evidence(
                "evidence imports", principal=remote,
            ) == ()
        assert memory.recall_historical_evidence(
            "evidence imports",
            principal=PrincipalContext(
                principal_id=SPARKS_PRINCIPAL_ID,
                audience_id="local:text",
                audience_kind=AudienceKind.SHARED,
            ),
        ) == ()
    finally:
        memory.close()
