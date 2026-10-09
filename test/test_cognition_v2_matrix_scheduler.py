"""Matrix v2 and scheduler authority, evidence, and budget regressions."""
from datetime import datetime, timezone
from pathlib import Path

from sofia.application import SofiaApplication
from sofia.cognition.v2 import (
    ActionRequirement,
    ConversationFocus,
    EvidenceNeed,
    FocusReference,
    MatrixV2Planner,
    ReasoningRequirement,
    TurnKernelInput,
    ValidatedCognitiveScheduler,
)
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.neuro import HomeostaticState, NeuralActivation, NeuroStateSnapshot


PROJECT_ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)


def _turn(content: str) -> TurnKernelInput:
    return TurnKernelInput(
        turn_id="turn:matrix-v2",
        session_id="session:matrix-v2",
        content=content,
        created_at=NOW,
        channel="desktop",
        principal_id="sparks",
        audience_id="private:sparks",
    )


def _focus(*, artemis: bool = False, pending: bool = False):
    if not artemis:
        return ConversationFocus("session:matrix-v2", "private:sparks", 1)
    reference = FocusReference(
        reference_id="reference:fleet-node-artemis",
        subject_id="fleet-node:artemis",
        kind="fleet-node",
        source_turn_id="turn:prior",
        confidence=1.0,
        aliases=("Artemis",),
    )
    return ConversationFocus(
        "session:matrix-v2",
        "private:sparks",
        1,
        primary_reference=reference,
        references=(reference,),
    )


def _multi_focus() -> ConversationFocus:
    references = (
        FocusReference(
            "reference:artemis", "fleet-node:artemis", "fleet-node",
            "turn:matrix-v2", 1.0, aliases=("Artemis",),
        ),
        FocusReference(
            "reference:venus", "fleet-node:venus", "fleet-node",
            "turn:matrix-v2", 1.0, aliases=("Venus",),
        ),
    )
    return ConversationFocus(
        "session:matrix-v2", "private:sparks", 1,
        primary_reference=references[0], references=references,
    )


def _snapshot(*, kind="ops", score=0.9, load=0.2, pressure=0.2):
    activation = NeuralActivation(
        key=f"{kind}:signal",
        source="test:trusted",
        kind=kind,
        score=score,
        novelty=0.5,
        updated_at=NOW,
    )
    return NeuroStateSnapshot(
        generated_at=NOW,
        focus=activation,
        homeostasis=HomeostaticState(
            cognitive_load=load,
            novelty_load=0.4,
            competition_pressure=pressure,
        ),
        active_signal_count=1,
    )


def test_matrix_v2_uses_structured_focus_for_elliptical_operational_query():
    plan = MatrixV2Planner().plan(
        _turn("Could you give me the figures?"),
        _focus(artemis=True),
    )

    assert plan.intent == "operational_query"
    assert {"machine", "ops"} <= set(plan.domains)
    assert {need.subject_id for need in plan.evidence_needs} == {
        "fleet-node:artemis"
    }
    assert plan.reasoning_requirement is ReasoningRequirement.DEEP
    assert plan.action_requirement is ActionRequirement.NONE


def test_matrix_v2_mutation_requires_authority_and_verify_but_grants_nothing():
    plan = MatrixV2Planner().plan(
        _turn("Restart Docker on Artemis."),
        _focus(artemis=True),
    )

    assert plan.action_requirement is ActionRequirement.MUTATION
    assert plan.action_requires_authority is True
    assert plan.reasoning_requirement is ReasoningRequirement.VERIFY
    assert not hasattr(plan, "permission_grant")
    assert not hasattr(plan, "execution_receipt")


def test_matrix_v2_environment_plan_is_subject_scoped_and_deterministic():
    plan = MatrixV2Planner().plan(
        _turn("How chilly is it outside?"),
        _focus(),
    )

    assert plan.intent == "environment_query"
    assert plan.domains == ("environment",)
    assert plan.evidence_needs[0].subject_id == "runtime:environment"
    assert plan.evidence_needs[0].scope_id == "private:sparks"
    assert plan.reasoning_requirement is ReasoningRequirement.DETERMINISTIC


