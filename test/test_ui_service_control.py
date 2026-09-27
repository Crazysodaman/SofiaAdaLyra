import pytest

from sofia.ui.control_center import ServiceAction, ServiceKind, ServiceTarget
from sofia.ui.service_control import (
    DesktopServiceController,
    RemoteControlUnavailable,
    ServiceControlResult,
)


class Local:
    def __init__(self):
        self.calls=[]

    def service(self,name,action):
        self.calls.append((name,action))
        return type("Result",(),{"stdout":"ok","stderr":""})()


class Ollama:
    def __init__(self):
        self.unloaded=[]

    def unload(self,name):
        self.unloaded.append(name)
        return {"done":True}


def test_local_runtime_service_action_uses_typed_maintenance():
    local=Local()
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=local,
        ollama=Ollama(),
        llm_model="qwen3:14b",
    )
    result=controller.execute(
        ServiceTarget(ServiceKind.SOFIA_RUNTIME,"venus","SofiaAdaLyra"),
        ServiceAction.RESTART,
    )
    assert local.calls==[("SofiaAdaLyra","restart")]
    assert result.action is ServiceAction.RESTART


def test_llm_unload_is_separate_from_stopping_ollama_service():
    local=Local(); ollama=Ollama()
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=local,
        ollama=ollama,
        llm_model="qwen3:14b",
    )
    result=controller.execute(
        ServiceTarget(ServiceKind.LLM_ENGINE,"venus","Ollama"),
        ServiceAction.UNLOAD_MODEL,
    )
    assert ollama.unloaded==["qwen3:14b"]
    assert local.calls==[]
    assert result.detail=="unload requested for qwen3:14b"


def test_remote_target_never_falls_back_to_local_service_control():
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=Local(),
        ollama=Ollama(),
        llm_model="qwen3:14b",
    )
    with pytest.raises(RemoteControlUnavailable):
        controller.execute(
            ServiceTarget(ServiceKind.LLM_ENGINE,"artemis","Ollama"),
            ServiceAction.STOP,
        )


def test_remote_target_uses_explicit_fleet_controller():
    class Remote:
        def __init__(self):
            self.calls=[]
        def execute(self,target,action):
            self.calls.append((target,action))
            return ServiceControlResult(target.host_id,target.service_name,action,"remote-ok")

    remote=Remote()
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=Local(),
        remote=remote,
        ollama=Ollama(),
        llm_model="qwen3:14b",
    )
    target=ServiceTarget(ServiceKind.LLM_ENGINE,"artemis","Ollama")
    result=controller.execute(target,ServiceAction.RESTART)
    assert remote.calls==[(target,ServiceAction.RESTART)]
    assert result.detail=="remote-ok"
