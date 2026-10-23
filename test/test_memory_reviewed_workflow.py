from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.memory.originals import ConversationOriginalRetriever
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.reviewed_workflow import ReviewedMemoryWorkflow


def test_workflow_preserves_exact_persisted_source(tmp_path):
    canonical = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    conversations = ConversationStore(canonical)
    session = conversations.create_session()
    message_id = str(uuid4())
    now = datetime.now(timezone.utc)
    conversations.save(
        ConversationMessage(
            id=message_id,
            session_id=session.id,
            role=ConversationRole.USER,
            content="exact source",
            created_at=now,
        )
    )
    candidates = DurableMemoryCandidateStore(canonical)
    result = ReviewedMemoryWorkflow(
        ConversationOriginalRetriever(conversations),
        candidates,
    ).propose_from_messages(
        session_id=session.id,
        message_ids=(message_id,),
        content="derived claim",
        created_at=now,
    )
    assert result.sources[0].content == "exact source"
    assert candidates.get(result.candidate_id) == result
    candidates.close()
    conversations.close()


def test_workflow_fails_if_any_requested_source_is_missing(tmp_path):
    canonical = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    conversations = ConversationStore(canonical)
    session = conversations.create_session()
    now = datetime.now(timezone.utc)
    candidates = DurableMemoryCandidateStore(canonical)
    with pytest.raises(LookupError):
        ReviewedMemoryWorkflow(
            ConversationOriginalRetriever(conversations),
            candidates,
        ).propose_from_messages(
            session_id=session.id,
            message_ids=("missing",),
            content="claim",
            created_at=now,
        )
    candidates.close()
    conversations.close()
