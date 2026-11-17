#!/usr/bin/env python3
"""Disposable guided-installer acceptance harness.

This tool exercises the existing canonical installer modules against a
temporary, synthetic, offline release bundle.  It does **not** install on the
real host, register a real OS service, create a production trust root, sign a
production release or certify a delivered installer.

The report is deliberately labelled ``SIMULATED`` and always records
``installed_host_verified=false`` and ``production_authorized=false``.  Real
signed disposable-host testing remains a separate required acceptance gate.
"""
from __future__ import annotations

import argparse
from base64 import b64encode
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import traceback
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from sofia.platform.config.roles import (  # noqa: E402
    PlatformRole, PlatformRoleConfiguration,
)
from sofia.platform.ops.platform_installation import (  # noqa: E402
    PlatformInstallationStore,
)
from sofia.platform.ops.platform_installer_bundle import (  # noqa: E402
    verify_offline_installer_bundle,
)
from sofia.platform.ops.platform_installer_cli import (  # noqa: E402
    InstallerInputs, SUCCESS_OUTCOMES, execute_command,
)
from sofia.platform.ops.platform_installer_code_install import (  # noqa: E402
    CODE_PUBLISH_CAPABILITY,
)
from sofia.platform.ops.platform_installer_native_service import (  # noqa: E402
    DebianSystemdNativeService,
)
from sofia.platform.ops.platform_installer_operator_apps import (  # noqa: E402
    InMemoryPathAdapter, OPERATOR_APPS_CAPABILITY, OperatorAppsConfiguration,
    apply_owner_approved_operator_apps, operator_apps_request,
)
from sofia.platform.ops.platform_installer_native_transaction import (  # noqa: E402
    native_transaction_state,
)
from sofia.platform.ops.platform_installer_preview import (  # noqa: E402
    preview_signed_platform_install,
)
from sofia.platform.ops.platform_release import (  # noqa: E402
    PlatformReleaseVerifier,
)
from sofia.platform.ops.platform_release_staging import (  # noqa: E402
    stage_platform_release,
)
from sofia.platform.safe.execution_approval import (  # noqa: E402
    ExecutionApproval, ExecutionApprovalVerifier,
)
from sofia.platform.safe.operator_stop import OperatorStopStore  # noqa: E402
from sofia.platform.state.canonical_sqlite import (  # noqa: E402
    bootstrap_canonical_sqlite,
)
from sofia.platform.state.installation_identity import (  # noqa: E402
    InstallationIdentityStore,
)
from sofia.platform.state.local_store import PlatformLocalStore  # noqa: E402
from sofia.platform.state.private_file import (  # noqa: E402
    ensure_owner_private_directory,
)
from sofia.platform.verify.component_artifacts import build_component  # noqa: E402
from sofia.platform.verify.python_runtime import build_python_runtime  # noqa: E402
from sofia.sdk.artifact import ArtifactReference  # noqa: E402
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION  # noqa: E402
from sofia.sdk.platform_release import (  # noqa: E402
    PlatformReleaseAsset, PlatformReleaseManifest, PlatformReleaseTarget,
)
from test.owner_auth_fixture import record_verified_owner_approval  # noqa: E402

SCHEMA = "aegis.guided-installer-acceptance.v1"
LABEL = "SIMULATED"
_TARGET = PlatformReleaseTarget.DEBIAN12_X86_64
_NATIVE_CAPABILITY = "platform.native_service.apply"
_CAPABILITY = {
    "code": CODE_PUBLISH_CAPABILITY,
    "native": _NATIVE_CAPABILITY,
    "operator_apps": OPERATOR_APPS_CAPABILITY,
}
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class AcceptanceFailure(AssertionError):
    """A simulated acceptance invariant did not hold."""


@contextmanager
def _simulated_debian_host():
    """Make the in-process harness host observation match its fixture."""
    from sofia.platform.ops import platform_installer_bundle as bundle_module

    original = bundle_module.host_release_target
    bundle_module.host_release_target = lambda: _TARGET
    try:
        yield
    finally:
        bundle_module.host_release_target = original


def _require(condition: object, label: str, detail: object = None) -> None:
    if not condition:
        raise AcceptanceFailure(f"{label}: {detail!r}")


def _json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _observed_checkout_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "-c", f"safe.directory={_ROOT}", "rev-parse", "HEAD"],
            cwd=str(_ROOT), capture_output=True, text=True, timeout=15,
        )
        value = completed.stdout.strip()
        if completed.returncode == 0 and _HEX40.fullmatch(value):
            return value
    except (OSError, subprocess.SubprocessError):
        pass
    return "a" * 40


def _source_tree_clean() -> bool | None:
    try:
        completed = subprocess.run(
            ["git", "-c", f"safe.directory={_ROOT}", "status", "--porcelain",
             "--untracked-files=normal"],
            cwd=str(_ROOT), capture_output=True, text=True, timeout=15,
        )
        if completed.returncode == 0:
            return not completed.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _fake_python_prefix(root: Path) -> Path:
    prefix = root / "python-prefix"
    binary = prefix / "bin/python3.12"
    binary.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(64)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 62)
    binary.write_bytes(data)
    for name in ("site.py", "ensurepip/__init__.py", "os.py"):
        path = prefix / "lib/python3.12" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            b"" if name.startswith("ensurepip") else b"# standard library fixture\n"
        )
    unwanted = prefix / "lib/python3.12/site-packages/sofia/core/synthetic.py"
    unwanted.parent.mkdir(parents=True, exist_ok=True)
    unwanted.write_bytes(b"# synthetic forbidden application payload")
    return prefix


@dataclass(frozen=True, slots=True)
class Bundle:
    root: Path
    manifest: PlatformReleaseManifest
    signature_b64: str
    assets: dict[str, str]

    @property
    def review(self) -> dict[str, object]:
        return {
            "release_id": self.manifest.release_id,
            "revision": self.manifest.revision,
            "source_sha": self.manifest.source_sha,
            "manifest_sha256": self.manifest.digest,
            "target": self.manifest.target.value,
            "assets": dict(self.assets),
        }


