"""Disposable end-to-end acceptance fixture for independent Aegis Cores.

The fixture creates a definition payload and personal asset files under a
caller-owned temporary directory.  It then exercises registration, authorized
activation, identity/constitution/memory loading, channel routing, injected
text inference, persistence and a simulated restart.  Nothing is installed,
downloaded, signed by a production key or launched as a real process.

Voice and avatar assets are deliberately optional: their absence never blocks
the text path.  Failures are fail-closed; a report is returned only after every
required stage completed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Callable, Mapping, Protocol
from uuid import UUID, uuid4

from sofia.core.multicore.contracts import ChannelKind, LifecycleState
from sofia.core.multicore.management import (
    CoreDefinitionView, InMemoryCoreDefinitionSource,
)
from sofia.platform.inference import (
    CoreIdentity as InferenceCoreIdentity,
    ModelIdentity, PromptMessage, PromptRole, WorkloadClass,
)
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreAssetReference, CoreDefinition
from sofia.sdk.identity import AegisIdentity, IdentityKind

ACCEPTANCE_SCHEMA = "aegis.core.multicore.acceptance.v1"
_DEFINITION_FILE = "definition.json"
_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class AcceptanceError(RuntimeError):
    """A required disposable acceptance stage failed."""


class AcceptanceDenied(PermissionError):
    """Authorization or the operator STOP boundary denied acceptance work."""


class AcceptanceStage(str, Enum):
    DEFINITION = "definition"
    REGISTRATION = "registration"
    ACTIVATION = "activation"
    IDENTITY_CONSTITUTION_MEMORY = "identity_constitution_memory"
    CHANNEL_ROUTING = "channel_routing"
    INFERENCE = "inference"
    PERSISTENCE = "persistence"
    RESTART_RECOVERY = "restart_recovery"


class AcceptanceStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AcceptanceEvidence(str, Enum):
    SIMULATED = "simulated"
    OBSERVED = "observed"


@dataclass(frozen=True, slots=True)
class AcceptanceStep:
    stage: AcceptanceStage
    status: AcceptanceStatus
    detail: str
    evidence: AcceptanceEvidence = AcceptanceEvidence.SIMULATED


@dataclass(frozen=True, slots=True)
class AcceptanceReport:
    schema: str
    core_id: UUID
    platform_id: str
    core_number: int
    full_name: str
    generation: int
    model: ModelIdentity
    steps: tuple[AcceptanceStep, ...]
    evidence: AcceptanceEvidence = AcceptanceEvidence.SIMULATED
    real_installation: bool = False
    voice_avatar_required: bool = False
    restart_simulated: bool = False

    @property
    def ok(self) -> bool:
        return all(
            step.status in {AcceptanceStatus.PASSED, AcceptanceStatus.SKIPPED}
            for step in self.steps
        )

    def step(self, stage: AcceptanceStage) -> AcceptanceStep | None:
        return next(
            (item for item in self.steps if item.stage is stage), None,
        )


@dataclass(frozen=True, slots=True)
class DisposableCoreFixture:
    root: Path
    core_id: UUID
    platform_id: str
    core_number: int
    full_name: str
    nickname: str | None
    generation: int
    model: ModelIdentity
    definition: CoreDefinition
    definition_path: Path
    constitution_path: Path
    personality_path: Path
    constitution_text: str
    personality_text: str
    constitution_sha256: str
    personality_sha256: str
    voice_available: bool = False
    avatar_available: bool = False

    @classmethod
    def create(
        cls, root: Path | str, *,
        core_id: UUID | None = None,
        platform_id: str,
        core_number: int,
        full_name: str,
        nickname: str | None = None,
        generation: int = 1,
        model: ModelIdentity,
        constitution_text: str = "Sofía Ada Lyra constitution fixture.",
        personality_text: str = "Independent Core personality fixture.",
        voice_available: bool = False,
        avatar_available: bool = False,
    ) -> "DisposableCoreFixture":
        """Write one disposable definition and personal asset set.

        No installer, registry, service, model or network endpoint is touched.
        """
        if not isinstance(platform_id, str) or not platform_id.strip():
            raise ValueError("platform_id is required")
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        if type(core_number) is not int or core_number < 1:
            raise ValueError("core_number must be positive")
        if type(generation) is not int or generation < 1:
            raise ValueError("generation must be positive")
        if not isinstance(full_name, str) or not full_name.strip():
            raise ValueError("full_name is required")
        if not isinstance(constitution_text, str) or not constitution_text.strip():
            raise ValueError("constitution_text is required")
        if not isinstance(personality_text, str) or not personality_text.strip():
            raise ValueError("personality_text is required")
        selected_id = core_id if core_id is not None else uuid4()
        if not isinstance(selected_id, UUID) or selected_id.int == 0:
            raise ValueError("core_id must be a nonzero UUID")
        directory = Path(root)
        assets = directory / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        constitution = assets / "constitution.md"
        personality = assets / "personality.md"
        constitution.write_text(constitution_text, encoding="utf-8")
        personality.write_text(personality_text, encoding="utf-8")
        constitution_digest = sha256(constitution.read_bytes()).hexdigest()
        personality_digest = sha256(personality.read_bytes()).hexdigest()
        definition = CoreDefinition(
            identity=AegisIdentity(IdentityKind.CORE, selected_id),
            name=full_name,
            revision=1,
            runtime_release_sha256="0" * 64,
            sdk_protocol=SDK_PROTOCOL_VERSION,
            constitution=CoreAssetReference(
                "constitution.md",
                constitution_digest,
                constitution.stat().st_size,
            ),
            personality=CoreAssetReference(
                "personality.md",
                personality_digest,
                personality.stat().st_size,
            ),
        )
        definition_path = directory / _DEFINITION_FILE
        definition_path.write_bytes(definition.canonical_bytes)
        return cls(
            root=directory,
            core_id=selected_id,
            platform_id=platform_id,
            core_number=core_number,
            full_name=full_name,
            nickname=nickname,
            generation=generation,
            model=model,
            definition=definition,
            definition_path=definition_path,
            constitution_path=constitution,
            personality_path=personality,
            constitution_text=constitution_text,
            personality_text=personality_text,
            constitution_sha256=constitution_digest,
            personality_sha256=personality_digest,
            voice_available=voice_available,
            avatar_available=avatar_available,
        )

    def management_view(
        self, lifecycle: LifecycleState = LifecycleState.DEFINED,
    ) -> CoreDefinitionView:
        return CoreDefinitionView(
            core_id=self.core_id,
            full_name=self.full_name,
            core_number=self.core_number,
            generation=self.generation,
            lifecycle=lifecycle,
            nickname=self.nickname,
            identity_concept="Disposable Aegis Core acceptance fixture",
            model=self.model,
            constitution_sha256=self.constitution_sha256,
            definition_revision=self.definition.revision,
            voice_available=self.voice_available,
            avatar_available=self.avatar_available,
        )

    def inference_identity(self) -> InferenceCoreIdentity:
        return InferenceCoreIdentity(
            self.core_id,
            self.platform_id,
            self.generation,
            self.full_name,
        )


@dataclass(frozen=True, slots=True)
class ActivationEvidence:
    core_id: UUID
    generation: int
    state: str
    observed_at: datetime
    evidence: AcceptanceEvidence = AcceptanceEvidence.SIMULATED


@dataclass(frozen=True, slots=True)
class LoadedCoreAssets:
    core_id: UUID
    generation: int
    display_name: str
    constitution: str
    constitution_sha256: str
    memory_owner_core_id: UUID
    memory_entries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoutingReceipt:
    message_id: str
    sender_core_id: UUID
    channel: ChannelKind
    body: str
    routed: bool


class AcceptanceAuthorizer(Protocol):
    def authorize(
        self, *, operation: str, core_id: UUID, generation: int,
        fingerprint: str,
    ) -> bool:
        ...


class AcceptanceLifecycle(Protocol):
    def activate(
        self, *, core_id: UUID, generation: int,
    ) -> ActivationEvidence:
        ...


class IdentityConstitutionLoader(Protocol):
    def load(self, *, fixture: DisposableCoreFixture) -> LoadedCoreAssets:
        ...


class ChannelRouter(Protocol):
    def route(
        self, *, sender: InferenceCoreIdentity, channel: ChannelKind,
        body: str,
    ) -> RoutingReceipt:
        ...


class AcceptancePersistence(Protocol):
    def save(self, key: str, payload: Mapping[str, object]) -> None:
        ...

    def load(self, key: str) -> Mapping[str, object] | None:
        ...


class AcceptanceSafety(Protocol):
    def is_operator_stopped(self) -> bool:
        ...


class FileAcceptancePersistence:
    """Bounded JSON files under a disposable acceptance directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if type(key) is not str or _SAFE_KEY.fullmatch(key) is None:
            raise ValueError("acceptance persistence key must be a safe identifier")
        return self.root / f"{key}.json"

    def save(self, key: str, payload: Mapping[str, object]) -> None:
        if not isinstance(payload, Mapping):
            raise TypeError("acceptance payload must be a mapping")
        path = self._path(key)
        encoded = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        temporary = path.with_suffix(".json.tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, path)

    def load(self, key: str) -> Mapping[str, object] | None:
        path = self._path(key)
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise AcceptanceError("acceptance persistence is not an object")
        return value


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AcceptanceError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


class AcceptanceHarness:
    """Runs the disposable multi-Core acceptance path with injected adapters."""

    def __init__(
        self, *,
        definitions: InMemoryCoreDefinitionSource,
        authorizer: AcceptanceAuthorizer,
        lifecycle: AcceptanceLifecycle,
        identity_loader: IdentityConstitutionLoader,
        channel_router: ChannelRouter,
        inference,
        persistence: AcceptancePersistence,
        safety: AcceptanceSafety | None = None,
        restart_inference: Callable[[], object] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(definitions, InMemoryCoreDefinitionSource):
            raise TypeError("definitions must be InMemoryCoreDefinitionSource")
        if not callable(getattr(authorizer, "authorize", None)):
            raise TypeError("authorizer must expose authorize()")
        if not callable(getattr(lifecycle, "activate", None)):
            raise TypeError("lifecycle must expose activate()")
        if not callable(getattr(identity_loader, "load", None)):
            raise TypeError("identity loader must expose load()")
        if not callable(getattr(channel_router, "route", None)):
            raise TypeError("channel router must expose route()")
        if not callable(getattr(inference, "register_core", None)) or not callable(
            getattr(inference, "submit", None)
        ):
            raise TypeError("inference must be a MultiCoreInference service")
        for method in ("save", "load"):
            if not callable(getattr(persistence, method, None)):
                raise TypeError("persistence must expose save() and load()")
        if safety is not None and not callable(
            getattr(safety, "is_operator_stopped", None)
        ):
            raise TypeError("safety must expose is_operator_stopped()")
        self.definitions = definitions
        self.authorizer = authorizer
        self.lifecycle = lifecycle
        self.identity_loader = identity_loader
        self.channel_router = channel_router
        self.inference = inference
        self.persistence = persistence
        self.safety = safety
        self.restart_inference = restart_inference
        self._clock = clock if callable(clock) else (
            lambda: datetime.now(timezone.utc)
        )

    def _now(self) -> datetime:
        return _aware(self._clock(), "acceptance clock")

    def _check_stop(self) -> None:
        if self.safety is not None:
            try:
                stopped = self.safety.is_operator_stopped()
            except Exception as exc:
                raise AcceptanceDenied(
                    "SAFE/STOP evidence is unavailable"
                ) from exc
            if stopped is not False:
                raise AcceptanceDenied("operator STOP is active")

    def _load_definition(self, fixture: DisposableCoreFixture) -> CoreDefinition:
        path = fixture.definition_path
        if not path.is_file():
            raise AcceptanceError("disposable definition file is missing")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            definition = CoreDefinition.from_payload(payload)
        except Exception as exc:
            raise AcceptanceError(
                "disposable definition is invalid or not canonical"
            ) from exc
        if definition.identity.identity_id != fixture.core_id:
            raise AcceptanceError("definition identity differs from fixture")
        if definition.name != fixture.full_name:
            raise AcceptanceError("definition name differs from fixture")
        if definition.digest != fixture.definition.digest:
            raise AcceptanceError("definition digest differs from fixture")
        for reference, digest_value, path_value in (
            (
                definition.constitution,
                fixture.constitution_sha256,
                fixture.constitution_path,
            ),
            (
                definition.personality,
                fixture.personality_sha256,
                fixture.personality_path,
            ),
        ):
            if not path_value.is_file():
                raise AcceptanceError("disposable personal asset is missing")
            raw = path_value.read_bytes()
            if len(raw) != reference.size_bytes:
                raise AcceptanceError("personal asset size differs")
            if sha256(raw).hexdigest() != reference.sha256:
                raise AcceptanceError("personal asset digest differs")
            if reference.sha256 != digest_value:
                raise AcceptanceError("fixture asset digest differs")
        return definition

    def _register(self, fixture: DisposableCoreFixture) -> None:
        self.definitions.register(
            fixture.management_view(LifecycleState.DEFINED)
        )
        self.definitions.replace(
            fixture.management_view(LifecycleState.REGISTERED)
        )

    def _activate(
        self, fixture: DisposableCoreFixture, definition: CoreDefinition,
    ) -> ActivationEvidence:
        self._check_stop()
        if self.authorizer.authorize(
            operation="activate",
            core_id=fixture.core_id,
            generation=fixture.generation,
            fingerprint=definition.digest,
        ) is not True:
            raise AcceptanceDenied("Core activation was not authorized")
        evidence = self.lifecycle.activate(
            core_id=fixture.core_id, generation=fixture.generation,
        )
        if not isinstance(evidence, ActivationEvidence):
            raise AcceptanceError("activation returned an invalid receipt")
        if (
            evidence.core_id != fixture.core_id
            or evidence.generation != fixture.generation
            or evidence.state.casefold() not in {"active", "running"}
        ):
            raise AcceptanceError("activation did not establish the exact Core")
        self.definitions.replace(
            fixture.management_view(LifecycleState.ACTIVE)
        )
        return evidence

    def _load_assets(
        self, fixture: DisposableCoreFixture,
    ) -> LoadedCoreAssets:
        self._check_stop()
        assets = self.identity_loader.load(fixture=fixture)
        if not isinstance(assets, LoadedCoreAssets):
            raise AcceptanceError("identity loader returned invalid assets")
        if (
            assets.core_id != fixture.core_id
            or assets.generation != fixture.generation
        ):
            raise AcceptanceError("loaded identity does not match the Core")
        if assets.display_name != fixture.full_name:
            raise AcceptanceError("loaded identity display name differs")
        if not isinstance(assets.constitution, str):
            raise AcceptanceError("constitution must be text")
        if sha256(assets.constitution.encode("utf-8")).hexdigest() != (
            fixture.constitution_sha256
        ):
            raise AcceptanceError("loaded constitution digest differs")
        if assets.constitution_sha256 != fixture.constitution_sha256:
            raise AcceptanceError("constitution evidence digest differs")
        if assets.memory_owner_core_id != fixture.core_id:
            raise AcceptanceError(
                "loaded memory belongs to another Core; refusing leakage"
            )
        if any(not isinstance(item, str) for item in assets.memory_entries):
            raise AcceptanceError("memory entries must be text")
        return assets

    def _route(
        self, fixture: DisposableCoreFixture, assets: LoadedCoreAssets,
    ) -> RoutingReceipt:
        self._check_stop()
        if self.authorizer.authorize(
            operation="channel.route",
            core_id=fixture.core_id,
            generation=fixture.generation,
            fingerprint=fixture.constitution_sha256,
        ) is not True:
            raise AcceptanceDenied("channel routing was not authorized")
        body = f"{fixture.full_name}: {assets.memory_entries[0] if assets.memory_entries else 'hello'}"
        receipt = self.channel_router.route(
            sender=fixture.inference_identity(),
            channel=ChannelKind.GENERAL,
            body=body,
        )
        if not isinstance(receipt, RoutingReceipt):
            raise AcceptanceError("channel router returned an invalid receipt")
        if (
            receipt.sender_core_id != fixture.core_id
            or receipt.channel is not ChannelKind.GENERAL
            or receipt.body != body
            or receipt.routed is not True
        ):
            raise AcceptanceError("channel routing did not preserve Core identity")
        return receipt

    def _infer(
        self, fixture: DisposableCoreFixture, assets: LoadedCoreAssets,
    ):
        self._check_stop()
        if self.authorizer.authorize(
            operation="inference.submit",
            core_id=fixture.core_id,
            generation=fixture.generation,
            fingerprint=fixture.model.label,
        ) is not True:
            raise AcceptanceDenied("injected inference was not authorized")
        try:
            self.inference.register_core(
                core_id=fixture.core_id,
                platform_id=fixture.platform_id,
                generation=fixture.generation,
                display_name=fixture.full_name,
                model=fixture.model,
            )
        except Exception as exc:
            existing = self.inference.registration(
                fixture.core_id, fixture.platform_id, fixture.generation,
            )
            if existing is None:
                raise AcceptanceError(
                    "Core inference registration failed"
                ) from exc
        binding = self.inference.open_conversation(
            core_id=fixture.core_id,
            platform_id=fixture.platform_id,
            generation=fixture.generation,
            conversation_id=f"acceptance-{fixture.core_id.hex[:16]}",
        )
        self.inference.append_context(
            binding,
            (
                PromptMessage(PromptRole.SYSTEM, assets.constitution),
                PromptMessage(
                    PromptRole.SYSTEM,
                    "Memory: " + " | ".join(assets.memory_entries),
                ),
            ),
        )
        submission = self.inference.submit(
            binding,
            request_id=f"acceptance-{uuid4().hex}",
            messages=(
                PromptMessage(
                    PromptRole.USER,
                    f"{fixture.full_name}, confirm the text path.",
                ),
            ),
            workload_class=WorkloadClass.FOREGROUND_OWNER,
            max_output_tokens=64,
        )
        if not submission.accepted:
            raise AcceptanceError(
                f"injected inference was denied: {submission.reason}"
            )
        dispatch = self.inference.dispatch_next()
        if dispatch.result is None:
            raise AcceptanceError(
                f"injected inference produced no text: {dispatch.reason}"
            )
        result = dispatch.result
        if (
            result.core_id != fixture.core_id
            or result.platform_id != fixture.platform_id
            or result.core_generation != fixture.generation
            or result.model != fixture.model
            or not result.text.strip()
        ):
            raise AcceptanceError(
                "injected inference provenance does not match the Core"
            )
        return binding, dispatch

    def _persist(
        self, fixture: DisposableCoreFixture, assets: LoadedCoreAssets,
        routing: RoutingReceipt, dispatch,
    ) -> dict[str, object]:
        result = dispatch.result
        payload: dict[str, object] = {
            "schema": ACCEPTANCE_SCHEMA,
            "core_id": str(fixture.core_id),
            "platform_id": fixture.platform_id,
            "core_number": fixture.core_number,
            "generation": fixture.generation,
            "full_name": fixture.full_name,
            "constitution_sha256": assets.constitution_sha256,
            "memory_owner_core_id": str(assets.memory_owner_core_id),
            "provider": result.model.provider,
            "model": result.model.model,
            "model_digest": result.model.digest,
            "request_id": result.request_id,
            "output_sha256": result.output_sha256,
            "evidence_level": result.evidence_level.value,
            "simulated": result.simulated,
            "channel": routing.channel.value,
            "message_id": routing.message_id,
            "real_installation": False,
        }
        key = f"acceptance-{fixture.core_id.hex}"
        self.persistence.save(key, payload)
        loaded = self.persistence.load(key)
        if loaded != payload:
            raise AcceptanceError("persisted acceptance evidence did not round-trip")
        return payload

    def _restart(
        self, fixture: DisposableCoreFixture, binding,
        payload: Mapping[str, object],
    ) -> AcceptanceStep:
        if self.restart_inference is None:
            return AcceptanceStep(
                AcceptanceStage.RESTART_RECOVERY,
                AcceptanceStatus.SKIPPED,
                "no restart inference factory was supplied",
            )
        recovered = self.restart_inference()
        if not callable(getattr(recovered, "recover_after_restart", None)):
            raise AcceptanceError(
                "restart factory did not return an inference service"
            )
        recovered.recover_after_restart()
        outcomes = recovered.results(binding)
        if not outcomes:
            raise AcceptanceError(
                "completed inference evidence did not survive the restart"
            )
        latest = outcomes[-1]
        if (
            latest.result.core_id != fixture.core_id
            or latest.result.core_generation != fixture.generation
            or latest.result.model != fixture.model
            or latest.provenance.output_sha256 != payload["output_sha256"]
        ):
            raise AcceptanceError(
                "restarted inference evidence does not match the original"
            )
        reopened = recovered.open_conversation(
            core_id=fixture.core_id,
            platform_id=fixture.platform_id,
            generation=fixture.generation,
            conversation_id=binding.conversation_id,
        )
        if reopened.key != binding.key:
            raise AcceptanceError(
                "restart changed the exact Core conversation binding"
            )
        loaded = self.persistence.load(f"acceptance-{fixture.core_id.hex}")
        if loaded != payload:
            raise AcceptanceError(
                "restart lost persisted acceptance evidence"
            )
        return AcceptanceStep(
            AcceptanceStage.RESTART_RECOVERY,
            AcceptanceStatus.PASSED,
            "simulated restart recovered bindings, results and persistence",
        )

    def run(self, fixture: DisposableCoreFixture) -> AcceptanceReport:
        if not isinstance(fixture, DisposableCoreFixture):
            raise TypeError("fixture must be DisposableCoreFixture")
        steps: list[AcceptanceStep] = []
        definition = self._load_definition(fixture)
        steps.append(AcceptanceStep(
            AcceptanceStage.DEFINITION,
            AcceptanceStatus.PASSED,
            "definition and personal asset digests verified without installation",
        ))
        self._register(fixture)
        steps.append(AcceptanceStep(
            AcceptanceStage.REGISTRATION,
            AcceptanceStatus.PASSED,
            "definition registered with the management adapter",
        ))
        self._activate(fixture, definition)
        steps.append(AcceptanceStep(
            AcceptanceStage.ACTIVATION,
            AcceptanceStatus.PASSED,
            "authorized activation evidence established the exact Core",
        ))
        assets = self._load_assets(fixture)
        steps.append(AcceptanceStep(
            AcceptanceStage.IDENTITY_CONSTITUTION_MEMORY,
            AcceptanceStatus.PASSED,
            "identity, constitution and owned memory loaded independently",
        ))
        routing = self._route(fixture, assets)
        steps.append(AcceptanceStep(
            AcceptanceStage.CHANNEL_ROUTING,
            AcceptanceStatus.PASSED,
            "general channel routing preserved the Core identity",
        ))
        binding, dispatch = self._infer(fixture, assets)
        steps.append(AcceptanceStep(
            AcceptanceStage.INFERENCE,
            AcceptanceStatus.PASSED,
            f"injected text inference returned {dispatch.result.model.label}",
        ))
        payload = self._persist(fixture, assets, routing, dispatch)
        steps.append(AcceptanceStep(
            AcceptanceStage.PERSISTENCE,
            AcceptanceStatus.PASSED,
            "text result and provenance persisted and re-read",
        ))
        restart_step = self._restart(fixture, binding, payload)
        steps.append(restart_step)
        return AcceptanceReport(
            schema=ACCEPTANCE_SCHEMA,
            core_id=fixture.core_id,
            platform_id=fixture.platform_id,
            core_number=fixture.core_number,
            full_name=fixture.full_name,
            generation=fixture.generation,
            model=fixture.model,
            steps=tuple(steps),
            evidence=AcceptanceEvidence.SIMULATED,
            real_installation=False,
            voice_avatar_required=False,
            restart_simulated=(
                restart_step.status is AcceptanceStatus.PASSED
            ),
        )
