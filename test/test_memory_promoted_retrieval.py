from datetime import datetime, timezone
from uuid import uuid4

from sofia.memory.promoted_retrieval import retrieve_promoted
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.retrieval_projection import SourceMessage
from sofia.personality.influence import ContinuityInfluence


def add(store, text, promote=True):
    src = SourceMessage(
        str(uuid4()),
        "s",
        "user",
        "e",
        datetime.now(timezone.utc),
        0,
    )
    item = MemoryCandidate(
        uuid4(),
        text,
        (src,),
        datetime.now(timezone.utc),
    )
    store.propose(item)
    if promote:
        store.promote(item.candidate_id)
    return item


def contextual_influence(**overrides):
    values = dict(
        daypart="evening",
        season="winter",
        daylight="night",
        weather_condition="snow",
        temperature_c=-2.0,
        weather_freshness="current",
        location_freshness="current",
        primary_emotion_evidence_refs=("emotion:memory-test",),
        emotional_tone="warm",
        primary_emotion="fondness",
        primary_intensity=0.5,
        active_emotions=("fondness",),
        daypart_evidence_refs=(
            "runtime.clock",
            "environment.location:test",
        ),
        season_evidence_refs=(
            "runtime.clock",
            "environment.location:test",
        ),
        weather_evidence_refs=("environment.weather:test",),
    )
    values.update(overrides)
    return ContinuityInfluence(**values)


def test_retrieval_ranks_promoted_token_overlap(tmp_path):
    s = DurableMemoryCandidateStore(tmp_path / "m.db")
    a = add(s, "Sparks likes model trains")
    b = add(s, "Sparks likes trains and model railroads")
    add(s, "model trains draft", False)

    out = retrieve_promoted(
        s,
        "model trains",
        limit=5,
        budget_characters=1000,
    )

    assert [x.candidate_id for x in out.selected] == [
        a.candidate_id,
        b.candidate_id,
    ]
    s.close()


def test_revoked_memory_is_not_retrieved(tmp_path):
    s = DurableMemoryCandidateStore(tmp_path / "m.db")
    a = add(s, "Artemis server")
    s.revoke(a.candidate_id)

    assert retrieve_promoted(s, "Artemis").selected == ()
    s.close()


def test_context_only_breaks_ties_between_query_relevant_memories(tmp_path):
    s = DurableMemoryCandidateStore(tmp_path / "m.db")
    summer = add(s, "Sparks runs model trains in summer")
    winter = add(s, "Sparks runs model trains in winter")

    out = retrieve_promoted(
        s,
        "model trains",
        influence=contextual_influence(season="winter"),
        limit=5,
        budget_characters=1000,
    )

    assert [x.candidate_id for x in out.selected] == [
        winter.candidate_id,
        summer.candidate_id,
    ]
    s.close()


def test_context_cannot_make_unrelated_memory_query_relevant(tmp_path):
    s = DurableMemoryCandidateStore(tmp_path / "m.db")
    relevant = add(s, "Sparks likes model trains")
    add(s, "Winter snow evenings are cozy")

    out = retrieve_promoted(
        s,
        "model trains",
        influence=contextual_influence(),
        limit=5,
        budget_characters=1000,
    )

    assert [x.candidate_id for x in out.selected] == [
        relevant.candidate_id,
    ]
    s.close()


def test_unprovenanced_context_cannot_rerank_promoted_memories(tmp_path):
    s = DurableMemoryCandidateStore(tmp_path / "m.db")
    add(s, "Sparks runs model trains in summer")
    add(s, "Sparks runs model trains in winter")

    baseline = retrieve_promoted(
        s,
        "model trains",
        limit=5,
        budget_characters=1000,
    )
    out = retrieve_promoted(
        s,
        "model trains",
        influence=contextual_influence(
            season="winter",
            season_evidence_refs=(),
        ),
        limit=5,
        budget_characters=1000,
    )

    assert [x.candidate_id for x in out.selected] == [
        x.candidate_id for x in baseline.selected
    ]
    s.close()
