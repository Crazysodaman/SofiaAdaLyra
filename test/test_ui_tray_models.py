from types import SimpleNamespace

from sofia.ui.control_center import GameMode
from sofia.ui.tray_agent import TrayAgentApplication


def _routing(primary: str, secondary: str):
    return SimpleNamespace(
        enabled=True,
        primary=SimpleNamespace(model=primary),
        secondary=SimpleNamespace(model=secondary),
    )


def test_tray_reads_single_model_from_effective_configuration():
    app=object.__new__(TrayAgentApplication)
    app.config=SimpleNamespace(
        provider=SimpleNamespace(model="vendor/single:7b"),
        routing=None,
    )

    assert app._configured_llm_models() == ("vendor/single:7b",)


def test_tray_reads_both_models_from_effective_routing_configuration():
    app=object.__new__(TrayAgentApplication)
    app.config=SimpleNamespace(
        provider=SimpleNamespace(model="legacy/ignored:1b"),
        routing=_routing("vendor/primary:9b", "vendor/open:4b"),
    )

    assert app._configured_llm_models() == (
        "vendor/primary:9b",
        "vendor/open:4b",
    )


def test_tray_status_exposes_primary_secondary_and_routing_mode():
    app=object.__new__(TrayAgentApplication)
    app.config=SimpleNamespace(
        provider=SimpleNamespace(model="legacy/ignored:1b"),
        routing=_routing("vendor/primary:9b", "vendor/open:4b"),
    )
    app.settings_store=SimpleNamespace(
        load=lambda: SimpleNamespace(
            runtime_service_name="SofiaAdaLyra",
            llm_service_name="Ollama",
            game_mode=GameMode.AUTO,
        )
    )
    app._runtime_authority=SimpleNamespace(current=lambda: None)
    app._service_state=lambda name: "running"
    app.host_id="venus"
    app.ops=SimpleNamespace(fleet=lambda: ())
    app._last_error=None

    status=app.status()

    assert status.llm_model == "vendor/primary:9b"
    assert status.llm_secondary_model == "vendor/open:4b"
    assert status.cognitive_routing_enabled is True
    assert status.configured_llm_models == (
        "vendor/primary:9b",
        "vendor/open:4b",
    )
    assert status.cognition_mode_label == "Dual-model routing"
