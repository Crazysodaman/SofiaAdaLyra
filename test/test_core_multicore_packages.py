"""Versioned installable Core package manifests, registry and inert adapters."""
from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
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
    LifecycleAuthorizationDenied,
    MulticoreCoreLifecycle,
)
from sofia.core.multicore.packages import (
    CORE_PACKAGE_SCHEMA,
    CorePackageAlreadyRegistered,
    CorePackageAssetError,
    CorePackageBlankIdentityError,
    CorePackageConflict,
    CorePackageError,
    CorePackageManifest,
    CorePackageRegistry,
    CorePackageSofiaSubstitution,
    load_core_package_manifest,
    register_package_with_lifecycle,
)
from sofia.platform.ops.core_definition import CoreDefinitionVerifier
from sofia.platform.ops.platform_install import InstallAuthority
from sofia.platform.ops.synthetic_core_lifecycle import (
    CoreProcessObservation,
    SyntheticCoreLifecycleReceipt,
    SyntheticCoreOperation,
    SyntheticCoreOutcome,
    SyntheticCoreState,
)
from sofia.sdk.core_definition import CoreAssetReference

ROOT = Path(__file__).resolve().parents[1]
OWNER = "owner:package-tests"
LINEAGE_ID = UUID("7a4e0d8f-9b12-43a4-dfe6-e15c6d7e8f90")
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
RUNTIME_SHA = "a" * 64


def _descriptor(
    core_number: int,
    full_name: str,
    *,
    core_id: UUID | None = None,
) -> CoreDescriptor:
    return CoreDescriptor(
        core_number=core_number,
        full_name=full_name,
        nickname=None,
        gender="Female",
        presentation_species="Human",
        apparent_age=30,
        identity_concept="The Test Core",
        personality_traits=("curious", "deliberate"),
        motivations=("continuity",),
        character_flaw="test-only flaw",
        constitutional_priorities=("Integrity",),
        avatar=AvatarMetadata(
            age_years=30,
            height_inches=65.0,
            weight_pounds=130.0,
            build="Test build",
            head_proportions=7.5,
            measurements={},
            hair="Brown",
            outfit="Test coat",
            default_expression="Calm",
            colors={},
            materials={},
            pbr={},
        ),
        voice=VoiceMetadata(
            target="test voice",
            register="mid",
            accent=None,
            cadence="steady",
            serious_delivery="calm",
            model_id=None,
            assets_created=False,
        ),
        core_id=core_id,
    )


def _write_assets(
    root: Path, slug: str, *,
    constitution: bytes = b"Test-only constitutional boundaries.\n",
    personality: bytes = b'{"schema":"test-only"}\n',
) -> tuple[CoreAssetReference, CoreAssetReference]:
    directory = root / "cores" / slug
    directory.mkdir(parents=True, exist_ok=True)
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


def _manifest(
    root: Path,
    *,
    core_number: int,
    slug: str,
    full_name: str,
    core_id: UUID | None = None,
    descriptor_id: UUID | None = None,
    lifecycle: LifecycleState = LifecycleState.DEFINED,
    avatar_present: bool = False,
    voice_present: bool = False,
) -> CorePackageManifest:
    core_id = core_id or uuid4()
    constitution, personality = _write_assets(root, slug)
    return CorePackageManifest(
        core_id=core_id,
        core_number=core_number,
        slug=slug,
        descriptor=_descriptor(
            core_number, full_name, core_id=descriptor_id,
        ),
        constitution=constitution,
        personality=personality,
        lifecycle=lifecycle,
        avatar_present=avatar_present,
        voice_present=voice_present,
    )


def _blank_manifest(
    *,
    core_number: int = 7,
    slug: str = "core-7",
    core_id: UUID | None = None,
) -> CorePackageManifest:
    return CorePackageManifest(
        core_id=core_id or uuid4(),
        core_number=core_number,
        slug=slug,
        descriptor=None,
        constitution=None,
        personality=None,
        lifecycle=LifecycleState.REGISTERED,
        blank_identity=True,
    )


def test_versioned_manifest_round_trip_accepts_caller_supplied_uuid(tmp_path):
    core_id = uuid4()
    manifest = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
        core_id=core_id, descriptor_id=None,
    )
    assert manifest.core_id == core_id
    assert manifest.to_payload()["schema"] == CORE_PACKAGE_SCHEMA
    restored = CorePackageManifest.from_payload(manifest.to_payload())
    assert restored == manifest
    assert restored.digest == manifest.digest
    assert restored.canonical_bytes == manifest.canonical_bytes
    assert manifest.core_profile().descriptor.core_id == core_id
    assert manifest.core_definition(
        revision=1, runtime_release_sha256=RUNTIME_SHA,
    ).identity.identity_id == core_id

    mismatched = _descriptor(6, "Vera", core_id=uuid4())
    with pytest.raises(CorePackageError):
        CorePackageManifest(
            core_id=core_id, core_number=6, slug="vera",
            descriptor=mismatched, constitution=manifest.constitution,
            personality=manifest.personality,
        )


