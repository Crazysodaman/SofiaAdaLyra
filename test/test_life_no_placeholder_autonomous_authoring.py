"""The production LIFE worker must never submit canned first artifacts.

Regression contracts are written for the final authorized test campaign.
Native adapters can still execute *explicit* approved Project Forge requests;
an installed serializer does not by itself authorize autonomous authorship.
"""
from datetime import timedelta

import pytest

from sofia.cognition.model import CognitiveResponse
from sofia.life import ProjectIdea
from test.test_life_project_forge import infrastructure, active_project


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_run, pytest.mark.pkg_interact]


def test_no_llm_draft_never_turns_project_brief_into_autonomous_artifact(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _ = active_project(life, now)
        result = life.tick(now=now + timedelta(seconds=3))
        assert result["selection"] == "project"
        assert result["draft_status"] == "model_generation_unavailable"
        assert result["scheduled"] == 0
        assert life.store.jobs(project.project_id) == ()
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_failed_model_draft_does_not_silently_fall_back_to_template(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        project, _ = active_project(life, now)
        result = life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda _request: CognitiveResponse(content="not JSON"),
        )
        assert result["draft_status"] == "failed_unverified"
        assert result["scheduled"] == 0
        assert life.store.jobs(project.project_id) == ()
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()


def test_native_art_serializer_is_not_automatically_an_art_author(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        evidence = life.record_observation(
            kind="interest",
            source="test:source-backed-art-interest",
            assertion="An optional illustration experiment is under consideration.",
            now=now,
        )
        idea = ProjectIdea(
            "idea:manual-art-intent", "Illustrated Violet Map",
            "Consider drawing an original set of hand-designed map symbols.",
            "illustrated-violet-map",
            ("Build several original illustrated map symbols.",),
            (), "art", (evidence,), 0.9, 0.85, now,
        )
        project = life.invent_project(idea)
        life.propose_project(
            project.project_id, reason="The project is an optional idea.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=1),
        )
        life.activate_project(
            project.project_id, reason="Active but no approved art authoring path exists.",
            evidence_refs=(evidence,), now=now + timedelta(seconds=2),
        )
        result = life.tick(
            now=now + timedelta(seconds=3),
            generate=lambda request: CognitiveResponse(content='{"content":"fake"}'),
        )
        assert result["draft_status"] == "approved_autonomous_authoring_unavailable"
        assert result["scheduled"] == 0
        assert life.store.jobs(project.project_id) == ()
        assert life.store.artifacts(project.project_id) == ()
    finally:
        life.close()
