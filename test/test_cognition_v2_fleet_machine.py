from datetime import datetime, timezone
from uuid import UUID

import pytest

from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import Capability
from sofia.capability.system import CapabilitySystem
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding, CognitiveToolDispatcher
from sofia.cognition.v2 import (
    ActionRequirement,
    CognitiveBudget,
    CognitiveSchedule,
    CognitiveTask,
    CognitiveTaskKind,
    ConversationFocus,
    CognitiveEvidenceLedger,
    EvidenceAcquisitionCoordinator,
    EvidenceClaimPlanner,
    EvidenceClaimValidator,
    EvidenceNeed,
    FleetMachineAnswerCoordinator,
    FocusReference,
    ReasoningRequirement,
    TurnPlan,
)


NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
ARTEMIS_NODE = UUID("12345678-1234-5678-1234-567812345678")
VENUS_NODE = UUID("87654321-4321-8765-4321-876543218765")


def _plan(scope="principal:sparks"):
    need = EvidenceNeed(
        "need:machine:1", f"fleet-node:{ARTEMIS_NODE}", "machine.cpu",
        scope, max_age_seconds=60, minimum_trust=0.8,
    )
    return TurnPlan(
        turn_id="turn:cpu", focus_revision=1, domains=("machine", "ops"),
        evidence_needs=(need,),
        schedule=CognitiveSchedule(
            "schedule:cpu",
            (CognitiveTask("evidence:cpu", CognitiveTaskKind.EVIDENCE_ACQUISITION),),
        ),
        response_strategy="evidence-first", action_requires_authority=False,
        intent="operational_query", action_requirement=ActionRequirement.NONE,
        reasoning_requirement=ReasoningRequirement.DEEP,
        budget=CognitiveBudget(512, 2000, 2, False),
    )


def _focus():
    reference = FocusReference(
        "reference:artemis", f"fleet-node:{ARTEMIS_NODE}", "fleet-node",
        "turn:cpu", 1.0, aliases=("Artemis",),
    )
    return ConversationFocus(
        "session:test", "principal:sparks", 1,
        primary_reference=reference, references=(reference,),
    )


def _coordinator(
    tmp_path, evidence, *, capability_name="remote.hardware.inspect",
    tool_name="inspect_remote_hardware", parameter_name="node_id",
):
    system = CapabilitySystem(authorization_checker=lambda request: True)
    capability = Capability(capability_name, "Inspect trusted machine evidence")
    system.register(capability, lambda request: evidence)
    dispatcher = CognitiveToolDispatcher(
        CapabilityGateway(system),
        (CognitiveToolBinding(
            CognitiveToolDefinition(
                tool_name, "Inspect trusted machine evidence",
                {"type": "object", "properties": {parameter_name: {"type": "string"}},
                 "required": [parameter_name], "additionalProperties": False},
            ),
            capability_name,
        ),),
    )
    ledger = CognitiveEvidenceLedger(tmp_path / "sofia.db")
    return FleetMachineAnswerCoordinator(
        dispatcher, EvidenceAcquisitionCoordinator(ledger)
    ), ledger


def test_artemis_cpu_uses_authenticated_subject_bound_capability(tmp_path):
    coordinator, ledger = _coordinator(tmp_path, {
        "request_id": "request-1", "node_id": str(ARTEMIS_NODE),
        "outcome": "reported_success",
        "message": '{"hardware":{"cpu":"Ryzen 9","gpu":[],"memory_bytes":64}}',
    })

    response = coordinator.answer(
        plan=_plan(), focus=_focus(), principal=None,
        allowed_capabilities=("remote.hardware.inspect",),
    )

    assert "Artemis" in response.content
    assert "Ryzen 9" in response.content
    assert "Venus" not in response.content
    atom = ledger.get(next(ref for ref in response.evidence_refs if ref.startswith("evidence:")))
    assert atom.subject_id == f"fleet-node:{ARTEMIS_NODE}"
    assert atom.predicate == "machine.cpu"


