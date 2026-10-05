"""Cognitive capability surface for governed EVOLVE proposals and execution."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from sofia.capability.model import Capability, CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding

from .amendment import ProtectedTarget
from .revision import RevisionScope


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


class EvolveCapabilitySet:
    """Expose proposal intelligence without granting approval authority."""

    NAMES = (
        "evolve.evidence.list",
        "evolve.proposals.list",
        "evolve.proposal.get",
        "evolve.proposal.revision.create",
        "evolve.proposal.amendment.create",
        "evolve.apply",
        "evolve.rollback",
    )

    def __init__(self, service: Any) -> None:
        required = (
            "lifecycle",
            "propose_revision",
            "propose_amendment",
            "apply_recorded",
            "rollback_recorded",
        )
        if any(not hasattr(service, name) for name in required):
            raise TypeError("service does not implement the EVOLVE production boundary")
        self.service = service

    def capabilities(self) -> tuple[Capability, ...]:
        descriptions = {
            "evolve.evidence.list": "List durable provenance-backed EVOLVE evidence. Read-only.",
            "evolve.proposals.list": "List durable EVOLVE proposals and lifecycle states. Read-only.",
            "evolve.proposal.get": "Inspect one durable EVOLVE proposal. Read-only.",
            "evolve.proposal.revision.create": (
                "Create a bounded preference/config proposal from existing evidence. "
                "This proposes only and grants no authority."
            ),
            "evolve.proposal.amendment.create": (
                "Create a protected identity/Constitution proposal from existing evidence. "
                "This proposes only and grants no authority."
            ),
            "evolve.apply": "Apply one exact externally approved canonical EVOLVE proposal.",
            "evolve.rollback": "Rollback one exact externally approved applied EVOLVE proposal.",
        }
        return tuple(Capability(name, descriptions[name]) for name in self.NAMES)

    def execute(self, request: CapabilityRequest) -> Any:
        name = request.capability.name
        p = dict(request.parameters)
        if name == "evolve.evidence.list":
            return _json_value(
                self.service.lifecycle.list_evidence(limit=int(p.get("limit", 50)))
            )
        if name == "evolve.proposals.list":
            return _json_value(self.service.proposals(limit=int(p.get("limit", 50))))
        if name == "evolve.proposal.get":
            record = self.service.proposal(p["proposal_id"])
            proposal = self.service.lifecycle.proposal_object(p["proposal_id"])
            return {
                "record": _json_value(record),
                "proposal": _json_value(proposal),
            }
        if name == "evolve.proposal.revision.create":
            result = self.service.propose_revision(
                proposal_id=p["proposal_id"],
                scope=RevisionScope(p["scope"]),
                key=p["key"],
                proposed_content=p["proposed_content"],
                evidence_ids=tuple(p["evidence_ids"]),
                reason=p["reason"],
                rollback_plan=p["rollback_plan"],
                success_metric=p["success_metric"],
                now=datetime.now(timezone.utc),
                ttl=timedelta(seconds=int(p.get("ttl_seconds", 604800))),
            )
            return _json_value(result)
        if name == "evolve.proposal.amendment.create":
            result = self.service.propose_amendment(
                proposal_id=p["proposal_id"],
                target=ProtectedTarget(p["target"]),
                proposed_content=p["proposed_content"],
                evidence_ids=tuple(p["evidence_ids"]),
                reason=p["reason"],
                rollback_plan=p["rollback_plan"],
                success_metric=p["success_metric"],
                now=datetime.now(timezone.utc),
                ttl=timedelta(seconds=int(p.get("ttl_seconds", 604800))),
            )
            return _json_value(result)
        if name == "evolve.apply":
            return _json_value(
                self.service.apply_recorded(
                    proposal_id=p["proposal_id"],
                    approval_id=p["approval_id"],
                    now=datetime.now(timezone.utc),
                )
            )
        if name == "evolve.rollback":
            return _json_value(
                self.service.rollback_recorded(
                    proposal_id=p["proposal_id"],
                    approval_id=p["approval_id"],
                    now=datetime.now(timezone.utc),
                )
            )
        raise ValueError("unsupported EVOLVE capability")


def create_evolve_tool_bindings() -> tuple[CognitiveToolBinding, ...]:
    def binding(
        tool: str,
        capability: str,
        description: str,
        properties: dict[str, Any],
        required: tuple[str, ...] = (),
    ) -> CognitiveToolBinding:
        return CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name=tool,
                description=description,
                parameters={
                    "type": "object",
                    "properties": properties,
                    "required": list(required),
                    "additionalProperties": False,
                },
            ),
            capability_name=capability,
            produces_execution_receipt=capability not in {
                "evolve.evidence.list",
                "evolve.proposals.list",
                "evolve.proposal.get",
            },
        )

    limit = {"limit": {"type": "integer", "minimum": 1, "maximum": 200}}
    proposal_id = {"proposal_id": {"type": "string"}}
    proposal_common = {
        **proposal_id,
        "proposed_content": {"type": "string"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
        "rollback_plan": {"type": "string"},
        "success_metric": {"type": "string"},
        "ttl_seconds": {"type": "integer", "minimum": 300, "maximum": 2592000},
    }
    proposal_required = (
        "proposal_id",
        "proposed_content",
        "evidence_ids",
        "reason",
        "rollback_plan",
        "success_metric",
    )
    return (
        binding(
            "list_evolve_evidence",
            "evolve.evidence.list",
            "List durable evidence available to support an EVOLVE proposal.",
            limit,
        ),
        binding(
            "list_evolve_proposals",
            "evolve.proposals.list",
            "List durable EVOLVE proposals and lifecycle state.",
            limit,
        ),
        binding(
            "inspect_evolve_proposal",
            "evolve.proposal.get",
            "Inspect one canonical EVOLVE proposal and its success metric.",
            proposal_id,
            ("proposal_id",),
        ),
        binding(
            "propose_evolve_revision",
            "evolve.proposal.revision.create",
            "Propose a bounded preference or configuration revision from existing evidence. Does not approve or apply it.",
            {
                **proposal_common,
                "scope": {"type": "string", "enum": ["preference", "config"]},
                "key": {"type": "string"},
            },
            (*proposal_required, "scope", "key"),
        ),
        binding(
            "propose_evolve_amendment",
            "evolve.proposal.amendment.create",
            "Propose a protected identity or Constitution amendment from existing evidence. Does not approve or apply it.",
            {
                **proposal_common,
                "target": {"type": "string", "enum": ["identity", "constitution"]},
            },
            (*proposal_required, "target"),
        ),
        binding(
            "apply_evolve_proposal",
            "evolve.apply",
            "Apply one exact externally approved canonical EVOLVE proposal.",
            {**proposal_id, "approval_id": {"type": "string"}},
            ("proposal_id", "approval_id"),
        ),
        binding(
            "rollback_evolve_proposal",
            "evolve.rollback",
            "Rollback one exact externally approved applied EVOLVE proposal.",
            {**proposal_id, "approval_id": {"type": "string"}},
            ("proposal_id", "approval_id"),
        ),
    )
