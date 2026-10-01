from types import SimpleNamespace

from sofia.cognition.activity import CognitiveActivityState
from sofia.cognition.model_lifecycle import (
    CognitiveModelRole,
    ModelLifecycleStatus,
    ModelResidency,
)
from sofia.config.model import ModelLifecycleConfiguration
from sofia.ui.control_center import GameMode
from sofia.ui.tray_agent import TrayAgentApplication


def _selection(primary: str, secondary: str | None = None):
    return SimpleNamespace(
        routing_enabled=secondary is not None,
        primary=SimpleNamespace(model=primary),
        secondary=(
            None
            if secondary is None
            else SimpleNamespace(model=secondary)
        ),
        model_names=(
            (primary,)
            if secondary is None or secondary == primary
            else (primary, secondary)
        ),
    )


def test_tray_status_exposes_single_effective_model():
    app=object.__new__(TrayAgentApplication)
    app._current_model_selection=lambda: _selection("vendor/single:7b")
    app._current_model_lifecycle_policy=lambda: ModelLifecycleConfiguration()
    app._current_model_statuses=lambda selection, policy: (
        ModelLifecycleStatus(
            CognitiveModelRole.PRIMARY,
            "ollama",
            "vendor/single:7b",
            ModelResidency.UNLOADED,
        ),
    )
    app.settings_store=SimpleNamespace(
        load=lambda: SimpleNamespace(
            runtime_service_name="SofiaAdaLyra",
            llm_service_name="Ollama",
            game_mode=GameMode.AUTO,
        )
    )
    app._service_state=lambda name: "running"
    app.host_id="venus"
    app.ops=SimpleNamespace(fleet=lambda: ())
    app._last_error=None

    status=app.status()

    assert status.llm_model == "vendor/single:7b"
    assert status.llm_secondary_model is None
    assert status.cognitive_routing_enabled is False
    assert status.configured_llm_models == ("vendor/single:7b",)
    assert status.llm_primary_residency == "unloaded"
    assert status.llm_secondary_residency is None
    assert status.cognitive_auto_manage is False


def test_tray_status_exposes_primary_secondary_and_routing_mode():
    app=object.__new__(TrayAgentApplication)
    app._current_model_selection=lambda: _selection(
        "vendor/primary:9b",
        "vendor/open:4b",
    )
    app._current_model_lifecycle_policy=lambda: ModelLifecycleConfiguration(
        enabled=True,
        idle_unload_seconds=600,
    )
    app._current_model_statuses=lambda selection, policy: (
        ModelLifecycleStatus(
            CognitiveModelRole.PRIMARY,
            "ollama",
            "vendor/primary:9b",
            ModelResidency.READY,
        ),
        ModelLifecycleStatus(
            CognitiveModelRole.SECONDARY,
            "ollama",
            "vendor/open:4b",
            ModelResidency.BUSY,
        ),
    )
    app.settings_store=SimpleNamespace(
        load=lambda: SimpleNamespace(
            runtime_service_name="SofiaAdaLyra",
            llm_service_name="Ollama",
            game_mode=GameMode.AUTO,
        )
    )
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
    assert status.llm_primary_residency == "ready"
    assert status.llm_secondary_residency == "busy"
    assert status.cognitive_auto_manage is True
    assert status.cognitive_idle_unload_seconds == 600
    assert status.llm_primary_host == "venus"
    assert status.llm_secondary_host == "venus"


