from pathlib import Path
from types import SimpleNamespace

from sofia.platform.config.cognitive_models import CognitiveModelSelection
from sofia.platform.config.model import (
    CognitiveRoutingConfiguration,
    ProviderConfiguration,
    SofiaConfiguration,
)
import sofia.modules.ui.tray_agent as tray_agent
from sofia.modules.ui.control_center import ServiceAction, ServiceKind
from sofia.modules.ui.tray_agent import TrayAgentApplication


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


def test_tray_unloads_every_current_configured_model_role(monkeypatch):
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

    from sofia.platform.safe import owner_approval_ui, owner_browser
    app.config = SimpleNamespace(state_path=Path("test-only-canonical.db"))
    app._service = Service()
    approved = []
    selected_kinds = []
    monkeypatch.setattr(
        owner_approval_ui, "active_owner_credentials",
        lambda state_path, *, kind: ("test-only-security-key",),
    )
    def choose(state_path, *, kind, parent=None):
        selected_kinds.append(kind)
        return "test-only-security-key"
    monkeypatch.setattr(
        owner_approval_ui, "select_owner_credential", choose,
    )
    def signed_approval(state_path, *, capability, parameters,
                        credential_id, expires_seconds):
        assert credential_id == "test-only-security-key"
        approved.append((capability, parameters))
        return SimpleNamespace(approval_id=f"signed-{len(approved)}")
    monkeypatch.setattr(
        owner_browser, "authorize_exact_action", signed_approval,
    )

    app._service_action(
        ServiceKind.LLM_ENGINE,
        ServiceAction.UNLOAD_MODEL,
    )

    assert [call[3] for call in calls] == [
        "vendor/primary:anything",
        "vendor/open:anything",
    ]
    assert selected_kinds == ["security_key", "security_key"]
    assert [call[2] for call in calls] == ["signed-1", "signed-2"]
    assert [item[1]["model"] for item in approved] == [
        "vendor/primary:anything", "vendor/open:anything",
    ]
