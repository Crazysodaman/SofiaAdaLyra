"""Regression tests for the effect-free Generalization -> ML shared evaluator."""
import pytest

from sofia.modules.transfer_evidence import review_transfer_trial

GOOD = {
    "id": "transfer:1",
    "baseline_successes": 6,
    "candidate_successes": 9,
    "trial_count": 10,
    "novel_task": True,
    "independent_holdout": True,
}


def test_positive_transfer_is_still_unverified_evidence():
    result = review_transfer_trial(GOOD)
    assert result == {
        "id": "transfer:1",
        "delta_success_rate": 0.3,
        "finding": "candidate_transfer_evidence",
        "generalized_intelligence_verified": False,
    }


def test_nonindependent_trial_is_not_promotion():
    result = review_transfer_trial(GOOD | {"independent_holdout": False})
    assert result["finding"] == "not_independent_transfer"
    assert result["generalized_intelligence_verified"] is False


@pytest.mark.parametrize("mutation", [
    {"execute": True},
    {"id": "../bad"},
    {"trial_count": 0},
    {"trial_count": True},
    {"baseline_successes": 11},
    {"candidate_successes": -1},
    {"novel_task": 1},
    {"independent_holdout": "true"},
])
def test_invalid_untrusted_trials_fail_closed(mutation):
    with pytest.raises(ValueError):
        review_transfer_trial(GOOD | mutation)


def test_bounded_exact_row_and_negative_delta():
    result = review_transfer_trial(GOOD | {
        "baseline_successes": 9, "candidate_successes": 6,
    })
    assert result["delta_success_rate"] == -0.3
    assert review_transfer_trial(GOOD) == review_transfer_trial(dict(GOOD))
