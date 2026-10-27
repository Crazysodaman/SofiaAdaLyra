from __future__ import annotations

from dataclasses import replace
import pytest

from sofia.modules.inference.endpoint import (
    DEFAULT_OLLAMA_ENDPOINT,
    configured_ollama_endpoint,
    validate_ollama_endpoint,
)
from sofia.modules.inference.ollama_provider import OllamaProvider
from sofia.modules.integrations.ollama import (
    OllamaAdapter,
    OllamaConnectionState,
)
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.config import create_production_configuration
from sofia.platform.config.defaults import production_storage_layout
from sofia.core.identity.model import IdentityBootstrapMode
from sofia.platform.config.user_settings import (
    RuntimeUserSettings, RuntimeUserSettingsStore,
)


def _production_state(path):
    layout = replace(
        production_storage_layout(state_path=path),
        identity_bootstrap_mode=IdentityBootstrapMode.FIRST_BOOTSTRAP,
    )
    layout.provision_from_source()
    return layout.state_path


@pytest.mark.parametrize(
    "value",
    (
        "file:///tmp/ollama.sock",
        "http://owner:secret@localhost:11434",
        "http://localhost:11434/api/tags",
        "http://localhost:11434?host=other",
        "http://localhost:99999",
        "",
    ),
)
def test_ollama_endpoint_rejects_unsafe_or_non_origin_values(value):
    with pytest.raises((TypeError, ValueError)):
        validate_ollama_endpoint(value)


def test_ollama_endpoint_is_canonical_and_has_a_stable_default():
    assert configured_ollama_endpoint({}) == DEFAULT_OLLAMA_ENDPOINT
    assert (
        configured_ollama_endpoint(
            {"SOFIA_OLLAMA_URL": " HTTPS://Inference.Example:11434/ "}
        )
        == "https://inference.example:11434"
    )


def test_provider_and_lifecycle_adapter_share_the_authoritative_endpoint(
    monkeypatch,
):
    provider_hosts = []
    lifecycle_hosts = []

    class Client:
        def __init__(self, *, host):
            provider_hosts.append(host)

    class Http:
        def __init__(self, base_url):
            lifecycle_hosts.append(base_url)

    monkeypatch.setenv("SOFIA_OLLAMA_URL", "http://inference.internal:12434")
    monkeypatch.setattr("sofia.modules.inference.ollama_provider.Client", Client)
    monkeypatch.setattr("sofia.modules.integrations.ollama.JsonHttpClient", Http)

    provider = OllamaProvider(
        ProviderConfiguration(provider="ollama", model="owner/model:exact")
    )
    adapter = OllamaAdapter()

    assert provider.endpoint == adapter.base_url == "http://inference.internal:12434"
    assert provider_hosts == lifecycle_hosts == ["http://inference.internal:12434"]


def test_host_owned_endpoint_reaches_production_configuration(tmp_path, monkeypatch):
    state = _production_state(tmp_path / "sofia.db")
    RuntimeUserSettingsStore(state).save(RuntimeUserSettings(
        ollama_endpoint="https://inference.example:12434/",
    ))
    monkeypatch.delenv("SOFIA_OLLAMA_URL", raising=False)

    configuration = create_production_configuration(state_path=state)

    assert configuration.ollama_endpoint == "https://inference.example:12434"


def test_explicit_deployment_endpoint_overrides_saved_host_endpoint(
    tmp_path, monkeypatch,
):
    state = _production_state(tmp_path / "sofia.db")
    RuntimeUserSettingsStore(state).save(RuntimeUserSettings(
        ollama_endpoint="https://saved.example:12434",
    ))
    monkeypatch.setenv("SOFIA_OLLAMA_URL", "https://deployed.example:22434/")

    configuration = create_production_configuration(state_path=state)

    assert configuration.ollama_endpoint == "https://deployed.example:22434"


class _DiagnosticHttp:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    def request(self, method, path, **kwargs):
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_diagnostic_reports_offline_then_ready_without_changing_models():
    adapter = OllamaAdapter("http://127.0.0.1:11434")
    adapter.http = _DiagnosticHttp(
        [ConnectionRefusedError(), ConnectionRefusedError()]
    )
    offline = adapter.diagnose(attempts=2, retry_delay_seconds=0)
    assert offline.state is OllamaConnectionState.OFFLINE
    assert offline.attempts == 2
    assert offline.failure_kind == "ConnectionRefusedError"
    assert offline.last_success_at is None

    adapter.http = _DiagnosticHttp(
        [{"version": "0.12.0"}, {"models": []}]
    )
    ready = adapter.diagnose(attempts=1, retry_delay_seconds=0)
    assert ready.state is OllamaConnectionState.READY
    assert ready.last_success_at is not None
    assert ready.failure_kind is None


def test_diagnostic_distinguishes_online_service_from_failed_inventory():
    adapter = OllamaAdapter("http://127.0.0.1:11434")
    adapter.http = _DiagnosticHttp(
        [{"version": "0.12.0"}, RuntimeError("malformed inventory")]
    )
    result = adapter.diagnose(attempts=1, retry_delay_seconds=0)
    assert result.state is OllamaConnectionState.ONLINE
    assert result.failure_kind == "RuntimeError"
    assert result.last_success_at is not None


def test_diagnostic_preserves_supervisor_starting_and_failed_states():
    adapter = OllamaAdapter("http://127.0.0.1:11434")
    starting = adapter.diagnose(service_state="starting")
    assert starting.state is OllamaConnectionState.STARTING
    assert starting.attempts == 0

    adapter.http = _DiagnosticHttp([ConnectionRefusedError()])
    failed = adapter.diagnose(
        service_state="failed", attempts=1, retry_delay_seconds=0
    )
    assert failed.state is OllamaConnectionState.FAILED
