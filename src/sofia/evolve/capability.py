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
from .orchestrator import CodeEvolutionOrchestrator
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
        "evolve.proposal.code.create",
        "evolve.code.candidate.build",
        "evolve.code.candidate.apply",
        "evolve.code.candidate.verify",
        "evolve.code.candidate.commit",
        "evolve.code.candidate.rollback",
        "evolve.code.release.accept",
        "evolve.apply",
        "evolve.rollback",
    )

    def __init__(
        self,
        service: Any,
        *,
        code_orchestrator: CodeEvolutionOrchestrator,
    ) -> None:
        required = (
            "lifecycle",
            "propose_revision",
            "propose_amendment",
            "apply_recorded",
            "rollback_recorded",
        )
        if any(not hasattr(service, name) for name in required):
            raise TypeError("service does not implement the EVOLVE production boundary")
        if not isinstance(code_orchestrator, CodeEvolutionOrchestrator):
            raise TypeError("code_orchestrator must be CodeEvolutionOrchestrator")
        self.service = service
        self.code_orchestrator = code_orchestrator

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
            "evolve.proposal.code.create": (
                "Create an evidence-backed bounded code proposal. This grants no authority."
            ),
            "evolve.code.candidate.build": (
                "Build and test the canonical code proposal in DEV's isolated worktree."
            ),
            "evolve.code.candidate.apply": (
                "Apply the exact built candidate using a separate DEV approval."
            ),
            "evolve.code.candidate.verify": (
                "Run the fixed candidate VERIFY gate and attach immutable evidence."
            ),
            "evolve.code.candidate.commit": (
                "Commit a verified candidate using a separate DEV approval."
            ),
            "evolve.code.candidate.rollback": (
                "Rollback an uncommitted candidate using a separate DEV approval."
            ),
            "evolve.code.release.accept": (
                "Bind a completed protected release rollout to code activation."
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
                "evidence": _json_value(
                    self.service.lifecycle.proposal_evidence(p["proposal_id"])
                ),
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
        if name == "evolve.proposal.code.create":
            return _json_value(
                self.service.propose_code(
                    proposal_id=p["proposal_id"],
                    base_sha=p["base_sha"],
                    prompt=p["prompt"],
                    allowed_paths=tuple(p["allowed_paths"]),
                    tests=tuple(p.get("tests", ())),
                    evidence_ids=tuple(p["evidence_ids"]),
                    reason=p["reason"],
                    rollback_plan=p["rollback_plan"],
                    success_metric=p["success_metric"],
                    now=datetime.now(timezone.utc),
                    ttl=timedelta(seconds=int(p.get("ttl_seconds", 604800))),
                )
            )
        if name == "evolve.code.candidate.build":
            return _json_value(
                self.code_orchestrator.build_candidate(
                    p["proposal_id"], now=datetime.now(timezone.utc)
                )
            )
        if name == "evolve.code.candidate.apply":
            return _json_value(
                self.code_orchestrator.apply_candidate(
                    p["proposal_id"],
                    approval_id=p["approval_id"],
                    now=datetime.now(timezone.utc),
                )
            )
        if name == "evolve.code.candidate.verify":
            return _json_value(
                self.code_orchestrator.verify_candidate(
                    p["proposal_id"], now=datetime.now(timezone.utc)
                )
            )
        if name == "evolve.code.candidate.commit":
            return _json_value(
                self.code_orchestrator.commit_candidate(
                    p["proposal_id"],
                    approval_id=p["approval_id"],
                    message=p["message"],
                    now=datetime.now(timezone.utc),
                )
            )
        if name == "evolve.code.candidate.rollback":
            return _json_value(
                self.code_orchestrator.rollback_candidate(
                    p["proposal_id"],
                    approval_id=p["approval_id"],
                    now=datetime.now(timezone.utc),
                )
            )
        if name == "evolve.code.release.accept":
            return _json_value(
                self.service.mark_release_effective(
                    p["proposal_id"],
                    rollout_id=p["rollout_id"],
                    now=datetime.now(timezone.utc),
                )
            )
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
    code_common = {
        key: value
        for key, value in proposal_common.items()
        if key != "proposed_content"
    }
    code_required = tuple(
        item for item in proposal_required if item != "proposed_content"
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
            "propose_evolve_code_change",
            "evolve.proposal.code.create",
            "Propose a bounded evidence-backed code change. Does not build, approve, apply, or commit it.",
            {
                **code_common,
                "base_sha": {"type": "string"},
                "prompt": {"type": "string"},
                "allowed_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 64,
                },
                "tests": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 32,
                },
            },
            (*code_required, "base_sha", "prompt", "allowed_paths"),
        ),
        binding(
            "build_evolve_code_candidate",
            "evolve.code.candidate.build",
            "Build the canonical code proposal in DEV's isolated worktree.",
            proposal_id,
            ("proposal_id",),
        ),
        binding(
            "apply_evolve_code_candidate",
            "evolve.code.candidate.apply",
            "Apply the exact built candidate using a separate exact DEV approval.",
            {**proposal_id, "approval_id": {"type": "string"}},
            ("proposal_id", "approval_id"),
        ),
        binding(
            "verify_evolve_code_candidate",
            "evolve.code.candidate.verify",
            "Run the fixed candidate verification gate and attach its evidence.",
            proposal_id,
            ("proposal_id",),
        ),
        binding(
            "commit_evolve_code_candidate",
            "evolve.code.candidate.commit",
            "Commit a verified candidate using a separate exact DEV approval.",
            {
                **proposal_id,
                "approval_id": {"type": "string"},
                "message": {"type": "string"},
            },
            ("proposal_id", "approval_id", "message"),
        ),
        binding(
            "rollback_evolve_code_candidate",
            "evolve.code.candidate.rollback",
            "Rollback an uncommitted candidate using a separate exact DEV approval.",
            {**proposal_id, "approval_id": {"type": "string"}},
            ("proposal_id", "approval_id"),
        ),
        binding(
            "accept_evolve_code_release",
            "evolve.code.release.accept",
            "Accept completed protected rollout evidence and begin outcome evaluation.",
            {**proposal_id, "rollout_id": {"type": "string"}},
            ("proposal_id", "rollout_id"),
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
