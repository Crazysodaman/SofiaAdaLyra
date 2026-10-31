"""CA-3704 operator-controlled failover/failback review stays non-authoritative."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import hmac
import json

import pytest

from sofia.platform.config.state_home_pointer import _DOMAIN, _SCHEMA
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
    # Syntactically valid synthetic signed candidate; the independent
    # control-plane callback in these tests stands in for its HMAC verifier.
    document = {
        "schema": _SCHEMA,
        "state_root": str(destination.resolve(strict=True)),
        "writer_host_id": "artemis-sofia",
        "epoch": 8,
        "operator_approval_ref": "approval:exact-cutover",
    }
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    document["hmac_sha256"] = hmac.new(
        b"test-fixture-key-not-for-production", _DOMAIN + canonical, sha256,
    ).hexdigest()
    pointer.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
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


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("schema", "unrecognized-pointer-v1"),
        ("state_root", "/foreign/state/home"),
        ("writer_host_id", "venus"),
        ("epoch", 9),
        ("epoch", True),
        ("operator_approval_ref", "approval:another-cutover"),
        ("hmac_sha256", "not-a-valid-signature"),
        ("unexpected", "unreviewed-field"),
    ),
)
def test_handoff_pointer_payload_must_match_exact_approved_transfer(
    tmp_path, field, invalid,
):
    evidence = _evidence(tmp_path)
    pointer = evidence.pending.pending_path
    document = json.loads(pointer.read_text(encoding="utf-8"))
    document[field] = invalid
    pointer.write_text(json.dumps(document), encoding="utf-8")
    # Even a refreshed metadata digest cannot turn the wrong host/epoch/
    # approval into authorized candidate content.
    updated = replace(
        evidence,
        pending=replace(
            evidence.pending,
            pointer_sha256=sha256(pointer.read_bytes()).hexdigest(),
        ),
    )
    review = review_operator_handoff(
        updated, now=NOW + timedelta(minutes=1),
        independently_verify_evidence=lambda _candidate: True,
    )
    assert "signed_pending_pointer_payload_mismatch" in review.blockers
    assert not review.ready_for_privileged_broker
    assert review.may_activate_writer is False


def test_handoff_pointer_oversized_even_with_matching_receipt_digest(tmp_path):
    evidence = _evidence(tmp_path)
    pointer = evidence.pending.pending_path
    pointer.write_bytes(b" " * 16_385)
    updated = replace(
        evidence,
        pending=replace(
            evidence.pending, pointer_sha256=sha256(pointer.read_bytes()).hexdigest(),
        ),
    )
    review = review_operator_handoff(
        updated, now=NOW + timedelta(minutes=1),
        independently_verify_evidence=lambda _candidate: True,
    )
    assert "signed_pending_pointer_exceeds_size_policy" in review.blockers
    assert not review.ready_for_privileged_broker


def test_g7_handoff_cannot_reuse_single_evidence_ref_for_independent_checks(tmp_path):
    evidence = _evidence(tmp_path)
    aliased = replace(
        evidence,
        promoted_writer_lease_ref=evidence.authorization.writer_fence_ref,
    )
    review = review_operator_handoff(
        aliased, now=NOW + timedelta(minutes=1),
        independently_verify_evidence=lambda _value: True,
    )
    assert "handoff_evidence_references_not_independent" in review.blockers
    assert review.ready_for_privileged_broker is False
    assert review.may_activate_writer is False


def test_g7_handoff_cannot_promote_source_onto_same_writer_host(tmp_path):
    evidence = _evidence(tmp_path)
    same = replace(
        evidence, authorization=replace(
            evidence.authorization,
            source_writer_host_id=evidence.authorization.writer_host_id,
        ),
    )
    review = review_operator_handoff(
        same, now=NOW + timedelta(minutes=1),
        independently_verify_evidence=lambda _value: True,
    )
    assert "source_and_target_writer_host_not_distinct" in review.blockers
    assert review.ready_for_privileged_broker is False
    assert review.may_activate_writer is False
