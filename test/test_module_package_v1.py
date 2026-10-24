from base64 import b64encode
from dataclasses import replace
from hashlib import sha256
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.modules import (
    DependencyRequirement,
    ModuleMaintenanceProfile,
    ModuleOperationProfile,
    OperationProfileKind,
    PackageManifestError,
    PlacementMode,
    SignedModuleManifest,
    parse_signed_manifest,
    validate_dependency_graph,
    verify_module_package,
)


def identity_digest(module_id, version, publisher, artifacts):
    return sha256(json.dumps({
        "artifacts": list(artifacts), "module_id": module_id,
        "publisher": publisher, "version": version,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def manifest(
    artifact_digests, *, module_id="org.sofia.research", version="9.0.0",
    dependencies=(), capabilities=("research.search",),
):
    publisher = "owner-reviewed"
    digest = identity_digest(module_id, version, publisher, artifact_digests)
    maintenance = ModuleMaintenanceProfile(
        "sofia.module.maintenance.v1", module_id, version, 1, digest, "supported",
        ("process.health",), 2, 3, (version,), ("weekly",),
        "signed staged updates only", "restore previous signed package",
        ("owner review after quarantine",),
    )
    profile = ModuleOperationProfile(
        OperationProfileKind.OBSERVE, 1, capabilities, 1,
        ("public",), (("cpu_millis", 100), ("ram_mib", 128)),
        ("linux-x86_64",), (), "none",
    )
    return SignedModuleManifest(
        1, module_id, version, "optional", publisher, artifact_digests,
        b64encode(b"\0" * 64).decode(), "trust:owner-modules",
        ("linux-x86_64", "windows-x86_64"), "1.0.0", "2.0.0",
        tuple((item, "schema:v1") for item in capabilities),
        dependencies, "subprocess-restricted", (("ram_mib", 128),), (),
        PlacementMode.PORTABLE_STATELESS, module_id + ".state",
        "no-state-migration-v1", "module-health.v1", "signed-rollback.v1",
        (profile,), (), maintenance,
    )


def signed(manifest_value, private_key):
    return replace(
        manifest_value,
        signature_b64=b64encode(
            private_key.sign(manifest_value.canonical_unsigned_bytes())
        ).decode(),
    )


def test_signed_package_verifies_without_importing_artifact(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    artifact = package / "module.py"
    artifact.write_text("raise AssertionError('must not import')\n", encoding="utf-8")
    artifacts = (("module.py", sha256(artifact.read_bytes()).hexdigest()),)
    key = Ed25519PrivateKey.generate()
    value = signed(manifest(artifacts), key)
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )

    verified = verify_module_package(
        value, package_root=package, trusted_public_key=public,
    )
    assert verified.package_digest == value.package_identity_digest()


def test_tampered_artifact_is_rejected(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    artifact = package / "module.py"
    artifact.write_text("original", encoding="utf-8")
    artifacts = (("module.py", sha256(artifact.read_bytes()).hexdigest()),)
    key = Ed25519PrivateKey.generate()
    value = signed(manifest(artifacts), key)
    artifact.write_text("tampered", encoding="utf-8")
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    with pytest.raises(PackageManifestError, match="digest"):
        verify_module_package(value, package_root=package, trusted_public_key=public)


def test_wrong_signing_key_is_rejected(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    artifact = package / "module.py"
    artifact.write_text("content", encoding="utf-8")
    artifacts = (("module.py", sha256(artifact.read_bytes()).hexdigest()),)
    value = signed(manifest(artifacts), Ed25519PrivateKey.generate())
    wrong = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    with pytest.raises(PackageManifestError, match="signature"):
        verify_module_package(value, package_root=package, trusted_public_key=wrong)


def test_artifact_path_traversal_and_portable_collisions_are_rejected():
    digest = "0" * 64
    with pytest.raises(PackageManifestError, match="escapes"):
        manifest((("../outside.py", digest),))
    with pytest.raises(PackageManifestError, match="portable-unique"):
        manifest((("A.py", digest), ("a.py", digest)))


def test_dependency_uses_declared_requirement_not_requester_major_version():
    digest = "0" * 64
    dependency = manifest(
        (("dep.py", digest),), module_id="org.sofia.library", version="1.5.0",
        capabilities=("library.read",),
    )
    requester = manifest(
        (("main.py", digest),),
        dependencies=(DependencyRequirement(
            "org.sofia.library", "1.0.0", "2.0.0",
        ),),
    )
    assert validate_dependency_graph((requester, dependency)) == (
        "org.sofia.library", "org.sofia.research",
    )


def test_dependency_mismatch_and_cycle_fail_closed():
    digest = "0" * 64
    dependency = manifest(
        (("dep.py", digest),), module_id="org.sofia.library", version="2.0.0",
        capabilities=("library.read",),
    )
    requester = manifest(
        (("main.py", digest),),
        dependencies=(DependencyRequirement(
            "org.sofia.library", "1.0.0", "2.0.0",
        ),),
    )
    with pytest.raises(PackageManifestError, match="version incompatible"):
        validate_dependency_graph((requester, dependency))

    first = manifest(
        (("a.py", digest),), module_id="org.sofia.first",
        dependencies=(DependencyRequirement("org.sofia.second", "1.0.0"),),
        capabilities=("first.read",),
    )
    second = manifest(
        (("b.py", digest),), module_id="org.sofia.second",
        dependencies=(DependencyRequirement("org.sofia.first", "1.0.0"),),
        capabilities=("second.read",),
    )
    with pytest.raises(PackageManifestError, match="cycle"):
        validate_dependency_graph((first, second))


def test_profile_cannot_expose_undeclared_capability():
    digest = "0" * 64
    value = manifest((("a.py", digest),))
    bad_profile = replace(
        value.profiles[0], available_capability_ids=("system.delete",),
    )
    with pytest.raises(PackageManifestError, match="undeclared"):
        replace(value, profiles=(bad_profile,))


def test_maintenance_profile_must_bind_exact_package_identity():
    digest = "0" * 64
    value = manifest((("a.py", digest),))
    bad = replace(value.maintenance_profile, artifact_digest="f" * 64)
    with pytest.raises(PackageManifestError, match="maintenance digest"):
        replace(value, maintenance_profile=bad)


def test_untrusted_manifest_parser_round_trips_exact_signed_document():
    value = manifest((("a.py", "0" * 64),))
    document = value.unsigned_document()
    document["signature_b64"] = value.signature_b64
    assert parse_signed_manifest(document) == value


def test_untrusted_manifest_parser_rejects_unknown_fields_and_wrong_types():
    value = manifest((("a.py", "0" * 64),))
    document = value.unsigned_document()
    document["signature_b64"] = value.signature_b64
    document["self_authorized"] = True
    with pytest.raises(PackageManifestError, match="invalid fields"):
        parse_signed_manifest(document)

    document.pop("self_authorized")
    document["schema_version"] = True
    with pytest.raises(PackageManifestError, match="schema_version"):
        parse_signed_manifest(document)
