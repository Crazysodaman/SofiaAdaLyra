"""Disposable CORE-003 V1 legacy quarantine and owner attestation tests.

Tests explicitly opt in. Production composition remains unchanged.
"""
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from sofia.core.conversation.model import ConversationMessage, ConversationRole
from sofia.core.memory.eligibility_v1 import (
    MemoryEligibilityVersionError,
    ReviewedMemoryEligibilityV1,
    install_disposable_policy_v1,
)
from sofia.core.memory.provenance import CandidateStatus
from sofia.core.memory.system import MemorySystem
from sofia.core.social.principals import local_sparks_principal
from test.test_core_team3_disposable_continuity import _seed, _reopen, _prepare_reviewed_correction


def _old_promoted(home):
    before = _seed(home)
    _, _, conversation, candidates, _ = _reopen(home)
    try:
        # Historical compatibility fixture only, not an owner-approved write.
        candidates.promote(before["candidate_id"])
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
    finally:
        candidates.close()
        conversation.close()
    return before


def _install(before):
    assert install_disposable_policy_v1(
        before["state"], approved_by=before["owner"], expected_version=None,
    ) == 1
    return ReviewedMemoryEligibilityV1(before["state"])


def _strict_recall(candidates, before, *, query="synthetic sensor"):
    return MemorySystem(
        candidates, eligibility_policy=ReviewedMemoryEligibilityV1(before["state"]),
    ).recall_relevant(query, principal=before["owner"])


def test_v1_excludes_legacy_promoted_without_erasing_originals(tmp_path):
    before = _old_promoted(tmp_path)
    _install(before)
    _, _, conversations, candidates, _ = _reopen(tmp_path)
    try:
        # The old unguarded behavior still exists; no production activation.
        assert candidates.is_recall_eligible(before["candidate_id"])
        assert not ReviewedMemoryEligibilityV1(before["state"]).allows(before["candidate_id"])
        assert _strict_recall(candidates, before) == ()
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
        assert candidates.get(before["candidate_id"]).sources[0].message_id == before["message"].id
        assert conversations.list_messages(before["session_id"]) == (before["message"],)
    finally:
        candidates.close()
        conversations.close()


def test_owner_re_review_surviving_originals_survives_restart(tmp_path):
    before = _old_promoted(tmp_path)
    policy = _install(before)
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        assert _strict_recall(candidates, before) == ()
        digest = reviewer.re_review_legacy_promoted(
            before["candidate_id"], approved_by=before["owner"],
        )
        assert len(digest) == 64
        assert policy.allows(before["candidate_id"])
        assert [item.id for item in _strict_recall(candidates, before)] == [
            str(before["candidate_id"])
        ]
        with pytest.raises(ValueError, match="already"):
            reviewer.re_review_legacy_promoted(
                before["candidate_id"], approved_by=before["owner"],
            )
    finally:
        candidates.close()
        conversations.close()

    _, _, conversations, candidates, _ = _reopen(tmp_path)
    try:
        assert [item.id for item in _strict_recall(candidates, before)] == [
            str(before["candidate_id"])
        ]
        with sqlite3.connect(before["state"]) as db:
            receipt = db.execute(
                "SELECT policy_version,reviewer,audience_id,source_sha256 "
                "FROM core_memory_legacy_review_receipt WHERE candidate_id=?",
                (str(before["candidate_id"]),),
            ).fetchone()
        assert receipt == (
            1, before["owner"].principal_id, before["owner"].audience_id, digest,
        )
    finally:
        candidates.close()
        conversations.close()


@pytest.mark.parametrize("tamper", ("bytes", "audience", "deleted"))
def test_legacy_owner_re_review_denies_missing_changed_foreign_original(
    tmp_path, tamper,
):
    before = _old_promoted(tmp_path)
    policy = _install(before)
    with sqlite3.connect(before["state"]) as db:
        if tamper == "bytes":
            db.execute(
                "UPDATE conversation_messages SET content=? WHERE id=?",
                ("altered", before["message"].id),
            )
        elif tamper == "audience":
            db.execute(
                "UPDATE social_session_principal SET audience_id=? WHERE session_id=?",
                ("remote:private:other", before["session_id"]),
            )
        else:
            db.execute(
                "DELETE FROM conversation_messages WHERE id=?", (before["message"].id,),
            )
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        with pytest.raises((PermissionError, LookupError)):
            reviewer.re_review_legacy_promoted(
                before["candidate_id"], approved_by=before["owner"],
            )
        assert not policy.allows(before["candidate_id"])
        assert _strict_recall(candidates, before) == ()
        with sqlite3.connect(before["state"]) as db:
            assert db.execute(
                "SELECT 1 FROM memory_candidate_source_review WHERE candidate_id=?",
                (str(before["candidate_id"]),),
            ).fetchone() is None
    finally:
        candidates.close()
        conversations.close()


