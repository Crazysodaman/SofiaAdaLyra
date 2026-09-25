from pathlib import Path
import subprocess
import pytest

from sofia.dev import (
    ChangeScopeError,
    EngineeringCandidate,
    EngineeringExecutionRequest,
    EngineeringExecutionResult,
    EngineeringWorkflow,
    GitWorkspace,
    path_in_scope,
)

def _git(root:Path,*args:str)->str:
    cp=subprocess.run(("git",*args),cwd=root,text=True,capture_output=True,check=True)
    return cp.stdout.strip()

def _repo(tmp_path:Path)->tuple[Path,str]:
    root=tmp_path/"repo"; root.mkdir()
    _git(root,"init"); _git(root,"config","user.email","tests@example.invalid"); _git(root,"config","user.name","Sofia Tests")
    (root/"src").mkdir(); (root/"src"/"allowed.py").write_text("VALUE = 1\n",encoding="utf-8")\n    (root/"state").mkdir(); (root/"state"/"sofia.db").write_bytes(b"baseline")
    _git(root,"add","."); _git(root,"commit","-m","base")
    return root,_git(root,"rev-parse","HEAD")

def test_directory_scope_matches_children():
    assert path_in_scope("src/sofia/dev/x.py",("src/sofia/dev",))
    assert not path_in_scope("src/sofia/ops/x.py",("src/sofia/dev",))

def test_git_workspace_detects_out_of_scope_change(tmp_path:Path):
    root,sha=_repo(tmp_path); (root/"outside.txt").write_text("nope",encoding="utf-8")
    git=GitWorkspace(root); git.require_head(sha)
    with pytest.raises(ChangeScopeError): git.require_changes_within(("src",))

def test_isolated_build_does_not_touch_real_workspace(tmp_path:Path,monkeypatch):
    root,sha=_repo(tmp_path)
    request=EngineeringExecutionRequest("p",sha,"change value",("src/allowed.py",),True,tests=())
    def fake_execute(self,req):
        (self.workspace/"src"/"allowed.py").write_text("VALUE = 2\n",encoding="utf-8")
        return EngineeringExecutionResult(req.proposal_id,0,"","",req.base_sha,("src/allowed.py",),None,False)
    monkeypatch.setattr("sofia.dev.workflow.OpenCodeAdapter.execute",fake_execute)
    flow=EngineeringWorkflow(root)
    candidate=flow.build(request)
    assert candidate.changed_paths==("src/allowed.py",)
    assert "VALUE = 2" in candidate.patch
    assert (root/"src"/"allowed.py").read_text(encoding="utf-8")=="VALUE = 1\n"

def test_apply_commit_and_push_have_separate_authority(tmp_path:Path):
    root,sha=_repo(tmp_path); (root/"state"/"sofia.db").write_bytes(b"runtime"); flow=EngineeringWorkflow(root)
    patch='diff --git a/src/allowed.py b/src/allowed.py\nindex 4903f36..7e03b80 100644\n--- a/src/allowed.py\n+++ b/src/allowed.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n'
    candidate=EngineeringCandidate("p",sha,patch,("src/allowed.py",),("src/allowed.py",),True)
    with pytest.raises(PermissionError): flow.apply(candidate,authorized=False)
    changed=flow.apply(candidate,authorized=True)
    assert "src/allowed.py" in changed
    with pytest.raises(PermissionError): flow.commit("candidate",authorized=False)
    commit_sha=flow.commit("candidate",authorized=True)
    assert commit_sha!=sha
    assert (root/"state"/"sofia.db").read_bytes()==b"runtime"
    assert "state/sofia.db" in _git(root,"status","--porcelain")
    with pytest.raises(PermissionError): flow.push("main",authorized=False)

def test_candidate_apply_refuses_stale_base(tmp_path:Path):
    root,sha=_repo(tmp_path); flow=EngineeringWorkflow(root)
    candidate=EngineeringCandidate("p","0"*40,"",(),("src/allowed.py",),True)
    with pytest.raises(Exception): flow.apply(candidate,authorized=True)

def test_rollback_only_reverts_unchanged_applied_candidate(tmp_path:Path):
    root,sha=_repo(tmp_path); flow=EngineeringWorkflow(root)
    patch='diff --git a/src/allowed.py b/src/allowed.py\nindex 4903f36..7e03b80 100644\n--- a/src/allowed.py\n+++ b/src/allowed.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n'
    candidate=EngineeringCandidate("p",sha,patch,("src/allowed.py",),("src/allowed.py",),True)
    flow.apply(candidate,authorized=True)
    with pytest.raises(PermissionError): flow.rollback_applied(authorized=False)
    flow.rollback_applied(authorized=True)
    assert (root/"src"/"allowed.py").read_text(encoding="utf-8")=="VALUE = 1\n"
