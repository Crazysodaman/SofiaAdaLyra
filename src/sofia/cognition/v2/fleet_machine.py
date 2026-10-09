"""Host-owned Fleet/Machine evidence acquisition and deterministic answers."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
from typing import Any
from uuid import uuid4

from sofia.capability.model import CapabilityResult, CapabilityResultKind
from sofia.cognition.model import CognitiveResponse, CognitiveToolCall
from sofia.cognition.tools import CognitiveToolDispatcher
from sofia.social.model import PrincipalContext

from .claims import EvidenceClaimPlanner, EvidenceClaimValidator
from .contracts import (
    ActionRequirement,
    AcquisitionState,
    ConversationFocus,
    EvidenceAtom,
    EvidenceNeed,
    TurnPlan,
)
from .evidence import CapabilityEvidencePayload, EvidenceAcquisitionCoordinator


_SUPPORTED = {
    "machine.cpu": ("cpu",),
    "machine.gpu": ("gpu",),
    "machine.memory_bytes": ("memory_bytes",),
    "machine.storage": ("storage",),
    "machine.hardware": ("hardware",),
    "ops.cpu_percent": ("cpu_percent",),
}


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_plain(item) for item in value]
    return value


class FleetMachineAnswerCoordinator:
    """Complete simple hardware questions without giving the model truth authority."""

    def __init__(
        self,
        dispatcher: CognitiveToolDispatcher,
        acquisition: EvidenceAcquisitionCoordinator,
    ) -> None:
        if not isinstance(dispatcher, CognitiveToolDispatcher):
            raise TypeError("dispatcher must be CognitiveToolDispatcher")
        if not isinstance(acquisition, EvidenceAcquisitionCoordinator):
            raise TypeError("acquisition must be EvidenceAcquisitionCoordinator")
        self.dispatcher = dispatcher
        self.acquisition = acquisition
        self.claim_planner = EvidenceClaimPlanner()
        self.claim_validator = EvidenceClaimValidator()

    def answer(
        self,
        *,
        plan: TurnPlan,
        focus: ConversationFocus,
        principal: PrincipalContext | None,
        allowed_capabilities: tuple[str, ...],
    ) -> CognitiveResponse | None:
        if not isinstance(allowed_capabilities, tuple):
            raise TypeError("allowed_capabilities must be tuple")
        needs = tuple(
            need for need in plan.evidence_needs if need.predicate in _SUPPORTED
        )
        if (
            not needs
            or plan.action_requirement is ActionRequirement.MUTATION
            or focus.primary_reference is None
        ):
            return None
        reference = focus.primary_reference
        remote = reference.kind == "fleet-node"
        telemetry = all(need.predicate.startswith("ops.") for need in needs)
        if remote and telemetry:
            tool = CognitiveToolCall(
                name="inspect_fleet_telemetry",
                arguments={"host_id": reference.aliases[0]},
                call_id=f"v2-fleet-telemetry:{plan.turn_id}",
            )
            capability = "ops.telemetry.latest"
        elif remote:
            prefix = "fleet-node:"
            if not reference.subject_id.startswith(prefix):
                return self._unknown(plan, needs, reference.aliases, "the Fleet identity is incomplete")
            node_id = reference.subject_id[len(prefix):]
            tool = CognitiveToolCall(
                name="inspect_remote_hardware",
                arguments={"node_id": node_id},
                call_id=f"v2-fleet-machine:{plan.turn_id}",
            )
            capability = "remote.hardware.inspect"
        elif reference.kind == "local-host":
            tool = CognitiveToolCall(
                name="inspect_hardware",
                arguments={},
                call_id=f"v2-local-machine:{plan.turn_id}",
            )
            capability = "hardware.inspect"
        else:
            return None
        if capability not in allowed_capabilities:
            return None
        try:
            result = self.dispatcher.dispatch(
                tool,
                principal=principal,
                allowed_capabilities=(capability,),
            )
        except Exception as exc:
            return self._record_failure(
                plan, needs, reference.aliases, capability,
                CapabilityResult(capability, CapabilityResultKind.FAILED, error=str(exc)),
            )
        values = self._normalize_result(
            result,
            expected_node_id=(node_id if remote and not telemetry else None),
        )
        if values is None:
            return self._record_failure(plan, needs, reference.aliases, capability, result)
        atoms = []
        now = datetime.now(timezone.utc)
        for need in needs:
            value = self._value_for(need, values)
            normalized_result = result
            if value is None:
                normalized_result = CapabilityResult(
                    capability, CapabilityResultKind.UNAVAILABLE,
                    error=f"{need.predicate} was absent from hardware evidence",
                )
            payload = CapabilityEvidencePayload(
                evidence_id=f"evidence:{uuid4()}",
                subject_id=need.subject_id,
                predicate=need.predicate,
                value=value,
                source_id=f"capability:{capability}",
                observed_at=now,
                expires_at=now + timedelta(seconds=60),
                scope_id=need.scope_id,
                trust=0.95,
            )
            atoms.append(self.acquisition.record(need, normalized_result, payload))
        answer = self.claim_validator.validate(
            self.claim_planner.build(plan, tuple(atoms)), tuple(atoms)
        )
        label = reference.aliases[0] if reference.aliases else reference.subject_id
        if not answer.claims:
            return self._unknown(plan, needs, reference.aliases, "the requested measurement was unavailable")
        rendered = "; ".join(
            f"{self._label(claim.predicate)}: {self._render_claim(claim.predicate, claim.rendered_value)}"
            for claim in answer.claims
        )
        return CognitiveResponse(
            content=f"Observed {label} through the authenticated hardware inspection — {rendered}.",
            evidence_refs=tuple(dict.fromkeys((
                f"capability:{capability}",
                *(ref for claim in answer.claims for ref in claim.evidence_refs),
            ))),
        )

    @staticmethod
    def _normalize_result(
        result: CapabilityResult,
        *,
        expected_node_id: str | None,
    ) -> dict[str, Any] | None:
        if result.kind is not CapabilityResultKind.SUCCESS:
            return None
        value = _plain(result.evidence)
        if expected_node_id is not None:
            if not isinstance(value, dict) or value.get("node_id") != expected_node_id:
                return None
            if value.get("outcome") != "reported_success":
                return None
            try:
                value = json.loads(value.get("message", ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        if not isinstance(value, dict):
            return None
        hardware = value.get("hardware")
        if isinstance(hardware, dict):
            return {**value, **hardware, "hardware": hardware}
        return value

    @staticmethod
    def _value_for(need: EvidenceNeed, values: dict[str, Any]) -> Any:
        key = _SUPPORTED[need.predicate][0]
        return values if key == "hardware" else values.get(key)

    def _record_failure(self, plan, needs, aliases, capability, result):
        now = datetime.now(timezone.utc)
        atoms = []
        kind = result.kind
        if kind in {CapabilityResultKind.SUCCESS, CapabilityResultKind.DENIED, CapabilityResultKind.UNAUTHORIZED}:
            kind = CapabilityResultKind.FAILED
        safe = CapabilityResult(capability, kind, error=result.error)
        for need in needs:
            atoms.append(self.acquisition.record(
                need,
                safe,
                CapabilityEvidencePayload(
                    evidence_id=f"evidence:{uuid4()}", subject_id=need.subject_id,
                    predicate=need.predicate, value=None,
                    source_id=f"capability:{capability}", observed_at=now,
                    expires_at=None, scope_id=need.scope_id, trust=0.0,
                ),
            ))
        reason = result.error or "the authenticated inspection did not return usable evidence"
        return self._unknown(plan, needs, aliases, reason)

    @staticmethod
    def _unknown(plan, needs, aliases, reason):
        label = aliases[0] if aliases else needs[0].subject_id
        metrics = ", ".join(FleetMachineAnswerCoordinator._label(n.predicate) for n in needs)
        return CognitiveResponse(
            content=f"I couldn't establish {label}'s {metrics}: {reason}. It remains unknown.",
        )

    @staticmethod
    def _label(predicate: str) -> str:
        return {
            "machine.cpu": "CPU",
            "machine.gpu": "GPU",
            "machine.memory_bytes": "memory bytes",
            "machine.storage": "storage",
            "machine.hardware": "hardware",
            "ops.cpu_percent": "CPU utilization",
        }.get(predicate, predicate)

    @staticmethod
    def _render_claim(predicate: str, value: str) -> str:
        return f"{value}%" if predicate == "ops.cpu_percent" else value
