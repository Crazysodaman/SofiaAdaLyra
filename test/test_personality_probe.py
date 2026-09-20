"""Batch G4: offline observation harness tests; no Ollama calls."""
import pytest

from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import CognitiveResponse
from sofia.personality.model import PersonalityProfile
from sofia.personality.probe import (
    PersonalityProbeCase,
    observe_personality_cases,
)


class RecordingEngine(CognitiveEngine):
    def __init__(self, responses):
        self.requests = []
        self.responses = list(responses)

    def respond(self, request):
        self.requests.append(request)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_observations_preserve_raw_text_and_personality_context():
    engine = RecordingEngine([CognitiveResponse(content="I am a generic assistant.")])
    profile = PersonalityProfile(name="Sofía", traits=("playful", "rigorous"))
    (observation,) = observe_personality_cases(profile, engine, (
        PersonalityProbeCase("identity", "Who are you?"),
    ), max_cases=1)
    assert observation.succeeded
    assert observation.raw_response == "I am a generic assistant."
    assert observation.error_type is None
    assert len(observation.request_sha256) == 64
    assert observation.elapsed_seconds >= 0
    assert "Traits: playful, rigorous" in engine.requests[0].messages[0].content
    assert engine.requests[0].messages[-1].content == "Who are you?"
    # The harness does not pretend that this generic response passed fidelity.
    assert not hasattr(observation, "personality_score")


def test_each_case_retains_errors_without_erasing_other_responses():
    engine = RecordingEngine([RuntimeError("provider unavailable"), CognitiveResponse(content="Hi")])
    observations = observe_personality_cases(PersonalityProfile(name="Sofía"), engine, (
        PersonalityProbeCase("first", "Question one"),
        PersonalityProbeCase("second", "Question two"),
    ), max_cases=2)
    assert len(observations) == 2
    assert observations[0].raw_response is None
    assert observations[0].error_type == "RuntimeError"
    assert observations[0].error_message == "provider unavailable"
    assert observations[1].raw_response == "Hi"
    assert observations[1].succeeded


def test_case_limit_and_duplicate_labels_fail_before_generation():
    engine = RecordingEngine([])
    profile = PersonalityProfile(name="Sofía")
    case = PersonalityProbeCase("identity", "Who are you?")
    with pytest.raises(ValueError, match="exceeds max_cases"):
        observe_personality_cases(profile, engine, (case, case), max_cases=1)
    with pytest.raises(ValueError, match="unique"):
        observe_personality_cases(profile, engine, (case, case), max_cases=2)
    assert engine.requests == []


@pytest.mark.parametrize("limit", [0, -1, True, "2"])
def test_invalid_case_limit_rejected(limit):
    with pytest.raises(ValueError, match="max_cases"):
        observe_personality_cases(PersonalityProfile(name="Sofía"), RecordingEngine([]),
                                  (PersonalityProbeCase("x", "Hi"),), max_cases=limit)


def test_request_digest_is_repeatable_for_same_input():
    profile = PersonalityProfile(name="Sofía", traits=("direct",))
    case = (PersonalityProbeCase("identity", "Who are you?"),)
    first = observe_personality_cases(profile, RecordingEngine([CognitiveResponse(content="One")]),
                                      case, max_cases=1)
    second = observe_personality_cases(profile, RecordingEngine([CognitiveResponse(content="Two")]),
                                       case, max_cases=1)
    assert first[0].request_sha256 == second[0].request_sha256
    assert first[0].raw_response != second[0].raw_response


def test_engine_invalid_response_is_recorded_as_failure():
    result = observe_personality_cases(PersonalityProfile(name="Sofía"),
        RecordingEngine([object()]), (PersonalityProbeCase("x", "Hello"),), max_cases=1)
    assert result[0].error_type == "TypeError"
    assert result[0].raw_response is None
