"""Disposable end-to-end acceptance fixture for Aegis Cores #6 and #7.

The fixture models one Vera-like Core and one blank/unwritten Core.  Both are
ordinary independent Core identities: different UUIDs, different profile
metadata and no embedded authority.  The harness exercises registration,
authorized simulated activation, text routing, injected text inference,
owner-scoped memory isolation, restart/recovery, STOP/authorization denial,
invitation decline, Core-free Platform operation and compute-reservation
separation.

Nothing here installs a package, downloads a model, signs a production key,
launches a process, reserves a real GPU or contacts another host.  Profile,
package, memory and inference seams are Protocols; the reference adapters are
in-memory fixtures.  Presentation metadata (armor, appearance, callsign) is
inert and never participates in an authorization decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable, Mapping, Protocol
from uuid import UUID, uuid4

from sofia.core.multicore.contracts import SecurityClass
from sofia.core.multicore.memory import ShareAuthorization
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.sdk.core_definition import CoreAssetReference, CoreDefinition
from sofia.sdk.identity import AegisIdentity, IdentityKind

V6_V7_ACCEPTANCE_SCHEMA = "aegis.core.multicore.v6_v7_acceptance.v1"
VERA_MEMORY_KEY = "vera-private-note"
BLANK_MEMORY_KEY = "blank-private-note"
VERA_MEMORY_TEXT = "fixture-only Vera memory; never shared without authority"
BLANK_MEMORY_TEXT = "fixture-only blank Core memory; never shared without authority"
_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")
_SLUG = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_TEXT_LIMIT = 512


class V6V7AcceptanceError(RuntimeError):
    """A required V6/V7 acceptance stage failed."""


class V6V7Denied(PermissionError):
    """STOP or explicit authorization denied a V6/V7 acceptance operation."""


class V6V7Stage(str, Enum):
    FIXTURE = "fixture"
    CORE_FREE_PLATFORM = "core_free_platform"
    REGISTRATION = "registration"
    ACTIVATION = "activation"
    BLANK_UNSELECTED = "blank_unselected"
    TEXT_CONVERSATION = "text_conversation"
    INFERENCE = "inference"
    MEMORY_ISOLATION = "memory_isolation"
    UNAUTHORIZED_SHARING = "unauthorized_sharing"
    RESTART_RECOVERY = "restart_recovery"
    STOP_AND_AUTHORIZATION_DENIAL = "stop_and_authorization_denial"
    INVITATION_DECLINE = "invitation_decline"
    RESOURCE_RESERVATION = "resource_reservation"


class V6V7Status(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class V6V7Evidence(str, Enum):
    SIMULATED = "simulated"
    OBSERVED = "observed"


def _text(value: object, label: str, *, maximum: int = _TEXT_LIMIT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise V6V7AcceptanceError(f"{label} must be bounded nonempty text")
    if any(ord(character) < 0x20 for character in value):
        raise V6V7AcceptanceError(f"{label} cannot contain control characters")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _uuid(value: object, label: str) -> UUID:
    if not isinstance(value, UUID) or value.int == 0:
        raise V6V7AcceptanceError(f"{label} must be a nonzero UUID")
    return value


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise V6V7AcceptanceError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CoreProfileView:
    """Inert fixture profile for one independent Core.

    The object deliberately has no permission, capability, role or authority
    field.  ``armor_material``, ``presentation`` and ``callsign`` are display
    metadata only.
    """

    core_number: int
    full_name: str
    nickname: str
    slug: str
    identity_concept: str
    callsign: str
    presentation: str
    armor_material: str | None = None
    avatar_available: bool = False
    voice_available: bool = False
    blank: bool = False

    def __post_init__(self) -> None:
        if type(self.core_number) is not int or self.core_number < 2:
            raise V6V7AcceptanceError("core_number must be an integer >= 2")
        _text(self.full_name, "full_name", maximum=160)
        _text(self.nickname, "nickname", maximum=160)
        if not isinstance(self.slug, str) or _SLUG.fullmatch(self.slug) is None:
            raise V6V7AcceptanceError("slug must be a lowercase identifier")
        _text(self.identity_concept, "identity_concept", maximum=256)
        _text(self.callsign, "callsign", maximum=80)
        _text(self.presentation, "presentation", maximum=160)
        _optional_text(self.armor_material, "armor_material")
        for label, value in (
            ("avatar_available", self.avatar_available),
            ("voice_available", self.voice_available),
            ("blank", self.blank),
        ):
            if type(value) is not bool:
                raise V6V7AcceptanceError(f"{label} must be bool")

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def is_instruction(self) -> bool:
        return False

    def to_payload(self) -> dict[str, object]:
        return {
            "core_number": self.core_number,
            "full_name": self.full_name,
            "nickname": self.nickname,
            "slug": self.slug,
            "identity_concept": self.identity_concept,
            "callsign": self.callsign,
            "presentation": self.presentation,
            "armor_material": self.armor_material,
            "avatar_available": self.avatar_available,
            "voice_available": self.voice_available,
            "blank": self.blank,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "CoreProfileView":
        if not isinstance(payload, Mapping):
            raise V6V7AcceptanceError("profile payload must be a mapping")
        return cls(
            core_number=payload["core_number"],
            full_name=payload["full_name"],
            nickname=payload["nickname"],
            slug=payload["slug"],
            identity_concept=payload["identity_concept"],
            callsign=payload["callsign"],
            presentation=payload["presentation"],
            armor_material=payload.get("armor_material"),
            avatar_available=payload.get("avatar_available", False),
            voice_available=payload.get("voice_available", False),
            blank=payload.get("blank", False),
        )


VERA_LIKE_PROFILE = CoreProfileView(
    core_number=6,
    full_name="Vera (disposable fixture)",
    nickname="Vera",
    slug="vera-fixture",
    identity_concept="Vera-like armored fixture identity, metadata only",
    callsign="Vera Vantage",
    presentation="Vera-like armored presentation metadata",
    armor_material="layered ceramic fixture armor metadata",
    avatar_available=False,
    voice_available=False,
    blank=False,
)

BLANK_CORE_PROFILE = CoreProfileView(
    core_number=7,
    full_name="Unwritten Core (disposable fixture)",
    nickname="Unwritten",
    slug="unwritten-fixture",
    identity_concept="Blank fixture identity with no authored personal metadata",
    callsign="Unwritten Draft",
    presentation="blank/unwritten presentation metadata",
    armor_material=None,
    avatar_available=False,
    voice_available=False,
    blank=True,
)


@dataclass(frozen=True, slots=True)
class V6V7CoreFixture:
    """One disposable definition and personal asset set; never installed."""

    root: Path
    platform_id: str
    profile: CoreProfileView
    core_id: UUID
    generation: int
    definition: CoreDefinition
    definition_path: Path
    constitution_path: Path
    personality_path: Path
    constitution_text: str
    personality_text: str
    constitution_sha256: str
    personality_sha256: str

    @classmethod
    def create(
        cls,
        root: Path | str,
        *,
        profile: CoreProfileView,
        platform_id: str,
        core_id: UUID | None = None,
        generation: int = 1,
        constitution_text: str | None = None,
        personality_text: str | None = None,
    ) -> "V6V7CoreFixture":
        if not isinstance(profile, CoreProfileView):
            raise TypeError("profile must be CoreProfileView")
        _text(platform_id, "platform_id", maximum=160)
        if type(generation) is not int or generation < 1:
            raise V6V7AcceptanceError("generation must be positive")
        selected_id = core_id if core_id is not None else uuid4()
        _uuid(selected_id, "core_id")
        directory = Path(root)
        assets = directory / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        constitution = assets / "constitution.md"
        personality = assets / "personality.md"
        constitution_body = constitution_text or (
            f"{profile.full_name} disposable V6/V7 fixture constitution."
        )
        personality_body = personality_text or (
            f"{profile.full_name} disposable V6/V7 fixture personality metadata."
        )
        constitution.write_text(constitution_body, encoding="utf-8")
        personality.write_text(personality_body, encoding="utf-8")
        constitution_digest = sha256(constitution.read_bytes()).hexdigest()
        personality_digest = sha256(personality.read_bytes()).hexdigest()
        definition = CoreDefinition(
            identity=AegisIdentity(IdentityKind.CORE, selected_id),
            name=profile.full_name,
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
        definition_path = directory / "definition.json"
        definition_path.write_bytes(definition.canonical_bytes)
        return cls(
            root=directory,
            platform_id=platform_id,
            profile=profile,
            core_id=selected_id,
            generation=generation,
            definition=definition,
            definition_path=definition_path,
            constitution_path=constitution,
            personality_path=personality,
            constitution_text=constitution_body,
            personality_text=personality_body,
            constitution_sha256=constitution_digest,
            personality_sha256=personality_digest,
        )

    @property
    def callsign(self) -> str:
        return self.profile.callsign

    @property
    def definition_digest(self) -> str:
        return self.definition.digest


@dataclass(frozen=True, slots=True)
class V6V7Fixtures:
    """One Vera-like Core (#6) and one blank Core (#7), with unique UUIDs."""

    vera: V6V7CoreFixture
    blank: V6V7CoreFixture

    @classmethod
    def create(
        cls,
        root: Path | str,
        *,
        platform_id: str = "platform:v6v7-fixture",
    ) -> "V6V7Fixtures":
        base = Path(root)
        vera = V6V7CoreFixture.create(
            base / "vera",
            profile=VERA_LIKE_PROFILE,
            platform_id=platform_id,
        )
        blank = V6V7CoreFixture.create(
            base / "blank",
            profile=BLANK_CORE_PROFILE,
            platform_id=platform_id,
        )
        if vera.core_id == blank.core_id:
            raise V6V7AcceptanceError("the two fixture Cores must have unique UUIDs")
        if vera.profile.to_payload() == blank.profile.to_payload():
            raise V6V7AcceptanceError("the two fixture Cores must have distinct profiles")
        return cls(vera=vera, blank=blank)


@dataclass(frozen=True, slots=True)
class RegistrationReceipt:
    core_id: UUID
    platform_id: str
    generation: int
    definition_digest: str
    registered: bool
    installed: bool = False
    simulated: bool = True


@dataclass(frozen=True, slots=True)
class ActivationReceipt:
    core_id: UUID
    generation: int
    state: str
    observed_at: datetime
    installed: bool = False
    simulated: bool = True


@dataclass(frozen=True, slots=True)
class CoreRuntimeStatus:
    core_id: UUID
    full_name: str
    callsign: str
    generation: int
    registered: bool
    installed: bool
    active: bool


@dataclass(frozen=True, slots=True)
class RecoveryReceipt:
    core_id: UUID
    full_name: str
    callsign: str
    generation: int
    profile: CoreProfileView
    registered: bool
    installed: bool
    active: bool
    simulated: bool = True


@dataclass(frozen=True, slots=True)
class RoutingReceipt:
    message_id: str
    room_id: str
    owner_id: str
    body: str
    routed_core_ids: tuple[UUID, ...]

    @property
    def grants_authority(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class InferenceReceipt:
    core_id: UUID
    generation: int
    conversation_id: str
    text: str
    provider: str
    model: str
    simulated: bool = True

    def to_payload(self) -> dict[str, object]:
        return {
            "core_id": str(self.core_id),
            "generation": self.generation,
            "conversation_id": self.conversation_id,
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "simulated": self.simulated,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "InferenceReceipt":
        return cls(
            core_id=UUID(str(payload["core_id"])),
            generation=payload["generation"],
            conversation_id=payload["conversation_id"],
            text=payload["text"],
            provider=payload["provider"],
            model=payload["model"],
            simulated=payload.get("simulated", True),
        )


@dataclass(frozen=True, slots=True)
class CoreMemoryEntry:
    owner_core_id: UUID
    key: str
    content: str
    security: SecurityClass


@dataclass(frozen=True, slots=True)
class InvitationReceipt:
    invite_id: str
    core_id: UUID
    status: str


class ProfileResolver(Protocol):
    def resolve(self, core_id: UUID) -> CoreProfileView:
        ...


class CorePackage(Protocol):
    def register(
        self,
        *,
        core_id: UUID,
        profile: CoreProfileView,
        platform_id: str,
        generation: int,
        definition_digest: str,
    ) -> RegistrationReceipt:
        ...

    def activate(self, *, core_id: UUID, generation: int) -> ActivationReceipt:
        ...

    def deactivate(self, *, core_id: UUID, generation: int) -> ActivationReceipt:
        ...

    def status(self, *, core_id: UUID) -> CoreRuntimeStatus:
        ...

    def recover(self, *, core_id: UUID, generation: int) -> RecoveryReceipt:
        ...

    def active_core_ids(self) -> tuple[UUID, ...]:
        ...

    def installed_core_ids(self) -> tuple[UUID, ...]:
        ...

    def snapshot(self) -> Mapping[str, object]:
        ...

    def restore(self, snapshot: Mapping[str, object]) -> None:
        ...


class CoreMemory(Protocol):
    def remember(
        self,
        *,
        core_id: UUID,
        key: str,
        content: str,
        security: SecurityClass = SecurityClass.PRIVATE,
    ) -> CoreMemoryEntry:
        ...

    def recall(self, *, core_id: UUID, key: str) -> CoreMemoryEntry | None:
        ...

    def records(self, *, core_id: UUID) -> tuple[CoreMemoryEntry, ...]:
        ...

    def share(
        self,
        *,
        source_core_id: UUID,
        recipient_core_id: UUID,
        key: str,
        authorization: ShareAuthorization | None,
    ) -> CoreMemoryEntry:
        ...

    def snapshot(self) -> Mapping[str, object]:
        ...

    def restore(self, snapshot: Mapping[str, object]) -> None:
        ...


class CoreInference(Protocol):
    def register(
        self,
        *,
        core_id: UUID,
        platform_id: str,
        generation: int,
        display_name: str,
    ) -> None:
        ...

    def converse(
        self,
        *,
        core_id: UUID,
        generation: int,
        conversation_id: str,
        message: str,
    ) -> InferenceReceipt:
        ...

    def history(
        self, *, core_id: UUID, generation: int, conversation_id: str,
    ) -> tuple[InferenceReceipt, ...]:
        ...

    def recover_after_restart(self) -> None:
        ...

    def snapshot(self) -> Mapping[str, object]:
        ...

    def restore(self, snapshot: Mapping[str, object]) -> None:
        ...


class TextPlatform(Protocol):
    def register_core(
        self,
        *,
        core_id: UUID,
        display_name: str,
        platform_id: str,
        generation: int,
    ) -> None:
        ...

    def select_core(self, *, core_id: UUID) -> None:
        ...

    def post(
        self,
        *,
        owner_id: str,
        room_id: str,
        body: str,
        mentions: tuple[UUID, ...],
    ) -> RoutingReceipt:
        ...

    def create_private_room(self, *, owner_id: str, name: str) -> str:
        ...

    def invite(self, *, owner_id: str, room_id: str, core_id: UUID) -> str:
        ...

    def decline_invitation(self, *, invite_id: str, core_id: UUID) -> str:
        ...

    def invitation_status(self, *, invite_id: str) -> str:
        ...

    def history(self, *, room_id: str) -> tuple[str, ...]:
        ...

    def core_ids(self) -> tuple[UUID, ...]:
        ...


class SafetyGate(Protocol):
    def is_operator_stopped(self) -> bool:
        ...


class AuthorizationGate(Protocol):
    def authorize(
        self,
        *,
        operation: str,
        core_id: UUID,
        generation: int,
        fingerprint: str,
    ) -> bool:
        ...


class ResourceAuthority(Protocol):
    def reserve(self, *, core_id: UUID, generation: int) -> None:
        ...

    def release(self, *, core_id: UUID, generation: int) -> None:
        ...

    def reserved_core_ids(self) -> tuple[UUID, ...]:
        ...

    def generation_for(self, *, core_id: UUID) -> int | None:
        ...


class StaticCoreProfiles:
    """Reference profile resolver for disposable fixture profiles."""

    def __init__(self) -> None:
        self._by_uuid: dict[UUID, CoreProfileView] = {}

    def bind(self, core_id: UUID, profile: CoreProfileView) -> None:
        _uuid(core_id, "core_id")
        if not isinstance(profile, CoreProfileView):
            raise TypeError("profile must be CoreProfileView")
        self._by_uuid[_uuid(core_id, "core_id")] = profile

    def resolve(self, core_id: UUID) -> CoreProfileView:
        selected = _uuid(core_id, "core_id")
        profile = self._by_uuid.get(selected)
        if profile is None:
            raise V6V7AcceptanceError("no profile is registered for this Core UUID")
        return profile


class InMemoryCorePackage:
    """Reference package adapter; registration and activation are simulated."""

    def __init__(self) -> None:
        self._cores: dict[UUID, dict[str, object]] = {}

    def register(
        self,
        *,
        core_id: UUID,
        profile: CoreProfileView,
        platform_id: str,
        generation: int,
        definition_digest: str,
    ) -> RegistrationReceipt:
        selected = _uuid(core_id, "core_id")
        if not isinstance(profile, CoreProfileView):
            raise TypeError("profile must be CoreProfileView")
        _text(platform_id, "platform_id", maximum=160)
        if type(generation) is not int or generation < 1:
            raise V6V7AcceptanceError("generation must be positive")
        if not isinstance(definition_digest, str) or len(definition_digest) != 64:
            raise V6V7AcceptanceError("definition_digest must be SHA-256")
        existing = self._cores.get(selected)
        if existing is not None:
            if (
                existing["profile"] != profile.to_payload()
                or existing["platform_id"] != platform_id
                or existing["generation"] != generation
                or existing["definition_digest"] != definition_digest
            ):
                raise V6V7AcceptanceError("Core registration conflicts with existing state")
            return RegistrationReceipt(
                core_id=selected,
                platform_id=platform_id,
                generation=generation,
                definition_digest=definition_digest,
                registered=True,
                installed=bool(existing["installed"]),
            )
        self._cores[selected] = {
            "profile": profile.to_payload(),
            "platform_id": platform_id,
            "generation": generation,
            "definition_digest": definition_digest,
            "registered": True,
            "installed": False,
            "active": False,
        }
        return RegistrationReceipt(
            core_id=selected,
            platform_id=platform_id,
            generation=generation,
            definition_digest=definition_digest,
            registered=True,
            installed=False,
        )

    def seed_installed(
        self,
        *,
        core_id: UUID,
        profile: CoreProfileView,
        platform_id: str,
        generation: int,
        definition_digest: str,
    ) -> RegistrationReceipt:
        """Retain an already-installed Core so coexistence is observable."""
        receipt = self.register(
            core_id=core_id,
            profile=profile,
            platform_id=platform_id,
            generation=generation,
            definition_digest=definition_digest,
        )
        state = self._cores[_uuid(core_id, "core_id")]
        state["installed"] = True
        state["active"] = True
        return RegistrationReceipt(
            core_id=receipt.core_id,
            platform_id=receipt.platform_id,
            generation=receipt.generation,
            definition_digest=receipt.definition_digest,
            registered=True,
            installed=True,
        )

    def _state(self, core_id: UUID) -> dict[str, object]:
        state = self._cores.get(_uuid(core_id, "core_id"))
        if state is None:
            raise V6V7AcceptanceError("Core is not registered")
        return state

    def activate(self, *, core_id: UUID, generation: int) -> ActivationReceipt:
        state = self._state(core_id)
        if state["generation"] != generation:
            raise V6V7AcceptanceError("activation generation differs from registration")
        state["active"] = True
        return ActivationReceipt(
            core_id=_uuid(core_id, "core_id"),
            generation=generation,
            state="active",
            observed_at=datetime.now(timezone.utc),
            installed=bool(state["installed"]),
        )

    def deactivate(self, *, core_id: UUID, generation: int) -> ActivationReceipt:
        state = self._state(core_id)
        if state["generation"] != generation:
            raise V6V7AcceptanceError("deactivation generation differs from registration")
        state["active"] = False
        return ActivationReceipt(
            core_id=_uuid(core_id, "core_id"),
            generation=generation,
            state="stopped",
            observed_at=datetime.now(timezone.utc),
            installed=bool(state["installed"]),
        )

    def status(self, *, core_id: UUID) -> CoreRuntimeStatus:
        state = self._state(core_id)
        profile = CoreProfileView.from_payload(state["profile"])
        return CoreRuntimeStatus(
            core_id=_uuid(core_id, "core_id"),
            full_name=profile.full_name,
            callsign=profile.callsign,
            generation=state["generation"],
            registered=bool(state["registered"]),
            installed=bool(state["installed"]),
            active=bool(state["active"]),
        )

    def recover(self, *, core_id: UUID, generation: int) -> RecoveryReceipt:
        state = self._state(core_id)
        if state["generation"] != generation:
            raise V6V7AcceptanceError("recovery generation differs from persisted identity")
        profile = CoreProfileView.from_payload(state["profile"])
        return RecoveryReceipt(
            core_id=_uuid(core_id, "core_id"),
            full_name=profile.full_name,
            callsign=profile.callsign,
            generation=state["generation"],
            profile=profile,
            registered=bool(state["registered"]),
            installed=bool(state["installed"]),
            active=bool(state["active"]),
        )

    def active_core_ids(self) -> tuple[UUID, ...]:
        return tuple(
            sorted(
                (core_id for core_id, state in self._cores.items() if state["active"]),
                key=str,
            )
        )

    def installed_core_ids(self) -> tuple[UUID, ...]:
        return tuple(
            sorted(
                (core_id for core_id, state in self._cores.items() if state["installed"]),
                key=str,
            )
        )

    def snapshot(self) -> Mapping[str, object]:
        return {
            "cores": {
                str(core_id): {
                    "profile": dict(state["profile"]),
                    "platform_id": state["platform_id"],
                    "generation": state["generation"],
                    "definition_digest": state["definition_digest"],
                    "registered": state["registered"],
                    "installed": state["installed"],
                    "active": state["active"],
                }
                for core_id, state in self._cores.items()
            }
        }

    def restore(self, snapshot: Mapping[str, object]) -> None:
        cores = snapshot.get("cores")
        if not isinstance(cores, Mapping):
            raise V6V7AcceptanceError("package snapshot is invalid")
        restored: dict[UUID, dict[str, object]] = {}
        for raw_id, raw_state in cores.items():
            if not isinstance(raw_state, Mapping):
                raise V6V7AcceptanceError("package snapshot entry is invalid")
            core_id = UUID(str(raw_id))
            restored[core_id] = {
                "profile": dict(raw_state["profile"]),
                "platform_id": raw_state["platform_id"],
                "generation": raw_state["generation"],
                "definition_digest": raw_state["definition_digest"],
                "registered": bool(raw_state["registered"]),
                "installed": bool(raw_state["installed"]),
                "active": bool(raw_state["active"]),
            }
        self._cores = restored


class InMemoryCoreMemory:
    """Reference owner-scoped memory adapter with explicit sharing authority."""

    def __init__(self) -> None:
        self._entries: dict[UUID, dict[str, CoreMemoryEntry]] = {}

    def remember(
        self,
        *,
        core_id: UUID,
        key: str,
        content: str,
        security: SecurityClass = SecurityClass.PRIVATE,
    ) -> CoreMemoryEntry:
        owner = _uuid(core_id, "core_id")
        if not isinstance(key, str) or _SAFE_KEY.fullmatch(key) is None:
            raise V6V7AcceptanceError("memory key must be a safe identifier")
        _text(content, "memory content", maximum=1_000_000)
        if not isinstance(security, SecurityClass):
            raise TypeError("security must be SecurityClass")
        entry = CoreMemoryEntry(owner, key, content, security)
        bucket = self._entries.setdefault(owner, {})
        existing = bucket.get(key)
        if existing is not None:
            if existing != entry:
                raise V6V7AcceptanceError("memory key already holds different content")
            return existing
        bucket[key] = entry
        return entry

    def recall(self, *, core_id: UUID, key: str) -> CoreMemoryEntry | None:
        return self._entries.get(_uuid(core_id, "core_id"), {}).get(key)

    def records(self, *, core_id: UUID) -> tuple[CoreMemoryEntry, ...]:
        bucket = self._entries.get(_uuid(core_id, "core_id"), {})
        return tuple(bucket[key] for key in sorted(bucket))

    def share(
        self,
        *,
        source_core_id: UUID,
        recipient_core_id: UUID,
        key: str,
        authorization: ShareAuthorization | None,
    ) -> CoreMemoryEntry:
        source = _uuid(source_core_id, "source_core_id")
        recipient = _uuid(recipient_core_id, "recipient_core_id")
        if source == recipient:
            raise ValueError("a shared copy must belong to a different Core")
        if not isinstance(authorization, ShareAuthorization):
            raise PermissionError("explicit owner sharing authorization is required")
        if authorization.owner_core_id != source:
            raise PermissionError("sharing authorization belongs to another Core")
        entry = self.recall(core_id=source, key=key)
        if entry is None:
            raise KeyError(key)
        if entry.security not in {
            SecurityClass.SHAREABLE,
            SecurityClass.AUTHORIZED_SHARED_COPY,
        }:
            raise PermissionError("memory security class forbids sharing")
        shared_key = f"shared:{source.hex[:8]}:{key}"
        copy = CoreMemoryEntry(
            owner_core_id=recipient,
            key=shared_key,
            content=entry.content,
            security=SecurityClass.AUTHORIZED_SHARED_COPY,
        )
        bucket = self._entries.setdefault(recipient, {})
        existing = bucket.get(shared_key)
        if existing is not None and existing != copy:
            raise V6V7AcceptanceError("shared memory copy conflicts with existing state")
        bucket[shared_key] = copy
        return copy

    def snapshot(self) -> Mapping[str, object]:
        return {
            "entries": [
                {
                    "owner_core_id": str(entry.owner_core_id),
                    "key": entry.key,
                    "content": entry.content,
                    "security": entry.security.value,
                }
                for owner in sorted(self._entries, key=str)
                for entry in (
                    self._entries[owner][key] for key in sorted(self._entries[owner])
                )
            ]
        }

    def restore(self, snapshot: Mapping[str, object]) -> None:
        records = snapshot.get("entries")
        if not isinstance(records, list):
            raise V6V7AcceptanceError("memory snapshot is invalid")
        restored: dict[UUID, dict[str, CoreMemoryEntry]] = {}
        for record in records:
            entry = CoreMemoryEntry(
                owner_core_id=UUID(str(record["owner_core_id"])),
                key=record["key"],
                content=record["content"],
                security=SecurityClass(record["security"]),
            )
            restored.setdefault(entry.owner_core_id, {})[entry.key] = entry
        self._entries = restored


class InMemoryCoreInference:
    """Reference injected text inference adapter with per-Core history."""

    def __init__(self) -> None:
        self._registrations: dict[tuple[UUID, int], str] = {}
        self._history: dict[tuple[UUID, int, str], list[InferenceReceipt]] = {}
        self.recovered = False

    def register(
        self,
        *,
        core_id: UUID,
        platform_id: str,
        generation: int,
        display_name: str,
    ) -> None:
        _text(platform_id, "platform_id", maximum=160)
        _text(display_name, "display_name", maximum=200)
        if type(generation) is not int or generation < 1:
            raise V6V7AcceptanceError("generation must be positive")
        key = (_uuid(core_id, "core_id"), generation)
        existing = self._registrations.get(key)
        if existing is not None and existing != display_name:
            raise V6V7AcceptanceError("inference registration conflicts with existing state")
        self._registrations[key] = display_name

    def converse(
        self,
        *,
        core_id: UUID,
        generation: int,
        conversation_id: str,
        message: str,
    ) -> InferenceReceipt:
        owner = _uuid(core_id, "core_id")
        if type(generation) is not int or generation < 1:
            raise V6V7AcceptanceError("generation must be positive")
        if not isinstance(conversation_id, str) or _SAFE_KEY.fullmatch(conversation_id) is None:
            raise V6V7AcceptanceError("conversation_id must be a safe identifier")
        _text(message, "message", maximum=16_000)
        display_name = self._registrations.get((owner, generation))
        if display_name is None:
            raise V6V7AcceptanceError("Core is not registered for text inference")
        receipt = InferenceReceipt(
            core_id=owner,
            generation=generation,
            conversation_id=conversation_id,
            text=f"{display_name} text-only response: {message}",
            provider="fixture",
            model="fixture/text-v1",
        )
        self._history.setdefault((owner, generation, conversation_id), []).append(receipt)
        return receipt

    def history(
        self, *, core_id: UUID, generation: int, conversation_id: str,
    ) -> tuple[InferenceReceipt, ...]:
        return tuple(
            self._history.get((_uuid(core_id, "core_id"), generation, conversation_id), ())
        )

    def recover_after_restart(self) -> None:
        self.recovered = True

    def snapshot(self) -> Mapping[str, object]:
        return {
            "registrations": [
                {
                    "core_id": str(core_id),
                    "generation": generation,
                    "display_name": display_name,
                }
                for (core_id, generation), display_name in sorted(
                    self._registrations.items(), key=lambda item: (str(item[0][0]), item[0][1])
                )
            ],
            "history": [
                {
                    "core_id": str(core_id),
                    "generation": generation,
                    "conversation_id": conversation_id,
                    "receipts": [receipt.to_payload() for receipt in receipts],
                }
                for (core_id, generation, conversation_id), receipts in sorted(
                    self._history.items(),
                    key=lambda item: (str(item[0][0]), item[0][1], item[0][2]),
                )
            ],
        }

    def restore(self, snapshot: Mapping[str, object]) -> None:
        registrations = snapshot.get("registrations")
        history = snapshot.get("history")
        if not isinstance(registrations, list) or not isinstance(history, list):
            raise V6V7AcceptanceError("inference snapshot is invalid")
        self._registrations = {}
        for item in registrations:
            self._registrations[(UUID(str(item["core_id"])), item["generation"])] = (
                item["display_name"]
            )
        self._history = {}
        for item in history:
            key = (
                UUID(str(item["core_id"])),
                item["generation"],
                item["conversation_id"],
            )
            self._history[key] = [
                InferenceReceipt.from_payload(payload) for payload in item["receipts"]
            ]


class InMemoryTextPlatform:
    """Reference Platform text surface with explicit Core selection."""

    def __init__(self) -> None:
        self._cores: dict[UUID, dict[str, object]] = {}
        self._selected: set[UUID] = set()
        self._rooms: dict[str, list[str]] = {"general": []}
        self._invitations: dict[str, dict[str, object]] = {}

    def register_core(
        self,
        *,
        core_id: UUID,
        display_name: str,
        platform_id: str,
        generation: int,
    ) -> None:
        selected = _uuid(core_id, "core_id")
        _text(display_name, "display_name", maximum=200)
        _text(platform_id, "platform_id", maximum=160)
        if type(generation) is not int or generation < 1:
            raise V6V7AcceptanceError("generation must be positive")
        record = {
            "display_name": display_name,
            "platform_id": platform_id,
            "generation": generation,
        }
        existing = self._cores.get(selected)
        if existing is not None and existing != record:
            raise V6V7AcceptanceError("Platform Core registration conflicts with existing state")
        self._cores[selected] = record

    def select_core(self, *, core_id: UUID) -> None:
        selected = _uuid(core_id, "core_id")
        if selected not in self._cores:
            raise V6V7AcceptanceError("Core must be enrolled before selection")
        self._selected.add(selected)

    def post(
        self,
        *,
        owner_id: str,
        room_id: str,
        body: str,
        mentions: tuple[UUID, ...],
    ) -> RoutingReceipt:
        _text(owner_id, "owner_id", maximum=160)
        _text(body, "body", maximum=64 * 1024)
        if room_id not in self._rooms:
            raise V6V7AcceptanceError("Platform room does not exist")
        if not isinstance(mentions, tuple):
            raise TypeError("mentions must be a tuple")
        for mention in mentions:
            _uuid(mention, "mention")
        routed = tuple(
            mention for mention in mentions if mention in self._selected
        )
        message_id = f"message-{uuid4().hex}"
        self._rooms[room_id].append(body)
        return RoutingReceipt(
            message_id=message_id,
            room_id=room_id,
            owner_id=owner_id,
            body=body,
            routed_core_ids=routed,
        )

    def create_private_room(self, *, owner_id: str, name: str) -> str:
        _text(owner_id, "owner_id", maximum=160)
        _text(name, "room name", maximum=200)
        room_id = f"room-{uuid4().hex}"
        self._rooms[room_id] = []
        return room_id

    def invite(self, *, owner_id: str, room_id: str, core_id: UUID) -> str:
        _text(owner_id, "owner_id", maximum=160)
        if room_id not in self._rooms:
            raise V6V7AcceptanceError("Platform room does not exist")
        selected = _uuid(core_id, "core_id")
        if selected not in self._cores:
            raise V6V7AcceptanceError("invited Core is not enrolled")
        invite_id = f"invite-{uuid4().hex}"
        self._invitations[invite_id] = {
            "room_id": room_id,
            "core_id": selected,
            "status": "pending",
        }
        return invite_id

    def decline_invitation(self, *, invite_id: str, core_id: UUID) -> str:
        invitation = self._invitations.get(invite_id)
        if invitation is None:
            raise V6V7AcceptanceError("invitation does not exist")
        if invitation["core_id"] != _uuid(core_id, "core_id"):
            raise PermissionError("invitation belongs to another Core")
        if invitation["status"] != "pending":
            raise V6V7AcceptanceError("invitation is no longer pending")
        invitation["status"] = "declined"
        return "declined"

    def invitation_status(self, *, invite_id: str) -> str:
        invitation = self._invitations.get(invite_id)
        if invitation is None:
            raise V6V7AcceptanceError("invitation does not exist")
        return str(invitation["status"])

    def history(self, *, room_id: str) -> tuple[str, ...]:
        if room_id not in self._rooms:
            raise V6V7AcceptanceError("Platform room does not exist")
        return tuple(self._rooms[room_id])

    def core_ids(self) -> tuple[UUID, ...]:
        return tuple(sorted(self._cores, key=str))

    def selected_core_ids(self) -> tuple[UUID, ...]:
        return tuple(sorted(self._selected, key=str))


class InMemoryResourceAuthority:
    """Reference compute reservation ledger; no GPU or host is touched."""

    def __init__(self) -> None:
        self._reservations: dict[UUID, int] = {}

    def reserve(self, *, core_id: UUID, generation: int) -> None:
        selected = _uuid(core_id, "core_id")
        if type(generation) is not int or generation < 1:
            raise V6V7AcceptanceError("generation must be positive")
        existing = self._reservations.get(selected)
        if existing is not None and existing != generation:
            raise V6V7AcceptanceError("reservation generation differs")
        self._reservations[selected] = generation

    def release(self, *, core_id: UUID, generation: int) -> None:
        selected = _uuid(core_id, "core_id")
        if self._reservations.get(selected) == generation:
            del self._reservations[selected]

    def reserved_core_ids(self) -> tuple[UUID, ...]:
        return tuple(sorted(self._reservations, key=str))

    def generation_for(self, *, core_id: UUID) -> int | None:
        return self._reservations.get(_uuid(core_id, "core_id"))


class NeverStoppedSafety:
    def is_operator_stopped(self) -> bool:
        return False


class AlwaysStoppedSafety:
    def is_operator_stopped(self) -> bool:
        return True


class AllowAllAuthorization:
    """Reference authorizer that records every exact UUID-addressed decision."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID, int, str]] = []

    def authorize(
        self,
        *,
        operation: str,
        core_id: UUID,
        generation: int,
        fingerprint: str,
    ) -> bool:
        self.calls.append((operation, core_id, generation, fingerprint))
        return True


class DenyAllAuthorization:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID, int, str]] = []

    def authorize(
        self,
        *,
        operation: str,
        core_id: UUID,
        generation: int,
        fingerprint: str,
    ) -> bool:
        self.calls.append((operation, core_id, generation, fingerprint))
        return False


@dataclass(frozen=True, slots=True)
class V6V7AcceptanceStep:
    stage: V6V7Stage
    status: V6V7Status
    detail: str
    evidence: V6V7Evidence = V6V7Evidence.SIMULATED


@dataclass(frozen=True, slots=True)
class V6V7AcceptanceReport:
    schema: str
    owner_id: str
    platform_id: str
    vera_core_id: UUID
    blank_core_id: UUID
    vera_generation: int
    blank_generation: int
    steps: tuple[V6V7AcceptanceStep, ...]
    recovery: RecoveryReceipt | None = None
    reservations: tuple[UUID, ...] = ()
    evidence: V6V7Evidence = V6V7Evidence.SIMULATED
    real_installation: bool = False
    voice_avatar_required: bool = False
    restart_simulated: bool = False
    core_free_platform_verified: bool = False

    @property
    def ok(self) -> bool:
        return all(
            step.status in {V6V7Status.PASSED, V6V7Status.SKIPPED}
            for step in self.steps
        )

    def step(self, stage: V6V7Stage) -> V6V7AcceptanceStep | None:
        return next((item for item in self.steps if item.stage is stage), None)


class V6V7AcceptanceHarness:
    """Runs the disposable V6/V7 acceptance path with injected Protocol ports."""

    def __init__(
        self,
        *,
        owner_id: str,
        platform_id: str,
        profiles: ProfileResolver,
        package: CorePackage,
        authorization: AuthorizationGate,
        memory: CoreMemory,
        inference: CoreInference,
        platform: TextPlatform,
        safety: SafetyGate | None = None,
        resources: ResourceAuthority | None = None,
        core_free_platform: TextPlatform | None = None,
        restart_package: Callable[[], CorePackage] | None = None,
        restart_inference: Callable[[], CoreInference] | None = None,
        restart_memory: Callable[[], CoreMemory] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        _text(owner_id, "owner_id", maximum=160)
        _text(platform_id, "platform_id", maximum=160)
        self._check_port("profiles", profiles, ("resolve",))
        self._check_port(
            "package", package,
            (
                "register", "activate", "deactivate", "status", "recover",
                "active_core_ids", "installed_core_ids", "snapshot", "restore",
            ),
        )
        self._check_port("authorization", authorization, ("authorize",))
        self._check_port(
            "memory", memory, ("remember", "recall", "records", "share", "snapshot", "restore")
        )
        self._check_port(
            "inference", inference,
            ("register", "converse", "history", "recover_after_restart", "snapshot", "restore"),
        )
        self._check_port(
            "platform", platform,
            (
                "register_core", "select_core", "post", "create_private_room",
                "invite", "decline_invitation", "invitation_status", "history", "core_ids",
            ),
        )
        if safety is not None:
            self._check_port("safety", safety, ("is_operator_stopped",))
        if resources is not None:
            self._check_port(
                "resources",
                resources,
                ("reserve", "release", "reserved_core_ids", "generation_for"),
            )
        if core_free_platform is not None:
            self._check_port(
                "core_free_platform", core_free_platform,
                ("post", "history", "core_ids"),
            )
        for label, factory in (
            ("restart_package", restart_package),
            ("restart_inference", restart_inference),
            ("restart_memory", restart_memory),
        ):
            if factory is not None and not callable(factory):
                raise TypeError(f"{label} must be callable")
        self.owner_id = owner_id
        self.platform_id = platform_id
        self.profiles = profiles
        self.package = package
        self.authorization = authorization
        self.memory = memory
        self.inference = inference
        self.platform = platform
        self.safety = safety
        self.resources = resources
        self.core_free_platform = core_free_platform
        self.restart_package = restart_package
        self.restart_inference = restart_inference
        self.restart_memory = restart_memory
        self._clock = clock if callable(clock) else (
            lambda: datetime.now(timezone.utc)
        )
        self._active_profile: CoreProfileView | None = None
        self._blank_profile: CoreProfileView | None = None
        self._inference_receipt: InferenceReceipt | None = None
        self._conversation_id = ""

    @staticmethod
    def _check_port(label: str, port: object, methods: tuple[str, ...]) -> None:
        if port is None:
            raise TypeError(f"{label} port is required")
        for method in methods:
            if not callable(getattr(port, method, None)):
                raise TypeError(f"{label} port must expose {method}()")

    def _now(self) -> datetime:
        return _aware(self._clock(), "acceptance clock")

    def _require_not_stopped(
        self, safety: SafetyGate | None, fixture: V6V7CoreFixture,
    ) -> None:
        if safety is None:
            return
        try:
            stopped = safety.is_operator_stopped()
        except Exception as exc:
            raise V6V7Denied("SAFE/STOP evidence is unavailable") from exc
        if stopped is not False:
            raise V6V7Denied(
                "operator STOP blocks Core "
                f"{fixture.profile.core_number} regardless of presentation metadata"
            )

    def _require_authorized(
        self,
        authorizer: AuthorizationGate,
        *,
        operation: str,
        fixture: V6V7CoreFixture,
        fingerprint: str,
    ) -> None:
        try:
            decision = authorizer.authorize(
                operation=operation,
                core_id=fixture.core_id,
                generation=fixture.generation,
                fingerprint=fingerprint,
            )
        except Exception as exc:
            raise V6V7Denied(f"{operation} authorization failed") from exc
        if decision is not True:
            raise V6V7Denied(f"{operation} authorization denied for Core {fixture.core_id}")

    def _verify_definition(self, fixture: V6V7CoreFixture) -> None:
        path = fixture.definition_path
        if not path.is_file():
            raise V6V7AcceptanceError("disposable definition file is missing")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            definition = CoreDefinition.from_payload(payload)
        except Exception as exc:
            raise V6V7AcceptanceError("disposable definition is invalid") from exc
        if definition.identity.identity_id != fixture.core_id:
            raise V6V7AcceptanceError("definition identity differs from fixture")
        if definition.name != fixture.profile.full_name:
            raise V6V7AcceptanceError("definition name differs from fixture")
        if definition.digest != fixture.definition.digest:
            raise V6V7AcceptanceError("definition digest differs from fixture")
        for reference, digest_value, asset_path in (
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
            if not asset_path.is_file():
                raise V6V7AcceptanceError("disposable personal asset is missing")
            raw = asset_path.read_bytes()
            if len(raw) != reference.size_bytes or sha256(raw).hexdigest() != reference.sha256:
                raise V6V7AcceptanceError("personal asset evidence differs")
            if reference.sha256 != digest_value:
                raise V6V7AcceptanceError("fixture asset digest differs")

    def _fixture_stage(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        if not isinstance(vera, V6V7CoreFixture) or not isinstance(blank, V6V7CoreFixture):
            raise TypeError("both fixtures must be V6V7CoreFixture")
        _uuid(vera.core_id, "vera.core_id")
        _uuid(blank.core_id, "blank.core_id")
        if vera.core_id == blank.core_id:
            raise V6V7AcceptanceError("Core UUIDs must be unique")
        if vera.generation < 1 or blank.generation < 1:
            raise V6V7AcceptanceError("Core generations must be positive")
        if vera.profile.to_payload() == blank.profile.to_payload():
            raise V6V7AcceptanceError("Core profiles must remain distinct")
        if vera.profile.core_number == blank.profile.core_number:
            raise V6V7AcceptanceError("Core numbers must remain distinct")
        if vera.profile.blank is not False or blank.profile.blank is not True:
            raise V6V7AcceptanceError("exactly one fixture must be the blank Core")
        for fixture in (vera, blank):
            if fixture.callsign == str(fixture.core_id):
                raise V6V7AcceptanceError("callsign must be separate from Core UUID")
            try:
                UUID(fixture.callsign)
            except ValueError:
                pass
            else:
                raise V6V7AcceptanceError("callsign must not be a UUID")
            if fixture.profile.grants_authority or fixture.profile.is_instruction:
                raise V6V7AcceptanceError("presentation metadata cannot grant authority")
            if fixture.profile.avatar_available or fixture.profile.voice_available:
                raise V6V7AcceptanceError("avatar and voice assets stay deferred")
            resolved = self.profiles.resolve(fixture.core_id)
            if not isinstance(resolved, CoreProfileView):
                raise V6V7AcceptanceError("profile resolver returned an invalid profile")
            if resolved.to_payload() != fixture.profile.to_payload():
                raise V6V7AcceptanceError("profile resolver returned another Core profile")
            self._verify_definition(fixture)
        if vera.callsign == blank.callsign:
            raise V6V7AcceptanceError("Core callsigns must remain distinct")
        return V6V7AcceptanceStep(
            V6V7Stage.FIXTURE,
            V6V7Status.PASSED,
            "unique UUIDs, distinct inert profiles, separate callsigns and verified assets",
        )

    def _core_free_stage(self) -> V6V7AcceptanceStep:
        if self.core_free_platform is None:
            return V6V7AcceptanceStep(
                V6V7Stage.CORE_FREE_PLATFORM,
                V6V7Status.SKIPPED,
                "no Core-free Platform probe was supplied",
            )
        if self.core_free_platform.core_ids() != ():
            raise V6V7AcceptanceError("Core-free Platform probe already contains Cores")
        body = "Platform-only owner heartbeat without any Core"
        receipt = self.core_free_platform.post(
            owner_id=self.owner_id,
            room_id="general",
            body=body,
            mentions=(),
        )
        if receipt.routed_core_ids != ():
            raise V6V7AcceptanceError("Core-free Platform routed to an absent Core")
        if body not in self.core_free_platform.history(room_id="general"):
            raise V6V7AcceptanceError("Core-free Platform lost the owner message")
        return V6V7AcceptanceStep(
            V6V7Stage.CORE_FREE_PLATFORM,
            V6V7Status.PASSED,
            "Platform owner text path works with zero registered Cores",
        )

    def _registration_stage(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        self._require_not_stopped(self.safety, vera)
        for fixture in (vera, blank):
            self._require_authorized(
                self.authorization,
                operation="register",
                fixture=fixture,
                fingerprint=fixture.definition_digest,
            )
            receipt = self.package.register(
                core_id=fixture.core_id,
                profile=fixture.profile,
                platform_id=fixture.platform_id,
                generation=fixture.generation,
                definition_digest=fixture.definition_digest,
            )
            if (
                receipt.core_id != fixture.core_id
                or receipt.generation != fixture.generation
                or receipt.registered is not True
                or receipt.installed is not False
            ):
                raise V6V7AcceptanceError("registration receipt does not prove the fixture Core")
            self.platform.register_core(
                core_id=fixture.core_id,
                display_name=fixture.profile.full_name,
                platform_id=fixture.platform_id,
                generation=fixture.generation,
            )
        return V6V7AcceptanceStep(
            V6V7Stage.REGISTRATION,
            V6V7Status.PASSED,
            "both Cores registered by UUID without installation",
        )

    def _activation_stage(self, vera: V6V7CoreFixture) -> V6V7AcceptanceStep:
        self._require_not_stopped(self.safety, vera)
        self._require_authorized(
            self.authorization,
            operation="activate",
            fixture=vera,
            fingerprint=vera.definition_digest,
        )
        receipt = self.package.activate(
            core_id=vera.core_id, generation=vera.generation,
        )
        if (
            receipt.core_id != vera.core_id
            or receipt.generation != vera.generation
            or receipt.state.casefold() not in {"active", "running"}
            or receipt.installed is not False
        ):
            raise V6V7AcceptanceError("activation did not establish the exact fixture Core")
        self.platform.select_core(core_id=vera.core_id)
        if self.resources is not None:
            self.resources.reserve(core_id=vera.core_id, generation=vera.generation)
        return V6V7AcceptanceStep(
            V6V7Stage.ACTIVATION,
            V6V7Status.PASSED,
            "authorized simulated activation selected the Vera-like Core only",
        )

    def _blank_unselected_stage(
        self, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        status = self.package.status(core_id=blank.core_id)
        if status.registered is not True or status.active is not False:
            raise V6V7AcceptanceError("blank Core did not remain unselected")
        if status.installed is not False:
            raise V6V7AcceptanceError("blank Core must not claim an installation")
        receipt = self.platform.post(
            owner_id=self.owner_id,
            room_id="general",
            body="Mention the blank Core without selecting it",
            mentions=(blank.core_id,),
        )
        if receipt.routed_core_ids != ():
            raise V6V7AcceptanceError("an unselected blank Core received a routed message")
        if self.resources is not None:
            if blank.core_id in self.resources.reserved_core_ids():
                raise V6V7AcceptanceError("an inactive blank Core reserved compute")
        if self.inference.history(
            core_id=blank.core_id,
            generation=blank.generation,
            conversation_id="unselected",
        ):
            raise V6V7AcceptanceError("an unselected blank Core produced inference")
        return V6V7AcceptanceStep(
            V6V7Stage.BLANK_UNSELECTED,
            V6V7Status.PASSED,
            "blank Core stayed registered, unselected, uninstalled and unreserved",
        )

    def _conversation_stage(self, vera: V6V7CoreFixture) -> V6V7AcceptanceStep:
        self._require_not_stopped(self.safety, vera)
        self._require_authorized(
            self.authorization,
            operation="conversation.route",
            fixture=vera,
            fingerprint=vera.definition_digest,
        )
        body = f"{vera.profile.full_name}, confirm the text conversation path."
        receipt = self.platform.post(
            owner_id=self.owner_id,
            room_id="general",
            body=body,
            mentions=(vera.core_id,),
        )
        if (
            receipt.body != body
            or receipt.routed_core_ids != (vera.core_id,)
            or body not in self.platform.history(room_id="general")
        ):
            raise V6V7AcceptanceError("text routing did not preserve the selected Core identity")
        return V6V7AcceptanceStep(
            V6V7Stage.TEXT_CONVERSATION,
            V6V7Status.PASSED,
            "general text routing reached only the selected Vera-like Core",
        )

    def _inference_stage(self, vera: V6V7CoreFixture) -> V6V7AcceptanceStep:
        self._require_not_stopped(self.safety, vera)
        self._require_authorized(
            self.authorization,
            operation="inference.submit",
            fixture=vera,
            fingerprint="fixture:fixture/text-v1",
        )
        self.inference.register(
            core_id=vera.core_id,
            platform_id=vera.platform_id,
            generation=vera.generation,
            display_name=vera.profile.full_name,
        )
        conversation_id = f"v6v7-{vera.core_id.hex[:16]}"
        receipt = self.inference.converse(
            core_id=vera.core_id,
            generation=vera.generation,
            conversation_id=conversation_id,
            message="Confirm the injected text path.",
        )
        if (
            receipt.core_id != vera.core_id
            or receipt.generation != vera.generation
            or receipt.conversation_id != conversation_id
            or not receipt.text.strip()
            or receipt.simulated is not True
        ):
            raise V6V7AcceptanceError("injected inference provenance does not match the Core")
        self._conversation_id = conversation_id
        self._inference_receipt = receipt
        return V6V7AcceptanceStep(
            V6V7Stage.INFERENCE,
            V6V7Status.PASSED,
            "injected text inference returned Core-addressed simulated provenance",
        )

    def _memory_stage(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        self._require_not_stopped(self.safety, vera)
        self.memory.remember(
            core_id=vera.core_id,
            key=VERA_MEMORY_KEY,
            content=VERA_MEMORY_TEXT,
            security=SecurityClass.PRIVATE,
        )
        self.memory.remember(
            core_id=blank.core_id,
            key=BLANK_MEMORY_KEY,
            content=BLANK_MEMORY_TEXT,
            security=SecurityClass.PRIVATE,
        )
        for fixture, key, content in (
            (vera, VERA_MEMORY_KEY, VERA_MEMORY_TEXT),
            (blank, BLANK_MEMORY_KEY, BLANK_MEMORY_TEXT),
        ):
            entry = self.memory.recall(core_id=fixture.core_id, key=key)
            if entry is None or entry.content != content or entry.owner_core_id != fixture.core_id:
                raise V6V7AcceptanceError("Core memory did not round-trip under its owner")
        if self.memory.recall(core_id=blank.core_id, key=VERA_MEMORY_KEY) is not None:
            raise V6V7AcceptanceError("blank Core read Vera-like private memory")
        if self.memory.recall(core_id=vera.core_id, key=BLANK_MEMORY_KEY) is not None:
            raise V6V7AcceptanceError("Vera-like Core read blank Core private memory")
        for fixture, foreign_text in (
            (vera, BLANK_MEMORY_TEXT),
            (blank, VERA_MEMORY_TEXT),
        ):
            records = self.memory.records(core_id=fixture.core_id)
            if any(record.owner_core_id != fixture.core_id for record in records):
                raise V6V7AcceptanceError("memory store returned another Core's record")
            if any(record.content == foreign_text for record in records):
                raise V6V7AcceptanceError("cross-Core memory content leaked")
        return V6V7AcceptanceStep(
            V6V7Stage.MEMORY_ISOLATION,
            V6V7Status.PASSED,
            "owner-scoped memory stayed isolated across both Cores",
        )

    def _sharing_stage(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        self._require_not_stopped(self.safety, vera)
        moment = self._now()
        attempts = (
            None,
            ShareAuthorization(
                owner_core_id=blank.core_id,
                granted_by="owner:fixture",
                reason="wrong owner probe",
                granted_at=moment,
            ),
            ShareAuthorization(
                owner_core_id=vera.core_id,
                granted_by="owner:fixture",
                reason="private memory still cannot be shared",
                granted_at=moment,
            ),
        )
        for authorization in attempts:
            try:
                self.memory.share(
                    source_core_id=vera.core_id,
                    recipient_core_id=blank.core_id,
                    key=VERA_MEMORY_KEY,
                    authorization=authorization,
                )
            except PermissionError:
                continue
            raise V6V7AcceptanceError("unauthorized cross-Core memory sharing was permitted")
        if any(
            record.content == VERA_MEMORY_TEXT
            for record in self.memory.records(core_id=blank.core_id)
        ):
            raise V6V7AcceptanceError("denied sharing still created a recipient copy")
        return V6V7AcceptanceStep(
            V6V7Stage.UNAUTHORIZED_SHARING,
            V6V7Status.PASSED,
            "missing, foreign-owner and private-class sharing were all denied",
        )

    def _restart_stage(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        if not any(
            factory is not None
            for factory in (
                self.restart_package, self.restart_inference, self.restart_memory,
            )
        ):
            return V6V7AcceptanceStep(
                V6V7Stage.RESTART_RECOVERY,
                V6V7Status.SKIPPED,
                "no restart factories were supplied",
            )
        snapshots = {
            "package": self.package.snapshot(),
            "inference": self.inference.snapshot(),
            "memory": self.memory.snapshot(),
        }
        recovered_package = self._recover_port(
            self.restart_package, self.package, "package",
            snapshots["package"],
            ("register", "recover", "status", "snapshot", "restore"),
        )
        recovered_inference = self._recover_port(
            self.restart_inference, self.inference, "inference",
            snapshots["inference"],
            ("history", "recover_after_restart", "snapshot", "restore"),
        )
        recovered_memory = self._recover_port(
            self.restart_memory, self.memory, "memory",
            snapshots["memory"],
            ("recall", "records", "snapshot", "restore"),
        )
        recovered_inference.recover_after_restart()
        recovery = recovered_package.recover(
            core_id=vera.core_id, generation=vera.generation,
        )
        if (
            recovery.core_id != vera.core_id
            or recovery.generation != vera.generation
            or recovery.full_name != vera.profile.full_name
            or recovery.callsign != vera.profile.callsign
            or recovery.profile.to_payload() != vera.profile.to_payload()
            or recovery.registered is not True
            or recovery.active is not True
            or recovery.simulated is not True
        ):
            raise V6V7AcceptanceError("recovery did not preserve the exact Core identity")
        blank_status = recovered_package.status(core_id=blank.core_id)
        if blank_status.registered is not True or blank_status.active is not False:
            raise V6V7AcceptanceError("restart changed the blank Core selection state")
        history = recovered_inference.history(
            core_id=vera.core_id,
            generation=vera.generation,
            conversation_id=self._conversation_id,
        )
        if (
            self._inference_receipt is None
            or not history
            or history[-1] != self._inference_receipt
        ):
            raise V6V7AcceptanceError("inference history did not survive restart")
        if recovered_memory.recall(core_id=vera.core_id, key=VERA_MEMORY_KEY) is None:
            raise V6V7AcceptanceError("Vera-like memory did not survive restart")
        if recovered_memory.recall(core_id=blank.core_id, key=BLANK_MEMORY_KEY) is None:
            raise V6V7AcceptanceError("blank Core memory did not survive restart")
        if self.resources is not None and blank.core_id in self.resources.reserved_core_ids():
            raise V6V7AcceptanceError("restart reserved compute for an inactive Core")
        self._last_recovery = recovery
        return V6V7AcceptanceStep(
            V6V7Stage.RESTART_RECOVERY,
            V6V7Status.PASSED,
            "simulated restart preserved identity, memory and inference evidence",
        )

    @staticmethod
    def _recover_port(
        factory: Callable[[], object] | None,
        current: object,
        label: str,
        snapshot: Mapping[str, object],
        methods: tuple[str, ...],
    ):
        port = current if factory is None else factory()
        for method in methods:
            if not callable(getattr(port, method, None)):
                raise TypeError(f"recovered {label} port must expose {method}()")
        port.restore(snapshot)
        return port

    def _denial_stage(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        for fixture in (vera, blank):
            self._expect_denied(
                lambda fixture=fixture: self._require_not_stopped(
                    AlwaysStoppedSafety(), fixture,
                ),
                "operator STOP",
            )
            probe = DenyAllAuthorization()
            self._expect_denied(
                lambda fixture=fixture, probe=probe: self._require_authorized(
                    probe,
                    operation="activate",
                    fixture=fixture,
                    fingerprint=fixture.definition_digest,
                ),
                "deny-all authorization",
            )
            if len(probe.calls) != 1 or probe.calls[0][1] != fixture.core_id:
                raise V6V7AcceptanceError(
                    "authorization probe did not address the Core by UUID"
                )
        return V6V7AcceptanceStep(
            V6V7Stage.STOP_AND_AUTHORIZATION_DENIAL,
            V6V7Status.PASSED,
            "STOP and deny-all authorization blocked both personas by UUID",
        )

    @staticmethod
    def _expect_denied(action: Callable[[], None], label: str) -> None:
        try:
            action()
        except (V6V7Denied, PermissionError):
            return
        raise V6V7AcceptanceError(f"{label} did not deny the operation")

    def _invitation_stage(self, blank: V6V7CoreFixture) -> V6V7AcceptanceStep:
        self._require_not_stopped(self.safety, blank)
        room_id = self.platform.create_private_room(
            owner_id=self.owner_id,
            name="V6/V7 disposable invitation",
        )
        invite_id = self.platform.invite(
            owner_id=self.owner_id,
            room_id=room_id,
            core_id=blank.core_id,
        )
        if self.platform.invitation_status(invite_id=invite_id) != "pending":
            raise V6V7AcceptanceError("invitation did not start in a pending state")
        status = self.platform.decline_invitation(
            invite_id=invite_id, core_id=blank.core_id,
        )
        observed_status = self.platform.invitation_status(invite_id=invite_id)
        if status != "declined" or observed_status != "declined":
            raise V6V7AcceptanceError("blank Core did not decline the invitation")
        if self.package.status(core_id=blank.core_id).active:
            raise V6V7AcceptanceError("declining an invitation activated the blank Core")
        return V6V7AcceptanceStep(
            V6V7Stage.INVITATION_DECLINE,
            V6V7Status.PASSED,
            "blank Core declined an invitation without becoming selected or active",
        )

    def _resource_stage(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        if self.resources is None:
            return V6V7AcceptanceStep(
                V6V7Stage.RESOURCE_RESERVATION,
                V6V7Status.SKIPPED,
                "no compute reservation authority was supplied",
            )
        reserved = self.resources.reserved_core_ids()
        if vera.core_id not in reserved:
            raise V6V7AcceptanceError("the active Vera-like Core has no reservation evidence")
        if blank.core_id in reserved:
            raise V6V7AcceptanceError("an inactive Core holds a compute reservation")
        if self.resources.generation_for(core_id=vera.core_id) != vera.generation:
            raise V6V7AcceptanceError("reservation generation differs from the active Core")
        return V6V7AcceptanceStep(
            V6V7Stage.RESOURCE_RESERVATION,
            V6V7Status.PASSED,
            "compute reservation evidence exists only for the active Core",
        )

    def verify_denials(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceStep:
        """Run the persona-independent STOP and authorization denial probe."""
        return self._denial_stage(vera, blank)

    def run(
        self, vera: V6V7CoreFixture, blank: V6V7CoreFixture,
    ) -> V6V7AcceptanceReport:
        steps: list[V6V7AcceptanceStep] = []
        steps.append(self._fixture_stage(vera, blank))
        steps.append(self._core_free_stage())
        steps.append(self._registration_stage(vera, blank))
        steps.append(self._activation_stage(vera))
        steps.append(self._blank_unselected_stage(blank))
        steps.append(self._conversation_stage(vera))
        steps.append(self._inference_stage(vera))
        steps.append(self._memory_stage(vera, blank))
        steps.append(self._sharing_stage(vera, blank))
        steps.append(self._restart_stage(vera, blank))
        steps.append(self._denial_stage(vera, blank))
        steps.append(self._invitation_stage(blank))
        steps.append(self._resource_stage(vera, blank))
        recovery = getattr(self, "_last_recovery", None)
        restart_step = next(
            (step for step in steps if step.stage is V6V7Stage.RESTART_RECOVERY),
            None,
        )
        core_free_step = next(
            (step for step in steps if step.stage is V6V7Stage.CORE_FREE_PLATFORM),
            None,
        )
        return V6V7AcceptanceReport(
            schema=V6_V7_ACCEPTANCE_SCHEMA,
            owner_id=self.owner_id,
            platform_id=self.platform_id,
            vera_core_id=vera.core_id,
            blank_core_id=blank.core_id,
            vera_generation=vera.generation,
            blank_generation=blank.generation,
            steps=tuple(steps),
            recovery=recovery if isinstance(recovery, RecoveryReceipt) else None,
            reservations=(
                () if self.resources is None else self.resources.reserved_core_ids()
            ),
            evidence=V6V7Evidence.SIMULATED,
            real_installation=False,
            voice_avatar_required=False,
            restart_simulated=(
                restart_step is not None
                and restart_step.status is V6V7Status.PASSED
            ),
            core_free_platform_verified=(
                core_free_step is not None
                and core_free_step.status is V6V7Status.PASSED
            ),
        )


__all__ = [
    "AllowAllAuthorization",
    "AlwaysStoppedSafety",
    "BLANK_CORE_PROFILE",
    "BLANK_MEMORY_KEY",
    "BLANK_MEMORY_TEXT",
    "ActivationReceipt",
    "AuthorizationGate",
    "CoreInference",
    "CoreMemory",
    "CoreMemoryEntry",
    "CorePackage",
    "CoreProfileView",
    "CoreRuntimeStatus",
    "DenyAllAuthorization",
    "InMemoryCoreInference",
    "InMemoryCoreMemory",
    "InMemoryCorePackage",
    "InMemoryResourceAuthority",
    "InMemoryTextPlatform",
    "InferenceReceipt",
    "InvitationReceipt",
    "NeverStoppedSafety",
    "ProfileResolver",
    "RecoveryReceipt",
    "RegistrationReceipt",
    "ResourceAuthority",
    "RoutingReceipt",
    "SafetyGate",
    "StaticCoreProfiles",
    "TextPlatform",
    "V6V7AcceptanceError",
    "V6V7AcceptanceHarness",
    "V6V7AcceptanceReport",
    "V6V7AcceptanceStep",
    "V6V7CoreFixture",
    "V6V7Denied",
    "V6V7Evidence",
    "V6V7Fixtures",
    "V6V7Stage",
    "V6V7Status",
    "VERA_LIKE_PROFILE",
    "VERA_MEMORY_KEY",
    "VERA_MEMORY_TEXT",
    "V6_V7_ACCEPTANCE_SCHEMA",
]
