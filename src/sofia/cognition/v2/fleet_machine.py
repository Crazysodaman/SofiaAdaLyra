"""Host-owned multi-subject Fleet/Machine evidence acquisition and answers."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import re
from typing import Any
from uuid import uuid4

from sofia.capability.model import CapabilityResult, CapabilityResultKind
from sofia.cognition.model import CognitiveResponse, CognitiveToolCall
from sofia.cognition.tools import CognitiveToolDispatcher
from sofia.social.model import PrincipalContext

from .claims import EvidenceClaimPlanner, EvidenceClaimValidator
from .contracts import (
    ActionRequirement, AcquisitionState, AnswerPlan, ConversationFocus,
    EvidenceAtom, EvidenceNeed, TurnPlan,
)
from .evidence import CapabilityEvidencePayload, EvidenceAcquisitionCoordinator
from .rendering import ValidatedAnswerDraft


_SUPPORTED = {
    "machine.cpu": "cpu",
    "machine.gpu": "gpu",
    "machine.memory_bytes": "memory_bytes",
    "machine.storage": "storage",
    "ops.cpu_percent": "cpu_percent",
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
    """Answer bounded hardware comparisons without giving models truth authority."""

    def __init__(self, dispatcher, acquisition) -> None:
        if not isinstance(dispatcher, CognitiveToolDispatcher):
            raise TypeError("dispatcher must be CognitiveToolDispatcher")
        if not isinstance(acquisition, EvidenceAcquisitionCoordinator):
            raise TypeError("acquisition must be EvidenceAcquisitionCoordinator")
        self.dispatcher = dispatcher
        self.acquisition = acquisition
        self.claim_planner = EvidenceClaimPlanner()
        self.claim_validator = EvidenceClaimValidator()

    def answer(self, **kwargs) -> CognitiveResponse | None:
        draft = self.planned_answer(**kwargs)
        if draft is None:
            return None
        return CognitiveResponse(draft.content, evidence_refs=draft.evidence_refs)

    def planned_answer(
        self,
        *,
        plan: TurnPlan,
        focus: ConversationFocus,
        principal: PrincipalContext | None,
        allowed_capabilities: tuple[str, ...],
        query: str | None = None,
    ) -> ValidatedAnswerDraft | None:
        _ = query
        if not isinstance(allowed_capabilities, tuple):
            raise TypeError("allowed_capabilities must be tuple")
        needs = tuple(need for need in plan.evidence_needs if need.predicate in _SUPPORTED)
        if not needs or plan.action_requirement is ActionRequirement.MUTATION:
            return None
        references = {item.subject_id: item for item in focus.references}
        if focus.primary_reference is not None:
            references.setdefault(focus.primary_reference.subject_id, focus.primary_reference)

        operations: dict[tuple[str, str], list[EvidenceNeed]] = {}
        details = {}
        for need in needs:
            reference = references.get(need.subject_id)
            if reference is None:
                return self._unknown_draft(plan, needs, (), "the subject reference is unavailable")
            telemetry = need.predicate.startswith("ops.")
            if reference.kind == "fleet-node" and telemetry:
                capability = "ops.telemetry.latest"
                if not reference.aliases:
                    return self._unknown_draft(plan, (need,), (), "the Fleet host alias is unavailable")
                arguments = {"host_id": reference.aliases[0]}
                expected_node_id = None
            elif reference.kind == "fleet-node":
                prefix = "fleet-node:"
                if not reference.subject_id.startswith(prefix):
                    return self._unknown_draft(plan, (need,), reference.aliases, "the Fleet identity is incomplete")
                capability = "remote.hardware.inspect"
                arguments = {"node_id": reference.subject_id[len(prefix):]}
                expected_node_id = reference.subject_id[len(prefix):]
            elif reference.kind == "local-host":
                capability = "hardware.inspect"
                arguments = {}
                expected_node_id = None
            else:
                return None
            key = (need.subject_id, capability)
            operations.setdefault(key, []).append(need)
            details[key] = (reference, arguments, expected_node_id)

        if any(capability not in allowed_capabilities for _, capability in operations):
            # Never execute a partial comparison and then let a model repeat it.
            return None

        atoms: list[EvidenceAtom] = []
        capability_refs: list[str] = []
        failure_reasons: dict[str, str] = {}
        for operation_index, ((subject_id, capability), operation_needs) in enumerate(
            operations.items(), start=1,
        ):
            reference, arguments, expected_node_id = details[(subject_id, capability)]
            tool_name = (
                "inspect_fleet_telemetry" if capability == "ops.telemetry.latest"
                else "inspect_remote_hardware" if capability == "remote.hardware.inspect"
                else "inspect_hardware"
            )
            call_subject = re.sub(r"[^A-Za-z0-9_.-]", "-", subject_id)
            tool = CognitiveToolCall(
                name=tool_name,
                arguments=arguments,
                call_id=f"v2-machine:{plan.turn_id}:{operation_index}:{call_subject}",
            )
            try:
                result = self.dispatcher.dispatch(
                    tool,
                    principal=principal,
                    allowed_capabilities=(capability,),
                )
            except Exception as exc:
                result = CapabilityResult(
                    capability, CapabilityResultKind.FAILED, error=str(exc),
                )
            values = self._normalize_result(result, expected_node_id=expected_node_id)
            normalization_error = self._normalization_failure(
                result, expected_node_id=expected_node_id,
            )
            now = datetime.now(timezone.utc)
            operation_has_current_evidence = False
            for need in operation_needs:
                value = None if values is None else values.get(_SUPPORTED[need.predicate])
                normalized_result = result
                if value is None and result.kind is CapabilityResultKind.SUCCESS:
                    normalized_result = CapabilityResult(
                        capability,
                        (
                            CapabilityResultKind.FAILED
                            if normalization_error is not None
                            else CapabilityResultKind.UNAVAILABLE
                        ),
                        error=(
                            normalization_error
                            or f"{need.predicate} was absent from evidence"
                        ),
                    )
                atom = self.acquisition.record(
                    need,
                    self._safe_result(capability, normalized_result),
                    CapabilityEvidencePayload(
                        evidence_id=f"evidence:{uuid4()}",
                        subject_id=need.subject_id,
                        predicate=need.predicate,
                        value=value,
                        source_id=f"capability:{capability}",
                        observed_at=now,
                        expires_at=(
                            now + timedelta(seconds=60)
                            if value is not None else None
                        ),
                        scope_id=need.scope_id,
                        trust=(0.95 if value is not None else 0.0),
                    ),
                )
                atoms.append(atom)
                operation_has_current_evidence |= (
                    atom.acquisition_state is AcquisitionState.CURRENT
                )
                if atom.acquisition_state is not AcquisitionState.CURRENT:
                    failure_reasons[need.need_id] = (
                        normalized_result.error
                        or "the authenticated inspection returned no usable value"
                    )
            if operation_has_current_evidence:
                capability_refs.append(f"capability:{capability}")

        answer = self.claim_validator.validate(
            self.claim_planner.build(plan, tuple(atoms)), tuple(atoms),
        )
        claims_by_subject = {}
        for claim in answer.claims:
            claims_by_subject.setdefault(claim.subject_id, []).append(claim)
        sections = []
        for subject_id in dict.fromkeys(need.subject_id for need in needs):
            reference = references[subject_id]
            label = reference.aliases[0] if reference.aliases else subject_id
            claims = claims_by_subject.get(subject_id, [])
            values = "; ".join(
                f"{self._label(claim.predicate)}: "
                f"{self._render_claim(claim.predicate, claim.rendered_value)}"
                for claim in claims
            )
            missing = [need for need in needs if need.subject_id == subject_id and need.need_id in answer.unknown_need_ids]
            if values:
                sections.append(f"{label} — {values}")
            if missing:
                metrics = ", ".join(self._label(need.predicate) for need in missing)
                reason = failure_reasons.get(missing[0].need_id, "no current exact evidence")
                sections.append(
                    f"{label} — {metrics} unavailable ({reason}); remains unknown"
                )
        refs = tuple(dict.fromkeys((
            *capability_refs,
            *(ref for claim in answer.claims for ref in claim.evidence_refs),
        )))
        return ValidatedAnswerDraft(
            answer=answer,
            content="Authenticated machine evidence: " + " | ".join(sections),
            evidence_refs=refs,
            domain="machine",
        )

    @staticmethod
    def _safe_result(capability, result):
        kind = result.kind
        if kind in {CapabilityResultKind.DENIED, CapabilityResultKind.UNAUTHORIZED}:
            kind = CapabilityResultKind.FAILED
        return CapabilityResult(capability, kind, error=result.error)

    @staticmethod
    def _normalize_result(result, *, expected_node_id):
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
        return {**value, **hardware, "hardware": hardware} if isinstance(hardware, dict) else value

    @staticmethod
    def _normalization_failure(result, *, expected_node_id):
        """Explain authenticated transport failures without treating absence as proof."""
        if result.kind is not CapabilityResultKind.SUCCESS:
            return result.error or "the authenticated inspection failed"
        if expected_node_id is None:
            return None
        value = _plain(result.evidence)
        if not isinstance(value, dict):
            return "the remote inspection returned an invalid envelope"
        if value.get("node_id") != expected_node_id:
            return "the remote inspection returned evidence for a different node"
        if value.get("outcome") != "reported_success":
            return "the remote node did not report a successful inspection"
        try:
            decoded = json.loads(value.get("message", ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            return "the remote inspection payload was invalid"
        if not isinstance(decoded, dict):
            return "the remote inspection payload was invalid"
        return None

    @staticmethod
    def _unknown_draft(plan, needs, aliases, reason):
        label = aliases[0] if aliases else needs[0].subject_id
        metrics = ", ".join(FleetMachineAnswerCoordinator._label(n.predicate) for n in needs)
        return ValidatedAnswerDraft(
            answer=AnswerPlan(
                turn_id=plan.turn_id,
                claims=(),
                unknown_need_ids=tuple(need.need_id for need in needs),
            ),
            content=f"I couldn't establish {label}'s {metrics}: {reason}. It remains unknown.",
            evidence_refs=(),
            domain="machine",
        )

    @staticmethod
    def _label(predicate):
        return {
            "machine.cpu": "CPU", "machine.gpu": "GPU",
            "machine.memory_bytes": "memory bytes",
            "machine.storage": "storage", "machine.hardware": "hardware",
            "ops.cpu_percent": "CPU utilization",
        }.get(predicate, predicate)

    @staticmethod
    def _render_claim(predicate, value):
        return f"{value}%" if predicate == "ops.cpu_percent" else value
