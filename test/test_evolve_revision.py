from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.evolve import (
    ApprovalAction,
    ReviewedRevisionExecutor,
    RevisionAdapter,
    RevisionApproval,
    RevisionApprovalVerifier,
    RevisionExecutionError,
    RevisionProposal,
    RevisionScope,
    RevisionStatus,
    revision_content_digest,
)

NOW = datetime(2026, 9, 25, 17, 30, tzinfo=timezone.utc)


class MemoryAdapter(RevisionAdapter):
    def __init__(self, values):
        self.values = dict(values)
        self.backups = {}
        self.next_token = 1

    def read_digest(self, scope, key):
        return revision_content_digest(self.values[(scope, key)])

    def validate(self, scope, key, proposed_content):
        if (scope, key) not in self.values:
            raise ValueError("unknown revision target")
        if not proposed_content.strip():
            raise ValueError("empty value denied")

    def apply(self, scope, key, *, expected_digest, proposed_content):
        current = self.values[(scope, key)]
        if revision_content_digest(current) != expected_digest:
            raise RuntimeError("compare-and-swap mismatch")
        token = f"rollback-{self.next_token}"
        self.next_token += 1
        self.backups[token] = current
        self.values[(scope, key)] = proposed_content
        return token

    def rollback(self, scope, key, *, expected_current_digest, rollback_token):
        current = self.values[(scope, key)]
        if revision_content_digest(current) != expected_current_digest:
            raise RuntimeError("rollback compare-and-swap mismatch")
        self.values[(scope, key)] = self.backups[rollback_token]


class ExactVerifier(RevisionApprovalVerifier):
    def __init__(self, accepted):
        self.accepted = set(accepted)

    def verify(self, proposal, approval, *, now):
        return (
            approval.approval_id in self.accepted
            and approval.approved_by == "Sparks"
        )


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "sofia.db"
    with sqlite3.connect(path):
        pass
    return path


def proposal(adapter, *, scope=RevisionScope.PREFERENCE, key="response_style", new="warm"):
    old_digest = adapter.read_digest(scope, key)
    return RevisionProposal(
        proposal_id="rev-1",
        scope=scope,
        key=key,
        expected_digest=old_digest,
        proposed_digest=revision_content_digest(new),
        evidence_ids=("source-1",),
        reason="Reviewed improvement",
        rollback_plan="Restore prior adapter revision",
        created_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=2),
    )


def approval(p, approval_id, action):
    return RevisionApproval(
        approval_id=approval_id,
        proposal_id=p.proposal_id,
        proposal_fingerprint=p.fingerprint,
        action=action,
        approved_by="Sparks",
        approved_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
        authority_reference="operator-session",
    )


def test_reviewed_preference_revision_applies_and_rolls_back(state):
    adapter = MemoryAdapter(
        {(RevisionScope.PREFERENCE, "response_style"): "neutral"}
    )
    p = proposal(adapter, new="warm")
    executor = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"apply-1", "rollback-1"}),
    )

    applied = executor.apply(
        p,
        approval(p, "apply-1", ApprovalAction.APPLY),
        proposed_content="warm",
        now=NOW,
    )
    assert applied.status is RevisionStatus.APPLIED
    assert adapter.values[(RevisionScope.PREFERENCE, "response_style")] == "warm"

    restored = executor.rollback(
        p,
        approval(p, "rollback-1", ApprovalAction.ROLLBACK),
        now=NOW + timedelta(minutes=10),
    )
    assert restored.status is RevisionStatus.ROLLED_BACK
    assert adapter.values[(RevisionScope.PREFERENCE, "response_style")] == "neutral"


def test_config_scope_uses_same_reviewed_revision_pipeline(state):
    adapter = MemoryAdapter(
        {(RevisionScope.CONFIG, "reflection_budget"): "8"}
    )
    p = proposal(
        adapter,
        scope=RevisionScope.CONFIG,
        key="reflection_budget",
        new="6",
    )
    executor = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"apply-1"}),
    )
    result = executor.apply(
        p,
        approval(p, "apply-1", ApprovalAction.APPLY),
        proposed_content="6",
        now=NOW,
    )
    assert result.scope is RevisionScope.CONFIG
    assert adapter.values[(RevisionScope.CONFIG, "reflection_budget")] == "6"


