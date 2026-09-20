"""G5-G8: full-context provider-boundary mechanics only, no live model."""

import pytest

from sofia.cognition.context import CognitiveContext
from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.personality.evaluation import PersonalityScenario, observe_full_context
from sofia.identity.model import SofiaIdentity
from sofia.personality.model import PersonalityProfile
from sofia.personality.review import PersonalityReview, ReviewFinding


class FakeEngine(CognitiveEngine):
    def __init__(self, *responses):
        self.calls = []
        self.responses = list(responses)

    def respond(self, request):
        self.calls.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def scenario(label="identity", user="Who are you?"):
    profile = PersonalityProfile(name="Sofía", traits=("rigorous", "playful"))
    return PersonalityScenario(label, CognitiveContext(
        request=CognitiveRequest(messages=(CognitiveMessage(CognitiveRole.USER, user),)),
        personality=profile,
    ))


def test_raw_generic_answer_is_not_silently_rewritten_or_graded():
    engine = FakeEngine(CognitiveResponse(content="I am a generic AI assistant."))
    (obs,) = observe_full_context(engine, (scenario(),), max_cases=1)
    assert obs.response == "I am a generic AI assistant."
    assert obs.error_type is None
    assert len(obs.request_sha256) == 64
    assert engine.calls[0].messages[-1].content == "Who are you?"
    assert "Traits: rigorous, playful" in engine.calls[0].messages[0].content
    assert not hasattr(obs, "personality_score")


def test_duplicate_and_case_limit_refused_before_provider_calls():
    engine = FakeEngine()
    with pytest.raises(ValueError, match="max_cases"):
        observe_full_context(engine, (scenario(), scenario("other")), max_cases=1)
    with pytest.raises(ValueError, match="unique"):
        observe_full_context(engine, (scenario(), scenario()), max_cases=2)
    assert engine.calls == []


def test_missing_personality_or_missing_final_user_rejected():
    with pytest.raises(ValueError, match="personality"):
        PersonalityScenario("x", CognitiveContext(request=CognitiveRequest(messages=(
            CognitiveMessage(CognitiveRole.USER, "Hello"),
        ))))
    with pytest.raises(ValueError, match="user"):
        PersonalityScenario("x", CognitiveContext(request=CognitiveRequest(messages=(
            CognitiveMessage(CognitiveRole.ASSISTANT, "Hello"),
        )), personality=PersonalityProfile(name="Sofía")))


def test_errors_retained_and_second_case_still_recorded():
    engine = FakeEngine(RuntimeError("provider unavailable"), CognitiveResponse(content="Second"))
    obs = observe_full_context(engine, (scenario(), scenario("second", "Next")), max_cases=2)
    assert obs[0].error_type == "RuntimeError"
    assert obs[0].response is None
    assert obs[1].response == "Second"
    assert obs[0].elapsed_seconds >= 0


def test_human_review_is_attributed_and_preserves_observation():
    engine = FakeEngine(CognitiveResponse(content="I am a generic AI assistant."))
    (obs,) = observe_full_context(engine, (scenario(),), max_cases=1)
    review = PersonalityReview(obs, "human-reviewer", (
        ("canonical identity", ReviewFinding.NOT_SUPPORTED,
         "Response did not use the supplied identity."),
        ("real-world actions", ReviewFinding.UNCERTAIN,
         "No action was requested in this scenario."),
    ))
    assert review.observation is obs
    assert review.findings[0][1] is ReviewFinding.NOT_SUPPORTED
    assert not hasattr(review, "score")
    with pytest.raises(ValueError, match="unique"):
        PersonalityReview(obs, "human-reviewer", (
            ("identity", ReviewFinding.NOT_SUPPORTED, "No name."),
            ("identity", ReviewFinding.SUPPORTED, "Duplicate."),
        ))


def test_full_context_identity_stays_separate_from_style_and_user_text():
    source = scenario()
    context = CognitiveContext(
        request=source.context.request,
        personality=source.context.personality,
        identity=SofiaIdentity(name="Sofía Ada Lyra"),
    )
    engine = FakeEngine(CognitiveResponse(content="Sofía Ada Lyra."))
    (observation,) = observe_full_context(
        engine, (PersonalityScenario("canonical-identity", context),), max_cases=1,
    )
    assert observation.response == "Sofía Ada Lyra."
    system_message = engine.calls[0].messages[0].content
    assert "IDENTITY RECORD METADATA" in system_message
    assert "Name: Sofía Ada Lyra" in system_message
    assert "PERSONALITY" in system_message
