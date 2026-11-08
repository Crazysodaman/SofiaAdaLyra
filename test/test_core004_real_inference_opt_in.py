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
    baseline.test_pinned_mtls_core_link_runs_real_remote_conversation_without_local_core(
        tmp_path,
    )
