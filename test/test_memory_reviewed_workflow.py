from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sofia.conversation.model import ConversationMessage, ConversationSession
from sofia.conversation.store import ConversationStore
from sofia.memory.conversation_originals import ConversationOriginalRetriever
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.reviewed_workflow import ReviewedMemoryWorkflow


def test_workflow_preserves_exact_persisted_source(tmp_path):
    conversations=ConversationStore(tmp_path/"c.db"); sid=str(uuid4()); mid=str(uuid4()); now=datetime.now(timezone.utc)
    conversations.save_session(ConversationSession(id=sid,started_at=now))
    conversations.save_message(ConversationMessage(id=mid,session_id=sid,role="user",content="exact source",created_at=now))
    candidates=DurableMemoryCandidateStore(tmp_path/"m.db")
    result=ReviewedMemoryWorkflow(ConversationOriginalRetriever(conversations),candidates).propose_from_messages(
        session_id=sid,message_ids=(mid,),content="derived claim",created_at=now)
    assert result.sources[0].content=="exact source"
    assert candidates.get(result.candidate_id)==result
    candidates.close(); conversations.close()


def test_workflow_fails_if_any_requested_source_is_missing(tmp_path):
    conversations=ConversationStore(tmp_path/"c.db"); sid=str(uuid4()); now=datetime.now(timezone.utc)
    conversations.save_session(ConversationSession(id=sid,started_at=now))
    candidates=DurableMemoryCandidateStore(tmp_path/"m.db")
    with pytest.raises(LookupError):
        ReviewedMemoryWorkflow(ConversationOriginalRetriever(conversations),candidates).propose_from_messages(
            session_id=sid,message_ids=("missing",),content="claim",created_at=now)
    candidates.close(); conversations.close()