class DisposableBundleFactory:
    """Test-signed, offline bundles made from the current checkout.

    The Ed25519 key is generated in memory and is never a production or owner
    key.  The resulting bundle is real canonical release data; its trust and
    installation authority are intentionally disposable.
    """

    def __init__(self, root: Path, wheels: dict[str, Path], source_sha: str):
        self.root = Path(root)
        ensure_owner_private_directory(self.root)
        self.wheels = dict(wheels)
        self.source_sha = source_sha
        self.signer_key_id = "aegis-guided-acceptance-disposable-signer"
        self._key = Ed25519PrivateKey.generate()
        public = self.public_key_bytes()
        self.verifier = PlatformReleaseVerifier({self.signer_key_id: public})
        self._prefix: Path | None = None

    def public_key_bytes(self) -> bytes:
        return self._key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def stage(self, *, release_id: str, revision: int,
              parent_manifest_sha256: str | None = None) -> Bundle:
        safe_name = re.sub(r"[^a-z0-9-]+", "-", release_id.lower()).strip("-")[:32]
        build = self.root / f"assets-{safe_name}-r{revision}"
        if build.exists():
            raise FileExistsError("disposable bundle build already exists")
        build.mkdir()
        if self._prefix is None:
            self._prefix = _fake_python_prefix(self.root)
        prefix = self._prefix
        service = build / "aegis-platform-service"
        service.write_bytes((prefix / "bin/python3.12").read_bytes())
        contents: dict[str, tuple[str, bytes]] = {}
        for kind, wheel in self.wheels.items():
            contents[wheel.name] = (kind, wheel.read_bytes())
        contents["aegis-platform-service"] = ("service", service.read_bytes())
        runtime = build_python_runtime(
            prefix, build / "python-runtime.zip", target=_TARGET,
            python_version="3.12.16",
        )
        contents[runtime.reference.path] = (
            "python-runtime", (build / "python-runtime.zip").read_bytes(),
        )
        observed = []
        for kind, wheel in self.wheels.items():
            observed.append({"distribution": wheel.stem.split("-")[0], "path": wheel.name})
        contents["dependency-index.json"] = ("dependency-lock", _json({
            "schema": "aegis.guided.acceptance.dependency-index.v1",
            "wheels": observed,
            "production_authorized": False,
        }))
        contents["observed-sbom.json"] = ("sbom", _json({
            "schema": "aegis.guided.acceptance.sbom.v1",
            "packages": observed,
            "production_authorized": False,
            "standards_compliance_claimed": False,
        }))
        contents["assembly-provenance.json"] = ("provenance", _json({
            "schema": "aegis.guided.acceptance.provenance.v1",
            "source_sha": self.source_sha,
            "fixture_signing_only": True,
            "production_release_attested": False,
        }))
        assets: list[PlatformReleaseAsset] = []
        asset_digests: dict[str, str] = {}
        for name, (kind, data) in sorted(contents.items()):
            path = build / name
            path.write_bytes(data)
            digest = _sha256_bytes(data)
            asset_digests[name] = digest
            assets.append(PlatformReleaseAsset(
                kind, ArtifactReference(name, digest, len(data)),
            ))
        manifest = PlatformReleaseManifest(
            release_id, "0.1.0", int(revision), self.source_sha, _TARGET,
            SDK_PROTOCOL_VERSION, "3.12.16", tuple(assets), parent_manifest_sha256,
        )
        signature = b64encode(
            self._key.sign(manifest.digest.encode("ascii"))
        ).decode("ascii")
        destination = self.root / f"bundle-{safe_name}-r{revision}"
        stage_platform_release(
            verifier=self.verifier, payload=manifest.to_payload(),
            signature_b64=signature, signer_key_id=self.signer_key_id,
            assets_root=build, destination=destination,
            expected_source_sha=self.source_sha, expected_target=_TARGET,
            minimum_revision=1,
            expected_parent_manifest_sha256=parent_manifest_sha256,
        )
        return Bundle(destination, manifest, signature, asset_digests)


@dataclass(frozen=True, slots=True)
class TrustAnchor:
    root: Path
    key_path: Path
    key_sha256: str
    signer_key_id: str
    source_sha: str
    target: PlatformReleaseTarget
    minimum_revision: int


