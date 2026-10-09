"""Batch 11 production domain and personality-after-truth contracts."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.v2 import (
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
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.personality.modulation import ExpressionModulation


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
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["direct"],'
        '"communication_style":"Clear and direct."}',
        encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=PROJECT_ROOT / "src/sofia/constitution/constitution.md",
        constitution_hash_path=(
            PROJECT_ROOT / "src/sofia/constitution/constitution.sha256"
        ),
        identity_path=PROJECT_ROOT / "src/sofia/identity/identity.json",
        personality_path=personality,
        avatar_path=PROJECT_ROOT / "src/sofia/embodiment/avatar.json",
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