def test_registry_rejects_duplicate_uuid_number_and_slug(tmp_path):
    registry = CorePackageRegistry()
    first = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
    )
    assert registry.register(first) is first
    assert registry.resolve(first.core_id) is first
    assert registry.resolve(6) is first
    assert registry.resolve("vera") is first
    assert registry.manifests() == (first,)

    same_uuid = _manifest(
        tmp_path / "second", core_number=8, slug="vera-two",
        full_name="Vera Two", core_id=first.core_id,
    )
    with pytest.raises(CorePackageAlreadyRegistered):
        registry.register(same_uuid)

    same_number = _manifest(
        tmp_path / "third", core_number=6, slug="other-six",
        full_name="Other Six",
    )
    with pytest.raises(CorePackageAlreadyRegistered):
        registry.register(same_number)

    same_slug = _manifest(
        tmp_path / "fourth", core_number=9, slug="vera",
        full_name="Vera Again",
    )
    with pytest.raises(CorePackageAlreadyRegistered):
        registry.register(same_slug)

    with pytest.raises(KeyError):
        registry.resolve(99)


def test_manifest_requires_an_explicit_nonzero_caller_uuid():
    with pytest.raises(TypeError):
        CorePackageManifest(
            core_number=6, slug="vera", descriptor=None, constitution=None,
            personality=None, blank_identity=True,
        )
    with pytest.raises(ValueError):
        _blank_manifest(core_id=UUID(int=0))


def test_authority_and_capability_metadata_fields_are_rejected(tmp_path):
    manifest = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
    )
    for field in ("authority", "capabilities", "permissions", "grant"):
        forged = dict(manifest.to_payload())
        forged[field] = True
        with pytest.raises(CorePackageError):
            CorePackageManifest.from_payload(forged)
    with pytest.raises(TypeError):
        CorePackageManifest(
            core_id=manifest.core_id, core_number=6, slug="vera",
            descriptor=manifest.descriptor,
            constitution=manifest.constitution,
            personality=manifest.personality,
            authority=True,
        )


def test_registry_refuses_sofia_identity_substitution(tmp_path):
    sofia_id = uuid4()
    registry = CorePackageRegistry(sofia_instance_id=sofia_id)
    forged_sofia = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
        core_id=sofia_id,
    )
    with pytest.raises(CorePackageSofiaSubstitution):
        registry.register(forged_sofia)
    assert len(registry) == 0

    with pytest.raises(CorePackageError):
        _blank_manifest(core_number=1, slug="core-1")


def test_blank_identity_package_can_be_completed_only_with_same_identity(
    tmp_path,
):
    registry = CorePackageRegistry()
    reserved = _blank_manifest(core_number=7, slug="core-7")
    registry.register(reserved)
    assert registry.resolve(7) is reserved
    assert registry.resolve(7).is_blank
    with pytest.raises(CorePackageBlankIdentityError):
        reserved.core_profile()
    with pytest.raises(CorePackageBlankIdentityError):
        reserved.core_definition(revision=1, runtime_release_sha256=RUNTIME_SHA)

    completed = _manifest(
        tmp_path, core_number=7, slug="core-7", full_name="Unwritten Core",
        core_id=reserved.core_id,
        lifecycle=LifecycleState.REGISTERED,
    )
    assert registry.complete_blank(completed) is completed
    assert registry.resolve(reserved.core_id) is completed
    assert reserved.is_blank is True
    assert len(registry) == 1

    later = _blank_manifest(core_number=8, slug="later")
    registry.register(later)
    supplied = _manifest(
        tmp_path / "later", core_number=8, slug="later",
        full_name="Later Core", core_id=later.core_id,
        lifecycle=LifecycleState.REGISTERED,
    )
    assert registry.register(supplied) is supplied
    assert registry.resolve(later.core_id) is supplied

    with pytest.raises(CorePackageConflict):
        registry.complete_blank(completed)

    changed_slug = _manifest(
        tmp_path / "changed", core_number=7, slug="changed-slug",
        full_name="Changed Slug", core_id=reserved.core_id,
    )
    with pytest.raises(CorePackageConflict):
        registry.complete_blank(changed_slug)
    changed_number = _manifest(
        tmp_path / "changed-number", core_number=8, slug="core-7",
        full_name="Changed Number", core_id=reserved.core_id,
    )
    with pytest.raises(CorePackageConflict):
        registry.complete_blank(changed_number)
    assert registry.resolve(reserved.core_id) is completed


