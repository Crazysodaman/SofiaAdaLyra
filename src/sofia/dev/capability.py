"""Capability surface for governed DEV/OpenCode operations."""
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from .opencode import EngineeringExecutionRequest
from .workflow import EngineeringCandidate,EngineeringWorkflow

class DevCandidateStore:
    def __init__(self,path:Path)->None:
        self.path=path; self._items:dict[str,EngineeringCandidate]={}
        if path.exists():
            raw=json.loads(path.read_text(encoding="utf-8"))
            for item in raw.get("candidates",[]):
                item["changed_paths"]=tuple(item["changed_paths"])
                item["allowed_paths"]=tuple(item["allowed_paths"])
                candidate=EngineeringCandidate(**item)
                self._items[candidate.proposal_id]=candidate
    def put(self,candidate:EngineeringCandidate)->None:
        self._items[candidate.proposal_id]=candidate; self.flush()
    def get(self,proposal_id:str)->EngineeringCandidate:
        try: return self._items[proposal_id]
        except KeyError as exc: raise KeyError(f"unknown DEV proposal: {proposal_id}") from exc
    def remove(self,proposal_id:str)->None:
        self._items.pop(proposal_id,None); self.flush()
    def flush(self)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload={"candidates":[asdict(self._items[k]) for k in sorted(self._items)]}
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        tmp.write_text(json.dumps(payload,sort_keys=True,indent=2),encoding="utf-8")
        tmp.replace(self.path)

class DevToolService:
    def __init__(self,workspace:Path,state_path:Path,*,executable:str="opencode")->None:
        self.workflow=EngineeringWorkflow(workspace,executable)
        self.store=DevCandidateStore(state_path.parent/"dev-candidates.json")
        self._applied_proposal_id:str|None=None
    def head(self)->dict[str,Any]:
        return {"head_sha":self.workflow.git.head_sha(),"changed_paths":self.workflow.git.changed_paths()}
    def build(self,p:dict[str,Any])->dict[str,Any]:
        request=EngineeringExecutionRequest(
            proposal_id=p["proposal_id"],base_sha=p["base_sha"],prompt=p["prompt"],
            allowed_paths=tuple(p["allowed_paths"]),authorized=True,
            timeout_seconds=int(p.get("timeout_seconds",900)),tests=tuple(p.get("tests",())),
        )
        candidate=self.workflow.build(request); self.store.put(candidate)
        return {"proposal_id":candidate.proposal_id,"base_sha":candidate.base_sha,
            "changed_paths":candidate.changed_paths,"allowed_paths":candidate.allowed_paths,
            "tests_passed":candidate.tests_passed,"patch":candidate.patch}
    def apply(self,p:dict[str,Any])->dict[str,Any]:
        candidate=self.store.get(p["proposal_id"])
        changed=self.workflow.apply(candidate,authorized=True)
        self._applied_proposal_id=candidate.proposal_id
        return {"proposal_id":candidate.proposal_id,"changed_paths":changed}
    def rollback(self,p:dict[str,Any])->dict[str,Any]:
        if self._applied_proposal_id is not None and p["proposal_id"]!=self._applied_proposal_id:
            raise ValueError("rollback proposal does not match currently applied candidate")
        self.workflow.rollback_applied(authorized=True)
        proposal_id=p["proposal_id"]; self._applied_proposal_id=None
        return {"proposal_id":proposal_id,"rolled_back":True}
    def commit(self,p:dict[str,Any])->dict[str,Any]:
        if self._applied_proposal_id is not None and p["proposal_id"]!=self._applied_proposal_id:
            raise ValueError("commit proposal does not match currently applied candidate")
        sha=self.workflow.commit(p["message"],authorized=True)
        proposal_id=p["proposal_id"]; self.store.remove(proposal_id); self._applied_proposal_id=None
        return {"proposal_id":proposal_id,"commit_sha":sha}
    def push(self,p:dict[str,Any])->dict[str,Any]:
        self.workflow.push(p["branch"],authorized=True,remote=p.get("remote","origin"))
        return {"branch":p["branch"],"remote":p.get("remote","origin"),"pushed":True}

class DevCapabilitySet:
    NAMES=("dev.status","dev.build","dev.apply","dev.rollback","dev.commit","dev.push")
    def __init__(self,service:DevToolService)->None: self.service=service
    def capabilities(self)->tuple[Capability,...]:
        descriptions={
            "dev.status":"Inspect the local Git workspace HEAD and changed paths. Read-only.",
            "dev.build":"Build and test a candidate change in an isolated detached worktree using OpenCode.",
            "dev.apply":"Apply one previously reviewed DEV candidate to the real workspace.",
            "dev.rollback":"Rollback the currently applied reviewed DEV candidate if it has not changed since apply.",
            "dev.commit":"Commit only the currently applied reviewed candidate paths.",
            "dev.push":"Push the current HEAD to one exact remote branch.",
        }
        return tuple(Capability(name,descriptions[name]) for name in self.NAMES)
    def execute(self,request:CapabilityRequest)->Any:
        p=dict(request.parameters); name=request.capability.name
        if name=="dev.status": return self.service.head()
        if name=="dev.build": return self.service.build(p)
        if name=="dev.apply": return self.service.apply(p)
        if name=="dev.rollback": return self.service.rollback(p)
        if name=="dev.commit": return self.service.commit(p)
        if name=="dev.push": return self.service.push(p)
        raise ValueError("unsupported DEV capability")

def create_dev_tool_bindings()->tuple[CognitiveToolBinding,...]:
    def b(tool,cap,description,properties,required=()):
        return CognitiveToolBinding(
            definition=CognitiveToolDefinition(name=tool,description=description,
                parameters={"type":"object","properties":properties,"required":list(required),"additionalProperties":False}),
            capability_name=cap,
        )
    return (
        b("inspect_dev_status","dev.status","Inspect current Git HEAD and working-tree changes. Read-only.",{}),
        b("build_dev_candidate","dev.build","Build/test an authorized candidate in an isolated OpenCode worktree.",
            {"proposal_id":{"type":"string"},"base_sha":{"type":"string"},"prompt":{"type":"string"},
             "allowed_paths":{"type":"array","items":{"type":"string"}},"tests":{"type":"array","items":{"type":"string"}},
             "timeout_seconds":{"type":"integer"}},("proposal_id","base_sha","prompt","allowed_paths")),
        b("apply_dev_candidate","dev.apply","Apply one reviewed candidate to the real workspace.",
            {"proposal_id":{"type":"string"}},("proposal_id",)),
        b("rollback_dev_candidate","dev.rollback","Rollback the currently applied reviewed candidate.",
            {"proposal_id":{"type":"string"}},("proposal_id",)),
        b("commit_dev_candidate","dev.commit","Commit only the currently applied reviewed candidate paths.",
            {"proposal_id":{"type":"string"},"message":{"type":"string"}},("proposal_id","message")),
        b("push_dev_branch","dev.push","Push current HEAD to one exact remote branch.",
            {"branch":{"type":"string"},"remote":{"type":"string"}},("branch",)),
    )
