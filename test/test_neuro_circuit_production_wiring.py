"""Source-only Workstream 4 NEURO integration contracts. Do not run until VERIFY."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.neuro import NeuralSignal, NeuroRuntime
from sofia.neuro.connectome.competition import CircuitCompetition, CompetitionResult
from sofia.neuro.store import NeuroObservabilityStore


pytestmark = pytest.mark.pkg_core
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


class DeliberatelyContraryCompetition(CircuitCompetition):
    def run(self, inputs, *, iterations=6):
        ordered = tuple((key, value) for key, value in reversed(tuple(inputs.items())))
        return CompetitionResult(ordered, ordered[0][0], iterations)


class InvalidCompetition(CircuitCompetition):
    def run(self, inputs, *, iterations=6):
        raise ValueError("invalid engineered activation")


def signal(source, value):
    return NeuralSignal(source=source, kind="diagnostic",
                        value=value, confidence=0.7, novelty=0.7,
                        urgency=0.7, observed_at=NOW)


def test_circuit_is_in_single_runtime_path_and_observable(tmp_path):
    runtime = NeuroRuntime(competition=DeliberatelyContraryCompetition(),
                           observability=NeuroObservabilityStore(tmp_path / "sofia.db"))
    runtime.observe_signal(signal("a", 0.70))
    snap = runtime.observe_signal(signal("b", 0.68))
    assert snap.focus.key == "diagnostic:b"
    assert snap.selection_method == CircuitCompetition.ALGORITHM_VERSION
    saved = runtime._observability.current()["snapshot"]
    assert saved["selection_method"] == snap.selection_method
    assert "selected=diagnostic:b" in saved["selection_reason"]
    assert "baseline=diagnostic:a" in saved["selection_reason"]
    assert "NOT evidence" in snap.prompt()


def test_expired_signal_can_never_be_restored_by_competition():
    runtime = NeuroRuntime(competition=DeliberatelyContraryCompetition())
    runtime.observe_signal(signal("a", 0.7))
    assert runtime.snapshot(now=NOW + timedelta(seconds=301)).focus is None


def test_invalid_circuit_falls_back_and_disable_restores_baseline():
    runtime = NeuroRuntime(competition=InvalidCompetition())
    runtime.observe_signal(signal("a", 0.7))
    snap = runtime.observe_signal(signal("b", 0.68))
    assert snap.focus.key == "diagnostic:a"
    assert snap.selection_method == "salience-v1"
    assert runtime.last_competition_error == "ValueError"
    runtime.set_competition_enabled(False)
    assert runtime.snapshot(now=NOW).focus.key == "diagnostic:a"


def test_nonfinite_neural_input_is_rejected_not_promoted():
    with pytest.raises(ValueError, match="0..1"):
        signal("bad", float("nan"))


class UnexpectedBackendFailure(CircuitCompetition):
    def run(self, inputs, *, iterations=6):
        raise RuntimeError("experimental circuit backend unavailable")


def test_unexpected_circuit_backend_error_also_falls_back_without_losing_turn():
    runtime = NeuroRuntime(competition=UnexpectedBackendFailure())
    runtime.observe_signal(signal("a", 0.7))
    snapshot = runtime.observe_signal(signal("b", 0.68))
    assert snapshot.focus.key == "diagnostic:a"
    assert snapshot.selection_method == "salience-v1"
    assert runtime.last_competition_error == "RuntimeError"


def test_current_turn_focus_outranks_engineered_circuit_without_faking_evidence():
    runtime = NeuroRuntime(competition=DeliberatelyContraryCompetition())
    turn = runtime.observe_turn(
        content="This is my new question", created_at=NOW, channel="desktop", turn=None,
    )
    assert turn.focus is not None
    assert turn.focus.kind == "foreground"
    after = runtime.observe_signal(signal("background", 0.15))
    assert after.focus.key == turn.focus.key
    assert after.selection_method == CircuitCompetition.ALGORITHM_VERSION
    assert "current-turn precedence" in after.selection_reason
    assert f"selected={turn.focus.key}" in after.selection_reason


def test_malformed_duplicate_circuit_channels_fall_back_to_baseline():
    class DuplicateCircuit(CircuitCompetition):
        def run(self, inputs, *, iterations=6):
            key = next(iter(inputs))
            return CompetitionResult(((key, .95), (key, .90)), key, iterations)
    runtime = NeuroRuntime(competition=DuplicateCircuit())
    runtime.observe_signal(signal("a", 0.70))
    after = runtime.observe_signal(signal("b", 0.68))
    assert after.selection_method == "salience-v1"
    assert after.focus.key == "diagnostic:a"
    assert runtime.last_competition_error == "ValueError"


def test_new_user_subject_wins_over_higher_aged_nonconversational_signal():
    runtime = NeuroRuntime()
    previous = NeuralSignal(
        source="old-ongoing-goal", kind="goal",
        value=1.0, confidence=1.0, novelty=1.0, urgency=1.0,
        observed_at=NOW, ttl_seconds=600.0,
    )
    runtime.observe_signal(previous)
    redirected = runtime.observe_turn(
        content="Correction: switch to troubleshooting the NAS instead.",
        created_at=NOW + timedelta(seconds=1),
        channel="desktop",
        turn=None,
    )
    assert redirected.focus is not None
    assert redirected.focus.kind == "foreground"
    assert any(
        activation.key == "goal:old-ongoing-goal"
        for activation in redirected.secondary
    )
    assert "current-turn precedence" in redirected.selection_reason

    switched_again = runtime.observe_turn(
        content="New topic: hexapod foot kinematics.",
        created_at=NOW + timedelta(seconds=2),
        channel="discord",
        turn=None,
    )
    assert switched_again.focus is not None
    assert switched_again.focus.kind == "foreground"
    assert "conversation:discord" in switched_again.focus.key
    assert all(
        activation.key != redirected.focus.key
        for activation in switched_again.secondary
    )
