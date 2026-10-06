from pathlib import Path
from unittest.mock import patch, Mock
import pytest
from sofia.dev.opencode import (
    EngineeringExecutionRequest,
    OpenCodeAdapter,
    OpenCodeExecutionError,
    WorkspaceGuard,
)

SHA="a"*40

def req(**kw):
    data=dict(proposal_id="p2",base_sha=SHA,prompt="fix it",allowed_paths=("src/ok.py",),authorized=True)
    data.update(kw); return EngineeringExecutionRequest(**data)

def test_base_sha_must_match(tmp_path:Path):
    a=OpenCodeAdapter(tmp_path)
    with patch.object(a,"_git",return_value=Mock(returncode=0,stdout="b"*40+"\n")):
        with pytest.raises(OpenCodeExecutionError): a.verify_base(req())

def test_scope_rejects_changed_path(tmp_path:Path):
    a=OpenCodeAdapter(tmp_path)
    with pytest.raises(Exception): a.verify_scope(req(),("src/nope.py",))

def test_request_accepts_targeted_tests():
    r=req(tests=("test/test_x.py",))
    assert r.tests==("test/test_x.py",)

def test_request_bounds_engineering_iterations_and_test_selectors():
    assert req(max_iterations=5).max_iterations==5
    with pytest.raises(ValueError,match="max_iterations"):
        req(max_iterations=6)
    with pytest.raises(ValueError,match="relative selectors"):
        req(tests=("--pdb",))

def test_directory_write_scope_allows_children(tmp_path:Path):
    guard=WorkspaceGuard(tmp_path,("src/sofia/dev",))
    assert guard.resolve_allowed("src/sofia/dev/workflow.py")==(
        tmp_path/"src/sofia/dev/workflow.py"
    )

def test_opencode_uses_default_agent_unless_host_configures_one(tmp_path:Path,monkeypatch):
    executable=tmp_path/"opencode"
    executable.write_text("",encoding="utf-8")
    monkeypatch.setattr("sofia.dev.opencode.shutil.which",lambda value:str(executable))
    default=OpenCodeAdapter(tmp_path).command(req())
    named=OpenCodeAdapter(tmp_path,agent="sofia-build").command(req())
    assert "--agent" not in default.argv
    assert named.argv[2:4]==("--agent","sofia-build")