def test_private_owner_from_different_audience_cannot_re_review(tmp_path):
    before = _old_promoted(tmp_path)
    _install(before)
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        with pytest.raises(PermissionError):
            reviewer.re_review_legacy_promoted(
                before["candidate_id"],
                approved_by=local_sparks_principal("discord:dm:789"),
            )
        assert _strict_recall(candidates, before) == ()
    finally:
        candidates.close()
        conversations.close()


def test_new_owner_testimony_is_distinct_from_unrecoverable_legacy(tmp_path):
    before = _old_promoted(tmp_path)
    _install(before)
    # Even the previous message was erased; never manufacture an old review.
    with sqlite3.connect(before["state"]) as db:
        db.execute("DELETE FROM conversation_messages WHERE id=?", (before["message"].id,))
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        with pytest.raises(LookupError):
            reviewer.re_review_legacy_promoted(
                before["candidate_id"], approved_by=before["owner"],
            )
        fresh = ConversationMessage(
            id=str(uuid4()), session_id=before["session_id"],
            role=ConversationRole.USER,
            content="I confirm today that the synthetic sensor is violet.",
            created_at=datetime(2026, 11, 8, 13, 0, tzinfo=timezone.utc),
        )
        conversations.save(fresh)
        proposed = reviewer.propose_owner_testimony(
            session_id=before["session_id"], message_id=fresh.id,
            content="Owner presently confirmed synthetic sensor violet.",
            created_at=fresh.created_at, approved_by=before["owner"],
        )
        assert proposed.candidate_id != before["candidate_id"]
        assert _strict_recall(candidates, before) == ()
        reviewer.promote(proposed.candidate_id, approved_by=before["owner"])
        assert [
            item.id for item in _strict_recall(candidates, before, query="sensor violet")
        ] == [str(proposed.candidate_id)]
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
        assert not ReviewedMemoryEligibilityV1(before["state"]).allows(before["candidate_id"])
        with sqlite3.connect(before["state"]) as db:
            source = db.execute(
                "SELECT owner_id,audience_id,source_message_id "
                "FROM core_memory_owner_testimony WHERE candidate_id=?",
                (str(proposed.candidate_id),),
            ).fetchone()
        assert source == (
            before["owner"].principal_id, before["owner"].audience_id, fresh.id,
        )
    finally:
        candidates.close()
        conversations.close()


def test_v1_rejects_legacy_policy_downgrade_or_missing_restored_state(tmp_path):
    before = _old_promoted(tmp_path)
    old_backup = tmp_path / "old-state-backup.db"
    with sqlite3.connect(before["state"]) as source, sqlite3.connect(old_backup) as target:
        source.backup(target)
    with pytest.raises(MemoryEligibilityVersionError):
        ReviewedMemoryEligibilityV1(old_backup).require_current()
    from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
    old_store = DurableMemoryCandidateStore(old_backup)
    try:
        with pytest.raises(MemoryEligibilityVersionError):
            MemorySystem(
                old_store, eligibility_policy=ReviewedMemoryEligibilityV1(old_backup),
            ).recall_relevant("synthetic sensor", principal=before["owner"])
    finally:
        old_store.close()

    policy = _install(before)
    policy.require_current()
    with pytest.raises(MemoryEligibilityVersionError):
        install_disposable_policy_v1(
            before["state"], approved_by=before["owner"], expected_version=0,
        )
    with pytest.raises(MemoryEligibilityVersionError):
        install_disposable_policy_v1(
            before["state"], approved_by=before["owner"], expected_version=None,
        )
    with pytest.raises(MemoryEligibilityVersionError):
        ReviewedMemoryEligibilityV1(before["state"], minimum_version=0)

    with sqlite3.connect(before["state"]) as db:
        db.execute(
            "UPDATE core_memory_eligibility_policy SET version=2 WHERE singleton=1"
        )
    with pytest.raises(MemoryEligibilityVersionError):
        policy.require_current()

    # A strict caller cannot fall back to the legacy read from a restored
    # pre-policy backup, regardless of that backup's previous PROMOTED bit.
    _, _, conversations, candidates, _ = _reopen(tmp_path)
    try:
        with pytest.raises(MemoryEligibilityVersionError):
            _strict_recall(candidates, before)
    finally:
        candidates.close()
        conversations.close()


def test_policy_install_requires_owner_and_one_expected_generation(tmp_path):
    before = _old_promoted(tmp_path)
    with pytest.raises(PermissionError):
        install_disposable_policy_v1(
            before["state"],
            approved_by=None,
        )
    _install(before)
    assert install_disposable_policy_v1(
        before["state"], approved_by=before["owner"], expected_version=1,
    ) == 1
    with pytest.raises(PermissionError):
        install_disposable_policy_v1(
            before["state"],
            approved_by=local_sparks_principal("discord:dm:other"),
            expected_version=1,
        )