def make_trust_anchor(root: Path, factory: DisposableBundleFactory,
                      *, minimum_revision: int = 1) -> TrustAnchor:
    root = Path(root)
    ensure_owner_private_directory(root)
    key_path = root / "publisher.pem"
    public = factory.public_key_bytes()
    key_path.write_bytes(public)
    anchor = {
        "schema": "aegis.guided-installer-trust-anchor.v1",
        "publisher_key_sha256": _sha256_bytes(public),
        "signer_key_id": factory.signer_key_id,
        "source_sha": factory.source_sha,
        "target": _TARGET.value,
        "minimum_revision": int(minimum_revision),
        "note": "DISPOSABLE ACCEPTANCE TRUST ANCHOR - NOT PRODUCTION",
        "production_authorized": False,
    }
    (root / "trust-anchor.json").write_text(
        json.dumps(anchor, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    return TrustAnchor(
        root=root, key_path=key_path,
        key_sha256=anchor["publisher_key_sha256"],
        signer_key_id=factory.signer_key_id,
        source_sha=factory.source_sha, target=_TARGET,
        minimum_revision=int(minimum_revision),
    )


def discover_inputs(bundle_root: Path, trust_root: Path) -> dict[str, object]:
    """Discover bundle/trust inputs without operator-entered SHA/Python values."""
    bundle_root = Path(bundle_root).absolute()
    trust_root = Path(trust_root).absolute()
    anchor_path = trust_root / "trust-anchor.json"
    key_path = trust_root / "publisher.pem"
    if not anchor_path.is_file() or not key_path.is_file():
        raise AcceptanceFailure("trust anchor is not independently provisioned")
    try:
        anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AcceptanceFailure("trust anchor is unreadable") from error
    if type(anchor) is not dict:
        raise AcceptanceFailure("trust anchor is not an object")
    key_digest = _sha256_file(key_path)
    if not _HEX64.fullmatch(str(anchor.get("publisher_key_sha256", ""))):
        raise AcceptanceFailure("trust anchor pin is not canonical")
    if key_digest != anchor["publisher_key_sha256"]:
        raise AcceptanceFailure("publisher key differs from the independent pin")
    if anchor.get("target") != _TARGET.value:
        raise AcceptanceFailure("trust anchor target is not the simulated host")
    source_sha = anchor.get("source_sha")
    if not isinstance(source_sha, str) or not _HEX40.fullmatch(source_sha):
        raise AcceptanceFailure("trust anchor source SHA is not canonical")
    runtime = bundle_root / "runtime" / "python" / "bin" / "python3.12"
    if not runtime.is_file():
        raise AcceptanceFailure("signed runtime interpreter is not discoverable")
    return {
        "bundle_root": bundle_root,
        "publisher_key": key_path,
        "publisher_key_sha256": key_digest,
        "publisher_signer": anchor["signer_key_id"],
        "expected_source_sha": source_sha,
        "target": anchor["target"],
        "minimum_revision": int(anchor["minimum_revision"]),
        "runtime_python": runtime,
        "manual_inputs_required": [],
    }


@dataclass(slots=True)
class Host:
    root: Path
    identity: InstallationIdentityStore
    current: object
    local_state: Path
    safe: Path
    store_path: Path
    destination: Path
    operator_root: Path
    operator_code: Path
    operator_bin: Path
    operator_global_bin: Path
    operator_desktop: Path
    operator_gui: Path

    @property
    def store(self) -> PlatformInstallationStore:
        return PlatformInstallationStore(self.store_path)


def provision_host(root: Path) -> Host:
    root = Path(root)
    ensure_owner_private_directory(root)
    identity = InstallationIdentityStore(root / "identity")
    current = identity.initialize()
    local_state = root / "platform.db"
    PlatformLocalStore(
        local_state,
        roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
        host_identity=current.identity.canonical_uuid,
    )
    safe = bootstrap_canonical_sqlite(root / "safe.db")
    OperatorStopStore(safe)
    operator_root = root / "operator"
    operator_code = operator_root / "code"
    operator_bin = operator_root / "bin"
    operator_global_bin = operator_root / "global-bin"
    operator_desktop = operator_root / "desktop"
    operator_gui = operator_root / "gui/aegis-control-center"
    operator_code.mkdir(parents=True, exist_ok=True)
    operator_gui.parent.mkdir(parents=True, exist_ok=True)
    operator_gui.write_bytes(b"simulated-aegis-control-center")
    return Host(
        root=root, identity=identity, current=current,
        local_state=local_state, safe=safe,
        store_path=root / "b1.db", destination=root / "installed",
        operator_root=operator_root, operator_code=operator_code,
        operator_bin=operator_bin, operator_global_bin=operator_global_bin,
        operator_desktop=operator_desktop, operator_gui=operator_gui,
    )


def _operator_fields(host: Host, runtime_python: Path,
                     bundle_root: Path) -> dict[str, object]:
    return {
        "operator_apps_requested": True,
        "operator_apps_runtime_python": runtime_python,
        "operator_apps_code_directory": host.operator_code,
        "operator_apps_bin_directory": host.operator_bin,
        "operator_apps_gui_executable": host.operator_gui,
        "operator_apps_global_bin_directory": host.operator_global_bin,
        "operator_apps_desktop_directory": host.operator_desktop,
        "operator_apps_approved_roots": (host.root, bundle_root),
        "operator_apps_protected_paths": (
            host.identity.home, host.local_state, host.safe,
        ),
        "operator_apps_path_scope": "user",
    }


def build_inputs(bundle: Bundle, trust: TrustAnchor, host: Host, *,
                 minimum_revision: int, destination: Path | None = None,
                 previous_destination: Path | None = None,
                 expected_parent_manifest_sha256: str | None = None,
                 operator_apps: bool = False,
                 code_approval_id: str | None = None,
                 approval_id: str | None = None,
                 operator_apps_approval_id: str | None = None) -> InstallerInputs:
    runtime = bundle.root / "runtime" / "python" / "bin" / "python3.12"
    values: dict[str, object] = {
        "release_root": bundle.root,
        "publisher_key": trust.key_path,
        "publisher_key_sha256": trust.key_sha256,
        "publisher_signer": trust.signer_key_id,
        "expected_source_sha": trust.source_sha,
        "target": trust.target.value,
        "minimum_revision": minimum_revision,
        "destination": destination or host.destination,
        "identity_home": host.identity.home,
        "local_state": host.local_state,
        "canonical_safe_state": host.safe,
        "store_path": host.store_path,
        "previous_destination": previous_destination,
        "expected_parent_manifest_sha256": expected_parent_manifest_sha256,
        "code_approval_id": code_approval_id,
        "approval_id": approval_id,
        "operator_apps_approval_id": operator_apps_approval_id,
    }
    if operator_apps:
        values.update(_operator_fields(host, runtime, bundle.root))
    return InstallerInputs(**values)


def fake_native_backend() -> DebianSystemdNativeService:
    """Real reviewed driver type with simulated in-memory OS effect methods."""
    backend = DebianSystemdNativeService()
    backend.unit_path = Path("/etc/systemd/system/aegis-platform.service")
    effects: list[dict[str, object]] = []
    backend.effects = effects  # type: ignore[attr-defined]
    backend.current = None  # type: ignore[attr-defined]

    def receipt(spec, process_state: str) -> dict[str, object]:
        effects.append({
            "operation": "register" if getattr(backend, "current", None) is None else "effect",
            "platform_id": spec.platform_id,
            "release_manifest_sha256": spec.manifest_sha256,
            "process_state": process_state,
        })
        return {
            "schema": "aegis.native-service-receipt.v1",
            "service": spec.service_name,
            "origin": "OWNED_CONFIG_VERIFIED",
            "process_state": process_state,
            "process_id": 1 if process_state == "RUNNING" else None,
            "platform_id": spec.platform_id,
            "release_manifest_sha256": spec.manifest_sha256,
            "service_health": "UNKNOWN",
            "core_activated": False,
            "fully_healthy": False,
        }

    def register(spec):
        _require(getattr(backend, "current", None) is None,
                 "duplicate native registration", spec.release_id)
        backend.current = spec  # type: ignore[attr-defined]
        return receipt(spec, "RUNNING")

    def restart_verified(spec):
        current = getattr(backend, "current", None)
        _require(current is not None, "repair without registered service")
        _require(current.manifest_sha256 == spec.manifest_sha256,
                 "repair changed signed release")
        return receipt(spec, "RUNNING")

    def replace_verified(previous, candidate):
        current = getattr(backend, "current", None)
        _require(current is not None, "replacement without registered service")
        _require(previous.manifest_sha256 == current.manifest_sha256,
                 "replacement previous release differs")
        backend.current = candidate  # type: ignore[attr-defined]
        return receipt(candidate, "RUNNING")

    def stop_and_unregister(spec):
        current = getattr(backend, "current", None)
        _require(current is not None, "unregister without registered service")
        _require(current.manifest_sha256 == spec.manifest_sha256,
                 "unregister release differs")
        backend.current = None  # type: ignore[attr-defined]
        return receipt(spec, "REMOVED")

    def observe(spec):
        _require(getattr(backend, "current", None) is not None,
                 "observe without registered service")
        return receipt(spec, "RUNNING")

    backend.register = register  # type: ignore[method-assign]
    backend.restart_verified = restart_verified  # type: ignore[method-assign]
    backend.replace_verified = replace_verified  # type: ignore[method-assign]
    backend.stop_and_unregister = stop_and_unregister  # type: ignore[method-assign]
    backend.observe = observe  # type: ignore[method-assign]
    return backend


class FakeShortcuts:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.removed: list[str] = []

    def create(self, spec) -> None:
        self.created.append(str(spec.path))
        spec.path.parent.mkdir(parents=True, exist_ok=True)
        spec.path.write_bytes(b"simulated-shortcut")

    def remove(self, spec) -> None:
        self.removed.append(str(spec.path))
        spec.path.unlink(missing_ok=True)


def _record_approval(safe: Path, capability: str, fingerprint: str,
                     label: str) -> str:
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=f"approval:guided-{label}-{uuid4().hex[:12]}",
        capability=capability,
        request_fingerprint=fingerprint,
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(safe), approval)
    return approval.approval_id


def _record_for_request(safe: Path, request: dict[str, object],
                        label: str) -> str:
    return _record_approval(
        safe, str(request["capability"]), str(request["fingerprint"]), label,
    )


def _run_with_approvals(command: str, inputs: InstallerInputs, host: Host,
                        backend, path_adapter, shortcuts,
                        *, allow_failure: bool = False) -> tuple[
                            dict[str, object], list[dict[str, object]]]:
    attempts: list[dict[str, object]] = []
    current = inputs
    for _ in range(8):
        result = execute_command(
            command, current, backend=backend,
            operator_apps_path_adapter=path_adapter,
            operator_apps_shortcut_adapter=shortcuts,
        )
        attempts.append({
            "outcome": result["outcome"],
            "required_approval": result.get("required_approval"),
            "approval_fingerprint": result.get("approval_fingerprint"),
            "executed": result["executed"],
            "owner_approved": result["owner_approved"],
        })
        if result["outcome"] in SUCCESS_OUTCOMES:
            return result, attempts
        kind = result.get("required_approval")
        fingerprint = result.get("approval_fingerprint")
        if result["outcome"] != "DENIED" or kind not in _CAPABILITY:
            if allow_failure:
                return result, attempts
            raise AcceptanceFailure(
                f"{command} did not request a supported owner approval: {result}"
            )
        if not isinstance(fingerprint, str) or not _HEX64.fullmatch(fingerprint):
            raise AcceptanceFailure(f"{command} returned an invalid approval fingerprint")
        approval_id = _record_approval(
            host.safe, _CAPABILITY[kind], fingerprint,
            f"{command}-{kind}",
        )
        if kind == "code":
            current = replace(current, code_approval_id=approval_id)
        elif kind == "native":
            current = replace(current, approval_id=approval_id)
        else:
            current = replace(current, operator_apps_approval_id=approval_id)
    raise AcceptanceFailure(f"{command} exhausted its bounded approval retries")


def _command_record(command: str, result: dict[str, object], attempts,
                    *, equivalent: str | None = None) -> dict[str, object]:
    return {
        "command": command,
        "equivalent_cli": equivalent or f"python -m sofia.platform.ops.platform_installer_cli {command}",
        "outcome": result["outcome"],
        "executed": result["executed"],
        "owner_approved": result["owner_approved"],
        "release_id": result.get("release_id"),
        "revision": result.get("revision"),
        "manifest_sha256": result.get("manifest_sha256"),
        "source_sha": result.get("source_sha"),
        "attempts": attempts,
        "pass": result["outcome"] in SUCCESS_OUTCOMES,
    }


def _assert_no_target_effects(host: Host, backend, shortcuts) -> None:
    _require(len(backend.effects) == 0, "native effects occurred before approval")
    _require(list(shortcuts.created) == [], "shortcut effects occurred before approval")
    _require(not host.destination.exists(), "destination exists before approval")
    _require(not host.operator_bin.exists(), "launcher bin exists before approval")
    _require(host.store.history() == [], "B1 history exists before approval")


class Accept:
    def __init__(self, root: Path, factory: DisposableBundleFactory,
                 trust: TrustAnchor):
        self.root = root
        self.factory = factory
        self.trust = trust
        self.commands: list[dict[str, object]] = []
        self.bundles: list[dict[str, object]] = []

    def bundle(self, bundle: Bundle) -> Bundle:
        self.bundles.append(bundle.review)
        return bundle


def _scenario_guided_discovery(accept: Accept, work: Path) -> dict[str, object]:
    host = provision_host(work / "discovery-host")
    bundle = accept.bundle(accept.factory.stage(
        release_id="aegis-guided-discovery-v1", revision=1,
    ))
    discovered = discover_inputs(bundle.root, accept.trust.root)
    _require(discovered["manual_inputs_required"] == [], "manual inputs were required")
    _require(discovered["expected_source_sha"] == bundle.manifest.source_sha,
             "discovered source SHA differs")
    _require(discovered["publisher_key_sha256"] == accept.trust.key_sha256,
             "discovered publisher pin differs")
    _require(Path(discovered["runtime_python"]).is_file(),
             "discovered runtime is missing")
    inputs = build_inputs(
        bundle, accept.trust, host, minimum_revision=1,
        operator_apps=True,
    )
    _require(inputs.publisher_key == accept.trust.key_path, "key path was not discovered")
    _require(inputs.operator_apps_runtime_python == discovered["runtime_python"],
             "runtime path was not discovered")
    verified = execute_command("verify", inputs)
    accept.commands.append(_command_record("verify", verified, []))
    _require(verified["outcome"] == "VERIFIED", "discovered bundle did not verify")
    return {
        "manual_inputs_required": [],
        "discovered": {
            "release_root": str(bundle.root),
            "publisher_key": str(accept.trust.key_path),
            "publisher_key_sha256": discovered["publisher_key_sha256"],
            "publisher_signer": discovered["publisher_signer"],
            "expected_source_sha": discovered["expected_source_sha"],
            "runtime_python": str(discovered["runtime_python"]),
            "target": discovered["target"],
        },
        "verify_outcome": verified["outcome"],
    }


def _scenario_check(accept: Accept, work: Path) -> dict[str, object]:
    host = provision_host(work / "check-host")
    bundle = accept.bundle(accept.factory.stage(
        release_id="aegis-guided-check-v1", revision=1,
    ))
    inputs = build_inputs(bundle, accept.trust, host, minimum_revision=1,
                          operator_apps=True)
    verified = execute_command("verify", inputs)
    accept.commands.append(_command_record("verify", verified, []))
    _require(verified["outcome"] == "VERIFIED", "check verify failed")
    store = PlatformInstallationStore(host.store_path)
    plan = preview_signed_platform_install(
        staging_path=bundle.root, destination=host.destination, store=store,
        verifier=accept.factory.verifier, expected_target=_TARGET,
    )
    effects: list[object] = []
    backend = fake_native_backend()
    shortcuts = FakeShortcuts()
    _require(plan["executed"] is False, "preview claimed execution")
    _require(plan["owner_approved"] is False, "preview claimed owner approval")
    _require(plan["production_authorized"] is False, "preview claimed production authority")
    _require(plan["os_service_registered"] is False, "preview claimed service registration")
    _require(not host.destination.exists(), "check created the target")
    _require(not host.operator_bin.exists(), "check created launcher files")
    _require(store.history() == [], "check wrote installation history")
    _require(backend.effects == [] and effects == [], "check caused native effects")
    _require(shortcuts.created == [], "check caused shortcut effects")
    return {
        "preview_only": True,
        "preview_executed": plan["executed"],
        "preview_owner_approved": plan["owner_approved"],
        "preview_production_authorized": plan["production_authorized"],
        "destination_exists": host.destination.exists(),
        "store_history_entries": len(store.history()),
        "native_effects": len(backend.effects),
        "shortcut_effects": len(shortcuts.created),
    }


def _scenario_lifecycle(accept: Accept, work: Path) -> dict[str, object]:
    host = provision_host(work / "lifecycle-host")
    v4 = accept.bundle(accept.factory.stage(
        release_id="aegis-guided-lifecycle-v4", revision=4,
    ))
    v5 = accept.bundle(accept.factory.stage(
        release_id="aegis-guided-lifecycle-v5", revision=5,
        parent_manifest_sha256=v4.manifest.digest,
    ))
    backend = fake_native_backend()
    shortcuts = FakeShortcuts()
    paths = InMemoryPathAdapter(value="/usr/local/bin:/usr/bin:/bin")
    failures: list[dict[str, object]] = []
    identity_before = InstallationIdentityStore(host.identity.home).load()
    state_before = _sha256_file(host.local_state)

    install_inputs = build_inputs(
        v4, accept.trust, host, minimum_revision=4, operator_apps=True,
    )
    _assert_no_target_effects(host, backend, shortcuts)
    installed, install_attempts = _run_with_approvals(
        "install", install_inputs, host, backend, paths, shortcuts,
    )
    accept.commands.append(_command_record("install", installed, install_attempts))
    _require(installed["outcome"] == "INSTALLED", "install did not complete")
    _require(len(backend.effects) == 1, "install duplicate native effects")
    _require((host.operator_bin / "aegis").is_file(), "install omitted aegis launcher")
    _require((host.operator_global_bin / "aegis").is_file(),
             "install omitted global aegis launcher")
    _require((host.operator_desktop / "aegis-platform.desktop").is_file(),
             "install omitted desktop entry")
    _require(paths.value == "/usr/local/bin:/usr/bin:/bin",
             "Debian operator apps changed PATH unexpectedly")

    verify_v4 = execute_command("verify", build_inputs(
        v4, accept.trust, host, minimum_revision=4,
    ))
    accept.commands.append(_command_record("verify", verify_v4, []))
    _require(verify_v4["outcome"] == "VERIFIED", "verify v4 failed")

    initial_repair_inputs = build_inputs(
        v4, accept.trust, host, minimum_revision=4,
        destination=host.destination, operator_apps=True,
    )
    effect_count = len(backend.effects)
    initial_repair, initial_repair_attempts = _run_with_approvals(
        "repair", initial_repair_inputs, host, backend, paths, shortcuts,
    )
    accept.commands.append(_command_record(
        "repair", initial_repair, initial_repair_attempts,
    ))
    _require(initial_repair["outcome"] == "REPAIRED",
             "current-release repair did not complete")
    _require(len(backend.effects) == effect_count + 1,
             "current-release repair duplicate native effects")

    v5_destination = work / "lifecycle-host" / "installed-v5"
    update_inputs = build_inputs(
        v5, accept.trust, host, minimum_revision=5,
        destination=v5_destination, previous_destination=host.destination,
        operator_apps=True,
    )
    effect_count = len(backend.effects)
    updated, update_attempts = _run_with_approvals(
        "update", update_inputs, host, backend, paths, shortcuts,
    )
    accept.commands.append(_command_record("update", updated, update_attempts))
    _require(updated["outcome"] == "UPDATED", "update did not complete")
    _require(len(backend.effects) == effect_count + 1, "update duplicate native effects")

    verify_v5 = execute_command("verify", build_inputs(
        v5, accept.trust, host, minimum_revision=5,
        expected_parent_manifest_sha256=v4.manifest.digest,
    ))
    accept.commands.append(_command_record("verify", verify_v5, []))
    _require(verify_v5["outcome"] == "VERIFIED", "verify v5 failed")

    repair_inputs = build_inputs(
        v5, accept.trust, host, minimum_revision=5,
        destination=v5_destination,
        expected_parent_manifest_sha256=v4.manifest.digest,
        operator_apps=True,
    )
    effect_count = len(backend.effects)
    repaired, repair_attempts = _run_with_approvals(
        "repair", repair_inputs, host, backend, paths, shortcuts,
        allow_failure=True,
    )
    accept.commands.append(_command_record("repair", repaired, repair_attempts))
    if repaired["outcome"] != "REPAIRED":
        failures.append({
            "operation": "repair_after_update",
            "outcome": repaired["outcome"],
            "required_approval": repaired.get("required_approval"),
            "reason": (
                "production platform_installer_cli did not forward the trusted "
                "predecessor digest from _verify_installed_release, so a signed "
                "child release could not be re-verified for repair"
            ),
        })
    else:
        _require(len(backend.effects) == effect_count + 1,
                 "repair duplicate native effects")

    rollback_inputs = build_inputs(
        v4, accept.trust, host, minimum_revision=5,
        destination=host.destination, previous_destination=v5_destination,
    )
    effect_count = len(backend.effects)
    rolled_back, rollback_attempts = _run_with_approvals(
        "rollback", rollback_inputs, host, backend, paths, shortcuts,
    )
    accept.commands.append(_command_record("rollback", rolled_back, rollback_attempts))
    _require(rolled_back["outcome"] == "ROLLED_BACK", "rollback did not complete")
    _require(len(backend.effects) == effect_count + 1, "rollback duplicate native effects")
    _require(host.store.revision_floor() == 5, "rollback lowered the durable floor")

    uninstall_inputs = build_inputs(
        v4, accept.trust, host, minimum_revision=4,
        destination=host.destination, operator_apps=True,
    )
    effect_count = len(backend.effects)
    uninstalled, uninstall_attempts = _run_with_approvals(
        "uninstall", uninstall_inputs, host, backend, paths, shortcuts,
    )
    accept.commands.append(_command_record("uninstall", uninstalled, uninstall_attempts))
    _require(uninstalled["outcome"] == "UNINSTALLED", "uninstall did not complete")
    _require(len(backend.effects) == effect_count + 1, "uninstall duplicate native effects")
    _require(not (host.operator_bin / "aegis").exists(), "uninstall left aegis launcher")
    _require(not (host.operator_global_bin / "aegis").exists(),
             "uninstall left global aegis launcher")
    _require(not (host.operator_desktop / "aegis-platform.desktop").exists(),
             "uninstall left desktop entry")
    _require(host.destination.is_dir(), "uninstall deleted the installed release")
    _require(InstallationIdentityStore(host.identity.home).load() == identity_before,
             "uninstall changed protected identity")
    _require(_sha256_file(host.local_state) == state_before,
             "uninstall changed protected local state")

    reinstall_inputs = build_inputs(
        v4, accept.trust, host, minimum_revision=4,
        destination=host.destination,
    )
    effect_count = len(backend.effects)
    reinstalled, reinstall_attempts = _run_with_approvals(
        "reinstall", reinstall_inputs, host, backend, paths, shortcuts,
    )
    accept.commands.append(_command_record("reinstall", reinstalled, reinstall_attempts))
    _require(reinstalled["outcome"] == "REINSTALLED", "reinstall did not complete")
    _require(len(backend.effects) == effect_count + 1, "reinstall duplicate native effects")
    _require(InstallationIdentityStore(host.identity.home).load() == identity_before,
             "reinstall changed protected identity")
    _require(_sha256_file(host.local_state) == state_before,
             "reinstall changed protected local state")
    _require(host.store.revision_floor() == 5, "reinstall changed durable floor")

    status = execute_command("status", build_inputs(
        v4, accept.trust, host, minimum_revision=4,
        destination=host.destination,
    ))
    accept.commands.append(_command_record("status", status, []))
    _require(status["outcome"] == "OK", "post-reinstall status is not OK")
    _require(status["installed_verified"] is True, "post-reinstall bytes are unverified")
    _require(status["release_id"] == v4.manifest.release_id,
             "post-reinstall status reported another release")

    journal = native_transaction_state(host.store)
    _require(journal is not None and journal["current"] is not None,
             "native service is not registered after reinstall")
    _require(journal["phase"] == "SERVICE_OBSERVED", "native journal phase differs")
    _require(sum(1 for item in backend.effects
                 if item["process_state"] == "RUNNING") == 5,
             "unexpected running-service effect count")

    launcher_names = sorted(
        path.name for path in host.operator_root.rglob("*")
        if path.is_file() and path.name in {"aegis", "aegis.cmd", "aegis.bat",
                                            "aegis.ps1", "aegis.exe"}
    )
    _require(launcher_names == [], "reinstall unexpectedly recreated operators")
    state_names = sorted(
        path.name for path in host.root.rglob("*")
        if path.name in {"sofia.db", "platform.db"}
    )
    _require(state_names.count("platform.db") == 1,
             "duplicate Platform writer state", state_names)
    _require("sofia.db" not in state_names, "unexpected Core writer state exists")
    _require(paths.value == "/usr/local/bin:/usr/bin:/bin",
             "Debian PATH changed during lifecycle")

    return {
        "_pass": not failures,
        "failures": failures,
        "pre_update_repair": initial_repair["outcome"],
        "effects": backend.effects,
        "effect_count": len(backend.effects),
        "durable_revision_floor": host.store.revision_floor(),
        "identity_preserved": True,
        "protected_state_preserved": True,
        "operator_launchers_after_uninstall": 0,
        "single_writer_state": state_names,
        "native_journal_phase": journal["phase"],
        "post_reinstall_status": status["outcome"],
        "post_reinstall_installed_verified": status["installed_verified"],
    }


def _windows_operator_scenario(work: Path) -> dict[str, object]:
    root = work / "operator-windows"
    ensure_owner_private_directory(root)
    runtime = root / "runtime/python.exe"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_bytes(b"simulated-windows-python")
    code = root / "code"
    code.mkdir()
    gui = root / "gui/aegis-control-center.exe"
    gui.parent.mkdir(parents=True, exist_ok=True)
    gui.write_bytes(b"simulated-windows-gui")
    bin_dir = root / "bin"
    global_bin = root / "global-bin"
    start_menu = root / "start-menu"
    desktop = root / "desktop"
    config = OperatorAppsConfiguration(
        target=PlatformReleaseTarget.WINDOWS_X86_64,
        runtime_python=runtime, code_directory=code, bin_directory=bin_dir,
        gui_executable=gui, start_menu_directory=start_menu,
        desktop_directory=desktop, global_bin_directory=global_bin,
        approved_roots=(root,), protected_paths=(),
        path_scope="user", include_powershell=True,
        include_desktop_shortcut=True,
    )
    paths = InMemoryPathAdapter(value=r"C:\Windows;C:\Tools")
    shortcuts = FakeShortcuts()
    safe = bootstrap_canonical_sqlite(root / "safe.db")
    OperatorStopStore(safe)
    store = PlatformInstallationStore(root / "b1.db")

    def apply(operation: str) -> dict[str, object]:
        request = operator_apps_request(operation, config)
        approval_id = _record_for_request(
            safe, request, f"operator-{operation}-{uuid4().hex[:6]}",
        )
        return apply_owner_approved_operator_apps(
            approval_id=approval_id, operation=operation, config=config,
            state_path=safe, store=store, path_adapter=paths,
            shortcut_adapter=shortcuts,
        )

    first = apply("install")
    _require((bin_dir / "aegis.cmd").is_file(), "Windows launcher is missing")
    _require((bin_dir / "aegis.ps1").is_file(), "PowerShell shim is missing")
    _require(len(shortcuts.created) == 2, "shortcut plan did not create both shortcuts")
    _require(paths.value.count(str(bin_dir)) == 1, "PATH entry was duplicated")
    launcher_hashes = {
        name: _sha256_file(bin_dir / name) for name in ("aegis.cmd", "aegis.ps1")
    }

    second = apply("install")
    _require(second["path_action"]["action"] == "NO_CHANGE", "reapply changed PATH")
    _require(all(item["action"] == "NO_CHANGE" for item in second["shortcut_actions"]),
             "reapply changed shortcuts")
    _require(paths.value.count(str(bin_dir)) == 1, "reapply duplicated the PATH entry")
    _require(launcher_hashes == {
        name: _sha256_file(bin_dir / name) for name in ("aegis.cmd", "aegis.ps1")
    }, "reapply rewrote owned launchers")

    removed = apply("uninstall")
    _require(not (bin_dir / "aegis.cmd").exists(), "uninstall left aegis.cmd")
    _require(not (bin_dir / "aegis.ps1").exists(), "uninstall left aegis.ps1")
    _require(str(bin_dir) not in paths.value, "uninstall left the PATH entry")
    _require(len(shortcuts.removed) == 2, "uninstall did not remove both shortcuts")
    _require(removed["path_action"]["action"] == "REMOVE", "uninstall did not remove PATH")

    again = apply("uninstall")
    _require(again["path_action"]["action"] == "NO_CHANGE", "second uninstall changed PATH")
    _require(all(item["action"] == "NO_CHANGE" for item in again["shortcut_actions"]),
             "second uninstall changed shortcuts")
    _require(paths.value == r"C:\Windows;C:\Tools", "uninstall corrupted PATH")
    return {
        "launchers": ["aegis.cmd", "aegis.ps1"],
        "path_entry": str(bin_dir),
        "path_after_uninstall": paths.value,
        "shortcuts_created": len(shortcuts.created),
        "shortcuts_removed": len(shortcuts.removed),
        "first_path_action": first["path_action"]["action"],
        "second_path_action": second["path_action"]["action"],
        "uninstall_path_action": removed["path_action"]["action"],
        "second_uninstall_path_action": again["path_action"]["action"],
    }


def _scenario_stop(accept: Accept, work: Path) -> dict[str, object]:
    host = provision_host(work / "stop-host")
    bundle = accept.bundle(accept.factory.stage(
        release_id="aegis-guided-stop-v1", revision=1,
    ))
    inputs = build_inputs(bundle, accept.trust, host, minimum_revision=1)
    now = datetime.now(timezone.utc)
    OperatorStopStore(host.safe).set(
        active=True, updated_by="Sparks", reason="simulated operator STOP",
        at=now,
    )
    backend = fake_native_backend()
    result = execute_command("install", inputs, backend=backend)
    accept.commands.append(_command_record("install", result, []))
    _require(result["outcome"] == "DENIED", "install bypassed operator STOP")
    _require(result["executed"] is False, "STOP denial claimed execution")
    _require(not host.destination.exists(), "STOP denial created the target")
    _require(backend.effects == [], "STOP denial caused native effects")
    _require(host.store.history() == [], "STOP denial wrote history")
    return {
        "stop_active": OperatorStopStore(host.safe).current().active,
        "outcome": result["outcome"],
        "executed": result["executed"],
        "native_effects": len(backend.effects),
    }


def _scenario_revoked(accept: Accept, work: Path) -> dict[str, object]:
    host = provision_host(work / "revoked-host")
    bundle = accept.bundle(accept.factory.stage(
        release_id="aegis-guided-revoked-v1", revision=1,
    ))
    inputs = build_inputs(bundle, accept.trust, host, minimum_revision=1)
    first = execute_command("install", inputs)
    _require(first["outcome"] == "DENIED", "revocation setup was not denied")
    _require(first.get("required_approval") == "code",
             "revocation setup did not request code approval")
    approval_id = _record_approval(
        host.safe, CODE_PUBLISH_CAPABILITY, first["approval_fingerprint"],
        "revoked-code",
    )
    with sqlite3.connect(host.safe) as db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=? WHERE revoked_at IS NULL",
            (datetime.now(timezone.utc).isoformat(),),
        )
        db.commit()
    backend = fake_native_backend()
    result = execute_command(
        "install", replace(inputs, code_approval_id=approval_id),
        backend=backend,
    )
    accept.commands.append(_command_record("install", result, []))
    _require(result["outcome"] == "DENIED", "revoked owner proof was accepted")
    _require(result["executed"] is False, "revoked proof claimed execution")
    _require(not host.destination.exists(), "revoked proof created the target")
    _require(backend.effects == [], "revoked proof caused native effects")
    _require(host.store.history() == [], "revoked proof wrote history")
    return {
        "revoked_owner_proof": True,
        "outcome": result["outcome"],
        "executed": result["executed"],
        "native_effects": len(backend.effects),
    }


