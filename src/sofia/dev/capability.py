"""Host-authorized DEV capability over the isolated EngineeringWorkflow."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from sofia.capability.model import Capability,CapabilityRequest
from sofia.dev.opencode import EngineeringExecutionRequest
from sofia.dev.workflow import EngineeringCandidate,EngineeringWorkflow

DEV_ENGINEER_CAPABILITY=Capability(
    "dev.engineer",
    "Build, apply, roll back, commit, or push a reviewed engineering candidate under host-side approval.",
)

ApprovalChecker=Callable[[str],bool]

class DevEngineeringCapability:
    capability=DEV_ENGINEER_CAPABILITY

    def __init__(
        self,
        workspace:Path,
        *,
        approval_checker:ApprovalChecker,
        executable:str="opencode",
    )->None:
        if not callable(approval_checker): raise TypeError("approval_checker must be callable")
        self._workflow=EngineeringWorkflow(workspace,executable)
        self._approval=approval_checker
        self._candidates:dict[str,EngineeringCandidate]={}

    def _require(self,operation:str)->None:
        if self._approval(operation) is not True:
            raise PermissionError(f"DEV operation is not host-authorized: {operation}")

    def execute(self,request:CapabilityRequest):
        operation=request.parameters.get("operation")
        if not isinstance(operation,str): raise ValueError("DEV operation is required")
        self._require(operation)

        if operation=="build":
            proposal_id=request.parameters.get("proposal_id")
            base_sha=request.parameters.get("base_sha")
            prompt=request.parameters.get("prompt")
            allowed_paths=request.parameters.get("allowed_paths")
            tests=request.parameters.get("tests",[])
            if not isinstance(allowed_paths,list) or not all(isinstance(x,str) for x in allowed_paths):
                raise TypeError("allowed_paths must be a list of strings")
            if not isinstance(tests,list) or not all(isinstance(x,str) for x in tests):
                raise TypeError("tests must be a list of strings")
            candidate=self._workflow.build(EngineeringExecutionRequest(
                proposal_id=proposal_id,
                base_sha=base_sha,
                prompt=prompt,
                allowed_paths=tuple(allowed_paths),
                authorized=True,
                tests=tuple(tests),
            ))
            self._candidates[candidate.proposal_id]=candidate
            return {
                "proposal_id":candidate.proposal_id,
                "base_sha":candidate.base_sha,
                "changed_paths":candidate.changed_paths,
                "tests_passed":candidate.tests_passed,
            }

        proposal_id=request.parameters.get("proposal_id")
        if not isinstance(proposal_id,str) or proposal_id not in self._candidates:
            raise KeyError("known proposal_id required")
        candidate=self._candidates[proposal_id]

        if operation=="apply":
            return {"changed_paths":self._workflow.apply(candidate,authorized=True)}
        if operation=="rollback":
            self._workflow.rollback_applied(authorized=True)
            return {"rolled_back":True}
        if operation=="commit":
            message=request.parameters.get("message")
            if not isinstance(message,str) or not message.strip(): raise ValueError("commit message required")
            return {"commit_sha":self._workflow.commit(message,authorized=True)}
        if operation=="push":
            branch=request.parameters.get("branch")
            remote=request.parameters.get("remote","origin")
            if not isinstance(branch,str) or not branch.strip(): raise ValueError("branch required")
            if not isinstance(remote,str) or not remote.strip(): raise ValueError("remote required")
            self._workflow.push(branch,authorized=True,remote=remote)
            return {"pushed":True,"branch":branch,"remote":remote}
        raise ValueError(f"unsupported DEV operation: {operation}")
