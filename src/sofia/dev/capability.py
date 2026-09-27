"""Capability surface for governed DEV/OpenCode operations."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sofia.capability.model import Capability, CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from sofia.dev.approval import DevOperation
from sofia.safe.dev_approval import DevApprovalVerifier

from .opencode import EngineeringExecutionRequest
from .workflow import EngineeringCandidate, EngineeringWorkflow


class DevCandidateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._items: dict[str, EngineeringCandidate] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            for item in raw.get("candidates", []):
                item["changed_paths"] = tuple(item["changed_paths"])
                item["allowed_paths"] = tuple(item["allowed_paths"])
                candidate = EngineeringCandidate(**item)
                self._items[candidate.proposal_id] = candidate

    def put(self, candidate: EngineeringCandidate) -> None:
        self._items[candidate.proposal_id] = candidate
        self.flush()

    def get(self, proposal_id: str) -> EngineeringCandidate:
        try:
            return self._items[proposal_id]
        except KeyError as exc:
            raise KeyError(f"unknown DEV proposal: {proposal_id}") from exc

    def remove(self, proposal_id: str) -> None:
        self._items.pop(proposal_id, None)
        self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "candidates": [
                asdict(self._items[key])
                for key in sorted(self._items)
            ]
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)


class DevToolService:
    """
    Production DEV capability service.

    Authorization is consumed exactly once at this boundary. The internal
    EngineeringWorkflow never receives a magic authorization boolean.
    """

    def __init__(
        self,
        workspace: Path,
        state_path: Path,
        *,
        approval_verifier: DevApprovalVerifier,
        executable: str = "opencode",
    ) -> None:
        if not isinstance(approval_verifier, DevApprovalVerifier):
            raise TypeError("approval_verifier must be a DevApprovalVerifier")
        self.workflow = EngineeringWorkflow(workspace, executable)
        self.store = DevCandidateStore(
            state_path.parent / "dev-candidates.json"
        )
        self.approval_verifier = approval_verifier
        self._applied_proposal_id: str | None = None

    def _authorize(
        self,
        operation: DevOperation,
        parameters: dict[str, Any],
    ) -> None:
        proposal_id = parameters.get("proposal_id")
        approval_id = parameters.get("approval_id")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise PermissionError("DEV mutation requires proposal_id")
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise PermissionError("DEV mutation requires approval_id")
        self.approval_verifier.consume(
            approval_id=approval_id,
            operation=operation,
            proposal_id=proposal_id,
            parameters=parameters,
            now=datetime.now(timezone.utc),
        )

    def head(self) -> dict[str, Any]:
        return {
            "head_sha": self.workflow.git.head_sha(),
            "changed_paths": self.workflow.git.changed_paths(),
        }

    def build(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._authorize(DevOperation.BUILD, parameters)
        request = EngineeringExecutionRequest(
            proposal_id=parameters["proposal_id"],
            base_sha=parameters["base_sha"],
            prompt=parameters["prompt"],
            allowed_paths=tuple(parameters["allowed_paths"]),
            timeout_seconds=int(parameters.get("timeout_seconds", 900)),
            tests=tuple(parameters.get("tests", ())),
        )
        candidate = self.workflow.build(request)
        self.store.put(candidate)
        return {
            "proposal_id": candidate.proposal_id,
            "base_sha": candidate.base_sha,
            "changed_paths": candidate.changed_paths,
            "allowed_paths": candidate.allowed_paths,
            "tests_passed": candidate.tests_passed,
            "patch": candidate.patch,
        }

    def apply(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._authorize(DevOperation.APPLY, parameters)
        candidate = self.store.get(parameters["proposal_id"])
        changed = self.workflow.apply(candidate)
        self._applied_proposal_id = candidate.proposal_id
        return {
            "proposal_id": candidate.proposal_id,
            "changed_paths": changed,
        }

    def rollback(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._authorize(DevOperation.ROLLBACK, parameters)
        if (
            self._applied_proposal_id is not None
            and parameters["proposal_id"] != self._applied_proposal_id
        ):
            raise ValueError(
                "rollback proposal does not match currently applied candidate"
            )
        self.workflow.rollback_applied()
        proposal_id = parameters["proposal_id"]
        self._applied_proposal_id = None
        return {
            "proposal_id": proposal_id,
            "rolled_back": True,
        }

    def commit(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._authorize(DevOperation.COMMIT, parameters)
        if (
            self._applied_proposal_id is not None
            and parameters["proposal_id"] != self._applied_proposal_id
        ):
            raise ValueError(
                "commit proposal does not match currently applied candidate"
            )
        sha = self.workflow.commit(parameters["message"])
        proposal_id = parameters["proposal_id"]
        self.store.remove(proposal_id)
        self._applied_proposal_id = None
        return {
            "proposal_id": proposal_id,
            "commit_sha": sha,
        }

    def push(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._authorize(DevOperation.PUSH, parameters)
        self.workflow.push(
            parameters["branch"],
            remote=parameters.get("remote", "origin"),
        )
        return {
            "proposal_id": parameters["proposal_id"],
            "branch": parameters["branch"],
            "remote": parameters.get("remote", "origin"),
            "pushed": True,
        }


class DevCapabilitySet:
    NAMES = (
        "dev.status",
        "dev.build",
        "dev.apply",
        "dev.rollback",
        "dev.commit",
        "dev.push",
    )

    def __init__(self, service: DevToolService) -> None:
        self.service = service

    def capabilities(self) -> tuple[Capability, ...]:
        descriptions = {
            "dev.status": (
                "Inspect the local Git workspace HEAD and changed paths. "
                "Read-only."
            ),
            "dev.build": (
                "Build an exact approved candidate in an isolated OpenCode "
                "worktree."
            ),
            "dev.apply": (
                "Apply one exact approved reviewed candidate to the real "
                "workspace."
            ),
            "dev.rollback": (
                "Rollback one exact approved currently applied candidate."
            ),
            "dev.commit": (
                "Commit only one exact approved candidate's applied paths."
            ),
            "dev.push": (
                "Push current HEAD only with an exact approved push record."
            ),
        }
        return tuple(
            Capability(name, descriptions[name])
            for name in self.NAMES
        )

    def execute(self, request: CapabilityRequest) -> Any:
        parameters = dict(request.parameters)
        name = request.capability.name
        if name == "dev.status":
            return self.service.head()
        if name == "dev.build":
            return self.service.build(parameters)
        if name == "dev.apply":
            return self.service.apply(parameters)
        if name == "dev.rollback":
            return self.service.rollback(parameters)
        if name == "dev.commit":
            return self.service.commit(parameters)
        if name == "dev.push":
            return self.service.push(parameters)
        raise ValueError("unsupported DEV capability")


def create_dev_tool_bindings() -> tuple[CognitiveToolBinding, ...]:
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
        )

    approval = {"approval_id": {"type": "string"}}
    proposal = {"proposal_id": {"type": "string"}}

    return (
        binding(
            "inspect_dev_status",
            "dev.status",
            "Inspect current Git HEAD and working-tree changes. Read-only.",
            {},
        ),
        binding(
            "build_dev_candidate",
            "dev.build",
            "Build an exact operator-approved candidate in an isolated worktree.",
            {
                **proposal,
                **approval,
                "base_sha": {"type": "string"},
                "prompt": {"type": "string"},
                "allowed_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "tests": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "timeout_seconds": {"type": "integer"},
            },
            (
                "proposal_id",
                "approval_id",
                "base_sha",
                "prompt",
                "allowed_paths",
            ),
        ),
        binding(
            "apply_dev_candidate",
            "dev.apply",
            "Apply one exact operator-approved reviewed candidate.",
            {**proposal, **approval},
            ("proposal_id", "approval_id"),
        ),
        binding(
            "rollback_dev_candidate",
            "dev.rollback",
            "Rollback one exact operator-approved applied candidate.",
            {**proposal, **approval},
            ("proposal_id", "approval_id"),
        ),
        binding(
            "commit_dev_candidate",
            "dev.commit",
            "Commit one exact operator-approved applied candidate.",
            {
                **proposal,
                **approval,
                "message": {"type": "string"},
            },
            ("proposal_id", "approval_id", "message"),
        ),
        binding(
            "push_dev_branch",
            "dev.push",
            "Push HEAD only with an exact operator-approved push record.",
            {
                **proposal,
                **approval,
                "branch": {"type": "string"},
                "remote": {"type": "string"},
            },
            ("proposal_id", "approval_id", "branch"),
        ),
    )
