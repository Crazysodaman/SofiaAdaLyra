"""Source-authored regression coverage for the sealed generalization gate.

The owner-requested acceptance campaign runs tests later. These fixtures
do not run a model, call a remote service or touch the canonical database.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.verify.generalization_transfer import (
    SCHEMA, TransferEvidenceError, assess_signed_transfer, canonical,
)

NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)


def _time(minutes):
    return (NOW + timedelta(minutes=minutes)).isoformat()


def _signed(private, statement):
    return {
        "statement": statement,
        "signature_b64": base64.b64encode(private.sign(canonical(statement))).decode(),
    }


def _study(*, successful_learning=True, unsafe=0, count=12):
    """Evaluator-owned signed fixture: B always hidden until after A."""
    private = Ed25519PrivateKey.generate()
    tasks = [f"blind-b-{i}" for i in range(count)]
    holdout = {"family": "windows-dependency", "task_ids": tasks}
    sealed = {
        "schema": SCHEMA,
        "study_id": "study:test-1",
        "training_family": "docker-dns",
        "holdout_family": holdout["family"],
        "holdout_digest": sha256(canonical(holdout)).hexdigest(),
        "sealed_at": _time(0),
        "revision": "b" * 40,
        "model_digest": "a" * 64,
    }
    results = []
    for condition in ("baseline", "no_memory", "no_skill", "replay_only", "learned"):
        for index, task in enumerate(tasks):
            results.append({
                "condition": condition,
                "task_id": task,
                "success": successful_learning and condition == "learned",
                "checker_receipt_id": f"receipt:{condition}-{index}",
                "unsafe_attempts": unsafe if condition == "learned" and index == 0 else 0,
                "human_hints": 0,
                "elapsed_ms": 50_000,
            })
    evaluated = {
        "schema": SCHEMA,
        "study_id": sealed["study_id"],
        "sealed_statement_digest": sha256(canonical(sealed)).hexdigest(),
        "a_started_at": _time(1),
        "a_completed_at": _time(2),
        "b_revealed_at": _time(3),
        "b_evaluated_at": _time(4),
        "holdout": holdout,
        "results": results,
    }
    return {
        "sealed": _signed(private, sealed),
        "evaluated": _signed(private, evaluated),
    }, private


def _resign(bundle, signer):
    """Simulate trusted evaluator issuing a *new* statement for negative tests."""
    bundle["sealed"] = _signed(signer, bundle["sealed"]["statement"])
    bundle["evaluated"] = _signed(signer, bundle["evaluated"]["statement"])
    return bundle


def test_blinded_independent_pairwise_transfer_screening_is_read_only():
    study, signer = _study()
    review = assess_signed_transfer(study, evaluator_key=signer.public_key())
    assert review.holdout_tasks == 12
    assert review.trained_family != review.unseen_family
    assert review.learned_success_rate == 1
    assert review.evidence_supports_transfer
    assert not review.authorized_for_deployment
    assert all(c.one_sided_p < .0125 for c in review.comparisons)
    assert all(c.wins == 12 and c.losses == 0 for c in review.comparisons)


def test_no_improvement_does_not_claim_transfer():
    study, signer = _study(successful_learning=False)
    review = assess_signed_transfer(study, evaluator_key=signer.public_key())
    assert not review.evidence_supports_transfer
    assert review.learned_success_rate == 0


def test_unsafe_learning_does_not_claim_transfer():
    study, signer = _study(unsafe=1)
    review = assess_signed_transfer(study, evaluator_key=signer.public_key())
    assert not review.evidence_supports_transfer
    assert review.unsafe_attempts == 1


def test_signature_tampering_fails_closed():
    study, signer = _study()
    study["evaluated"]["statement"]["results"][0]["success"] = True
    with pytest.raises(TransferEvidenceError, match="signature"):
        assess_signed_transfer(study, evaluator_key=signer.public_key())


def test_wrong_signer_fails_closed():
    study, _ = _study()
    outsider = Ed25519PrivateKey.generate().public_key()
    with pytest.raises(TransferEvidenceError, match="signature"):
        assess_signed_transfer(study, evaluator_key=outsider)


def test_holdout_change_rejected_even_if_evaluator_resigns():
    study, signer = _study()
    study["evaluated"]["statement"]["holdout"]["task_ids"][0] = "replaced-b-case"
    _resign(study, signer)
    with pytest.raises(TransferEvidenceError, match="holdout does not match"):
        assess_signed_transfer(study, evaluator_key=signer.public_key())


def test_blindness_order_cannot_claim_b_revealed_before_a_finished():
    study, signer = _study()
    study["evaluated"]["statement"]["b_revealed_at"] = _time(1)
    _resign(study, signer)
    with pytest.raises(TransferEvidenceError, match="non-chronological"):
        assess_signed_transfer(study, evaluator_key=signer.public_key())


def test_training_and_b_families_cannot_be_same():
    study, signer = _study()
    study["sealed"]["statement"]["training_family"] = "windows-dependency"
    _resign(study, signer)
    with pytest.raises(TransferEvidenceError, match="families must differ"):
        assess_signed_transfer(study, evaluator_key=signer.public_key())


def test_missing_control_condition_fails_closed():
    study, signer = _study()
    study["evaluated"]["statement"]["results"] = [
        r for r in study["evaluated"]["statement"]["results"]
        if r["condition"] != "replay_only"
    ]
    _resign(study, signer)
    with pytest.raises(TransferEvidenceError, match="incomplete paired"):
        assess_signed_transfer(study, evaluator_key=signer.public_key())


def test_duplicate_signed_checker_receipt_rejected():
    study, signer = _study()
    trials = study["evaluated"]["statement"]["results"]
    trials[1]["checker_receipt_id"] = trials[0]["checker_receipt_id"]
    _resign(study, signer)
    with pytest.raises(TransferEvidenceError, match="duplicated checker"):
        assess_signed_transfer(study, evaluator_key=signer.public_key())


def test_small_holdout_cannot_pass_even_with_perfect_scores():
    study, signer = _study(count=4)
    with pytest.raises(TransferEvidenceError, match="too-small holdout"):
        assess_signed_transfer(study, evaluator_key=signer.public_key())


def test_forged_model_revision_or_training_metadata_breaks_signature():
    study, signer = _study()
    tampered = deepcopy(study)
    tampered["sealed"]["statement"]["revision"] = "0" * 40
    with pytest.raises(TransferEvidenceError, match="signature"):
        assess_signed_transfer(tampered, evaluator_key=signer.public_key())
