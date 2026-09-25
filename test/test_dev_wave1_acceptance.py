from pathlib import Path
import pytest
from sofia.dev import EngineeringExecutionRequest, OpenCodeAdapter, WorkspaceGuard, WorkspaceViolation

def test_opencode_refuses_unauthorized_execution(tmp_path):
    req=EngineeringExecutionRequest("p1","a"*40,"fix the bug",("src/a.py",),False)
    with pytest.raises(PermissionError): OpenCodeAdapter(tmp_path).command(req)

def test_workspace_denies_scope_escape(tmp_path):
    guard=WorkspaceGuard(tmp_path,("src/a.py",))
    with pytest.raises(WorkspaceViolation): guard.resolve_allowed("src/b.py")

def test_workspace_resolves_approved_path(tmp_path):
    guard=WorkspaceGuard(tmp_path,("src/a.py",))
    assert guard.resolve_allowed("src/a.py")==tmp_path.resolve()/"src/a.py"