def test_wrong_node_result_cannot_be_borrowed_for_artemis(tmp_path):
    coordinator, ledger = _coordinator(tmp_path, {
        "request_id": "request-1", "node_id": str(VENUS_NODE),
        "outcome": "reported_success",
        "message": '{"hardware":{"cpu":"Venus CPU"}}',
    })

    response = coordinator.answer(
        plan=_plan(), focus=_focus(), principal=None,
        allowed_capabilities=("remote.hardware.inspect",),
    )

    assert "remains unknown" in response.content
    assert "Venus CPU" not in response.content
    matches = ledger.matching(_plan().evidence_needs[0])
    assert matches[0].acquisition_state.value == "failed"


def test_remote_reported_failure_is_unknown_not_a_cpu_claim(tmp_path):
    coordinator, _ = _coordinator(tmp_path, {
        "request_id": "request-1", "node_id": str(ARTEMIS_NODE),
        "outcome": "reported_failure", "message": "sensor unavailable",
    })

    response = coordinator.answer(
        plan=_plan(), focus=_focus(), principal=None,
        allowed_capabilities=("remote.hardware.inspect",),
    )

    assert "remains unknown" in response.content
    assert not response.evidence_refs


def test_v2_coordinator_cannot_bypass_matrix_tool_exposure(tmp_path):
    coordinator, ledger = _coordinator(tmp_path, {
        "request_id": "request-1", "node_id": str(ARTEMIS_NODE),
        "outcome": "reported_success",
        "message": '{"hardware":{"cpu":"must not execute"}}',
    })

    response = coordinator.answer(
        plan=_plan(), focus=_focus(), principal=None, allowed_capabilities=(),
    )

    assert response is None
    assert ledger.matching(_plan().evidence_needs[0]) == ()


def test_matrix_routes_cpu_load_to_fleet_telemetry_not_cpu_model():
    from sofia.cognition.v2 import MatrixV2Planner, TurnKernelInput

    turn = TurnKernelInput(
        "turn:load", "session:test", "What is Artemis CPU load?", NOW,
        "desktop", "sparks", "principal:sparks",
    )
    plan = MatrixV2Planner().plan(turn, _focus())

    assert any(need.predicate == "ops.cpu_percent" for need in plan.evidence_needs)
    assert all(need.predicate != "machine.cpu" for need in plan.evidence_needs)


def test_cpu_load_uses_durable_fleet_telemetry(tmp_path):
    coordinator, ledger = _coordinator(
        tmp_path,
        {"cpu_percent": 37.5, "observed_at": NOW.isoformat()},
        capability_name="ops.telemetry.latest",
        tool_name="inspect_fleet_telemetry",
        parameter_name="host_id",
    )
    base = _plan()
    need = EvidenceNeed(
        "need:machine:1", f"fleet-node:{ARTEMIS_NODE}", "ops.cpu_percent",
        "principal:sparks", max_age_seconds=60, minimum_trust=0.8,
    )
    plan = TurnPlan(
        turn_id=base.turn_id, focus_revision=base.focus_revision,
        domains=base.domains, evidence_needs=(need,), schedule=base.schedule,
        response_strategy=base.response_strategy,
        action_requires_authority=base.action_requires_authority,
        intent=base.intent, action_requirement=base.action_requirement,
        reasoning_requirement=base.reasoning_requirement, budget=base.budget,
    )

    response = coordinator.answer(
        plan=plan, focus=_focus(), principal=None,
        allowed_capabilities=("ops.telemetry.latest",),
    )

    assert "CPU utilization: 37.5%" in response.content
    atom = ledger.get(next(ref for ref in response.evidence_refs if ref.startswith("evidence:")))
    assert atom.predicate == "ops.cpu_percent"
    assert atom.value_json == "37.5"


