from datetime import datetime, timezone
from uuid import uuid4
from sofia.memory.provenance import MemoryCandidate, CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage
from sofia.memory.source_invalidation import SourceInvalidator


def candidate(session, mid):
    src=SourceMessage(mid,session,"user","source",datetime.now(timezone.utc),0)
    return MemoryCandidate(uuid4(),"claim",(src,),datetime.now(timezone.utc))


def test_invalidating_source_revokes_promoted_dependents_only(tmp_path):
    store=DurableMemoryCandidateStore(tmp_path/"m.db")
    promoted=candidate("s","m"); proposed=candidate("s","m")
    store.propose(promoted); store.promote(promoted.candidate_id); store.propose(proposed)
    revoked=SourceInvalidator(store).invalidate_message(session_id="s",message_id="m")
    assert revoked==(promoted.candidate_id,)
    assert store.status(promoted.candidate_id) is CandidateStatus.REVOKED
    assert store.status(proposed.candidate_id) is CandidateStatus.PROPOSED
    store.close()


def test_other_session_same_message_id_is_untouched(tmp_path):
    store=DurableMemoryCandidateStore(tmp_path/"m.db")
    a,b=candidate("a","m"),candidate("b","m")
    for item in (a,b): store.propose(item); store.promote(item.candidate_id)
    SourceInvalidator(store).invalidate_message(session_id="a",message_id="m")
    assert store.status(a.candidate_id) is CandidateStatus.REVOKED
    assert store.status(b.candidate_id) is CandidateStatus.PROMOTED
    store.close()
