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
    assert "eligible-signal competition" in saved["selection_reason"]
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