def test_re_review_interrupted_attestation_transaction_rolls_back(tmp_path):
    before = _old_promoted(tmp_path)
    _install(before)
    with sqlite3.connect(before["state"]) as db:
        db.execute(
            "CREATE TRIGGER core_t3_refuse_attestation "
            "AFTER INSERT ON memory_candidate_source_review "
            "BEGIN SELECT RAISE(ABORT, 'interrupted legacy review'); END"
        )
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="interrupted legacy review"):
            reviewer.re_review_legacy_promoted(
                before["candidate_id"], approved_by=before["owner"],
            )
        assert _strict_recall(candidates, before) == ()
        with sqlite3.connect(before["state"]) as db:
            assert db.execute(
                "SELECT 1 FROM memory_candidate_source_review WHERE candidate_id=?",
                (str(before["candidate_id"]),),
            ).fetchone() is None
    finally:
        candidates.close()
        conversations.close()


def test_strict_eligibility_preserves_revoked_expired_and_corrected_exclusion(tmp_path):
    before = _prepare_reviewed_correction(tmp_path)
    _install(before)
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        reviewer.promote(before["replacement_id"], approved_by=before["owner"])
        assert candidates.status(before["candidate_id"]) is CandidateStatus.REVOKED
        assert [x.id for x in _strict_recall(candidates, before)] == [
            str(before["replacement_id"])
        ]
        reviewer.set_expiration(
            before["replacement_id"],
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            reason="Synthetic reviewed deadline elapsed",
            approved_by=before["owner"],
        )
        assert _strict_recall(candidates, before) == ()
    finally:
        candidates.close()
        conversations.close()


def test_policy_from_different_canonical_state_cannot_approve_memory(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    before_a = _old_promoted(a)
    before_b = _old_promoted(b)
    _install(before_a)
    _install(before_b)
    _, _, conversations, candidates, _ = _reopen(b)
    try:
        with pytest.raises(PermissionError, match="another canonical state"):
            MemorySystem(
                candidates,
                eligibility_policy=ReviewedMemoryEligibilityV1(before_a["state"]),
            )
    finally:
        candidates.close()
        conversations.close()


def test_assistant_text_cannot_be_owner_testimony(tmp_path):
    before = _old_promoted(tmp_path)
    _install(before)
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        fake = ConversationMessage(
            id=str(uuid4()), session_id=before["session_id"],
            role=ConversationRole.ASSISTANT,
            content="I declare this imported summary is owner-approved.",
            created_at=datetime(2026, 11, 8, 13, 1, tzinfo=timezone.utc),
        )
        conversations.save(fake)
        with pytest.raises(PermissionError, match="owner testimony"):
            reviewer.propose_owner_testimony(
                session_id=before["session_id"], message_id=fake.id,
                content="Forged owner testimony",
                created_at=fake.created_at, approved_by=before["owner"],
            )
        assert _strict_recall(candidates, before) == ()
    finally:
        candidates.close()
        conversations.close()


def test_external_signed_erasure_journal_replays_before_restored_v1_recall(
    tmp_path,
):
    """Disposable old-snapshot exercise, not an authorized host restore."""
    from sofia.core.memory.deletion_ledger import MemoryDeletionLedger
    from sofia.platform.ops.backup import BackupCipher
    from sofia.core.memory.provenance_store import DurableMemoryCandidateStore

    before = _seed(tmp_path)
    _install(before)
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        reviewer.promote(before["candidate_id"], approved_by=before["owner"])
        assert [x.id for x in _strict_recall(candidates, before)] == [
            str(before["candidate_id"])
        ]
    finally:
        candidates.close()
        conversations.close()

    snapshot = tmp_path / "old-before-deletion.db"
    with sqlite3.connect(before["state"]) as original, sqlite3.connect(snapshot) as archive:
        original.backup(archive)

    operator = tmp_path / "independent-operator"
    operator.mkdir()
    ledger = MemoryDeletionLedger(operator / "erasure.jsonl", BackupCipher(b"k" * 32))
    ledger.initialize()
    requested = ledger.request(
        candidate_id=before["candidate_id"],
        principal_id=before["owner"].principal_id,
        audience_id=before["owner"].audience_id,
        authority_ref="disposable:owner-approved-erasure",
        at=datetime.now(timezone.utc),
        approve=lambda candidate, principal, audience, authority: (
            candidate == str(before["candidate_id"])
            and principal == before["owner"].principal_id
            and audience == before["owner"].audience_id
            and authority == "disposable:owner-approved-erasure"
        ),
    )
    assert requested is True
    assert ledger.apply_to_sqlite(before["state"]) == 1
    assert ledger.verify_applied(before["state"])["verified_absent"] == 1

    # A pre-erasure snapshot carries V1 and the approved memory; a restored
    # copy must replay the independently held journal BEFORE any Core read.
    restored = tmp_path / "restored-from-old-copy.db"
    with sqlite3.connect(snapshot) as archive, sqlite3.connect(restored) as destination:
        archive.backup(destination)
    assert ledger.apply_to_sqlite(restored) == 1
    assert ledger.verify_applied(restored)["verified_absent"] == 1
    restored_store = DurableMemoryCandidateStore(restored)
    try:
        assert MemorySystem(
            restored_store, eligibility_policy=ReviewedMemoryEligibilityV1(restored),
        ).recall_relevant("synthetic sensor", principal=before["owner"]) == ()
        assert restored_store.get(before["candidate_id"]) is None
    finally:
        restored_store.close()