def test_matrix_v2_plans_every_requested_machine_property():
    plan = MatrixV2Planner().plan(
        _turn("What are Artemis CPU, GPU, RAM, disk, and CPU utilization?"),
        _focus(artemis=True),
    )

    assert {(need.subject_id, need.predicate) for need in plan.evidence_needs} == {
        ("fleet-node:artemis", "machine.cpu"),
        ("fleet-node:artemis", "machine.gpu"),
        ("fleet-node:artemis", "machine.memory_bytes"),
        ("fleet-node:artemis", "machine.storage"),
        ("fleet-node:artemis", "ops.cpu_percent"),
    }


def test_matrix_v2_comparison_preserves_every_subject_predicate_pair():
    plan = MatrixV2Planner().plan(
        _turn("Compare CPU and RAM between Artemis and Venus."),
        _multi_focus(),
    )

    assert {(need.subject_id, need.predicate) for need in plan.evidence_needs} == {
        (subject, predicate)
        for subject in ("fleet-node:artemis", "fleet-node:venus")
        for predicate in ("machine.cpu", "machine.memory_bytes")
    }


def test_matrix_v2_interleaved_properties_do_not_cross_attribute_hosts():
    plan = MatrixV2Planner().plan(
        _turn("What are Artemis CPU and Venus RAM?"),
        _multi_focus(),
    )

    assert {(need.subject_id, need.predicate) for need in plan.evidence_needs} == {
        ("fleet-node:artemis", "machine.cpu"),
        ("fleet-node:venus", "machine.memory_bytes"),
    }


def test_neuro_can_promote_budget_but_cannot_add_evidence_or_downgrade_verify():
    planner = MatrixV2Planner()
    focus = _focus(artemis=True)
    without_neuro = planner.plan(_turn("What is happening?"), focus)
    with_neuro = planner.plan(
        _turn("What is happening?"),
        focus,
        neuro_snapshot=_snapshot(),
    )
    verified = planner.plan(
        _turn("Verify and restart Docker."),
        focus,
        neuro_snapshot=_snapshot(load=0.95, pressure=0.95),
    )

    assert with_neuro.reasoning_requirement is ReasoningRequirement.DEEP
    assert with_neuro.evidence_needs == without_neuro.evidence_needs
    assert verified.reasoning_requirement is ReasoningRequirement.VERIFY
    assert verified.budget.allow_parallelism is False
    assert verified.budget.retrieval_limit < 10


def test_scheduler_parallelizes_only_independent_evidence_tasks():
    scheduler = ValidatedCognitiveScheduler()
    reasoning, budget = scheduler.budget(ReasoningRequirement.DEEP)
    needs = (
        EvidenceNeed(
            "need:cpu", "fleet-node:artemis", "machine.cpu",
            "private:sparks",
        ),
        EvidenceNeed(
            "need:memory", "fleet-node:artemis", "machine.memory",
            "private:sparks",
        ),
    )
    schedule = scheduler.schedule(
        turn_id="turn:schedule",
        evidence_needs=needs,
        reasoning_requirement=reasoning,
        response_strategy="tool-assisted",
        budget=budget,
    )

    assert schedule.parallel_groups == (("evidence:1", "evidence:2"),)
    reasoning_task = next(
        task for task in schedule.tasks if task.task_id == "reason:answer"
    )
    assert set(reasoning_task.depends_on) == {"evidence:1", "evidence:2"}
    assert schedule.tasks[-1].depends_on == ("validate:claims",)


def _configuration(tmp_path: Path) -> SofiaConfiguration:
    personality_path = tmp_path / "personality.json"
    personality_path.write_text(
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
        personality_path=personality_path,
        avatar_path=PROJECT_ROOT / "src/sofia/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=PROJECT_ROOT,
    )


def test_production_conversation_retains_authoritative_v2_plan(tmp_path):
    app = SofiaApplication(_configuration(tmp_path))
    app.start()
    app.conversation.respond("What is the CPU load on Artemis?")
    plan = app.conversation.cognitive_plan

    assert plan is not None
    assert plan.turn_id == app.conversation.messages()[-2].id
    assert {"machine", "ops"} <= set(plan.domains)
    assert plan.reasoning_requirement is ReasoningRequirement.DEEP
    assert app.conversation._current_routing_plan.route.value == "deep"
    app.shutdown()
