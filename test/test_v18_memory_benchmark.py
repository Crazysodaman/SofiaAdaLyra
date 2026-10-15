"""CA-1205 executable deterministic retrieval proxy cases."""
import json

import pytest
from sofia.verify.v18_memory_benchmark import (
    ABLATIONS, FAMILIES, evaluate, main, scenarios,
)

pytestmark = pytest.mark.pkg_verify


def test_benchmark_all_synthetic_cases_have_reproducible_source_licenses():
    data = scenarios()
    assert len(data) == 36
    assert len({x.case_id for x in data}) == 36
    assert {x.family for x in data} == set(FAMILIES)
    assert {x.task_kind for x in data} == {
        "abstention", "single_source", "multi_source", "updated_fact", "temporal",
    }
    for scenario in data:
        assert scenario.originals
        assert all(msg.session_id == scenario.originals[0].session_id
                   for msg in scenario.originals)
        assert scenario.expected_source_ids.issubset({
            msg.id for msg in scenario.originals
        })


def test_benchmark_real_selector_with_recent_only_ablations_is_honest():
    result = evaluate()
    assert result["schema"] == "sofia.v18-synthetic-retrieval-benchmark-v1"
    assert result["question_count"] == 36
    assert result["gate4_proof"] is False
    assert result["model_evaluations_performed"] == 0
    assert result["live_host_evaluations_performed"] == 0
    assert "no original benchmark samples" in result["dataset_provenance"]
    assert set(result["scores"]) == set(ABLATIONS)
    assert len(result["cases"]) == 36
    for name in ABLATIONS:
        row = result["scores"][name]
        assert row["samples"] == 36
        assert 0 <= row["correct"] <= 36
        assert 0 <= row["accuracy"] <= 1
        assert sum((row["correct"], *row["errors"].values())) == 36
    assert evaluate() == result


def test_benchmark_cli_writes_structured_cases_and_actual_scores(tmp_path):
    output = tmp_path / "memory-benchmark.json"
    assert main(["--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result == evaluate()
    assert all(result["by_family"][f][a]["samples"] == 12
               for f in FAMILIES for a in ABLATIONS)