def _negative(
    accept: Accept, work: Path, name: str, inputs: InstallerInputs,
) -> dict[str, object]:
    host_root = work / f"negative-{name}"
    host = provision_host(host_root)
    inputs = replace(
        inputs, identity_home=host.identity.home, local_state=host.local_state,
        canonical_safe_state=host.safe, store_path=host.store_path,
        destination=host.destination,
    )
    backend = fake_native_backend()
    result = execute_command("install", inputs, backend=backend)
    accept.commands.append(_command_record("install", result, []))
    observed = {
        "scenario": name,
        "outcome": result["outcome"],
        "executed": result["executed"],
        "owner_approved": result["owner_approved"],
        "error_code": (result.get("error") or {}).get("code"),
        "destination_exists": host.destination.exists(),
        "native_effects": len(backend.effects),
        "history_entries": len(host.store.history()) if host.store_path.exists() else 0,
    }
    _require(result["outcome"] == "DENIED", f"{name} was not denied", result)
    _require(result["executed"] is False, f"{name} claimed execution")
    _require(result["owner_approved"] is False, f"{name} claimed owner approval")
    _require(not host.destination.exists(), f"{name} created the target")
    _require(backend.effects == [], f"{name} caused native effects")
    _require(not host.store_path.exists() or host.store.history() == [],
             f"{name} wrote installation history")
    return observed