def test_tray_status_exposes_last_matrix_and_actual_dual_llm_execution():
    app=object.__new__(TrayAgentApplication)
    app._current_model_selection=lambda: _selection(
        "vendor/primary:9b",
        "vendor/open:4b",
    )
    app._current_model_lifecycle_policy=lambda: ModelLifecycleConfiguration(
        enabled=True,
        idle_unload_seconds=600,
    )
    app._current_model_statuses=lambda selection, policy: (
        ModelLifecycleStatus(
            CognitiveModelRole.PRIMARY,
            "ollama",
            "vendor/primary:9b",
            ModelResidency.READY,
        ),
        ModelLifecycleStatus(
            CognitiveModelRole.SECONDARY,
            "ollama",
            "vendor/open:4b",
            ModelResidency.UNLOADED,
        ),
    )
    app.settings_store=SimpleNamespace(
        load=lambda: SimpleNamespace(
            runtime_service_name="SofiaAdaLyra",
            llm_service_name="Ollama",
            game_mode=GameMode.AUTO,
        )
    )
    app._service_state=lambda name: "running"
    app.host_id="venus"
    app.ops=SimpleNamespace(fleet=lambda: ())
    app._last_error=None

    execution = SimpleNamespace(
        actual_route="verify",
        successful_steps=(
            SimpleNamespace(
                role="primary",
                model="vendor/primary:9b",
                host="venus",
            ),
            SimpleNamespace(
                role="secondary",
                model="vendor/open:4b",
                host="artemis",
            ),
            SimpleNamespace(
                role="primary",
                model="vendor/primary:9b",
                host="venus",
            ),
        ),
        last_successful_step=SimpleNamespace(
            role="primary",
            model="vendor/primary:9b",
            host="venus",
        ),
    )
    matrix = SimpleNamespace(
        turn=SimpleNamespace(
            intent=SimpleNamespace(value="action_request"),
            domains=(
                SimpleNamespace(
                    domain=SimpleNamespace(value="ops"),
                    relevance=SimpleNamespace(value=3),
                ),
                SimpleNamespace(
                    domain=SimpleNamespace(value="authority"),
                    relevance=SimpleNamespace(value=3),
                ),
            ),
        ),
        response_validation=SimpleNamespace(
            disposition=SimpleNamespace(value="pass"),
        ),
    )
    execution_trace = SimpleNamespace(cognition_execution=execution)
    app._matrix_trace_store=SimpleNamespace(
        latest=lambda: matrix,
        latest_with_execution=lambda: execution_trace,
    )

    status=app.status()

    assert status.cognitive_last_route == "verify"
    assert status.cognitive_last_model == "vendor/primary:9b"
    assert status.cognitive_last_host == "venus"
    assert status.llm_primary_host == "venus"
    assert status.llm_secondary_host == "artemis"
    assert status.matrix_last_intent == "action_request"
    assert status.matrix_last_domains == ("ops", "authority")
    assert status.matrix_last_validation == "pass"


def test_tray_busy_state_comes_from_canonical_runtime_activity():
    app=object.__new__(TrayAgentApplication)
    app._current_model_selection=lambda: _selection(
        "vendor/primary:9b",
        "vendor/open:4b",
    )
    app._current_model_lifecycle_policy=lambda: ModelLifecycleConfiguration(
        enabled=True,
        idle_unload_seconds=600,
    )
    app._current_model_statuses=lambda selection, policy: (
        ModelLifecycleStatus(
            CognitiveModelRole.PRIMARY,
            "ollama",
            "vendor/primary:9b",
            ModelResidency.READY,
        ),
        ModelLifecycleStatus(
            CognitiveModelRole.SECONDARY,
            "ollama",
            "vendor/open:4b",
            ModelResidency.UNLOADED,
        ),
    )
    app.settings_store=SimpleNamespace(
        load=lambda: SimpleNamespace(
            runtime_service_name="SofiaAdaLyra",
            llm_service_name="Ollama",
            game_mode=GameMode.AUTO,
        )
    )
    app._service_state=lambda name: "running"
    app.host_id="venus"
    app.ops=SimpleNamespace(fleet=lambda: ())
    app._last_error=None
    app._matrix_trace_store=SimpleNamespace(
        latest=lambda: None,
        latest_with_execution=lambda: None,
    )
    app._cognitive_activity_store=SimpleNamespace(
        get=lambda role: (
            SimpleNamespace(
                model="vendor/open:4b",
                state=CognitiveActivityState.BUSY,
                host="artemis",
            )
            if role == "secondary"
            else None
        )
    )

    status=app.status()

    assert status.llm_primary_residency == "ready"
    assert status.llm_primary_host == "venus"
    assert status.llm_secondary_residency == "busy"
    assert status.llm_secondary_host == "artemis"
