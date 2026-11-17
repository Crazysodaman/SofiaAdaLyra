"""Release assembler tests use disposable git repos and Ed25519 test keys."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import struct
import subprocess
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseTarget
from tools.build_aegis_release import (
    ReleaseAssemblyError, assemble_release, verify_installer_payload,
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


def _public_path(tmp_path: Path, public: bytes) -> Path:
    path = tmp_path / "trusted-publisher.pem"
    path.write_bytes(public)
    return path


def _wheel(root: Path, name: str, *, platform: str = "any") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    stem = name.replace("-", "_")
    path = root / f"{stem}-1.0.0-py3-none-{platform}.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{stem}-1.0.0.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0.0\n",
        )
        archive.writestr(f"{stem}/__init__.py", "")
    return path


def _wheelhouse(tmp_path: Path) -> Path:
    root = tmp_path / "wheelhouse"
    for name in ("cryptography", "cffi", "pycparser", "pywin32", "tzdata"):
        _wheel(root, name)
    return root


def _installer_payload(tmp_path: Path) -> Path:
    root = tmp_path / "installer-payload"
    root.mkdir()
    (root / "Install-Aegis.ps1").write_text(
        "param([switch]$Check)\n# windows entrypoint\n", encoding="utf-8",
    )
    (root / "install-aegis.sh").write_text(
        "#!/usr/bin/env bash\n# --check linux entrypoint\n", encoding="utf-8",
    )
    (root / "Aegis-Setup.exe").write_bytes(_pe())
    (root / "verify-aegis-capsule.sh").write_text(
        "#!/usr/bin/env bash\n# setup helper\n", encoding="utf-8",
    )
    return root


def _installer_changes(tmp_path: Path) -> dict:
    key_dir = tmp_path / "installer-key"
    key_dir.mkdir()
    _key_path, public = _key(key_dir)
    return {
        "installer_dir": _installer_payload(tmp_path),
        "trusted_public_key": _public_path(tmp_path, public),
        "trusted_signer_key_id": "test-installer-publisher",
        "dependency_wheelhouse": _wheelhouse(tmp_path),
    }


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
    supplied = inputs.get("trusted_public_key")
    if supplied is not None:
        try:
            supplied_bytes = Path(supplied).read_bytes()
        except OSError:
            supplied_bytes = b""
        if b"PRIVATE KEY" not in supplied_bytes:
            inputs["trusted_public_key"] = _public_path(tmp_path, public)
            inputs["trusted_signer_key_id"] = "test-p6-release"
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
            json.loads((bundle / "release" / "release-manifest.json").read_text())
        )
        assert manifest.source_sha == sha
        assert manifest.target is target
        kinds = {asset.kind for asset in manifest.assets}
        assert {"sdk", "platform", "service", "python-runtime",
                "dependency-lock", "sbom", "provenance"} <= kinds
        envelope = json.loads((bundle / "release" / "release-signature.json").read_text())
        assert set(envelope) == {"signer_key_id", "signature_b64"}
        verified = PlatformReleaseVerifier({
            envelope["signer_key_id"]: public,
        }).verify(
            manifest.to_payload(),
            signature_b64=envelope["signature_b64"],
            signer_key_id=envelope["signer_key_id"],
            assets_root=bundle / "release" / "assets",
            expected_source_sha=sha,
            expected_target=target,
            minimum_revision=1,
        )
        assert verified.digest == manifest.digest
        digests = json.loads((bundle / "release" / "artifact-digests.json").read_text())
        assert digests["manifest_digest"] == manifest.digest
        assert digests["signature_sha256"] == sha256(
            __import__("base64").b64decode(envelope["signature_b64"])
        ).hexdigest()
        listed = {item["path"]: item["sha256"] for item in digests["assets"]}
        assert set(listed) == {
            asset.reference.path for asset in manifest.assets
        }
        for path, digest in listed.items():
            assert sha256((bundle / "release" / "assets" / path).read_bytes()).hexdigest() == digest
        receipt = json.loads((bundle / "release" / "build-receipt.json").read_text())
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
             "release" / "release-manifest.json").read_text()
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
        "release/release-manifest.json", "release/release-signature.json",
        "release/artifact-digests.json", "release/build-receipt.json",
        "release/assets/dependency-inventory.json", "release/assets/sbom.json",
        "release/assets/assembly-provenance.json", "release/assets/python-runtime.zip",
    ):
        assert (tmp_path / "det-a" / "debian12-x86_64" / relative).read_bytes() == (
            tmp_path / "det-b" / "debian12-x86_64" / relative
        ).read_bytes()


def test_assembles_bundle_with_installer_payload_and_wheelhouse(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    changes = _installer_changes(tmp_path)
    installer_source = Path(changes["installer_dir"])
    _repo, sha, key, public, output, result = _assemble(
        tmp_path, platform_wheels, **changes,
    )
    assert result["test_signing_only"] is True
    for target in (
        PlatformReleaseTarget.DEBIAN12_X86_64,
        PlatformReleaseTarget.WINDOWS_X86_64,
    ):
        bundle = output / target.value
        runtime = bundle / "release" / "runtime" / "python"
        site_packages = (
            runtime / "Lib" / "site-packages"
            if target is PlatformReleaseTarget.WINDOWS_X86_64
            else runtime / "lib" / "python3.12" / "site-packages"
        )
        assert (site_packages / "sofia").is_dir()
        installer = bundle / "installer"
        assert (installer / "Install-Aegis.ps1").read_bytes() == (
            installer_source / "Install-Aegis.ps1"
        ).read_bytes()
        assert (installer / "install-aegis.sh").read_bytes() == (
            installer_source / "install-aegis.sh"
        ).read_bytes()
        assert (installer / "Aegis-Setup.exe").read_bytes() == _pe()
        assert (installer / "verify-aegis-capsule.sh").is_file()
        assert b"$Check" in (installer / "Install-Aegis.ps1").read_bytes()
        assert b"--check" in (installer / "install-aegis.sh").read_bytes()
        trusted_pem = Path(changes["trusted_public_key"]).read_bytes()
        trusted_digest = sha256(trusted_pem).hexdigest()
        assert (installer / "trusted-publisher.pem").read_bytes() == trusted_pem
        private_pem = key.read_bytes()
        for path in installer.rglob("*"):
            if path.is_file() and path.suffix.casefold() not in {".exe"}:
                assert private_pem not in path.read_bytes()
        assert b"BEGIN PRIVATE KEY" not in (
            installer / "trust.json"
        ).read_bytes()

        trust = json.loads((installer / "trust.json").read_text())
        assert trust["schema"] == "aegis.installer.trust.v1"
        assert trust["signer_key_id"] == "test-p6-release"
        assert trust["public_key_sha256"] == sha256(trusted_pem).hexdigest()
        assert trust["private_key_included"] is False
        assert trust["release_signature_separate"] is True

        plan = json.loads((installer / "install-plan.json").read_text())
        assert plan["bundle_source_sha"] == sha
        assert plan["target"] == target.value
        assert plan["revision"] == 1
        assert plan["grants_authority"] is False
        assert plan["trust_anchor"]["sha256"] == trusted_digest
        assert plan["trust_anchor"]["signer_key_id"] == "test-p6-release"
        assert plan["runtime"]["archive_path"] == "assets/python-runtime.zip"
        assert plan["runtime"]["extracted_prefix"] == "runtime/python"
        assert plan["installer_entrypoints"]["Install-Aegis.ps1"] == (
            "installer/Install-Aegis.ps1"
        )
        assert plan["installer_entrypoints"]["install-aegis.sh"] == (
            "installer/install-aegis.sh"
        )
        assert plan["installer_entrypoints"]["Aegis-Setup.exe"] == (
            "installer/Aegis-Setup.exe"
        )
        expected_runtime = (
            "runtime/python/python.exe"
            if target is PlatformReleaseTarget.WINDOWS_X86_64
            else "runtime/python/bin/python3.12"
        )
        assert plan["runtime"]["executable"] == expected_runtime
        assert plan["service_defaults"]["service_manager"] == (
            "scm" if target is PlatformReleaseTarget.WINDOWS_X86_64 else "systemd"
        )
        assert plan["operator_app_defaults"]["requested"] is False
        assert plan["operator_app_defaults"]["requires_owner_approval"] is True
        assert plan["wheelhouse"]["required_distributions"] == (
            ["cryptography", "cffi", "pycparser", "pywin32", "tzdata"]
            if target is PlatformReleaseTarget.WINDOWS_X86_64
            else ["cryptography", "cffi", "pycparser", "tzdata"]
        )
        assert len(plan["wheelhouse"]["wheels"]) == len(
            plan["wheelhouse"]["required_distributions"]
        )
        for wheel in plan["wheelhouse"]["wheels"]:
            assert sha256(
                (bundle / "release" / wheel["path"]).read_bytes()
            ).hexdigest() == wheel["sha256"]

        manifest = PlatformReleaseManifest.from_payload(
            json.loads((bundle / "release" / "release-manifest.json").read_text())
        )
        wheel_assets = [
            asset for asset in manifest.assets if asset.kind == "dependency"
            and asset.reference.path.startswith("wheelhouse/")
        ]
        assert len(wheel_assets) == len(plan["wheelhouse"]["wheels"])
        envelope = json.loads((bundle / "release" / "release-signature.json").read_text())
        verified = PlatformReleaseVerifier({
            envelope["signer_key_id"]: public,
        }).verify(
            manifest.to_payload(),
            signature_b64=envelope["signature_b64"],
            signer_key_id=envelope["signer_key_id"],
            assets_root=bundle / "release" / "assets",
            expected_source_sha=sha,
            expected_target=target,
            minimum_revision=1,
        )
        assert verified.digest == manifest.digest

        payload_report = verify_installer_payload(
            bundle,
            trusted_public_key=changes["trusted_public_key"],
            trusted_key_sha256=trusted_digest,
            trusted_signer_key_id="test-p6-release",
        )
        assert payload_report["installer_payload_verified"] is True
        assert payload_report["grants_authority"] is False
        assert payload_report["trust_anchor_sha256"] == trusted_digest

        digests = json.loads((bundle / "release" / "artifact-digests.json").read_text())
        assert digests["installer_payload_included"] is True
        assert {
            item["path"] for item in digests["installer"]
        } >= {
            "installer/Install-Aegis.ps1", "installer/install-aegis.sh",
            "installer/trusted-publisher.pem", "installer/trust.json",
            "installer/install-plan.json",
        }
        assert len(digests["wheelhouse"]) == len(plan["wheelhouse"]["wheels"])
        receipt = json.loads((bundle / "release" / "build-receipt.json").read_text())
        assert receipt["installer_payload_included"] is True
        assert receipt["trust_anchor_sha256"] == trusted_digest
        assert receipt["installer_trust_is_release_trust"] is False
        assert receipt["trust_root_embedded"] is False


def test_auto_detects_packaging_installers(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, _sha = _git_repo(tmp_path)
    installer = repo / "packaging" / "installers"
    installer.mkdir(parents=True)
    (installer / "Install-Aegis.ps1").write_text(
        "param([switch]$Check)\n", encoding="utf-8",
    )
    (installer / "install-aegis.sh").write_text(
        "#!/usr/bin/env bash\n# --check\n", encoding="utf-8",
    )
    wheelhouse = repo / "packaging" / "wheelhouse"
    for name in ("cryptography", "cffi", "pycparser", "pywin32", "tzdata"):
        _wheel(wheelhouse, name)
    subprocess.run(["git", "add", "packaging"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "installer fixtures"], cwd=repo, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    key, public = _key(tmp_path)
    public_path = _public_path(tmp_path, public)
    inputs = _inputs(tmp_path, platform_wheels)
    result = assemble_release(
        repo=repo,
        source_sha=sha,
        output_dir=tmp_path / "auto-installer",
        test_signing_key=key,
        signer_key_id="test-p6-release",
        trusted_public_key=public_path,
        application_version="0.1.0",
        python_version=PYTHON_VERSION,
        **inputs,
    )
    assert result["test_signing_only"] is True
    for target in (
        PlatformReleaseTarget.DEBIAN12_X86_64,
        PlatformReleaseTarget.WINDOWS_X86_64,
    ):
        bundle = tmp_path / "auto-installer" / target.value
        assert (bundle / "installer" / "Install-Aegis.ps1").is_file()
        assert (bundle / "installer" / "install-aegis.sh").is_file()
        assert (bundle / "installer" / "install-plan.json").is_file()
        assert (bundle / "release" / "assets" / "wheelhouse").is_dir()


def test_installer_payload_requires_trust_anchor(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    changes = _installer_changes(tmp_path)
    del changes["trusted_public_key"]
    with pytest.raises(ReleaseAssemblyError, match="trusted public key"):
        _assemble(tmp_path, platform_wheels, **changes)


def test_installer_payload_requires_wheelhouse(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    changes = _installer_changes(tmp_path)
    del changes["dependency_wheelhouse"]
    with pytest.raises(ReleaseAssemblyError, match="wheelhouse"):
        _assemble(tmp_path, platform_wheels, **changes)


def test_private_key_cannot_be_installer_trust_anchor(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    repo, _sha = _git_repo(tmp_path)
    key, _public = _key(tmp_path)
    with pytest.raises(ReleaseAssemblyError, match="private"):
        assemble_release(
            repo=repo,
            source_sha=_sha,
            output_dir=tmp_path / "private-trust",
            test_signing_key=key,
            signer_key_id="test-p6-release",
            installer_dir=_installer_payload(tmp_path),
            trusted_public_key=key,
            dependency_wheelhouse=_wheelhouse(tmp_path),
            application_version="0.1.0",
            python_version=PYTHON_VERSION,
            **_inputs(tmp_path, platform_wheels),
        )


def test_missing_dependency_closure_is_refused(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    changes = _installer_changes(tmp_path)
    (Path(changes["dependency_wheelhouse"]) /
     "cryptography-1.0.0-py3-none-any.whl").unlink()
    with pytest.raises(ReleaseAssemblyError, match="missing cryptography"):
        _assemble(tmp_path, platform_wheels, **changes)


def test_tampered_installer_digest_is_refused(
    tmp_path: Path, platform_wheels: dict[str, Path],
) -> None:
    changes = _installer_changes(tmp_path)
    _repo, _sha, _key_path, _public, output, _result = _assemble(
        tmp_path, platform_wheels, **changes,
    )
    bundle = output / PlatformReleaseTarget.DEBIAN12_X86_64.value
    script = bundle / "installer" / "install-aegis.sh"
    original = script.read_bytes()
    script.write_bytes(b"X" + original[1:])
    with pytest.raises(ReleaseAssemblyError, match="digest differs"):
        verify_installer_payload(bundle)
    envelope = json.loads((bundle / "release" / "release-signature.json").read_text())
    manifest = PlatformReleaseManifest.from_payload(
        json.loads((bundle / "release" / "release-manifest.json").read_text())
    )
    PlatformReleaseVerifier({
        envelope["signer_key_id"]: _public,
    }).verify(
        manifest.to_payload(),
        signature_b64=envelope["signature_b64"],
        signer_key_id=envelope["signer_key_id"],
        assets_root=bundle / "release" / "assets",
        expected_source_sha=_sha,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        minimum_revision=1,
    )



