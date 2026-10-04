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
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane
from sofia.state.sqlite_plane import SQLiteStatePlane

from .opencode import EngineeringExecutionRequest
from .workflow import EngineeringCandidate, EngineeringWorkflow


class DevCandidateStore:
    NAMESPACE = "dev-candidate"

    def __init__(
        self,
        state_plane: StatePlane,
        *,
        legacy_path: Path | None = None,
    ) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self.state_plane = state_plane
        self.legacy_path = legacy_path
        self._import_legacy_if_needed()

    @staticmethod
    def _encode(candidate: EngineeringCandidate) -> bytes:
        return json.dumps(
            asdict(candidate),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def _decode(record: StateRecord) -> EngineeringCandidate:
        raw = json.loads(record.value.decode("utf-8"))
        raw["changed_paths"] = tuple(raw["changed_paths"])
        raw["allowed_paths"] = tuple(raw["allowed_paths"])
        return EngineeringCandidate(**raw)

    def _import_legacy_if_needed(self) -> None:
        if self.state_plane.list_namespace(self.NAMESPACE):
            return
        if self.legacy_path is None or not self.legacy_path.is_file():
            return
        raw = json.loads(self.legacy_path.read_text(encoding="utf-8"))
        for item in raw.get("candidates", []):
            item["changed_paths"] = tuple(item["changed_paths"])
            item["allowed_paths"] = tuple(item["allowed_paths"])
            self.put(
                EngineeringCandidate(**item),
                source="legacy-json:dev-candidates",
            )

    def put(
        self,
        candidate: EngineeringCandidate,
        *,
        source: str = "dev:reviewed-candidate",
    ) -> None:
        if not isinstance(candidate, EngineeringCandidate):
            raise TypeError("candidate must be an EngineeringCandidate")
        key = StateKey(
            namespace=self.NAMESPACE,
            key=candidate.proposal_id,
        )
        existing = self.state_plane.read(key)
        payload = self._encode(candidate)
        if existing is not None:
            if existing.value != payload:
                raise ValueError(
                    "proposal_id already belongs to a different DEV candidate"
                )
            return
        self.state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=1,
                value=payload,
                updated_at=datetime.now(timezone.utc),
                source=source,
            ),
            expected_revision=None,
        )

    def get(self, proposal_id: str) -> EngineeringCandidate:
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id must be nonempty")
        record = self.state_plane.read(
            StateKey(
                namespace=self.NAMESPACE,
                key=proposal_id,
            )
        )
        if record is None:
            raise KeyError(f"unknown DEV proposal: {proposal_id}")
        return self._decode(record)

    def remove(self, proposal_id: str) -> None:
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id must be nonempty")
        key = StateKey(
            namespace=self.NAMESPACE,
            key=proposal_id,
        )
        record = self.state_plane.read(key)
        if record is None:
            return
        self.state_plane.delete(
            key,
            expected_revision=record.revision,
        )


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
        state_plane: StatePlane | None = None,
        executable: str = "opencode",
    ) -> None:
        if not isinstance(approval_verifier, DevApprovalVerifier):
            raise TypeError("approval_verifier must be a DevApprovalVerifier")
        self.workflow = EngineeringWorkflow(workspace, executable)
        plane = state_plane or SQLiteStatePlane(state_path)
        self.store = DevCandidateStore(
            plane,
            legacy_path=state_path.parent / "dev-candidates.json",
        )
        self.approval_verifier = approval_verifier
        self._applied_proposal_id: str | None = None

    def _authorize(
        self,
        operation: DevOperation,
        parameters: dict[str, Any],
    ) -> None:
        proposal_id = parameters.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise PermissionError("DEV operation requires proposal_id")

        # Building/testing a candidate happens only in the isolated detached
        # worktree and is Level-2 safe-autonomous. Applying that patch to the
        # real workspace, rollback, commit, and push remain exact approvals.
        if operation is DevOperation.BUILD:
            return

        approval_id = parameters.get("approval_id")
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
            authorized=True,
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
        changed = self.workflow.apply(candidate, authorized=True)
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
        self.workflow.rollback_applied(authorized=True)
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
        sha = self.workflow.commit(
            parameters["message"],
            authorized=True,
        )
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
            authorized=True,
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
                "Build and test a bounded candidate in an isolated OpenCode "
                "worktree. Safe-autonomous; does not modify the real workspace."
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
            produces_execution_receipt=(capability != "dev.status"),
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
            "Build and test a bounded candidate in an isolated worktree without modifying the real workspace.",
            {
                **proposal,
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