def _scenario_negatives(accept: Accept, work: Path) -> dict[str, object]:
    bundle = accept.bundle(accept.factory.stage(
        release_id="aegis-guided-negative-v1", revision=1,
    ))
    host = provision_host(work / "negative-base")
    base = build_inputs(bundle, accept.trust, host, minimum_revision=1)
    results = []

    results.append(_negative(accept, work, "missing_trust_anchor", replace(
        base, publisher_key=work / "absent-publisher.pem",
    )))
    results.append(_negative(accept, work, "wrong_trust_pin", replace(
        base, publisher_key_sha256="0" * 64,
    )))
    results.append(_negative(accept, work, "wrong_trust_signer", replace(
        base, publisher_signer="attacker",
    )))
    results.append(_negative(accept, work, "wrong_source_sha", replace(
        base, expected_source_sha="0" * 40,
    )))
    results.append(_negative(accept, work, "stale_revision_floor", replace(
        base, minimum_revision=2,
    )))
    results.append(_negative(accept, work, "wrong_release_target", replace(
        base, target=PlatformReleaseTarget.WINDOWS_X86_64.value,
    )))
    results.append(_negative(accept, work, "wrong_parent_manifest", replace(
        base, expected_parent_manifest_sha256="f" * 64,
    )))

    inside = bundle.root / "self-supplied-publisher.pem"
    inside.write_bytes(accept.trust.key_path.read_bytes())
    results.append(_negative(accept, work, "trust_inside_bundle", replace(
        base, publisher_key=inside, publisher_key_sha256=_sha256_file(inside),
    )))

    def copied(name: str) -> Path:
        target = work / f"tampered-{name}"
        shutil.copytree(bundle.root, target)
        return target

    tampered_manifest = copied("manifest")
    (tampered_manifest / "release-manifest.json").write_text("{}", encoding="utf-8")
    results.append(_negative(accept, work, "tampered_release_manifest", replace(
        base, release_root=tampered_manifest,
    )))

    tampered_signature = copied("signature")
    signature_path = tampered_signature / "release-signature.json"
    document = json.loads(signature_path.read_text(encoding="utf-8"))
    document["signature_b64"] = "A" * 88
    signature_path.write_text(json.dumps(document), encoding="utf-8")
    results.append(_negative(accept, work, "tampered_release_signature", replace(
        base, release_root=tampered_signature,
    )))

    tampered_asset = copied("asset")
    first_asset = next(
        item for item in sorted((tampered_asset / "assets").rglob("*"))
        if item.is_file()
    )
    first_asset.write_bytes(first_asset.read_bytes() + b"tampering")
    results.append(_negative(accept, work, "tampered_release_asset", replace(
        base, release_root=tampered_asset,
    )))

    missing_dependency = copied("dependency")
    dependency = next(
        item.reference.path for item in bundle.manifest.assets
        if item.kind == "dependency-lock"
    )
    (missing_dependency / "assets" / dependency).unlink()
    results.append(_negative(accept, work, "missing_dependency_wheelhouse", replace(
        base, release_root=missing_dependency,
    )))

    missing_runtime = copied("runtime")
    runtime = next(
        item.reference.path for item in bundle.manifest.assets
        if item.kind == "python-runtime"
    )
    (missing_runtime / "assets" / runtime).unlink()
    results.append(_negative(accept, work, "missing_runtime_asset", replace(
        base, release_root=missing_runtime,
    )))

    return {"cases": results, "count": len(results)}


