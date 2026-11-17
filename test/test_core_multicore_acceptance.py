"""Disposable end-to-end multi-Core acceptance path without real installation."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from sofia.core.multicore.acceptance import (
    AcceptanceDenied,
    AcceptanceError,
    AcceptanceEvidence,
    AcceptanceHarness,
    AcceptanceStage,
    AcceptanceStatus,
    ActivationEvidence,
    DisposableCoreFixture,
    FileAcceptancePersistence,
    LoadedCoreAssets,
    RoutingReceipt,
)
from sofia.core.multicore.contracts import ChannelKind
from sofia.core.multicore.inference import (
    InMemoryCoreInferenceJournal, MultiCoreInference,
)
from sofia.core.multicore.management import InMemoryCoreDefinitionSource
from sofia.platform.inference import (
    BackendOutput, ModelResidencyTracker, ProviderPolicy, StaticCapacitySource,
)
from sofia.platform.inference.gaming import GamingPolicy
from sofia.platform.ops.activity import ActivityMode
from test._shared_inference_support import (
    MODEL, AdmissionStub, budgets, capacity, footprint,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class EchoBackend:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, call):
        self.calls.append(call)
        return BackendOutput(
            model=call.model,
            text="text-path-ok",
            prompt_tokens=12,
            generated_tokens=3,
            time_to_first_token_ms=1.0,
            total_duration_ms=5.0,
            simulated=True,
        )

    def cancel(self, job_id: str) -> bool:
        return True


def build_inference(journal, backend=None) -> MultiCoreInference:
    return MultiCoreInference(
        backend=backend if backend is not None else EchoBackend(),
        admission=AdmissionStub(),
        models={MODEL: footprint()},
        policy=ProviderPolicy.local_only((MODEL,)),
        residency=ModelResidencyTracker((MODEL,)),
        capacity=StaticCapacitySource(capacity(activity=ActivityMode.IDLE)),
        budgets=budgets(),
        gaming=GamingPolicy(allow_background_preload=True),
        clock=lambda: 1_000.0,
        journal=journal,
    )


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls = []

    def authorize(self, *, operation, core_id, generation, fingerprint):
        self.calls.append((operation, core_id, generation, fingerprint))
        return self.allowed


class Lifecycle:
    def __init__(self) -> None:
        self.calls = []

    def activate(self, *, core_id, generation):
        self.calls.append((core_id, generation))
        return ActivationEvidence(
            core_id=core_id,
            generation=generation,
            state="active",
            observed_at=NOW,
            evidence=AcceptanceEvidence.SIMULATED,
        )


class Loader:
    def __init__(self, *, wrong_core: bool = False) -> None:
        self.wrong_core = wrong_core
        self.calls = []

    def load(self, *, fixture: DisposableCoreFixture):
        self.calls.append(fixture.core_id)
        return LoadedCoreAssets(
            core_id=(uuid4() if self.wrong_core else fixture.core_id),
            generation=fixture.generation,
            display_name=fixture.full_name,
            constitution=fixture.constitution_text,
            constitution_sha256=fixture.constitution_sha256,
            memory_owner_core_id=fixture.core_id,
            memory_entries=("owner preference: concise",),
        )


class Router:
    def __init__(self) -> None:
        self.calls = []

    def route(self, *, sender, channel, body):
        self.calls.append((sender, channel, body))
        return RoutingReceipt(
            message_id=f"message-{uuid4().hex}",
            sender_core_id=sender.core_id,
            channel=channel,
            body=body,
            routed=True,
        )


class Safety:
    def __init__(self, stopped: bool = False) -> None:
        self.stopped = stopped

    def is_operator_stopped(self) -> bool:
        return self.stopped


def harness(
    tmp_path: Path, *, definitions=None, authorizer=None, lifecycle=None,
    loader=None, router=None, inference=None, journal=None,
    persistence=None, safety=None, restart=None,
) -> AcceptanceHarness:
    journal = journal if journal is not None else InMemoryCoreInferenceJournal()
    return AcceptanceHarness(
        definitions=(
            definitions if definitions is not None
            else InMemoryCoreDefinitionSource()
        ),
        authorizer=authorizer if authorizer is not None else Authorizer(),
        lifecycle=lifecycle if lifecycle is not None else Lifecycle(),
        identity_loader=loader if loader is not None else Loader(),
        channel_router=router if router is not None else Router(),
        inference=(
            inference if inference is not None else build_inference(journal)
        ),
        persistence=(
            persistence if persistence is not None
            else FileAcceptancePersistence(tmp_path / "persistence")
        ),
        safety=safety,
        restart_inference=restart,
        clock=lambda: NOW,
    )


def fixture(tmp_path: Path) -> DisposableCoreFixture:
    return DisposableCoreFixture.create(
        tmp_path / "mack",
        platform_id="platform:test",
        core_number=2,
        full_name="Mack",
        nickname="Mack",
        model=MODEL,
    )


def test_disposable_end_to_end_text_path_and_simulated_restart(tmp_path) -> None:
    journal = InMemoryCoreInferenceJournal()
    backend = EchoBackend()
    router = Router()
    lifecycle = Lifecycle()
    authorizer = Authorizer()
    definitions = InMemoryCoreDefinitionSource()
    service = harness(
        tmp_path,
        definitions=definitions,
        authorizer=authorizer,
        lifecycle=lifecycle,
        router=router,
        inference=build_inference(journal, backend=backend),
        journal=journal,
        safety=Safety(False),
        restart=lambda: build_inference(journal),
    )
    report = service.run(fixture(tmp_path))

    assert report.ok is True
    assert report.real_installation is False
    assert report.voice_avatar_required is False
    assert report.restart_simulated is True
    assert report.evidence is AcceptanceEvidence.SIMULATED
    assert report.step(AcceptanceStage.DEFINITION).status is AcceptanceStatus.PASSED
    assert report.step(AcceptanceStage.INFERENCE).status is AcceptanceStatus.PASSED
    assert report.step(AcceptanceStage.RESTART_RECOVERY).status is (
        AcceptanceStatus.PASSED
    )
    assert backend.calls and backend.calls[0].request.core.core_id == report.core_id
    assert router.calls[0][1] is ChannelKind.GENERAL
    assert lifecycle.calls == [(report.core_id, report.generation)]
    assert [call[0] for call in authorizer.calls] == [
        "activate", "channel.route", "inference.submit",
    ]
    assert definitions.definitions()


def test_identity_mismatch_fails_closed_before_inference(tmp_path) -> None:
    backend = EchoBackend()
    journal = InMemoryCoreInferenceJournal()
    service = harness(
        tmp_path,
        loader=Loader(wrong_core=True),
        inference=build_inference(journal, backend=backend),
        journal=journal,
    )
    with pytest.raises(AcceptanceError, match="identity"):
        service.run(fixture(tmp_path))
    assert backend.calls == []


def test_missing_asset_definition_fails_closed_without_activation(tmp_path) -> None:
    core = fixture(tmp_path)
    core.personality_path.unlink()
    lifecycle = Lifecycle()
    backend = EchoBackend()
    journal = InMemoryCoreInferenceJournal()
    service = harness(
        tmp_path,
        lifecycle=lifecycle,
        inference=build_inference(journal, backend=backend),
        journal=journal,
    )
    with pytest.raises(AcceptanceError):
        service.run(core)
    assert lifecycle.calls == []
    assert backend.calls == []


def test_denied_activation_and_operator_stop_never_activate_or_infer(
    tmp_path,
) -> None:
    core = fixture(tmp_path)
    lifecycle = Lifecycle()
    backend = EchoBackend()
    journal = InMemoryCoreInferenceJournal()

    denied = harness(
        tmp_path,
        authorizer=Authorizer(False),
        lifecycle=lifecycle,
        inference=build_inference(journal, backend=backend),
        journal=journal,
    )
    with pytest.raises(AcceptanceDenied):
        denied.run(core)
    assert lifecycle.calls == []
    assert backend.calls == []

    stopped = harness(
        tmp_path / "stopped",
        lifecycle=lifecycle,
        inference=build_inference(
            InMemoryCoreInferenceJournal(), backend=backend,
        ),
        journal=InMemoryCoreInferenceJournal(),
        safety=Safety(True),
    )
    stopped_core = fixture(tmp_path / "stopped")
    with pytest.raises(AcceptanceDenied, match="STOP"):
        stopped.run(stopped_core)
    assert lifecycle.calls == []
    assert backend.calls == []


def test_missing_voice_and_avatar_do_not_block_text(tmp_path) -> None:
    core = fixture(tmp_path)
    assert core.voice_available is False
    assert core.avatar_available is False
    journal = InMemoryCoreInferenceJournal()
    backend = EchoBackend()
    service = harness(
        tmp_path,
        inference=build_inference(journal, backend=backend),
        journal=journal,
        restart=lambda: build_inference(journal),
    )
    report = service.run(core)
    assert report.ok is True
    assert report.step(AcceptanceStage.INFERENCE).status is (
        AcceptanceStatus.PASSED
    )
    assert report.voice_avatar_required is False
    assert backend.calls


def test_missing_definition_file_is_rejected(tmp_path) -> None:
    core = fixture(tmp_path)
    core.definition_path.unlink()
    journal = InMemoryCoreInferenceJournal()
    backend = EchoBackend()
    service = harness(
        tmp_path,
        inference=build_inference(journal, backend=backend),
        journal=journal,
    )
    with pytest.raises(AcceptanceError, match="definition file"):
        service.run(core)
    assert backend.calls == []
