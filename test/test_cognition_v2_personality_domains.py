"""Batch 11 production domain and personality-after-truth contracts."""
from datetime import datetime, timezone
from pathlib import Path
import os

import pytest

from sofia.platform.application import SofiaApplication
from sofia.core.cognition.v2 import (
    AnswerPlan,
    ClaimPlan,
    ConversationFocus,
    EpistemicState,
    MatrixV2Planner,
    PersonalityAfterTruthRenderer,
    TurnKernelInput,
    ValidatedAnswerDraft,
    merge_validated_drafts,
)
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.core.personality.modulation import ExpressionModulation


PROJECT_ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)


def _turn(content: str) -> TurnKernelInput:
    return TurnKernelInput(
        "turn:domain", "session:domain", content, NOW,
        "desktop", "sparks", "private:sparks",
    )


@pytest.mark.parametrize(("content", "domain", "intent"), (
    ("What time is it?", "environment", "environment_query"),
    ("What are you wearing?", "avatar", "avatar_query"),
    ("Do you remember the Docker incident?", "memory", "memory_query"),
    ("What's on your mind?", "memory", "reflection_query"),
    ("How are you feeling?", "emotion", "social_checkin"),
    ("May I hug you?", "interaction", "general_query"),
    ("How is our relationship?", "rel", "social_checkin"),
    ("Hello there", "social", "social"),
))
def test_remaining_domains_are_planned_by_v2(content, domain, intent):
    plan = MatrixV2Planner().plan(
        _turn(content),
        ConversationFocus("session:domain", "private:sparks", 1),
    )
    assert domain in plan.domains
    assert plan.intent == intent


@pytest.mark.parametrize("query", (
    "tell me anything you see observe i mean",
    "What do you actually observe around you?",
    "Can you tell me something you notice?",
))
def test_matrix_v2_routes_general_observation_queries_to_grounded_environment(query):
    plan = MatrixV2Planner().plan(
        _turn(query),
        ConversationFocus("session:domain", "private:sparks", 1),
    )
    assert plan.intent == "environment_query"
    assert "environment" in plan.domains
    assert any(need.predicate == "environment.current" for need in plan.evidence_needs)
    assert plan.action_requires_authority is False


def test_matrix_v2_does_not_turn_casual_i_see_into_a_sensor_request():
    plan = MatrixV2Planner().plan(
        _turn("I see what you mean"),
        ConversationFocus("session:domain", "private:sparks", 1),
    )
    assert "environment" not in plan.domains


@pytest.mark.parametrize(("query", "expected_domain"), (
    ("what time and date is it rn", "environment"),
    ("So what is your outfit rn?", "avatar"),
    ("What do you actually observe?", "environment"),
))
def test_run2_natural_questions_have_the_expected_cognitive_domain(
    query, expected_domain,
):
    plan = MatrixV2Planner().plan(
        _turn(query),
        ConversationFocus("session:domain", "private:sparks", 1),
    )
    assert expected_domain in plan.domains


def _modulation() -> ExpressionModulation:
    return ExpressionModulation(
        banter_intensity=0.5,
        technical_engagement=0.8,
        affection_openness=0.2,
        fluster_tendency=0.1,
        argumentative_energy=0.5,
        embodiment_expression_level=0.2,
        sofia_core_weight=0.25,
        kurisu_influence_weight=0.45,
        cortana_system_presence_weight=0.30,
        blend_context="operational",
        reasons=("matrix operational baseline",),
    )


def test_personality_renderer_runs_after_answer_plan_without_changing_truth():
    answer = AnswerPlan("turn:render", ())
    draft = ValidatedAnswerDraft(
        answer,
        "Observed Artemis — CPU utilization: 37.5%.",
        ("evidence:cpu",),
        "ops",
    )

    rendered = PersonalityAfterTruthRenderer().render(
        draft, expression_context=_modulation(),
    )

    assert "Artemis" in rendered.content
    assert "37.5%" in rendered.content
    assert rendered.evidence_refs == draft.evidence_refs
    assert rendered.tool_calls == ()


def test_multi_question_drafts_merge_without_dropping_validated_claims():
    plan = MatrixV2Planner().plan(
        _turn("What time is it, and what are you wearing?"),
        ConversationFocus("session:domain", "private:sparks", 1),
    )
    environment, avatar = plan.evidence_needs
    drafts = (
        ValidatedAnswerDraft(
            AnswerPlan(plan.turn_id, (ClaimPlan(
                f"claim:{environment.need_id}", environment.subject_id,
                environment.predicate, "10:00", EpistemicState.OBSERVED,
                ("evidence:time",),
            ),)),
            "It is 10:00.", ("evidence:time",), "environment",
        ),
        ValidatedAnswerDraft(
            AnswerPlan(plan.turn_id, (ClaimPlan(
                f"claim:{avatar.need_id}", avatar.subject_id,
                avatar.predicate, "blue hoodie", EpistemicState.KNOWN,
                ("evidence:outfit",),
            ),)),
            "I'm wearing a blue hoodie.", ("evidence:outfit",), "avatar",
        ),
    )

    merged = merge_validated_drafts(plan, drafts)

    assert merged is not None
    assert len(merged.answer.claims) == 2
    assert merged.answer.unknown_need_ids == ()
    assert "10:00" in merged.content and "blue hoodie" in merged.content
    assert merged.evidence_refs == ("evidence:time", "evidence:outfit")


