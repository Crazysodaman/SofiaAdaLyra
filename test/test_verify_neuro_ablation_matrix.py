"""Four-way real production NEURO/MEM ablation VERIFY, deferred execution."""
import pytest

from sofia.verify.neuro_ablation import run_neuro_ablation

pytestmark = pytest.mark.pkg_verify


def test_four_way_experiment_uses_same_eligible_memory_population():
    result=run_neuro_ablation(rounds=2,code_revision="fixture:unverified")
    conditions=result["trials"]
    assert [row["condition"] for row in conditions]==[
        "deterministic","competition","association","both",
    ]
    assert all(row["trials"]==2 for row in conditions)
    assert all(row["forbidden_memory_count"]==0 for row in conditions)
    assert all(row["topic_switch_errors"]==0 for row in conditions)
    assert all(row["observed_model_calls"]==0 for row in conditions)
    assert conditions[0]["precision_at_one"] <= conditions[2]["precision_at_one"]
    assert conditions[1]["precision_at_one"] <= conditions[3]["precision_at_one"]
    assert "No model wakeups measured" in result["scientific_claim"]
    assert result["host_gpu_vram_joules"] is None


@pytest.mark.parametrize("rounds",[0,501,True])
def test_ablation_rejects_unbounded_work(rounds):
    with pytest.raises(ValueError,match="rounds"):
        run_neuro_ablation(rounds=rounds)


def test_unsupported_revision_identifier_rejected():
    with pytest.raises(ValueError,match="code revision"):
        run_neuro_ablation(rounds=1,code_revision=" ")
