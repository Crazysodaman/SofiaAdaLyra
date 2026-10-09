"""The Batch 1 benchmark reports unavailable metrics honestly."""

from sofia.verify.cognition_v2_baseline import capture_baseline


def test_cognition_v2_control_path_baseline_is_measured_without_fake_metrics():
    baseline = capture_baseline()

    assert baseline["schema"] == "sofia.cognition-v2.baseline-v1"
    assert baseline["environment"]["provider"] == "test"
    assert baseline["startup"]["wall_ms"] >= 0
    assert set(baseline["scenarios"]) == {
        "casual_conversation",
        "technical_question",
        "fleet_status_request",
        "multi_turn_followup",
    }
    assert baseline["database"]["conversation_messages"] == 8
    assert baseline["database"]["matrix_traces"] == 4
    assert baseline["efficiency"]["sqlite_queries"] > 0
    assert baseline["efficiency"]["sqlite_writes"] > 0
    assert baseline["efficiency"]["cache_hits"] >= 0
    assert "sqlite_operation_count" not in baseline["unavailable"]
    assert "live primary model was not invoked" in (
        baseline["unavailable"]["primary_model_inference"]
    )
    assert "no portable production VRAM observer" in (
        baseline["unavailable"]["vram_bytes"]
    )
