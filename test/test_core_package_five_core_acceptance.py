"""Five-Core packaging composition and inert registration acceptance.

These tests observe source assets and package-data declarations.  They do not
install a wheel, start a Core process, activate a package, or mutate production
state.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tomllib
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.core.multicore.contracts import (
    AvatarMetadata,
    CoreDescriptor,
    LifecycleState,
    VoiceMetadata,
)
from sofia.core.multicore.lifecycle import (
    LifecycleRegistrationRequired,
    MulticoreCoreLifecycle,
    MulticoreLifecycleError,
)
from sofia.core.multicore.packages import (
    CorePackageAlreadyRegistered,
    CorePackageAssetError,
    CorePackageBlankIdentityError,
    CorePackageConflict,
    CorePackageError,
    CorePackageManifest,
    CorePackageRegistry,
    blank_unwritten_package,
    manifest_from_core_profile,
    register_package_with_lifecycle,
)
from sofia.core.multicore.profiles import (
    DEFAULT_CORE_PROFILES,
    UnknownCoreProfile,
    mack_core_profile,
    nova_core_profile,
)
from sofia.core.multicore.unwritten import (
    blank_core_profile,
    unwritten_constitution_bytes,
    unwritten_constitution_sha256,
)
from sofia.core.multicore.vera import vera_core_profile
from sofia.platform.ops.core_definition import CoreDefinitionVerifier
from sofia.platform.verify.component_artifacts import CORE_ASSET_FILES
from sofia.sdk.core_definition import CoreAssetReference

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
CORE_ROOT = SRC_ROOT / "sofia" / "core"
RUNTIME_SHA = "a" * 64
NOW = datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)
IDS = {
    1: UUID("11111111-1111-4111-8111-111111111111"),
    2: UUID("22222222-2222-4222-8222-222222222222"),
    3: UUID("33333333-3333-4333-8333-333333333333"),
    6: UUID("66666666-6666-4666-8666-666666666666"),
    7: UUID("77777777-7777-4777-8777-777777777777"),
}
NON_ACTIVE = {
    LifecycleState.DEFINED,
    LifecycleState.REGISTERED,
    LifecycleState.DETACHED,
}
SOFIA_PACKAGE_DATA = {
    "sofia.core.constitution": {"constitution.md", "constitution.sha256"},
    "sofia.core.identity": {"identity.json"},
    "sofia.core.embodiment": {"avatar.json"},
    "sofia.core.personality": {"personality.json"},
}
APPROVED_CORE_ASSET_SETS = {
    "sofia/core/constitution/constitution.md",
    "sofia/core/constitution/constitution.sha256",
    "sofia/core/identity/identity.json",
    "sofia/core/embodiment/avatar.json",
    "sofia/core/personality/personality.json",
    "sofia/core/cores/mack/constitution.md",
    "sofia/core/cores/mack/personality.json",
    "sofia/core/cores/mack/avatar.json",
    "sofia/core/cores/mack/voice.json",
    "sofia/core/cores/nova/constitution.md",
    "sofia/core/cores/nova/personality.json",
    "sofia/core/cores/nova/avatar.json",
    "sofia/core/cores/nova/voice.json",
    "sofia/core/cores/vera/constitution.md",
    "sofia/core/cores/vera/personality.json",
    "sofia/core/cores/vera/avatar.json",
    "sofia/core/cores/vera/voice.json",
    "sofia/core/cores/unwritten/constitution.md",
}


def _components_manifest() -> dict[str, object]:
    return tomllib.loads(
        (ROOT / "packaging" / "components.toml").read_text(encoding="utf-8")
    )


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _descriptor(
    core_number: int, full_name: str, *, core_id: UUID,
) -> CoreDescriptor:
    return CoreDescriptor(
        core_number=core_number,
        full_name=full_name,
        nickname=None,
        gender="Unspecified",
        presentation_species="Unspecified",
        apparent_age=30,
        identity_concept="test-only absent package fixture",
        personality_traits=("test-only",),
        motivations=("test-only",),
        character_flaw="test-only",
        constitutional_priorities=("test-only",),
        avatar=AvatarMetadata(
            age_years=30,
            height_inches=1.0,
            weight_pounds=1.0,
            build="test-only",
            head_proportions=1.0,
            measurements={},
            hair="test-only",
            outfit="test-only",
            default_expression="test-only",
            colors={},
            materials={},
            pbr={},
        ),
        voice=VoiceMetadata(
            target="test-only",
            register="test-only",
            accent=None,
            cadence="test-only",
            serious_delivery="test-only",
            model_id=None,
            assets_created=False,
        ),
        core_id=core_id,
    )


def _write_assets(
    root: Path, slug: str,
) -> tuple[CoreAssetReference, CoreAssetReference]:
    directory = root / "cores" / slug
    directory.mkdir(parents=True, exist_ok=True)
    constitution = b"Test-only absent Core asset boundary.\n"
    personality = b'{"schema":"test-only-absent-core"}\n'
    (directory / "constitution.md").write_bytes(constitution)
    (directory / "personality.json").write_bytes(personality)
    return (
        CoreAssetReference(
            f"cores/{slug}/constitution.md",
            sha256(constitution).hexdigest(),
            len(constitution),
        ),
        CoreAssetReference(
            f"cores/{slug}/personality.json",
            sha256(personality).hexdigest(),
            len(personality),
        ),
    )


def _populated_manifest(
    root: Path,
    *,
    core_id: UUID,
    core_number: int,
    slug: str,
    full_name: str,
) -> CorePackageManifest:
    constitution, personality = _write_assets(root, slug)
    return CorePackageManifest(
        core_id=core_id,
        core_number=core_number,
        slug=slug,
        descriptor=_descriptor(core_number, full_name, core_id=core_id),
        constitution=constitution,
        personality=personality,
    )


def _absent_manifest(
    *,
    core_id: UUID,
    core_number: int,
    slug: str,
    full_name: str,
) -> CorePackageManifest:
    """Describe assets that are intentionally absent from the source tree."""
    constitution = b"Absent Core constitution reference.\n"
    personality = b'{"schema":"absent-core-reference"}\n'
    return CorePackageManifest(
        core_id=core_id,
        core_number=core_number,
        slug=slug,
        descriptor=_descriptor(core_number, full_name, core_id=core_id),
        constitution=CoreAssetReference(
            f"cores/{slug}/constitution.md",
            sha256(constitution).hexdigest(),
            len(constitution),
        ),
        personality=CoreAssetReference(
            f"cores/{slug}/personality.json",
            sha256(personality).hexdigest(),
            len(personality),
        ),
    )


class _InertSynthetic:
    """Lifecycle double that records any consequential call."""

    def __init__(self) -> None:
        self.store = object()
        self.installer = object()
        self.backend = object()
        self.calls: list[str] = []

    def install(self, **kwargs):
        self.calls.append("install")

    def activate(self, **kwargs):
        self.calls.append("activate")

    def stop(self, **kwargs):
        self.calls.append("stop")

    def remove(self, **kwargs):
        self.calls.append("remove")

    def reconcile(self):
        self.calls.append("reconcile")
        return ()


def _lifecycle() -> tuple[MulticoreCoreLifecycle, _InertSynthetic, list[object]]:
    synthetic = _InertSynthetic()
    authorization_calls: list[object] = []

    def authorization(*args):
        authorization_calls.append(args)
        return False

    adapter = MulticoreCoreLifecycle(
        synthetic=synthetic, authorization=authorization, clock=lambda: NOW,
    )
    return adapter, synthetic, authorization_calls


def _signed(manifest: CorePackageManifest):
    definition = manifest.core_definition(
        revision=1, runtime_release_sha256=RUNTIME_SHA,
    )
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = b64encode(
        private.sign(definition.digest.encode("ascii"))
    ).decode("ascii")
    return definition, CoreDefinitionVerifier({"operator": public}), signature


def test_core_1_canonical_assets_are_declared_package_data():
    pyproject = _pyproject()
    components = _components_manifest()
    patterns = pyproject["tool"]["setuptools"]["package-data"]
    core_data = components["components"]["core"]["package_data"]

    for package, files in SOFIA_PACKAGE_DATA.items():
        assert package in patterns
        assert package in core_data
        assert files <= set(patterns[package])
        assert files <= set(core_data[package])
        relative = package.removeprefix("sofia.core.").replace(".", "/")
        for file_name in files:
            assert (CORE_ROOT / relative / file_name).is_file()

    constitution = (CORE_ROOT / "constitution" / "constitution.md").read_bytes()
    recorded = (
        CORE_ROOT / "constitution" / "constitution.sha256"
    ).read_text(encoding="ascii").strip().lower()
    # The digest binds canonical LF content; a Windows checkout may materialize
    # CRLF without changing the reviewed Git blob.
    canonical = constitution.replace(b"\r\n", b"\n")
    assert sha256(canonical).hexdigest() == recorded
    for relative in (
        "identity/identity.json",
        "embodiment/avatar.json",
        "personality/personality.json",
    ):
        raw = (CORE_ROOT / relative).read_bytes()
        assert isinstance(json.loads(raw.decode("utf-8-sig")), dict)

    # Core #1 is the canonical Sofía Core, not an independent package slot.
    with pytest.raises(CorePackageError):
        CorePackageManifest(
            core_id=IDS[1],
            core_number=1,
            slug="sofia",
            descriptor=None,
            constitution=None,
            personality=None,
            blank_identity=True,
        )


def test_mack_nova_vera_manifests_verify_canonical_assets():
    registry = CorePackageRegistry()
    profiles = (
        mack_core_profile(IDS[2]),
        nova_core_profile(IDS[3]),
        vera_core_profile(IDS[6]),
    )
    expected = {2: "mack", 3: "nova", 6: "vera"}

    for profile in profiles:
        manifest = manifest_from_core_profile(profile)
        expected_number = profile.spec.core_number
        assert manifest.core_number == expected_number
        assert manifest.slug == expected[expected_number]
        assert manifest.slug == profile.spec.slug
        assert manifest.lifecycle in NON_ACTIVE
        assert manifest.avatar_present is True
        assert manifest.voice_present is True
        assert manifest.verify_assets(CORE_ROOT) == (
            profile.spec.constitution_path,
            profile.spec.personality_path,
        )
        assert CorePackageManifest.from_payload(manifest.to_payload()) == manifest
        registry.register(manifest)

    assert {manifest.core_number for manifest in registry.manifests()} == {
        2, 3, 6
    }
    for number, slug in expected.items():
        manifest = registry.resolve(number)
        assert manifest.slug == slug
        assert registry.resolve(slug) is manifest
        assert registry.resolve(manifest.core_id) is manifest


def test_twins_have_no_definition_and_absent_assets_cannot_register(tmp_path):
    for number in (4, 5):
        with pytest.raises(UnknownCoreProfile):
            DEFAULT_CORE_PROFILES.resolve(number)
        assert not (CORE_ROOT / "cores" / str(number)).exists()
        assert not (CORE_ROOT / "cores" / f"twin-{number}").exists()

    lifecycle, synthetic, authorization_calls = _lifecycle()
    for number, slug in ((4, "twin-a"), (5, "twin-b")):
        with pytest.raises(UnknownCoreProfile):
            DEFAULT_CORE_PROFILES.resolve(slug)
        manifest = _absent_manifest(
            core_id=UUID(int=number),
            core_number=number,
            slug=slug,
            full_name=f"Test-only Twin {number}",
        )
        with pytest.raises(CorePackageAssetError):
            manifest.verify_assets(tmp_path)

        definition, verifier, signature = _signed(manifest)
        assert definition.name == f"Test-only Twin {number}"
        with pytest.raises(MulticoreLifecycleError):
            register_package_with_lifecycle(
                lifecycle,
                manifest,
                revision=1,
                runtime_release_sha256=RUNTIME_SHA,
                verifier=verifier,
                signature_b64=signature,
                signer_key_id="operator",
                assets_root=tmp_path,
                minimum_revision=1,
            )
        with pytest.raises(LifecycleRegistrationRequired):
            lifecycle.registration(manifest.core_id)

    assert synthetic.calls == []
    assert authorization_calls == []
    assert all(
        "twin" not in path and "/4/" not in path and "/5/" not in path
        for path in CORE_ASSET_FILES
    )


def test_package_data_declares_all_five_approved_core_asset_sets():
    pyproject = _pyproject()
    components = _components_manifest()
    patterns = pyproject["tool"]["setuptools"]["package-data"]
    core_data = components["components"]["core"]["package_data"]

    assert "sofia.core.cores" in patterns
    assert "sofia.core.cores" in core_data
    assert "sofia.core.cores.unwritten" in patterns
    assert "sofia.core.cores.unwritten" in core_data
    assert set(patterns["sofia.core.cores.unwritten"]) == {"constitution.md"}
    assert set(core_data["sofia.core.cores.unwritten"]) == {"constitution.md"}
    generic = {
        "*/constitution.md",
        "*/personality.json",
        "*/avatar.json",
        "*/voice.json",
    }
    assert generic <= set(patterns["sofia.core.cores"])
    assert generic <= set(core_data["sofia.core.cores"])
    for slug in ("mack", "nova", "vera"):
        assert f"sofia.core.cores.{slug}" in patterns
        assert f"sofia.core.cores.{slug}" in core_data

    assert APPROVED_CORE_ASSET_SETS <= set(CORE_ASSET_FILES)
    for relative in APPROVED_CORE_ASSET_SETS:
        assert (SRC_ROOT / relative).is_file(), relative


def test_blank_core_7_package_is_personal_identity_free_and_immutable(tmp_path):
    blank = blank_unwritten_package(IDS[7])
    assert blank.core_id == IDS[7]
    assert blank.core_number == 7
    assert blank.slug == "unwritten"
    assert blank.blank_identity is True
    assert blank.is_blank is True
    assert blank.descriptor is None
    assert blank.constitution is None
    assert blank.personality is None
    assert blank.avatar_present is False
    assert blank.voice_present is False
    assert blank.lifecycle in NON_ACTIVE
    payload = blank.to_payload()
    assert payload["descriptor"] is None
    assert payload["constitution"] is None
    assert payload["personality"] is None
    assert payload["avatar_present"] is False
    assert payload["voice_present"] is False
    assert payload["blank_identity"] is True
    assert CorePackageManifest.from_payload(payload) == blank
    with pytest.raises(CorePackageBlankIdentityError):
        blank.core_profile()
    with pytest.raises(CorePackageBlankIdentityError):
        blank.core_definition(
            revision=1, runtime_release_sha256=RUNTIME_SHA,
        )

    unwritten_dir = CORE_ROOT / "cores" / "unwritten"
    assert (unwritten_dir / "constitution.md").is_file()
    assert not (unwritten_dir / "personality.json").exists()
    assert not (unwritten_dir / "avatar.json").exists()
    assert not (unwritten_dir / "voice.json").exists()
    constitution = unwritten_constitution_bytes()
    assert constitution.strip()
    assert sha256(constitution).hexdigest() == unwritten_constitution_sha256()
    assert (
        blank_core_profile(IDS[7]).constitution_sha256
        == unwritten_constitution_sha256()
    )

    registry = CorePackageRegistry()
    registry.register(blank)
    assert registry.resolve(7) is blank
    assert registry.resolve("unwritten") is blank

    different_uuid = _populated_manifest(
        tmp_path / "different-uuid",
        core_id=uuid4(),
        core_number=7,
        slug="unwritten",
        full_name="Test-only Completion",
    )
    with pytest.raises(CorePackageError):
        registry.complete_blank(different_uuid)
    with pytest.raises(CorePackageAlreadyRegistered):
        registry.register(different_uuid)

    changed_number = _populated_manifest(
        tmp_path / "changed-number",
        core_id=blank.core_id,
        core_number=8,
        slug="unwritten",
        full_name="Test-only Completion",
    )
    with pytest.raises(CorePackageConflict):
        registry.complete_blank(changed_number)

    changed_slug = _populated_manifest(
        tmp_path / "changed-slug",
        core_id=blank.core_id,
        core_number=7,
        slug="other-7",
        full_name="Test-only Completion",
    )
    with pytest.raises(CorePackageConflict):
        registry.complete_blank(changed_slug)

    assert registry.resolve(blank.core_id) is blank
    assert registry.resolve(7).is_blank is True


def test_package_registration_is_inert_and_lifecycle_stays_non_active():
    registry = CorePackageRegistry()
    lifecycle, synthetic, authorization_calls = _lifecycle()
    profiles = (
        mack_core_profile(IDS[2]),
        nova_core_profile(IDS[3]),
        vera_core_profile(IDS[6]),
    )

    for profile in profiles:
        manifest = manifest_from_core_profile(profile)
        registry.register(manifest)
        definition, verifier, signature = _signed(manifest)
        registration = register_package_with_lifecycle(
            lifecycle,
            manifest,
            revision=1,
            runtime_release_sha256=RUNTIME_SHA,
            verifier=verifier,
            signature_b64=signature,
            signer_key_id="operator",
            assets_root=CORE_ROOT,
            minimum_revision=1,
        )
        assert registration.definition.digest == definition.digest
        assert registration.definition.identity.identity_id == manifest.core_id
        assert lifecycle.registration(manifest.core_id) is registration
        assert registry.resolve(manifest.core_number) is manifest
        assert manifest.lifecycle in NON_ACTIVE
        assert manifest.to_payload()["lifecycle"] == LifecycleState.DEFINED.value
        assert "installed" not in manifest.to_payload()
        assert "activated" not in manifest.to_payload()

    blank = registry.register(blank_unwritten_package(IDS[7]))
    assert blank.lifecycle in NON_ACTIVE
    with pytest.raises(CorePackageBlankIdentityError):
        blank.core_definition(
            revision=1, runtime_release_sha256=RUNTIME_SHA,
        )
    with pytest.raises(LifecycleRegistrationRequired):
        lifecycle.registration(IDS[7])

    assert synthetic.calls == []
    assert authorization_calls == []
    assert {item.core_number for item in registry.manifests()} == {2, 3, 6, 7}
    assert all(item.lifecycle in NON_ACTIVE for item in registry.manifests())
