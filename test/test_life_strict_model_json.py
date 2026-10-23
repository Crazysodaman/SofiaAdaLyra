"""CA-1207/CA-2307: one strict model-JSON boundary across LIFE callers."""
from datetime import datetime, timezone

import pytest

from sofia.core.cognition.model import CognitiveResponse
from sofia.core.cognition.strict_json import loads_strict_model_json
from sofia.core.creative.model import ArtifactKind
from sofia.core.life.outreach_agent import (
    ProjectOutreachChoiceAgent, ProjectOutreachChoiceError,
)
from sofia.core.life.idea_agent import ProjectIdeaAgent, ProjectIdeaGenerationError
from sofia.core.life.draft_agent import ProjectDraftAgent, ProjectDraftGenerationError
from test.test_life_project_forge import active_project, infrastructure

pytestmark = pytest.mark.pkg_core


@pytest.mark.parametrize("payload", (
    '{"share_now":true,"share_now":false}',
    '{"nested":{"key":"first","key":"second"}}',
    '{"value":NaN}',
    '{"value":Infinity}',
    '{"value":-Infinity}',
))
def test_model_json_rejects_ambiguous_or_nonstandard_payloads(payload):
    with pytest.raises(ValueError):
        loads_strict_model_json(payload)


def test_model_json_preserves_valid_nested_utf8_objects():
    assert loads_strict_model_json('{"title":"café","values":[null,true,1.25]}') == {
        "title": "café", "values": [None, True, 1.25],
    }


def test_outreach_choice_does_not_promote_duplicate_intent():
    model = ProjectOutreachChoiceAgent(
        lambda _request: CognitiveResponse(
            '{"share_now":false,"share_now":true,"tone":"warm","reason":"Maybe"}'
        ),
    )
    with pytest.raises(ProjectOutreachChoiceError, match="invalid outreach choice JSON"):
        model.choose(
            moment_kind="verified_completion", title="Private project",
            verified_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
            salience=0.7,
        )


def test_idea_generation_does_not_promote_duplicate_pursue(tmp_path):
    life, _, now = infrastructure(tmp_path)
    try:
        evidence = life.record_observation(
            kind="curiosity", source="test:private-idea",
            assertion="Observed an original private interest.", now=now,
        )
        interest = life.revise_interest(
            name="fiction", context="creative", strength=0.8,
            confidence=0.8, reason="Source-backed original idea.",
            evidence_refs=(evidence,), now=now,
        )
        output = (
            '{"name":"An Atlas","description":"Original fiction",'
            '"objectives":["Write prose"],"optional_success_criteria":[],'
            '"artifact_kind":"text","confidence":0.8,"curiosity":0.9,'
            '"pursue":false,"pursue":true,"reason":"Maybe"}'
        )
        agent = ProjectIdeaAgent(lambda _request: CognitiveResponse(output))
        with pytest.raises(ProjectIdeaGenerationError, match="valid JSON"):
            agent.suggest(
                interests=(interest,), experience_summaries=(), now=now,
            )
    finally:
        life.close()


def test_draft_generation_does_not_accept_duplicate_content(tmp_path):
    life, _, now = infrastructure(tmp_path)
    try:
        project, _ = active_project(life, now)
        draft = (
            '{"content":"A legitimate original story with enough words to be used",'
            '"content":"A different hidden rewrite with the same apparent key"}'
        )
        agent = ProjectDraftAgent(lambda _request: CognitiveResponse(draft))
        with pytest.raises(ProjectDraftGenerationError, match="not JSON"):
            agent.draft(project, ArtifactKind.TEXT)
    finally:
        life.close()