def test_missing_and_corrupt_package_assets_are_rejected(tmp_path):
    manifest = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
    )
    assert manifest.verify_assets(tmp_path) == (
        "cores/vera/constitution.md", "cores/vera/personality.json",
    )

    missing_root = tmp_path / "missing-root"
    with pytest.raises(CorePackageAssetError):
        manifest.verify_assets(missing_root)

    corrupt = tmp_path / "corrupt"
    corrupt_manifest = _manifest(
        corrupt, core_number=6, slug="vera", full_name="Vera",
    )
    target = corrupt / "cores" / "vera" / "constitution.md"
    original = target.read_bytes()
    target.write_bytes(b"x" * len(original))
    with pytest.raises(CorePackageAssetError):
        corrupt_manifest.verify_assets(corrupt)

    absent = tmp_path / "absent"
    absent_manifest = _manifest(
        absent, core_number=6, slug="vera", full_name="Vera",
    )
    (absent / "cores" / "vera" / "personality.json").unlink()
    with pytest.raises(CorePackageAssetError):
        absent_manifest.verify_assets(absent)


def test_manifest_file_loading_rejects_missing_or_corrupt_bytes(tmp_path):
    manifest = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
    )
    path = tmp_path / "manifest.json"
    path.write_bytes(manifest.canonical_bytes)
    assert load_core_package_manifest(path) == manifest

    path.write_text("{", encoding="utf-8")
    with pytest.raises(CorePackageError):
        load_core_package_manifest(path)
    with pytest.raises(CorePackageError):
        load_core_package_manifest(tmp_path / "absent.json")
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema":"aegis.core.package_manifest.v1",'
        '"schema":"aegis.core.package_manifest.v1"}',
        encoding="utf-8",
    )
    with pytest.raises(CorePackageError):
        load_core_package_manifest(duplicate)


@dataclass
class _Artifact:
    sha256: str = "b" * 64
    version: str = "0.1.0"


class _Authorization:
    def __init__(self) -> None:
        self.allowed = True
        self.calls: list[tuple[str, str, str, int]] = []

    def __call__(self, operation, core_id, fingerprint, generation):
        self.calls.append((operation, core_id, fingerprint, generation))
        return self.allowed


class _Store:
    def __init__(self) -> None:
        self.bindings = {}

    def binding(self, owner_id, core_id):
        return self.bindings.get((owner_id, core_id))

    def unresolved_operations(self, core_id=None):
        return ()


class _Installer:
    def installed_component_root(self, version, artifact_sha256):
        return None


class _Backend:
    def observe(self, *, core_id, lineage_id, generation):
        return CoreProcessObservation.STOPPED


class _Synthetic:
    def __init__(self) -> None:
        self.store = _Store()
        self.installer = _Installer()
        self.backend = _Backend()
        self.install_calls: list[dict[str, object]] = []
        self.activate_calls: list[dict[str, object]] = []
        self.stop_calls: list[dict[str, object]] = []
        self.remove_calls: list[dict[str, object]] = []
        self.reconcile_calls = 0

    def install(self, **kwargs):
        self.install_calls.append(kwargs)
        return _receipt(
            "install", SyntheticCoreOutcome.SUCCEEDED,
            SyntheticCoreState.INSTALLED, kwargs["core_id"],
            artifact_sha256=kwargs["artifact"].sha256,
        )

    def activate(self, **kwargs):
        self.activate_calls.append(kwargs)
        return _receipt(
            "start", SyntheticCoreOutcome.SUCCEEDED,
            SyntheticCoreState.ACTIVE, kwargs["core_id"], generation=1,
        )

    def stop(self, **kwargs):
        self.stop_calls.append(kwargs)
        return _receipt(
            "stop", SyntheticCoreOutcome.SUCCEEDED,
            SyntheticCoreState.STOPPED, kwargs["core_id"], generation=1,
        )

    def remove(self, **kwargs):
        self.remove_calls.append(kwargs)
        return _receipt(
            "remove", SyntheticCoreOutcome.SUCCEEDED,
            SyntheticCoreState.REMOVED, kwargs["core_id"], generation=1,
        )

    def reconcile(self):
        self.reconcile_calls += 1
        return ()


