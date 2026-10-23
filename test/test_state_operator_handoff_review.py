"""CA-3704 operator-controlled failover/failback review stays non-authoritative."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from sofia.platform.ops.state_promotion import (
    OperatorHandoffEvidence,
    OperatorHandoffKind,
    PendingHomePointer,
    review_operator_handoff,
)
from sofia.platform.ops.state_relocation import RelocationAuthorization, StagedStateHome


NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def _evidence(tmp_path: Path, *, kind=OperatorHandoffKind.FAILOVER):
    destination = tmp_path / "recovered"
    destination.mkdir()
    database = destination / "sofia.db"
    database.write_bytes(b"verified staged sqlite fixture")
    (destination / "protected").mkdir()
    (destination / "protected" / "identity.json").write_text(
        '{"instance_id":"continuous"}\n', encoding="utf-8",
    )
    pointer = tmp_path / "state-home.pending.json"
    pointer.write_bytes(b'{"signed":"operator-owned"}\n')
    authorization = RelocationAuthorization(
        source_state_path=tmp_path / "old" / "sofia.db",
        destination_root=destination,
        writer_host_id="artemis-sofia",
        source_writer_host_id="venus",
        next_writer_epoch=8,
        operator_approval_ref="approval:exact-cutover",
        writer_fence_ref="fence:venus-epoch-7",
        protected_operation_id="operation:state-handoff",
        operator_principal_id="principal:sparks",
        source_writer_epoch=7,
    )
    staged = StagedStateHome(
        backup_dir=tmp_path / "backup",
        destination_state_path=database,
        backup_id="backup:verified",
        writer_host_id="artemis-sofia",
        proposed_writer_epoch=8,
        verified_restore=True,
    )
    pending = PendingHomePointer(
        pending_path=pointer,
        pointer_sha256=sha256(pointer.read_bytes()).hexdigest(),
        writer_host_id="artemis-sofia",
        new_epoch=8,
        operator_approval_ref="approval:exact-cutover",
    )
    return OperatorHandoffEvidence(
        kind=kind,
        staged=staged,
        pending=pending,
        authorization=authorization,
        backup_integrity_ref="backup-proof:sha256",
        promoted_writer_lease_ref="lease-reservation:epoch-8",
        old_runtime_fence_ref="runtime-fence:venus",
        device_identity_ref="identity-proof:sofia-instance",
        audience_privacy_audit_ref="privacy-audit:restored-scopes",
        uncertain_effects_review_ref="run-review:all-open-effects",
        old_writer_fenced=True,
        old_runtime_stopped=True,
        target_writer_lease_reserved=True,
        split_brain_absent=True,
        device_identity_continuity_verified=True,
        audience_privacy_verified=True,
        uncertain_effects_reconciled=True,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )


@pytest.mark.parametrize("kind", tuple(OperatorHandoffKind))
def test_complete_failover_or_failback_review_never_activates_writer(
    tmp_path, kind,
):
    evidence = _evidence(tmp_path, kind=kind)
    review = review_operator_handoff(
        evidence, now=NOW + timedelta(minutes=1),
        independently_verify_evidence=lambda candidate: candidate is evidence,
    )
    assert review.ready_for_privileged_broker is True
    assert review.blockers == ()
    assert review.may_activate_writer is False
    assert review.proposed_epoch == 8
    assert review.writer_host_id == "artemis-sofia"


@pytest.mark.parametrize(
    ("field", "blocker"),
    (
        ("old_writer_fenced", "old_writer_not_fenced"),
        ("old_runtime_stopped", "old_runtime_not_stopped"),
        ("target_writer_lease_reserved", "new_writer_lease_not_reserved"),
        ("split_brain_absent", "split_brain_not_excluded"),
        (
            "device_identity_continuity_verified",
            "device_identity_continuity_unverified",
        ),
        (
            "audience_privacy_verified",
            "post_restore_audience_privacy_unverified",
        ),
        (
            "uncertain_effects_reconciled",
            "uncertain_external_effects_unreconciled",
        ),
    ),
)
def test_each_required_handoff_fact_fails_closed(tmp_path, field, blocker):
    evidence = replace(_evidence(tmp_path), **{field: False})
    review = review_operator_handoff(
        evidence, now=NOW + timedelta(minutes=1),
        independently_verify_evidence=lambda _candidate: True,
    )
    assert review.ready_for_privileged_broker is False
    assert blocker in review.blockers
    assert review.may_activate_writer is False


def test_handoff_rejects_stale_or_tampered_local_artifacts(tmp_path):
    evidence = _evidence(tmp_path)
    evidence.pending.pending_path.write_bytes(b"tampered")
    review = review_operator_handoff(
        evidence, now=evidence.expires_at,
        independently_verify_evidence=lambda _candidate: False,
    )
    assert {
        "handoff_evidence_not_current",
        "signed_pending_pointer_digest_mismatch",
        "independent_privileged_witness_denied",
    }.issubset(review.blockers)
    assert review.ready_for_privileged_broker is False