def test_claim_validator_rejects_cross_subject_evidence(tmp_path):
    coordinator, ledger = _coordinator(tmp_path, {
        "request_id": "request-1", "node_id": str(ARTEMIS_NODE),
        "outcome": "reported_success",
        "message": '{"hardware":{"cpu":"Ryzen 9"}}',
    })
    response = coordinator.answer(
        plan=_plan(), focus=_focus(), principal=None,
        allowed_capabilities=("remote.hardware.inspect",),
    )
    atom = ledger.get(next(ref for ref in response.evidence_refs if ref.startswith("evidence:")))
    answer = EvidenceClaimPlanner().build(_plan(), (atom,))
    altered = type(atom)(
        atom.evidence_id, f"fleet-node:{VENUS_NODE}", atom.predicate,
        atom.value_json, atom.source_id, atom.observed_at, atom.scope_id,
        atom.trust, atom.epistemic_state, atom.acquisition_state, atom.expires_at,
    )

    with pytest.raises(ValueError, match="does not match exact"):
        EvidenceClaimValidator().validate(answer, (altered,))


def test_multi_machine_multi_property_answer_keeps_values_on_exact_hosts(tmp_path):
    system = CapabilitySystem(authorization_checker=lambda request: True)
    capability = Capability(
        "remote.hardware.inspect", "Inspect trusted machine evidence",
    )

    def inspect(request):
        node_id = request.parameters["node_id"]
        values = {
            str(ARTEMIS_NODE): ("Artemis CPU", 64),
            str(VENUS_NODE): ("Venus CPU", 32),
        }
        cpu, memory = values[node_id]
        return {
            "request_id": f"request-{node_id}",
            "node_id": node_id,
            "outcome": "reported_success",
            "message": (
                '{"hardware":{"cpu":"' + cpu
                + '","memory_bytes":' + str(memory) + '}}'
            ),
        }

    system.register(capability, inspect)
    dispatcher = CognitiveToolDispatcher(
        CapabilityGateway(system),
        (CognitiveToolBinding(
            CognitiveToolDefinition(
                "inspect_remote_hardware", "Inspect trusted machine evidence",
                {"type": "object", "properties": {"node_id": {"type": "string"}},
                 "required": ["node_id"], "additionalProperties": False},
            ),
            capability.name,
        ),),
    )
    ledger = CognitiveEvidenceLedger(tmp_path / "sofia.db")
    coordinator = FleetMachineAnswerCoordinator(
        dispatcher, EvidenceAcquisitionCoordinator(ledger),
    )
    references = tuple(
        FocusReference(
            f"reference:{label.casefold()}", f"fleet-node:{node_id}",
            "fleet-node", "turn:comparison", 1.0, aliases=(label,),
        )
        for label, node_id in (("Artemis", ARTEMIS_NODE), ("Venus", VENUS_NODE))
    )
    needs = tuple(
        EvidenceNeed(
            f"need:{subject_index}:{predicate_index}",
            reference.subject_id, predicate, "principal:sparks",
            max_age_seconds=60, minimum_trust=0.8,
        )
        for subject_index, reference in enumerate(references, start=1)
        for predicate_index, predicate in enumerate(
            ("machine.cpu", "machine.memory_bytes"), start=1,
        )
    )
    base = _plan()
    plan = TurnPlan(
        turn_id="turn:comparison", focus_revision=1,
        domains=("machine", "ops"), evidence_needs=needs,
        schedule=base.schedule, response_strategy=base.response_strategy,
        action_requires_authority=False, intent=base.intent,
        action_requirement=base.action_requirement,
        reasoning_requirement=base.reasoning_requirement, budget=base.budget,
    )
    focus = ConversationFocus(
        "session:test", "principal:sparks", 1,
        primary_reference=references[0], references=references,
    )

    response = coordinator.answer(
        plan=plan, focus=focus, principal=None,
        allowed_capabilities=("remote.hardware.inspect",),
    )

    assert "Artemis — CPU: Artemis CPU; memory bytes: 64" in response.content
    assert "Venus — CPU: Venus CPU; memory bytes: 32" in response.content
    atoms = tuple(
        ledger.get(ref) for ref in response.evidence_refs
        if ref.startswith("evidence:")
    )
    assert {(atom.subject_id, atom.predicate) for atom in atoms} == {
        (reference.subject_id, predicate)
        for reference in references
        for predicate in ("machine.cpu", "machine.memory_bytes")
    }