def _run_scenario(name: str, function, *args) -> dict[str, object]:
    try:
        observed = function(*args)
        passed = observed.pop("_pass", True) if isinstance(observed, dict) else True
        return {"name": name, "pass": bool(passed), "observed": observed}
    except Exception as error:  # noqa: BLE001 - report truthfully, never claim pass
        return {
            "name": name,
            "pass": False,
            "error": f"{type(error).__name__}: {error}",
            "trace": traceback.format_exc(limit=4),
        }


def _build_wheels(root: Path) -> dict[str, Path]:
    destination = root / "wheels"
    destination.mkdir(parents=True, exist_ok=True)
    return {
        kind: build_component(kind, destination, repo=_ROOT)
        for kind in ("sdk", "platform")
    }


def run_acceptance(*, check: bool = False, work_root: Path | str | None = None,
                   wheels: dict[str, Path] | None = None,
                   source_sha: str | None = None,
                   keep: bool = False) -> dict[str, object]:
    """Run the disposable acceptance matrix and return JSON-serializable evidence."""
    external_root = work_root is not None
    root = Path(work_root) if work_root is not None else Path(
        tempfile.mkdtemp(prefix="aegis-guided-acceptance-")
    )
    ensure_owner_private_directory(root)
    try:
        observed_sha = source_sha or _observed_checkout_sha()
        if not _HEX40.fullmatch(observed_sha):
            raise ValueError("exact lowercase 40-hex source SHA required")
        if wheels is None:
            wheels = _build_wheels(root)
        factory = DisposableBundleFactory(root / "bundles", wheels, observed_sha)
        trust = make_trust_anchor(root / "trust-root", factory)
        accept = Accept(root, factory, trust)
        with _simulated_debian_host():
            if check:
                scenarios = [
                    _run_scenario("check_preview_zero_effects", _scenario_check,
                                  accept, root),
                ]
                mode = "check"
                preview_only = True
            else:
                scenarios = [
                    _run_scenario("guided_discovery_no_manual_inputs",
                                  _scenario_guided_discovery, accept, root),
                    _run_scenario("default_guided_lifecycle", _scenario_lifecycle,
                                  accept, root),
                    _run_scenario("operator_apps_idempotent", _windows_operator_scenario,
                                  root),
                    _run_scenario("stop_denied", _scenario_stop, accept, root),
                    _run_scenario("revoked_owner_proof_denied", _scenario_revoked,
                                  accept, root),
                    _run_scenario("negative_release_and_trust_cases",
                                  _scenario_negatives, accept, root),
                ]
                mode = "guided"
                preview_only = False
        passed = all(item["pass"] for item in scenarios)
        report = {
            "schema": SCHEMA,
            "label": LABEL,
            "simulated": True,
            "mode": mode,
            "preview_only": preview_only,
            "pass": passed,
            "installed_host_verified": False,
            "production_authorized": False,
            "certified": False,
            "source_sha": observed_sha,
            "source_sha_origin": (
                "operator-supplied disposable fixture"
                if source_sha else "checkout HEAD (disposable fixture signed to this SHA)"
            ),
            "source_tree_clean": _source_tree_clean(),
            "fixture_signing_only": True,
            "trust_anchor_required_outside_bundle": True,
            "trust_anchor": {
                "root": str(trust.root),
                "publisher_key_sha256": trust.key_sha256,
                "signer_key_id": trust.signer_key_id,
                "expected_source_sha": trust.source_sha,
                "target": trust.target.value,
                "production_authorized": False,
            },
            "bundles": accept.bundles,
            "artifact_digests": {
                bundle["release_id"]: {
                    "manifest_sha256": bundle["manifest_sha256"],
                    "assets": bundle["assets"],
                }
                for bundle in accept.bundles
            },
            "commands": accept.commands,
            "scenarios": scenarios,
            "scenario_count": len(scenarios),
            "command_count": len(accept.commands),
            "work_root": str(root),
            "work_root_retained": bool(external_root or keep),
            "limitations": [
                "SIMULATED native service; no real SCM/systemd unit was created.",
                "SIMULATED operator shortcuts and PATH; no real registry/PATH/desktop was changed.",
                "Disposable test signing key; not a production publisher or owner trust root.",
                "installed_host_verified=false; production_authorized=false.",
                "Real signed Windows and Debian 12 disposable-host testing is still required.",
            ],
        }
        return report
    finally:
        if not external_root and not keep:
            shutil.rmtree(root, ignore_errors=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="run the read-only preview path only")
    parser.add_argument("--work-root", type=Path,
                        help="keep evidence and fixtures in this directory")
    parser.add_argument("--source-sha",
                        help="exact 40-hex fixture source SHA (defaults to checkout HEAD)")
    parser.add_argument("--keep", action="store_true",
                        help="retain a temporary work directory")
    parser.add_argument("--json", action="store_true",
                        help="emit one JSON report (default)")
    args = parser.parse_args(argv)
    try:
        report = run_acceptance(
            check=args.check, work_root=args.work_root,
            source_sha=args.source_sha, keep=args.keep,
        )
    except Exception as error:  # noqa: BLE001 - structured refusal, no false PASS
        print(json.dumps({
            "schema": SCHEMA,
            "label": LABEL,
            "simulated": True,
            "pass": False,
            "installed_host_verified": False,
            "production_authorized": False,
            "error": f"{type(error).__name__}: {error}",
        }, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2, default=str))
    return 0 if report["pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
