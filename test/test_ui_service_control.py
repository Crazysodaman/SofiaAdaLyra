import pytest

from sofia.modules.ui.control_center import ServiceAction, ServiceKind, ServiceTarget
from sofia.modules.ui.service_control import (
    DesktopServiceController,
    RemoteControlUnavailable,
    ServiceControlResult,
)
from sofia.modules.integrations.ollama import (
    OllamaConnectionDiagnostic,
    OllamaConnectionState,
)
from datetime import datetime, timezone


class Local:
    def __init__(self):
        self.calls=[]

    def service(self,name,action):
        self.calls.append((name,action))
        return type("Result",(),{"stdout":"ok","stderr":""})()

    def service_status(self,name):
        self.calls.append((name,"status"))
        return "running"


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
        self.installed=set()
        self.resident=set()

    def pull(self,name):
        self.pulled.append(name)
        self.installed.add(name)
        return {"done":True}

    def load(self,name,*,keep_alive):
        self.loaded.append((name,keep_alive))
        self.installed.add(name)
        self.resident.add(name)
        return {"done":True}

    def unload(self,name):
        self.unloaded.append(name)
        self.resident.discard(name)
        return {"done":True}

    def models(self):
        return {"models":[{"name": name} for name in self.installed]}

    def running(self):
        return {"models":[{"name": name} for name in self.resident]}

    def diagnose(self, *, service_state, attempts):
        return OllamaConnectionDiagnostic(
            endpoint="http://127.0.0.1:11434",
            state=(
                OllamaConnectionState.READY
                if service_state == "running" else OllamaConnectionState.OFFLINE
            ),
            observed_at=datetime.now(timezone.utc),
            attempts=attempts,
        )


def test_local_ollama_diagnostic_combines_service_and_api_evidence():
    local = Local()
    controller = DesktopServiceController(
        local_host_id="venus", local_maintenance=local, ollama=Ollama(),
        approval_verifier=Approval(),
    )
    result = controller.diagnose_ollama(
        ServiceTarget(ServiceKind.LLM_ENGINE, "venus", "Ollama"),
        attempts=1,
    )
    assert result.state is OllamaConnectionState.READY
    assert result.attempts == 1
    assert local.calls == [("Ollama", "status")]


def test_remote_ollama_diagnostic_never_probes_local_endpoint():
    class Remote:
        def execute(self, target, action):
            raise AssertionError

        def diagnose_ollama(self, target):
            return OllamaConnectionDiagnostic(
                endpoint="https://remote.example:11434",
                state=OllamaConnectionState.READY,
                observed_at=datetime.now(timezone.utc), attempts=1,
            )

    controller = DesktopServiceController(
        local_host_id="venus", local_maintenance=Local(), remote=Remote(),
        ollama=Ollama(), approval_verifier=Approval(),
    )
    result = controller.diagnose_ollama(
        ServiceTarget(ServiceKind.LLM_ENGINE, "worker:gpu", "Ollama")
    )
    assert result.endpoint == "https://remote.example:11434"


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
    assert result.detail=="unload confirmed for vendor/custom-open:4b"


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
    assert result.detail=="load confirmed for vendor/custom-primary:any"



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
    assert result.detail=="install confirmed for vendor/install-me:any"


def test_model_control_refuses_success_when_ollama_state_is_not_confirmed():
    class LyingOllama(Ollama):
        def load(self, name, *, keep_alive):
            self.loaded.append((name, keep_alive))
            return {"done": True}

    controller = DesktopServiceController(
        local_host_id="venus",
        local_maintenance=Local(),
        ollama=LyingOllama(),
        approval_verifier=Approval(),
    )

    with pytest.raises(RuntimeError, match="did not confirm"):
        controller.execute(
            ServiceTarget(ServiceKind.LLM_ENGINE, "venus", "Ollama"),
            ServiceAction.LOAD_MODEL,
            llm_model="vendor/not-really-loaded:any",
            llm_keep_alive="5m",
        )
