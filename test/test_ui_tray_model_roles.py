from pathlib import Path
from types import SimpleNamespace

from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import (
    CognitiveRoutingConfiguration,
    ProviderConfiguration,
    SofiaConfiguration,
)
import sofia.ui.tray_agent as tray_agent
from sofia.ui.control_center import ServiceAction, ServiceKind
from sofia.ui.tray_agent import TrayAgentApplication


def _configuration(
    root: Path,
    *,
    primary_model: str,
    secondary_model: str | None,
) -> SofiaConfiguration:
    provider = ProviderConfiguration(
        provider="ollama",
        model="owner-single:anything",
    )
    routing = None
    if secondary_model is not None:
        routing = CognitiveRoutingConfiguration(
            enabled=True,
            primary=ProviderConfiguration(
                provider="ollama",
                model=primary_model,
            ),
            secondary=ProviderConfiguration(
                provider="ollama",
                model=secondary_model,
            ),
        )
    else:
        provider = ProviderConfiguration(
            provider="ollama",
            model=primary_model,
        )

    return SofiaConfiguration(
        constitution_path=root / "constitution.md",
        constitution_hash_path=root / "constitution.sha256",
        identity_path=root / "identity.json",
        personality_path=root / "personality.json",
        avatar_path=root / "avatar.json",
        state_path=root / "sofia.db",
        provider=provider,
        filesystem_root=root,
        routing=routing,
    )


def test_tray_reloads_effective_model_roles_after_startup(
    tmp_path,
    monkeypatch,
):
    first = _configuration(
        tmp_path,
        primary_model="vendor/primary:first",
        secondary_model="vendor/open:first",
    )
    second = _configuration(
        tmp_path,
        primary_model="vendor/primary:second",
        secondary_model="vendor/open:second",
    )
    current = {"configuration": first}

    def configured(*, state_path):
        assert state_path == tmp_path / "sofia.db"
        return current["configuration"]

    monkeypatch.setattr(
        tray_agent,
        "create_production_configuration",
        configured,
    )

    app = object.__new__(TrayAgentApplication)
    app.config = SimpleNamespace(state_path=tmp_path / "sofia.db")

    assert app._current_model_selection().model_names == (
        "vendor/primary:first",
        "vendor/open:first",
    )

    current["configuration"] = second

    assert app._current_model_selection().model_names == (
        "vendor/primary:second",
        "vendor/open:second",
    )


def test_tray_unloads_every_current_configured_model_role():
    app = object.__new__(TrayAgentApplication)
    app.host_id = "venus"
    app._operator_stop = SimpleNamespace(
        current=lambda: SimpleNamespace(active=False)
    )
    app.settings_store = SimpleNamespace(
        load=lambda: SimpleNamespace(
            llm_service_name="Ollama",
            runtime_service_name="SofiaAdaLyra",
        )
    )
    app._runtime_authority = SimpleNamespace(current=lambda: None)
    app._current_model_selection = lambda: CognitiveModelSelection(
        routing_enabled=True,
        primary=ProviderConfiguration(
            provider="ollama",
            model="vendor/primary:anything",
        ),
        secondary=ProviderConfiguration(
            provider="ollama",
            model="vendor/open:anything",
        ),
    )

    calls = []

    class Service:
        @staticmethod
        def approval_spec(target, action, *, llm_model=None):
            return "ollama.model.unload", {"model": llm_model}

        @staticmethod
        def execute(
            target,
            action,
            *,
            approval_id=None,
            llm_model=None,
        ):
            calls.append((target, action, approval_id, llm_model))

    approvals = []
    app._service = Service()
    app._execution_approvals = SimpleNamespace(record=approvals.append)

    app._service_action(
        ServiceKind.LLM_ENGINE,
        ServiceAction.UNLOAD_MODEL,
    )

    assert [call[3] for call in calls] == [
        "vendor/primary:anything",
        "vendor/open:anything",
    ]
    assert len(approvals) == 2
