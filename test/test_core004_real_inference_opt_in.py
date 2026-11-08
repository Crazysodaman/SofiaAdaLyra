"""Opt-in CORE-004 real-inference exercise using disposable Core state.

Do not run on the owner's production Core host.  The test borrows the already
implemented real mTLS + desktop conversation acceptance path, replacing only
its deterministic test provider with an explicit loopback Ollama provider.

Normal CI skips this test.  Set both SOFIA_CORE004_REAL_INFERENCE=1 and
SOFIA_CORE004_OLLAMA_MODEL to explicitly request real inference.
"""
from dataclasses import replace
import os
from urllib.parse import urlparse

import pytest

from sofia.platform.config.model import ProviderConfiguration
from test import test_core_link_conversation as baseline


@pytest.mark.skipif(
    os.environ.get("SOFIA_CORE004_REAL_INFERENCE") != "1",
    reason="real Ollama inference requires explicit isolated opt-in",
)
def test_core004_disposable_pinned_mtls_desktop_uses_actual_ollama(
    tmp_path, monkeypatch,
):
    model = os.environ.get("SOFIA_CORE004_OLLAMA_MODEL", "").strip()
    assert model, "Set SOFIA_CORE004_OLLAMA_MODEL to an installed model"
    endpoint = os.environ.get(
        "SOFIA_CORE004_OLLAMA_ENDPOINT", "http://127.0.0.1:11434",
    ).strip()
    parsed = urlparse(endpoint)
    assert (
        parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        and parsed.port is not None
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    ), "CORE-004 real inference may call only an explicit loopback Ollama"
    original_configuration = baseline.configuration

    def disposable_ollama_configuration(path):
        isolated = original_configuration(path)
        assert path == tmp_path
        assert isolated.state_path == tmp_path / "sofia.db"
        return replace(
            isolated,
            provider=ProviderConfiguration(provider="ollama", model=model),
            ollama_endpoint=endpoint,
        )

    monkeypatch.setattr(baseline, "configuration", disposable_ollama_configuration)

    # The ordinary regression uses a 20s test-provider HTTPS timeout. Real
    # cold-start and model generation require an explicitly larger bound,
    # without weakening the normal CI test or changing production defaults.
    actual_client_class = baseline.PinnedCoreLinkClient

    def long_inference_client(*args, **kwargs):
        if kwargs.get("timeout_seconds") == 20:
            kwargs["timeout_seconds"] = 120
        return actual_client_class(*args, **kwargs)

    monkeypatch.setattr(baseline, "PinnedCoreLinkClient", long_inference_client)

    # Prove that the Core path actually called the installed Ollama model.
    # A generated desktop message without this evidence could have come from
    # a deterministic/fixture branch and is NOT real-inference acceptance.
    from ollama import Client
    from sofia.modules.inference.ollama_provider import OllamaProvider

    observed: list[tuple[str, bool]] = []

    class ObservedOllamaClient:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def chat(self, **kwargs):
            result = self.wrapped.chat(**kwargs)
            content = getattr(getattr(result, "message", None), "content", None)
            observed.append((kwargs.get("model"), isinstance(content, str) and bool(content.strip())))
            return result

    def monitored_factory(requested_endpoint):
        if requested_endpoint != endpoint:
            raise AssertionError("Ollama was redirected outside the isolated endpoint")
        # Keep the provisional per-I/O bound; this is not a complete 120s
        # wall-clock budget or a worker lease certification.
        return ObservedOllamaClient(Client(host=endpoint, timeout=45.0))

    monkeypatch.setattr(OllamaProvider, "_new_client", staticmethod(monitored_factory))
    baseline.test_pinned_mtls_core_link_runs_real_remote_conversation_without_local_core(
        tmp_path,
    )
    assert observed, "No genuine Ollama.chat call was observed"
    assert all(
        observed_model == model and nonblank for observed_model, nonblank in observed
    ), "Ollama model changed or returned no generated text"
