"""Deferred production MEM x NEURO associative-learning contracts. Not run."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import sqlite3

import pytest

from sofia.config.user_settings import RuntimeUserSettings, RuntimeUserSettingsStore
from sofia.memory.originals import SourceMessage
from sofia.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.system import MemorySystem
from sofia.neuro.connectome.association_store import ReviewedAssociationStore
from sofia.social.principals import local_sparks_principal, discord_sparks_principal


NOW = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)


def candidate(text: str, order: int, *, audience: str = "local:text"):
    created = NOW + timedelta(seconds=order)
    return MemoryCandidate(
        candidate_id=uuid4(),
        content=text,
        sources=(SourceMessage(
            "message-" + str(order), "session-" + str(order),
            "user", "reviewed source " + str(order), created, 0,
        ),),
        created_at=created,
        principal_id="person:sparks",
        audience_id=audience,
    )


def prepare(tmp_path, *, opted_in=False):
    state = tmp_path / "sofia.db"
    memories = DurableMemoryCandidateStore(state)
    settings = RuntimeUserSettingsStore(state)
    settings.save(RuntimeUserSettings(neuro_association_enabled=opted_in))
    association = ReviewedAssociationStore(state)
    system = MemorySystem(memories, association_store=association)
    return state, memories, settings, association, system


def teach(association, item, *, query="model trains", audience="local:text", amount=.1):
    return association.reinforce_reviewed(
        principal_id="person:sparks", audience_id=audience,
        candidate_id=item.candidate_id, query=query,
        approval_ref="operator-ui:" + uuid4().hex, amount=amount, at=NOW,
    )


def test_opted_out_associations_are_inert_and_training_refused(tmp_path):
    state, memories, settings, assoc, system = prepare(tmp_path)
    first = candidate("Sparks enjoys model trains", 1)
    second = candidate("Sparks repairs model trains", 2)
    for item in (first, second):
        memories.propose(item)
        memories.promote(item.candidate_id)
    baseline = system.recall_relevant("model trains", principal=local_sparks_principal())
    assert [record.id for record in baseline][:2] == [
        str(first.candidate_id), str(second.candidate_id),
    ]
    with pytest.raises(PermissionError, match="disabled"):
        teach(assoc, second)
    assert assoc.scores(
        principal_id="person:sparks", audience_id="local:text",
        query="model trains", eligible_ids=(second.candidate_id,),
    ) == {}
    memories.close()


def test_opted_in_learning_reranks_eligible_ties_and_survives_recreation(tmp_path):
    state, memories, settings, assoc, system = prepare(tmp_path, opted_in=True)
    first = candidate("Sparks enjoys model trains", 1)
    second = candidate("Sparks repairs model trains", 2)
    unrelated = candidate("Sparks likes hiking", 3)
    for item in (first, second, unrelated):
        memories.propose(item)
        memories.promote(item.candidate_id)
    teach(assoc, second)
    reread = MemorySystem(
        memories, association_store=ReviewedAssociationStore(state),
    )
    recalled = reread.recall_relevant(
        "model trains", limit=3, principal=local_sparks_principal(),
    )
    assert [record.id for record in recalled] == [
        str(second.candidate_id), str(first.candidate_id),
    ]
    assert all(record.id != str(unrelated.candidate_id) for record in recalled)
    # A different authenticated audience receives only MEM eligible records
    # and never consumes or reveals local:text association weights.
    remote = reread.recall_relevant(
        "model trains", principal=discord_sparks_principal(22222222),
    )
    assert remote == ()
    assert assoc.scores(
        principal_id="person:sparks", audience_id="discord:dm:22222222",
        query="model trains", eligible_ids=(second.candidate_id,),
    ) == {}
    memories.close()


def test_revocation_triggers_canonical_weight_and_provenance_cleanup(tmp_path):
    state, memories, _, assoc, system = prepare(tmp_path, opted_in=True)
    item = candidate("Reviewed home wiring diagram", 1)
    memories.propose(item)
    memories.promote(item.candidate_id)
    teach(assoc, item, query="wiring diagram")
    with sqlite3.connect(state) as db:
        before = db.execute(
            "SELECT COUNT(*) FROM neuro_association_event WHERE candidate_id=?",
            (str(item.candidate_id),),
        ).fetchone()[0]
    assert before == 1
    memories.revoke(item.candidate_id)
    with sqlite3.connect(state) as db:
        weight = db.execute(
            "SELECT COUNT(*) FROM neuro_association_weight WHERE candidate_id=?",
            (str(item.candidate_id),),
        ).fetchone()[0]
        events = db.execute(
            "SELECT COUNT(*) FROM neuro_association_event WHERE candidate_id=?",
            (str(item.candidate_id),),
        ).fetchone()[0]
    assert (weight, events) == (0, 0)
    assert system.recall_relevant(
        "wiring diagram", principal=local_sparks_principal(),
    ) == ()
    memories.close()


def test_reviewed_correction_never_inherits_old_associations(tmp_path):
    state, memories, _, assoc, system = prepare(tmp_path, opted_in=True)
    old = candidate("Model trains use red controller", 1)
    new = candidate("Model trains use blue controller", 2)
    memories.propose(old)
    memories.promote(old.candidate_id)
    teach(assoc, old)
    memories.propose(new)
    memories.link_correction(new.candidate_id, old.candidate_id)
    memories.promote(new.candidate_id)
    assert memories.status(old.candidate_id) is CandidateStatus.REVOKED
    assert assoc.scores(
        principal_id="person:sparks", audience_id="local:text",
        query="model trains",
        eligible_ids=(old.candidate_id, new.candidate_id),
    ) == {}
    recalled = system.recall_relevant(
        "model trains", principal=local_sparks_principal(),
    )
    assert [item.id for item in recalled] == [str(new.candidate_id)]
    memories.close()


def test_wrong_principal_audience_or_draft_cannot_be_reinforced(tmp_path):
    state, memories, _, assoc, _ = prepare(tmp_path, opted_in=True)
    proposed = candidate("Sparks repairs a radio", 1)
    approved = candidate("Sparks repairs a radio", 2)
    memories.propose(proposed)
    memories.propose(approved)
    memories.promote(approved.candidate_id)
    with pytest.raises(PermissionError, match="not promoted"):
        teach(assoc, proposed, query="radio")
    with pytest.raises(PermissionError, match="not promoted"):
        teach(assoc, approved, query="radio", audience="discord:dm:22")
    with pytest.raises(PermissionError, match="not promoted"):
        assoc.reinforce_reviewed(
            principal_id="other-user", audience_id="local:text",
            candidate_id=approved.candidate_id, query="radio",
            approval_ref="operator-ui:" + uuid4().hex, amount=.1, at=NOW,
        )
    memories.close()


def test_scope_reset_decay_and_no_raw_query_storage(tmp_path):
    state, memories, _, assoc, _ = prepare(tmp_path, opted_in=True)
    item = candidate("The ceramic storage tank is in Artemis", 1)
    memories.propose(item)
    memories.promote(item.candidate_id)
    secret = "ceramic confidential context word"
    teach(assoc, item, query=secret)
    with sqlite3.connect(state) as db:
        serialized = repr(db.execute(
            "SELECT feature_units_json,amount FROM neuro_association_event"
        ).fetchall())
    assert secret not in serialized
    scored = assoc.scores(
        principal_id="person:sparks", audience_id="local:text",
        query=secret, eligible_ids=(item.candidate_id,),
    )
    assert scored[item.candidate_id] > 0
    assert assoc.decay_scope(
        principal_id="person:sparks", audience_id="local:text",
        rate=.05, at=NOW + timedelta(days=1),
    ) > 0
    after = assoc.scores(
        principal_id="person:sparks", audience_id="local:text",
        query=secret, eligible_ids=(item.candidate_id,),
    )
    assert 0 < after[item.candidate_id] < scored[item.candidate_id]
    assert assoc.reset_scope(
        principal_id="person:sparks", audience_id="local:text",
    ) > 0
    assert assoc.scores(
        principal_id="person:sparks", audience_id="local:text",
        query=secret, eligible_ids=(item.candidate_id,),
    ) == {}
    memories.close()


def test_schema_migrates_to_disabled_opt_in():
    document = RuntimeUserSettingsStore._encode(
        RuntimeUserSettings()
    )
    import json
    values = json.loads(document)
    values["schema_version"] = 10
    del values["neuro_association_enabled"]
    assert RuntimeUserSettingsStore._decode(
        json.dumps(values)
    ).neuro_association_enabled is False
