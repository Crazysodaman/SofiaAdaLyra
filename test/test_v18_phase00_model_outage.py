"""CA-1207: production LIFE background idea isolation without grant bypass."""
from datetime import datetime, timezone

import pytest

from sofia.application.background_runtime import (
    _consider_life_idea_without_wedging_worker,
)
from sofia.cognition.engine import CognitiveEngineError
from sofia.life.idea_agent import ProjectIdeaGenerationError

pytestmark = pytest.mark.pkg_core
NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)


class IdeaFixture:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def consider_new_project(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


@pytest.mark.parametrize("failure", (
    CognitiveEngineError("Ollama model unavailable"),
    ProjectIdeaGenerationError("malformed untrusted JSON"),
))
def test_known_model_idea_failure_declines_without_worker_failure(failure, caplog):
    fixture = IdeaFixture(failure)
    result = _consider_life_idea_without_wedging_worker(
        fixture, generate=lambda _: None, now=NOW,
        busy=False, resource_pressure=0.0,
    )
    assert result is None
    assert len(fixture.calls) == 1
    assert fixture.calls[0]["now"] == NOW
    assert "Optional LIFE idea skipped" in caplog.text
    # The raw model response, payload, or private prompt must not be logged.
    assert str(failure) not in caplog.text


def test_successful_idea_keeps_exact_existing_admission_result():
    project = object()
    fixture = IdeaFixture(project)
    assert _consider_life_idea_without_wedging_worker(
        fixture, generate=lambda _: None, now=NOW,
        busy=False, resource_pressure=0.2,
    ) is project


@pytest.mark.parametrize("unexpected", (
    PermissionError("operator approval denied"),
    RuntimeError("database state inconsistent"),
))
def test_background_idea_guard_does_not_hide_authority_or_state_errors(unexpected):
    fixture = IdeaFixture(unexpected)
    with pytest.raises(type(unexpected)):
        _consider_life_idea_without_wedging_worker(
            fixture, generate=lambda _: None, now=NOW,
            busy=False, resource_pressure=0.0,
        )


def test_production_life_background_calls_guard_before_durable_tick():
    from inspect import getsource
    from sofia.application.background_runtime import create_background_coordinator
    source = getsource(create_background_coordinator)
    assert "project = _consider_life_idea_without_wedging_worker(" in source
    assert "result = life.tick(" in source
    assert source.index("project = _consider_life_idea_without_wedging_worker(") < source.index("result = life.tick(")
