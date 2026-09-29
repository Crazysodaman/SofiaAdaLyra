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


class Approval:
    def __init__(self):
        self.calls=[]

    def consume(self, **kwargs):
        self.calls.append(kwargs)


class Ollama:
    def __init__(self):
        self.pulled=[]
        self.loaded=[]
        self.unloaded=[]

    def pull(self,name):
        self.pulled.append(name)
        return {"done":True}

    def load(self,name,*,keep_alive):
        self.loaded.append((name,keep_alive))
        return {"done":True}

    def unload(self,name):
        self.unloaded.append(name)
        return {"done":True}


def test_local_runtime_service_action_uses_typed_maintenance():
    local=Local()
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=local,
        ollama=Ollama(),
        approval_verifier=Approval(),
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
        approval_verifier=Approval(),
    )
    result=controller.execute(
        ServiceTarget(ServiceKind.LLM_ENGINE,"venus","Ollama"),
        ServiceAction.UNLOAD_MODEL,
        llm_model="vendor/custom-open:4b",
    )
    assert ollama.unloaded==["vendor/custom-open:4b"]
    assert local.calls==[]
    assert result.detail=="unload requested for vendor/custom-open:4b"


def test_remote_target_never_falls_back_to_local_service_control():
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=Local(),
        ollama=Ollama(),
        approval_verifier=Approval(),
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
        approval_verifier=Approval(),
    )
    target=ServiceTarget(ServiceKind.LLM_ENGINE,"artemis","Ollama")
    result=controller.execute(target,ServiceAction.RESTART)
    assert remote.calls==[(target,ServiceAction.RESTART)]
    assert result.detail=="remote-ok"



def test_llm_unload_requires_model_from_caller_not_controller_state():
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=Local(),
        ollama=Ollama(),
        approval_verifier=Approval(),
    )
    with pytest.raises(ValueError, match="model identity"):
        controller.execute(
            ServiceTarget(ServiceKind.LLM_ENGINE,"venus","Ollama"),
            ServiceAction.UNLOAD_MODEL,
        )



def test_llm_load_is_separate_from_starting_ollama_service():
    local=Local(); ollama=Ollama()
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=local,
        ollama=ollama,
        approval_verifier=Approval(),
    )
    result=controller.execute(
        ServiceTarget(ServiceKind.LLM_ENGINE,"venus","Ollama"),
        ServiceAction.LOAD_MODEL,
        llm_model="vendor/custom-primary:any",
        llm_keep_alive="6m",
    )
    assert ollama.loaded==[("vendor/custom-primary:any","6m")]
    assert local.calls==[]
    assert result.detail=="load requested for vendor/custom-primary:any"



def test_llm_install_pulls_model_without_loading_or_starting_service():
    local=Local(); ollama=Ollama()
    controller=DesktopServiceController(
        local_host_id="venus",
        local_maintenance=local,
        ollama=ollama,
        approval_verifier=Approval(),
    )
    result=controller.execute(
        ServiceTarget(ServiceKind.LLM_ENGINE,"venus","Ollama"),
        ServiceAction.INSTALL_MODEL,
        llm_model="vendor/install-me:any",
    )
    assert ollama.pulled==["vendor/install-me:any"]
    assert ollama.loaded==[]
    assert local.calls==[]
    assert result.detail=="install requested for vendor/install-me:any"
