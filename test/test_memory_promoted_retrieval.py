from datetime import datetime, timezone
from uuid import uuid4
from sofia.memory.promoted_retrieval import retrieve_promoted
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage


def add(store,text,promote=True):
    src=SourceMessage(str(uuid4()),"s","user","e",datetime.now(timezone.utc),0)
    item=MemoryCandidate(uuid4(),text,(src,),datetime.now(timezone.utc))
    store.propose(item)
    if promote: store.promote(item.candidate_id)
    return item


def test_retrieval_ranks_promoted_token_overlap(tmp_path):
    s=DurableMemoryCandidateStore(tmp_path/"m.db")
    a=add(s,"Sparks likes model trains"); b=add(s,"Sparks likes trains and model railroads"); add(s,"model trains draft",False)
    out=retrieve_promoted(s,"model trains",limit=5,budget_characters=1000)
    assert [x.candidate_id for x in out.selected]==[a.candidate_id,b.candidate_id]
    s.close()


def test_revoked_memory_is_not_retrieved(tmp_path):
    s=DurableMemoryCandidateStore(tmp_path/"m.db"); a=add(s,"Artemis server"); s.revoke(a.candidate_id)
    assert retrieve_promoted(s,"Artemis").selected==()
    s.close()
