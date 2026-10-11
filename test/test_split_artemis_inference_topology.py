"""Deferred production topology admission for future Artemis/Venus split.

No host is reconfigured, enrolled, started, or migrated by these contracts.
"""
from dataclasses import replace

import pytest

from sofia.composition.engines import create_cognitive_engine, create_model_lifecycle
from sofia.composition.split_topology import (
    SplitInferenceDeployment,
    selected_split_deployment,
    validate_split_inference_runtime,
)
from sofia.distributed.inference_client import ConfiguredRemoteInferenceClient
from sofia.config.model import (
    FleetCognitionConfiguration,
    ProviderConfiguration,
    CognitiveRoutingConfiguration,
)
from test.test_memory_runtime_wiring import _configuration


class InsecureRemoteWorker:
    def infer(self, *_args):
        raise ConnectionError("An unpinned transport is never trusted")


def _configured_transport():
    # Validate type-level composition without opening any mTLS connections.
    return object.__new__(ConfiguredRemoteInferenceClient)


def _artemis(tmp_path, **fleet_overrides):
    fleet = FleetCognitionConfiguration(
        enabled=True,
        local_fallback=False,
        auto_provision_models=False,
        gpu_required=True,
        allowed_host_ids=("Venus",),
        **fleet_overrides,
    )
    return replace(
        _configuration(tmp_path),
        provider=ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
        fleet_cognition=fleet,
    )


def _deployment():
    return SplitInferenceDeployment(
        runtime_host_id="Artemis", gpu_worker_host_id="Venus",
    )


def test_split_deployment_is_never_implicitly_enabled():
    assert selected_split_deployment({}) is None
    with pytest.raises(ValueError, match="explicit role"):
        selected_split_deployment({"SOFIA_SPLIT_GPU_HOST_ID": "Venus"})
    with pytest.raises(ValueError, match="unknown"):
        selected_split_deployment({"SOFIA_SPLIT_INFERENCE_ROLE": "auto"})
    assert selected_split_deployment({
        "SOFIA_SPLIT_INFERENCE_ROLE": "artemis_runtime",
        "SOFIA_SPLIT_RUNTIME_HOST_ID": "Artemis",
        "SOFIA_SPLIT_GPU_HOST_ID": "Venus",
    }) == _deployment()
    with pytest.raises(ValueError, match="distinct"):
        SplitInferenceDeployment("Venus", "Venus")


def test_artemis_accepts_only_exact_remote_worker_without_fallback(tmp_path):
    cfg = _artemis(tmp_path)
    validate_split_inference_runtime(
        configuration=cfg, local_host_id="Artemis",
        remote_inference_client=_configured_transport(),
        deployment=_deployment(),
    )


@pytest.mark.parametrize("local_host", ("Venus", "unknown", None))
def test_other_host_cannot_claim_artemis_runtime_role(tmp_path, local_host):
    with pytest.raises(PermissionError, match="authorized host"):
        validate_split_inference_runtime(
            configuration=_artemis(tmp_path), local_host_id=local_host,
            remote_inference_client=_configured_transport(),
            deployment=_deployment(),
        )


@pytest.mark.parametrize("replacement", (
    FleetCognitionConfiguration(
        enabled=True, local_fallback=True, allowed_host_ids=("Venus",),
    ),
    FleetCognitionConfiguration(
        enabled=True, allowed_host_ids=("OtherGPU",),
    ),
    FleetCognitionConfiguration(
        enabled=True, allowed_host_ids=("Venus", "OtherGPU"),
    ),
    FleetCognitionConfiguration(
        enabled=True, auto_provision_models=True,
        allowed_host_ids=("Venus",),
    ),
    FleetCognitionConfiguration(
        enabled=False, allowed_host_ids=("Venus",),
    ),
))
def test_unsafe_worker_placement_is_refused(tmp_path, replacement):
    cfg = replace(_artemis(tmp_path), fleet_cognition=replacement)
    with pytest.raises((PermissionError, ValueError)):
        validate_split_inference_runtime(
            configuration=cfg, local_host_id="Artemis",
            remote_inference_client=_configured_transport(),
            deployment=_deployment(),
        )


def test_no_remote_mtls_transport_means_no_cognitive_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("SOFIA_SPLIT_INFERENCE_ROLE", "artemis_runtime")
    monkeypatch.setenv("SOFIA_SPLIT_RUNTIME_HOST_ID", "Artemis")
    monkeypatch.setenv("SOFIA_SPLIT_GPU_HOST_ID", "Venus")
    with pytest.raises(ValueError, match="pinned-mTLS"):
        create_cognitive_engine(
            _artemis(tmp_path), local_host_id="Artemis",
            remote_inference_client=None,
        )


def test_operator_rejects_automatic_alternate_model_route(tmp_path):
    cfg = replace(
        _artemis(tmp_path),
        routing=CognitiveRoutingConfiguration(
            enabled=True,
            primary=ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
            secondary=ProviderConfiguration(provider="ollama", model="qwen3.5:4b"),
            fallback_enabled=True,
        ),
    )
    with pytest.raises(PermissionError, match="alternate-model"):
        validate_split_inference_runtime(
            configuration=cfg, local_host_id="Artemis",
            remote_inference_client=_configured_transport(),
            deployment=_deployment(),
        )


def test_remote_only_configuration_rejects_local_provider(tmp_path):
    cfg = replace(
        _artemis(tmp_path),
        provider=ProviderConfiguration(provider="rule", model="rules"),
    )
    with pytest.raises(PermissionError, match="Ollama"):
        validate_split_inference_runtime(
            configuration=cfg, local_host_id="Artemis",
            remote_inference_client=_configured_transport(),
            deployment=_deployment(),
        )

def test_arbitrary_remote_callable_cannot_impersonate_pinned_transport(tmp_path):
    with pytest.raises(ValueError, match="pinned-mTLS"):
        validate_split_inference_runtime(
            configuration=_artemis(tmp_path),
            local_host_id="Artemis",
            remote_inference_client=InsecureRemoteWorker(),
            deployment=_deployment(),
        )


def test_non_gpu_remote_placement_is_refused(tmp_path):
    cfg = replace(
        _artemis(tmp_path),
        fleet_cognition=FleetCognitionConfiguration(
            enabled=True, allowed_host_ids=("Venus",),
            gpu_required=False,
        ),
    )
    with pytest.raises(PermissionError, match="GPU worker"):
        validate_split_inference_runtime(
            configuration=cfg,
            local_host_id="Artemis",
            remote_inference_client=_configured_transport(),
            deployment=_deployment(),
        )
