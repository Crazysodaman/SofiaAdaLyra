from datetime import datetime, timezone
from uuid import uuid4
from sofia.memory.cognition_projection import project_promoted_memories
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage


def item(text):
    src=SourceMessage(str(uuid4()),"s","user","evidence",datetime.now(timezone.utc),0)
    return MemoryCandidate(uuid4(),text,(src,),datetime.now(timezone.utc))


def test_projection_exposes_only_promoted_and_preserves_content(tmp_path):
    store=DurableMemoryCandidateStore(tmp_path/"m.db"); a,b=item("  exact memory  "),item("draft")
    store.propose(a); store.promote(a.candidate_id); store.propose(b)
    out=project_promoted_memories(store,[a.candidate_id,b.candidate_id],budget_characters=99)
    assert out.selected[0].content=="  exact memory  "
    assert out.missing_or_inactive_ids==(b.candidate_id,)
    store.close()


def test_budget_omits_without_truncation_and_deduplicates(tmp_path):
    store=DurableMemoryCandidateStore(tmp_path/"m.db"); a,b=item("1234"),item("x")
    for x in (a,b): store.propose(x); store.promote(x.candidate_id)
    out=project_promoted_memories(store,[a.candidate_id,a.candidate_id,b.candidate_id],budget_characters=1)
    assert out.omitted_ids==(a.candidate_id,)
    assert out.selected[0].content=="x"
    store.close()
