"""CA-1205: pinned multi-session source selection and privacy regressions."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from sofia.verify.v18_memory_dataset import FixtureError, evaluate, evaluate_file, main

pytestmark = pytest.mark.pkg_verify
DATA = Path(__file__).parent / "fixtures" / "v18-memory-multisession-v1.json"


def test_production_selector_runs_on_two_session_synthetic_fixtures():
    data = evaluate_file(DATA)
    assert data == evaluate_file(DATA)
    assert data["case_count"] == 3
    assert data["scores"]["production"]["wrong_scope"] == 0
    assert data["scores"]["no_retrieval"]["correct"] == 1
    assert data["gate4_proof"] is False
    assert data["model_answers_evaluated"] == 0
    assert all(case["sessions"] >= 2 for case in data["cases"])
    assert data["cases"][0]["excluded_source_count"] == 1
    assert "violet sensor inspection was completed" not in str(data)


def test_cli_emits_scored_ids_and_digest_without_original_text(tmp_path):
    destination = tmp_path / "score.json"
    assert main(["--fixture", str(DATA), "--output", str(destination)]) == 0
    report = json.loads(destination.read_text())
    assert report == evaluate_file(DATA)
    assert len(report["fixture_sha256"]) == 64
    assert "violet sensor inspection was completed" not in destination.read_text()


def test_private_wrong_scope_is_never_acceptable_ground_truth():
    dataset = json.loads(DATA.read_text())
    bad = deepcopy(dataset)
    bad["cases"][0]["required_source_ids"] = ["s3"]
    with pytest.raises(FixtureError, match="authorized"):
        evaluate(bad, digest="0" * 64)
    bad = deepcopy(dataset)
    bad["cases"][0]["messages"][0]["audience_id"] = "discord:shared"
    # Removing that permitted source also leaves only one authorized
    # session, so the multi-session precondition must fail first.
    with pytest.raises(FixtureError, match="authorized sessions"):
        evaluate(bad, digest="0" * 64)


def test_late_observations_and_private_dataset_are_rejected():
    dataset = json.loads(DATA.read_text())
    bad = deepcopy(dataset)
    bad["cases"][0]["messages"][0]["observed_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(FixtureError, match="future"):
        evaluate(bad, digest="0" * 64)
    bad = deepcopy(dataset)
    bad["data_class"] = "real_private_history"
    with pytest.raises(FixtureError, match="synthetic"):
        evaluate(bad, digest="0" * 64)


def test_duplicate_ids_and_single_session_do_not_pass():
    dataset = json.loads(DATA.read_text())
    bad = deepcopy(dataset)
    bad["cases"][0]["messages"][1]["id"] = "s1"
    with pytest.raises(FixtureError, match="unique"):
        evaluate(bad, digest="0" * 64)
    bad = deepcopy(dataset)
    for item in bad["cases"][0]["messages"]:
        item["session_id"] = "session:one"
    with pytest.raises(FixtureError, match="sessions"):
        evaluate(bad, digest="0" * 64)


def test_oversized_fixture_rejected_without_parsing(tmp_path):
    path = tmp_path / "oversize.json"
    path.write_bytes(b" " * (1_048_576 + 1))
    with pytest.raises(FixtureError, match="1 MiB"):
        evaluate_file(path)