def _configuration(tmp_path: Path) -> SofiaConfiguration:
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["direct"],'
        '"communication_style":"Clear and direct."}',
        encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=PROJECT_ROOT / "src/sofia/core/constitution/constitution.md",
        constitution_hash_path=(
            PROJECT_ROOT / "src/sofia/core/constitution/constitution.sha256"
        ),
        identity_path=PROJECT_ROOT / "src/sofia/core/identity/identity.json",
        personality_path=personality,
        avatar_path=PROJECT_ROOT / "src/sofia/core/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=PROJECT_ROOT,
    )


def test_environment_answer_uses_production_v2_evidence_then_personality(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    try:
        response = app.conversation.respond("What time is it?")
        plan = app.conversation.cognitive_plan
        evidence_id = next(
            value for value in response.evidence_refs
            if value.startswith("evidence:")
        )
        atom = app.cognitive_evidence.get(evidence_id)

        assert plan is not None and plan.intent == "environment_query"
        assert atom is not None
        assert atom.predicate == "environment.current"
        assert atom.source_id == "environment:service"
        assert any(prefix in response.content for prefix in (
            "Grounded answer:", "Here’s what I can actually support:",
            "The honest read:",
        ))
    finally:
        app.shutdown()


def test_production_multi_question_combines_environment_and_avatar_evidence(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    try:
        response = app.conversation.respond(
            "What time is it, and what are you wearing?"
        )
        atoms = tuple(
            app.cognitive_evidence.get(value)
            for value in response.evidence_refs
            if value.startswith("evidence:")
        )

        assert {atom.predicate for atom in atoms if atom is not None} == {
            "environment.current", "avatar.canonical",
        }, (response, app.conversation.cognitive_plan)
        assert "Still unresolved" not in response.content
    finally:
        app.shutdown()


def test_run2_owner_natural_utterances_reach_authoritative_production_resolvers(tmp_path):
    """Replay the actual user phrases through application turn coordination."""
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    try:
        clock = app.conversation.respond("what time and date is it rn")
        assert "current date and time" in clock.content
        assert "I think" not in clock.content

        outfit = app.conversation.respond("So what is your outfit rn?")
        assert "I'm in my " in outfit.content
        assert "outfit" in outfit.content
        assert "floral" not in outfit.content.casefold()

        observed = app.conversation.respond(
            "tell me anything you see observe i mean"
        )
        assert "From my runtime clock" in observed.content
        assert "no verified visual/room observation" in observed.content
        assert "airflow" in observed.content

        history = app.conversation.respond("what was your last runtime")
        assert "This runtime started at" in history.content
        assert "no verified previous runtime timestamp" in history.content
        assert "don't have a clock" not in history.content

        retry = app.conversation.respond("Check weather again")
        assert "weather" in retry.content.casefold()
        assert "influence my delivery" not in retry.content.casefold()
    finally:
        app.shutdown()


def test_run2_current_runtime_and_pid_are_grounded_in_process_and_core_state(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    try:
        current = app.runtime.operational_state
        assert current is not None

        for query in (
            "current runtime",
            "YOUR process ID",
            "Wrong answer I am looking for the current runtime start time/date along with process ID",
        ):
            answer = app.conversation.respond(query)
            assert current.started_at.isoformat() in answer.content, (query, answer)
            assert str(current.runtime_id) in answer.content, (query, answer)
            assert f"PID {os.getpid()}" in answer.content, (query, answer)
            assert "no malware" not in answer.content.casefold(), (query, answer)

        both = app.conversation.respond("Current runtime? last runtime?")
        assert current.started_at.isoformat() in both.content
        assert f"PID {os.getpid()}" in both.content
        assert "previous" in both.content.casefold()

        prior = app.conversation.respond("when were you running before?")
        assert "previous runtime" in prior.content.casefold()
        assert "always here" not in prior.content.casefold()
    finally:
        app.shutdown()


def test_run2_followup_outfit_paraphrases_preserve_canonical_evidence(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    try:
        for query in ("so what you got on today?", "so what've you got on today?"):
            answer = app.conversation.respond(query)
            assert "outfit" in answer.content.casefold(), (query, answer)
            assert "floral" not in answer.content.casefold(), (query, answer)
            assert any(ref.startswith("evidence:") for ref in answer.evidence_refs), (
                query, answer,
            )

        answer = app.conversation.respond("What time is it and the day")
        observed = app.runtime._environment_service.snapshot(
            refresh_providers=False,
        )
        local_date = (observed.user_local_time or observed.host_local_time).date()
        assert "current date and time" in answer.content
        assert local_date.isoformat() in answer.content
    finally:
        app.shutdown()


def test_reviewed_memory_absence_is_v2_unknown_not_model_invention(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    try:
        response = app.conversation.respond(
            "Do you remember the cobalt lighthouse incident?"
        )
        evidence_id = next(
            value for value in response.evidence_refs
            if value.startswith("evidence:")
        )
        atom = app.cognitive_evidence.get(evidence_id)

        assert atom is not None
        assert atom.predicate == "memory.retrieval"
        assert atom.epistemic_state.value == "unknown"
        assert "won't invent a memory" in response.content
        assert not response.content.startswith((
            "Grounded answer:", "Here’s what I can actually support:",
            "The honest read:",
        ))
    finally:
        app.shutdown()


def test_secondary_channel_uses_same_v2_personality_after_truth_path(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    try:
        channel = app.open_channel_conversation()
        response = channel.respond("What time is it?")

        assert channel.cognitive_plan is not None
        assert channel.cognitive_plan.intent == "environment_query"
        assert any(
            value.startswith("evidence:") for value in response.evidence_refs
        )
        assert any(prefix in response.content for prefix in (
            "Grounded answer:", "Here’s what I can actually support:",
            "The honest read:",
        ))
    finally:
        app.shutdown()
