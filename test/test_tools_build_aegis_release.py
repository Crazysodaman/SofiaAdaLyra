"""Release assembler tests use disposable git repos and Ed25519 test keys."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import struct
import subprocess

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseTarget
from tools.build_aegis_release import (
    ReleaseAssemblyError, assemble_release,
)

pytestmark = pytest.mark.pkg_ops

SOURCE = "a" * 40
PYTHON_VERSION = "3.12.16"


def _git_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "p6@test.invalid"], cwd=repo, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "P6 Test"], cwd=repo, check=True,
    )
    (repo / "README.md").write_text("deterministic release source\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    return repo, sha


def _key(tmp_path: Path) -> tuple[Path, bytes]:
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "test-signing-key.pem"
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return path, public


def _elf() -> bytes:
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 62)
    return bytes(data) + b"GLIBC_2.34\0"


def _pe() -> bytes:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<H", data, 68, 0x8664)
    struct.pack_into("<H", data, 88, 0x20B)
    return bytes(data)


def _prefix(root: Path, *, windows: bool) -> Path:
    if windows:
        primary = root / "python.exe"
        primary.parent.mkdir(parents=True, exist_ok=True)
        primary.write_bytes(_pe())
        library = root / "Lib"
        library.mkdir()
        (library / "os.py").write_text("# fixture\n", encoding="utf-8")
        (library / "site.py").write_text("# fixture\n", encoding="utf-8")
        (library / "ensurepip").mkdir()
        (library / "ensurepip" / "__init__.py").write_text("", encoding="utf-8")
        (root / "python312.dll").write_bytes(b"MZ fixture dll")
    else:
        primary = root / "bin" / "python3.12"
        primary.parent.mkdir(parents=True, exist_ok=True)
        primary.write_bytes(_elf())
        library = root / "lib" / "python3.12"
        library.mkdir(parents=True)
        (library / "os.py").write_text("# fixture\n", encoding="utf-8")
        (library / "site.py").write_text("# fixture\n", encoding="utf-8")
        (library / "ensurepip").mkdir()
        (library / "ensurepip" / "__init__.py").write_text("", encoding="utf-8")
    return root


def _payloads(tmp_path: Path) -> dict:
    service = _elf()
    tui = _elf()
    service_w = _pe()
    tui_w = _pe()
    return {
        PlatformReleaseTarget.DEBIAN12_X86_64: {
            "service": _write(tmp_path / "service-debian", service),
            "tui": _write(tmp_path / "tui-debian", tui),
            "prefix": _prefix(tmp_path / "prefix-debian", windows=False),
        },
        PlatformReleaseTarget.WINDOWS_X86_64: {
            "service": _write(tmp_path / "service-windows", service_w),
            "tui": _write(tmp_path / "tui-windows", tui_w),
            "prefix": _prefix(tmp_path / "prefix-windows", windows=True),
        },
    }


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _inputs(tmp_path: Path, platform_wheels: dict[str, Path]) -> dict:
    payloads = _payloads(tmp_path)
    return {
        "targets": [
            PlatformReleaseTarget.DEBIAN12_X86_64,
            PlatformReleaseTarget.WINDOWS_X86_64,
        ],
        "sdk_wheel": platform_wheels["sdk"],
        "platform_wheel": platform_wheels["platform"],
        "service_binaries": {
            target: value["service"] for target, value in payloads.items()
        },
        "tui_binaries": {
            target: value["tui"] for target, value in payloads.items()
        },
        "python_prefixes": {
            target: value["prefix"] for target, value in payloads.items()
        },
    }


def _assemble(tmp_path: Path, platform_wheels: dict[str, Path], **changes):
    repo, sha = _git_repo(tmp_path)
    key, public = _key(tmp_path)
    inputs = _inputs(tmp_path, platform_wheels)
    inputs.update(changes)
    output = tmp_path / "release-output"
    result = assemble_release(
        repo=repo,
        source_sha=sha,
        output_dir=output,
        test_signing_key=key,
        signer_key_id="test-p6-release",
        application_version="0.1.0",
        python_version=PYTHON_VERSION,
        **inputs,
    )
    return repo, sha, key, public, output, result


def test_assembles_complete_windows_and_debian_test_signed_bundles(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    _repo, sha, key, public, output, result = _assemble(
        tmp_path, platform_wheels,
    )
    assert result["test_signing_only"] is True
    assert result["production_signing_claim"] is False
    assert result["release_accepted"] is False
    assert result["installed_host_verified"] is False
    assert {item["target"] for item in result["releases"]} == {
        PlatformReleaseTarget.DEBIAN12_X86_64.value,
        PlatformReleaseTarget.WINDOWS_X86_64.value,
    }
    for target in (
        PlatformReleaseTarget.DEBIAN12_X86_64,
        PlatformReleaseTarget.WINDOWS_X86_64,
    ):
        bundle = output / target.value
        manifest = PlatformReleaseManifest.from_payload(
            json.loads((bundle / "release-manifest.json").read_text())
        )
        assert manifest.source_sha == sha
        assert manifest.target is target
        kinds = {asset.kind for asset in manifest.assets}
        assert {"sdk", "platform", "service", "python-runtime",
                "dependency-lock", "sbom", "provenance"} <= kinds
        envelope = json.loads((bundle / "release-signature.json").read_text())
        assert set(envelope) == {"signer_key_id", "signature_b64"}
        verified = PlatformReleaseVerifier({
            envelope["signer_key_id"]: public,
        }).verify(
            manifest.to_payload(),
            signature_b64=envelope["signature_b64"],
            signer_key_id=envelope["signer_key_id"],
            assets_root=bundle / "assets",
            expected_source_sha=sha,
            expected_target=target,
            minimum_revision=1,
        )
        assert verified.digest == manifest.digest
        digests = json.loads((bundle / "artifact-digests.json").read_text())
        assert digests["manifest_digest"] == manifest.digest
        assert digests["signature_sha256"] == sha256(
            __import__("base64").b64decode(envelope["signature_b64"])
        ).hexdigest()
        listed = {item["path"]: item["sha256"] for item in digests["assets"]}
        assert set(listed) == {
            asset.reference.path for asset in manifest.assets
        }
        for path, digest in listed.items():
            assert sha256((bundle / "assets" / path).read_bytes()).hexdigest() == digest
        receipt = json.loads((bundle / "build-receipt.json").read_text())
        assert receipt["result"].startswith("TEST_SIGNED_RELEASE_ASSEMBLED")
        assert receipt["inventory_complete"] is True
        assert receipt["production_authorized"] is False
        assert receipt["trust_root_embedded"] is False
        metadata = b"".join(
            path.read_bytes() for path in bundle.glob("*.json")
        )
        assert key.read_bytes() not in metadata
        assert b"BEGIN PRIVATE KEY" not in metadata
        assert b"BEGIN PUBLIC KEY" not in metadata


def test_source_sha_mismatch_is_refused(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, _sha = _git_repo(tmp_path)
    key, _public = _key(tmp_path)
    with pytest.raises(ReleaseAssemblyError, match="source SHA mismatch"):
        assemble_release(
            repo=repo,
            source_sha=SOURCE,
            output_dir=tmp_path / "wrong-sha",
            test_signing_key=key,
            signer_key_id="test-p6-release",
            application_version="0.1.0",
            python_version=PYTHON_VERSION,
            **_inputs(tmp_path, platform_wheels),
        )


def test_dirty_source_is_refused_unless_explicit_test_mode(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, sha = _git_repo(tmp_path)
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")
    key, _public = _key(tmp_path)
    inputs = _inputs(tmp_path, platform_wheels)
    with pytest.raises(ReleaseAssemblyError, match="dirty"):
        assemble_release(
            repo=repo, source_sha=sha, output_dir=tmp_path / "dirty-denied",
            test_signing_key=key, signer_key_id="test-p6-release",
            application_version="0.1.0", python_version=PYTHON_VERSION,
            **inputs,
        )
    result = assemble_release(
        repo=repo, source_sha=sha, output_dir=tmp_path / "dirty-test",
        test_signing_key=key, signer_key_id="test-p6-release",
        application_version="0.1.0", python_version=PYTHON_VERSION,
        allow_dirty=True,
        targets=[PlatformReleaseTarget.DEBIAN12_X86_64],
        sdk_wheel=platform_wheels["sdk"],
        platform_wheel=platform_wheels["platform"],
        service_binaries={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["service_binaries"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
        tui_binaries={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["tui_binaries"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
        python_prefixes={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["python_prefixes"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
    )
    assert result["source_tree_clean"] is False
    assert result["releases"][0]["result"].endswith("DIRTY_SOURCE_TEST_ONLY")


def test_core_wheel_is_refused(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, sha = _git_repo(tmp_path)
    key, _public = _key(tmp_path)
    core_bearing = tmp_path / "sofia_sdk-0.1.0-py3-none-any.whl"
    import zipfile
    with zipfile.ZipFile(core_bearing, "w") as archive:
        archive.writestr(
            "sofia_sdk-0.1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: sofia-sdk\nVersion: 0.1.0\n",
        )
        archive.writestr("sofia/core/forbidden.py", b"# Core payload\n")
    with pytest.raises(ReleaseAssemblyError, match="Core"):
        assemble_release(
            repo=repo, source_sha=sha, output_dir=tmp_path / "core-denied",
            test_signing_key=key, signer_key_id="test-p6-release",
            application_version="0.1.0", python_version=PYTHON_VERSION,
            targets=[PlatformReleaseTarget.DEBIAN12_X86_64],
            sdk_wheel=core_bearing,
            platform_wheel=platform_wheels["platform"],
            service_binaries={
                PlatformReleaseTarget.DEBIAN12_X86_64:
                    tmp_path / "service-debian",
            },
            tui_binaries={
                PlatformReleaseTarget.DEBIAN12_X86_64: tmp_path / "tui-debian",
            },
            python_prefixes={
                PlatformReleaseTarget.DEBIAN12_X86_64:
                    tmp_path / "prefix-debian",
            },
        )


def test_incomplete_target_inventory_is_refused(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, sha = _git_repo(tmp_path)
    key, _public = _key(tmp_path)
    with pytest.raises(ReleaseAssemblyError, match="cannot locate service"):
        assemble_release(
            repo=repo, source_sha=sha, output_dir=tmp_path / "incomplete",
            test_signing_key=key, signer_key_id="test-p6-release",
            application_version="0.1.0", python_version=PYTHON_VERSION,
            targets=[PlatformReleaseTarget.DEBIAN12_X86_64],
            sdk_wheel=platform_wheels["sdk"],
            platform_wheel=platform_wheels["platform"],
            service_binaries={},
            tui_binaries={},
            python_prefixes={},
        )


def test_locates_native_binaries_under_target_release(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, _sha = _git_repo(tmp_path)
    release_dir = repo / "target" / "release"
    release_dir.mkdir(parents=True)
    (release_dir / "aegis-platform-service").write_bytes(_elf())
    (release_dir / "aegis_tui").write_bytes(_elf())
    subprocess.run(["git", "add", "target"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "native fixtures"], cwd=repo, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    key, _public = _key(tmp_path)
    result = assemble_release(
        repo=repo, source_sha=sha, output_dir=tmp_path / "discovered",
        test_signing_key=key, signer_key_id="test-p6-release",
        application_version="0.1.0", python_version=PYTHON_VERSION,
        targets=[PlatformReleaseTarget.DEBIAN12_X86_64],
        sdk_wheel=platform_wheels["sdk"],
        platform_wheel=platform_wheels["platform"],
        python_prefixes={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                _prefix(tmp_path / "discovery-prefix", windows=False),
        },
    )
    assert result["releases"][0]["inventory_complete"] is True
    manifest = PlatformReleaseManifest.from_payload(
        json.loads(
            (tmp_path / "discovered" / "debian12-x86_64" /
             "release-manifest.json").read_text()
        )
    )
    service = next(asset for asset in manifest.assets if asset.kind == "service")
    assert service.reference.path == "aegis-platform-service"


def test_assembly_is_deterministic(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, sha = _git_repo(tmp_path)
    key, _public = _key(tmp_path)
    inputs = _inputs(tmp_path, platform_wheels)
    first = assemble_release(
        repo=repo, source_sha=sha, output_dir=tmp_path / "det-a",
        test_signing_key=key, signer_key_id="test-p6-release",
        application_version="0.1.0", python_version=PYTHON_VERSION,
        targets=[PlatformReleaseTarget.DEBIAN12_X86_64],
        sdk_wheel=inputs["sdk_wheel"], platform_wheel=inputs["platform_wheel"],
        service_binaries={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["service_binaries"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
        tui_binaries={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["tui_binaries"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
        python_prefixes={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["python_prefixes"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
    )
    second = assemble_release(
        repo=repo, source_sha=sha, output_dir=tmp_path / "det-b",
        test_signing_key=key, signer_key_id="test-p6-release",
        application_version="0.1.0", python_version=PYTHON_VERSION,
        targets=[PlatformReleaseTarget.DEBIAN12_X86_64],
        sdk_wheel=inputs["sdk_wheel"], platform_wheel=inputs["platform_wheel"],
        service_binaries={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["service_binaries"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
        tui_binaries={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["tui_binaries"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
        python_prefixes={
            PlatformReleaseTarget.DEBIAN12_X86_64:
                inputs["python_prefixes"][PlatformReleaseTarget.DEBIAN12_X86_64],
        },
    )
    assert first["releases"][0]["manifest_digest"] == second["releases"][0]["manifest_digest"]
    for relative in (
        "release-manifest.json", "release-signature.json",
        "artifact-digests.json", "build-receipt.json",
        "assets/dependency-inventory.json", "assets/sbom.json",
        "assets/assembly-provenance.json", "assets/python-runtime.zip",
    ):
        assert (tmp_path / "det-a" / "debian12-x86_64" / relative).read_bytes() == (
            tmp_path / "det-b" / "debian12-x86_64" / relative
        ).read_bytes()
