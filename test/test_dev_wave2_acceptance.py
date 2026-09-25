from pathlib import Path
from unittest.mock import patch, Mock
import pytest
from sofia.dev.opencode import EngineeringExecutionRequest, OpenCodeAdapter, OpenCodeExecutionError

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