def _receipt(
    operation: str, outcome: SyntheticCoreOutcome, state: SyntheticCoreState,
    core_id: str, *, generation: int = 0, artifact_sha256: str = "b" * 64,
) -> SyntheticCoreLifecycleReceipt:
    return SyntheticCoreLifecycleReceipt(
        operation=SyntheticCoreOperation(operation),
        outcome=outcome,
        owner_id=OWNER,
        core_id=core_id,
        lineage_id=str(LINEAGE_ID),
        generation=generation,
        state=state,
        artifact_sha256=artifact_sha256,
        happened_at=NOW,
        detail="test-only receipt",
    )


def _signed_manifest(manifest):
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
    return (
        definition,
        CoreDefinitionVerifier({"operator": public}),
        signature,
    )


def test_package_registration_is_inert_until_an_authorized_lifecycle_call(
    tmp_path,
):
    manifest = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
    )
    registry = CorePackageRegistry()
    registry.register(manifest)
    _, verifier, signature = _signed_manifest(manifest)
    auth = _Authorization()
    synthetic = _Synthetic()
    adapter = MulticoreCoreLifecycle(
        synthetic=synthetic, authorization=auth, clock=lambda: NOW,
    )
    registration = register_package_with_lifecycle(
        adapter, manifest, revision=1, runtime_release_sha256=RUNTIME_SHA,
        verifier=verifier, signature_b64=signature, signer_key_id="operator",
        assets_root=tmp_path, minimum_revision=1,
    )
    assert registration.definition.identity.identity_id == manifest.core_id
    assert adapter.registration(manifest.core_id) is registration
    assert auth.calls == []
    assert synthetic.install_calls == []
    assert synthetic.activate_calls == []
    assert synthetic.stop_calls == []
    assert synthetic.remove_calls == []
    assert synthetic.reconcile_calls == 0

    auth.allowed = False
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.install(
            owner_id=OWNER, core_id=manifest.core_id,
            lineage_id=LINEAGE_ID, artifact=_Artifact(),
            wheel_path=Path("/virtual/core.whl"),
            authority=InstallAuthority.STANDING_POLICY,
        )
    assert synthetic.install_calls == []

    auth.allowed = True
    receipt = adapter.install(
        owner_id=OWNER, core_id=manifest.core_id,
        lineage_id=LINEAGE_ID, artifact=_Artifact(),
        wheel_path=Path("/virtual/core.whl"),
        authority=InstallAuthority.STANDING_POLICY,
    )
    assert receipt.state is SyntheticCoreState.INSTALLED
    assert len(synthetic.install_calls) == 1
    assert synthetic.activate_calls == []

    with pytest.raises(TypeError):
        register_package_with_lifecycle(
            adapter, manifest, revision=1,
            runtime_release_sha256=RUNTIME_SHA, verifier=object(),
            signature_b64=signature, signer_key_id="operator",
            assets_root=tmp_path, minimum_revision=1,
        )


def test_package_adapters_preserve_existing_definition_contract(tmp_path):
    manifest = _manifest(
        tmp_path, core_number=6, slug="vera", full_name="Vera",
        avatar_present=True,
    )
    definition = manifest.core_definition(
        revision=1, runtime_release_sha256=RUNTIME_SHA,
    )
    profile = manifest.core_profile()
    assert definition.name == "Vera"
    assert definition.constitution == manifest.constitution
    assert definition.personality == manifest.personality
    assert profile.spec.slug == "vera"
    assert profile.descriptor.core_id == manifest.core_id
    assert profile.constitution_sha256 == manifest.constitution_sha256
    assert profile.personality_sha256 == manifest.personality_sha256
    assert profile.avatar_present is True
    assert profile.voice_present is False


def test_packaging_declares_generic_core_asset_patterns_for_installable_cores():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["sofia.core"]
    assert {
        "*/constitution.md",
        "*/personality.json",
        "*/avatar.json",
        "*/voice.json",
    } <= set(patterns)
    cores = ROOT / "src" / "sofia" / "core"
    assert (cores / "vera" / "avatar.json").is_file()


def test_platform_definition_and_lifecycle_import_without_core():
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    code = (
        "import importlib.abc, sys\n"
        "class BlockCore(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'sofia.core' or fullname.startswith('sofia.core.'):\n"
        "            raise ImportError(fullname)\n"
        "        return None\n"
        "sys.meta_path.insert(0, BlockCore())\n"
        "import sofia.platform.ops.core_definition\n"
        "import sofia.platform.ops.synthetic_core_lifecycle\n"
        "assert not [name for name in sys.modules if name == 'sofia.core' "
        "or name.startswith('sofia.core.')]\n"
        "print('CORE-FREE-PLATFORM-OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], env=environment,
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "CORE-FREE-PLATFORM-OK" in result.stdout

