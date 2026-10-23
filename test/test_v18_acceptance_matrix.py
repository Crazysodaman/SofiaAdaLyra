"""CA-1206: every acceptance axis combination is planned, never pretended."""
import pytest

from sofia.platform.verify.v18_acceptance_matrix import (
    AXES, EXPECTED_COUNT, acceptance_plan,
)

pytestmark = pytest.mark.pkg_verify


def test_acceptance_matrix_covers_all_axes_and_is_not_fake_acceptance():
    report = acceptance_plan()
    assert report["total"] == EXPECTED_COUNT == 34560
    assert report["states"] == {"not_executed": EXPECTED_COUNT}
    assert not report["production_accepted"]
    assert report["no_implicit_authority"]
    assert len({case["id"] for case in report["cases"]}) == EXPECTED_COUNT
    names = {name for name, _ in AXES}
    for row in report["cases"]:
        assert set(row["selectors"]) == names
        assert row["status"] == "not_executed"
        assert row["runtime_result"] is None
        assert row["test_run_ref"] is None
        assert row["host_receipt"] is None
    assert len(report["safety_examples"]) == 6
    assert all(not item["tested"] and item["observed_outcome"] is None
               for item in report["safety_examples"])


def test_every_pair_of_axes_is_exercised_across_complete_product():
    report = acceptance_plan()
    for index, (left, left_values) in enumerate(AXES):
        for right, right_values in AXES[index + 1:]:
            pairs = {
                (case["selectors"][left], case["selectors"][right])
                for case in report["cases"]
            }
            assert len(pairs) == len(left_values) * len(right_values)


def test_case_ids_are_stable_across_identical_plans():
    first = acceptance_plan()
    second = acceptance_plan()
    assert [x["id"] for x in first["cases"]] == [
        x["id"] for x in second["cases"]
    ]