def test_unverified_or_wrong_action_approval_denied(state):
    adapter = MemoryAdapter(
        {(RevisionScope.PREFERENCE, "response_style"): "neutral"}
    )
    p = proposal(adapter, new="warm")
    denied = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier(set()),
    )
    with pytest.raises(PermissionError):
        denied.apply(
            p,
            approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content="warm",
            now=NOW,
        )

    allowed = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"rollback-1"}),
    )
    with pytest.raises(PermissionError, match="exact revision"):
        allowed.apply(
            p,
            approval(p, "rollback-1", ApprovalAction.ROLLBACK),
            proposed_content="warm",
            now=NOW,
        )
    assert adapter.values[(RevisionScope.PREFERENCE, "response_style")] == "neutral"


def test_source_drift_blocks_compare_and_swap(state):
    adapter = MemoryAdapter(
        {(RevisionScope.PREFERENCE, "response_style"): "neutral"}
    )
    p = proposal(adapter, new="warm")
    adapter.values[(RevisionScope.PREFERENCE, "response_style")] = "other"
    executor = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"apply-1"}),
    )
    with pytest.raises(RevisionExecutionError, match="changed before apply"):
        executor.apply(
            p,
            approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content="warm",
            now=NOW,
        )


def test_proposed_content_must_match_reviewed_digest(state):
    adapter = MemoryAdapter(
        {(RevisionScope.PREFERENCE, "response_style"): "neutral"}
    )
    p = proposal(adapter, new="warm")
    executor = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"apply-1"}),
    )
    with pytest.raises(RevisionExecutionError, match="does not match"):
        executor.apply(
            p,
            approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content="different",
            now=NOW,
        )


def test_exact_applied_revision_replay_is_idempotent(state):
    adapter = MemoryAdapter(
        {(RevisionScope.PREFERENCE, "response_style"): "neutral"}
    )
    p = proposal(adapter, new="warm")
    executor = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"apply-1"}),
    )
    a = approval(p, "apply-1", ApprovalAction.APPLY)
    first = executor.apply(p, a, proposed_content="warm", now=NOW)
    second = executor.apply(p, a, proposed_content="warm", now=NOW)
    assert first == second
    assert adapter.next_token == 2


def test_later_change_blocks_rollback(state):
    adapter = MemoryAdapter(
        {(RevisionScope.PREFERENCE, "response_style"): "neutral"}
    )
    p = proposal(adapter, new="warm")
    executor = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"apply-1", "rollback-1"}),
    )
    executor.apply(
        p,
        approval(p, "apply-1", ApprovalAction.APPLY),
        proposed_content="warm",
        now=NOW,
    )
    adapter.values[(RevisionScope.PREFERENCE, "response_style")] = "newer"
    with pytest.raises(RevisionExecutionError, match="changed after apply"):
        executor.rollback(
            p,
            approval(p, "rollback-1", ApprovalAction.ROLLBACK),
            now=NOW + timedelta(minutes=10),
        )
    assert adapter.values[(RevisionScope.PREFERENCE, "response_style")] == "newer"


def test_expired_proposal_cannot_apply(state):
    adapter = MemoryAdapter(
        {(RevisionScope.PREFERENCE, "response_style"): "neutral"}
    )
    p = proposal(adapter, new="warm")
    executor = ReviewedRevisionExecutor(
        state_path=state,
        adapter=adapter,
        verifier=ExactVerifier({"apply-1"}),
    )
    with pytest.raises(RevisionExecutionError, match="expired"):
        executor.apply(
            p,
            approval(p, "apply-1", ApprovalAction.APPLY),
            proposed_content="warm",
            now=NOW + timedelta(hours=2),
        )
