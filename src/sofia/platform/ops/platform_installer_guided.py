"""One-step attended orchestrator for the signed Aegis Platform installer.

The Windows and Linux launchers invoke this module only. It discovers the
signed release media and the separately provisioned installer trust anchor,
derives the exact host paths, verifies the release, previews the complete plan
without effects, and drives the existing canonical installer owners.

Owner authority is never minted here. When the canonical installer CLI reports
that an exact capability needs approval, this module asks the existing attended
``sofia.platform.safe.approve_execution`` ceremony to authenticate the owner and
returns only the resulting one-use approval identifier. The owner secret is
never read, stored or printed. The canonical CLI then consumes that approval.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
import platform
from pathlib import Path
import shutil
import re
import sqlite3
import subprocess
import sys
from typing import Callable, Mapping, Protocol, Sequence

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
)
from sofia.platform.ops.platform_installer_bundle import (
    SignedInstallerRelease, host_release_target, verify_offline_installer_bundle,
)
from sofia.platform.ops.platform_installer_cli import (
    InstallerInputs, apply_operator_apps_command, execute_command,
)
from sofia.platform.ops.platform_installer_code_install import (
    CODE_PUBLISH_CAPABILITY,
)
from sofia.platform.ops.platform_installer_native_service import (
    DebianSystemdNativeService, WindowsScmNativeService,
)
from sofia.platform.ops.platform_installer_operator_apps import (
    InMemoryPathAdapter, OPERATOR_APPS_CAPABILITY, OperatorAppsConfiguration,
    PyWin32ShortcutAdapter, WindowsRegistryPathAdapter,
)
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.platform.safe.owner_approval_ui import enrolled_owner_credentials
from sofia.platform.safe.owner_secret import OwnerSecretStore
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.path_policy import inside_git_worktree
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget

GUIDED_SCHEMA = "aegis.installer.guided-result.v1"
PLAN_SCHEMA = "aegis.installer.guided-plan.v1"
TRUST_SCHEMA = "aegis.installer.trust.v1"
NATIVE_CHANNEL_CAPABILITY = "platform.native_service.apply"
SUCCESS_OUTCOMES = frozenset((
    "PREVIEW_OK", "VERIFIED", "OK", "NO_CHANGES_MADE", "INSTALLED", "UPDATED",
    "REPAIRED", "ROLLED_BACK", "UNINSTALLED", "REINSTALLED", "RECONCILED",
))
MUTATING_OPERATIONS = frozenset((
    "install", "update", "repair", "rollback", "uninstall", "reinstall",
    "reconcile",
))
OPERATIONS = (
    "install", "update", "repair", "rollback", "uninstall", "reinstall",
    "reconcile", "verify", "status", "diagnostics",
)
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_METADATA_BYTES = 131_072
_MAX_KEY_BYTES = 16_384
_MAX_TRUST_BYTES = 16_384
_TRUST_KEY_NAMES = (
    "publisher_key_sha256", "trusted_key_sha256", "key_sha256",
    "public_key_sha256", "trusted_public_key_sha256",
)
_TRUST_SIGNER_NAMES = (
    "signer_key_id", "trusted_signer_key_id", "publisher_signer",
)


class GuidedDenied(PlatformInstallationDenied):
    """A clear, non-secret refusal produced before any host effect."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ApprovalUnavailable(PlatformInstallationDenied):
    """The attended owner ceremony did not return a usable approval."""

    def __init__(self, detail: str, *, code: str = "OWNER_APPROVAL_UNAVAILABLE"):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ApprovalAdapter(Protocol):
    def authorize(self, request: Mapping[str, object]) -> str:
        """Return one fresh owner approval id for the exact request."""


@dataclass(frozen=True, slots=True)
class BundleLayout:
    bundle_root: Path
    release_root: Path
    installer_root: Path
    manifest_path: Path
    signature_path: Path
    assets_root: Path
    trust_key: Path
    trust_json: Path


@dataclass(frozen=True, slots=True)
class GuidedPaths:
    target: PlatformReleaseTarget
    destination: Path
    identity_home: Path
    local_state: Path
    safe_state: Path
    store_path: Path
    operator_bin: Path
    global_bin: Path | None
    start_menu: Path | None
    desktop: Path | None
    approved_roots: tuple[Path, ...]
    install_root: Path | None = None

    def as_plan(self) -> dict[str, str | None]:
        return {
            "destination": str(self.destination),
            "identity_home": str(self.identity_home),
            "local_state": str(self.local_state),
            "safe_state": str(self.safe_state),
            "installation_store": str(self.store_path),
            "operator_bin": str(self.operator_bin),
            "global_bin": None if self.global_bin is None else str(self.global_bin),
            "start_menu": None if self.start_menu is None else str(self.start_menu),
            "desktop": None if self.desktop is None else str(self.desktop),
            "install_root": (None if self.install_root is None
                             else str(self.install_root)),
        }


def _env(environ: Mapping[str, str], name: str, default: str) -> str:
    wanted = name.casefold()
    for key, value in environ.items():
        if str(key).casefold() == wanted:
            return str(value)
    return default


def _within(path: Path, root: Path) -> bool:
    left = os.path.normcase(os.path.abspath(str(path)))
    right = os.path.normcase(os.path.abspath(str(root)))
    try:
        return os.path.commonpath((left, right)) == right
    except ValueError:
        return False


def _approved(path: Path, roots: Sequence[Path]) -> Path:
    candidate = Path(os.path.abspath(str(path)))
    if not any(_within(candidate, root) for root in roots):
        raise GuidedDenied(
            "PATH_OUTSIDE_APPROVED_ROOT",
            "installer path is outside every approved host root",
        )
    return candidate


def _checked(path: Path) -> Path:
    candidate = Path(os.path.abspath(str(path)))
    assert_no_redirected_components(
        candidate, include_leaf=candidate.exists() or candidate.is_symlink(),
    )
    return candidate


def _validate_paths(paths: GuidedPaths) -> GuidedPaths:
    for value in (
        paths.destination, paths.identity_home, paths.local_state,
        paths.safe_state, paths.store_path, paths.operator_bin,
        paths.global_bin, paths.start_menu, paths.desktop, paths.install_root,
    ):
        if value is not None:
            _approved(value, paths.approved_roots)
            _checked(value)
    return paths


def default_paths(
    target: PlatformReleaseTarget, *, environ: Mapping[str, str] | None = None,
) -> GuidedPaths:
    """Return canonical, approved, non-redirected paths for the observed host."""
    if not isinstance(target, PlatformReleaseTarget):
        raise TypeError("typed release target required")
    environment = os.environ if environ is None else environ
    if target is PlatformReleaseTarget.WINDOWS_X86_64:
        program_files = Path(_env(
            environment, "ProgramFiles", r"C:\Program Files",
        ))
        program_data = Path(_env(environment, "ProgramData", r"C:\ProgramData"))
        base = program_files / "Aegis"
        data = program_data / "Aegis"
        start_menu = (
            program_data / "Microsoft/Windows/Start Menu/Programs/Aegis"
        )
        paths = GuidedPaths(
            target=target,
            destination=base / "platform",
            identity_home=data / "identity",
            local_state=data / "state" / "platform.db",
            safe_state=data / "safe",
            store_path=data / "installation" / "platform-installation.db",
            operator_bin=base / "bin",
            global_bin=None,
            start_menu=start_menu,
            desktop=None,
            approved_roots=(
                base, data,
                program_data / "Microsoft/Windows/Start Menu/Programs",
            ),
        )
    elif target is PlatformReleaseTarget.DEBIAN12_X86_64:
        base = Path("/opt/aegis")
        data = Path("/var/lib/aegis")
        paths = GuidedPaths(
            target=target,
            destination=base / "platform",
            identity_home=data / "identity",
            local_state=data / "state" / "platform.db",
            safe_state=data / "safe",
            store_path=data / "installation" / "platform-installation.db",
            operator_bin=base / "bin",
            global_bin=Path("/usr/local/bin"),
            start_menu=None,
            desktop=Path("/usr/share/applications"),
            approved_roots=(
                base, data, Path("/usr/local/bin"), Path("/usr/share/applications"),
            ),
        )
    else:
        raise GuidedDenied("UNSUPPORTED_TARGET", "unsupported signed release target")
    return _validate_paths(paths)


def default_install_root(
    target: PlatformReleaseTarget, *, environ: Mapping[str, str] | None = None,
) -> Path:
    """Return the owner-facing default install root for this exact target.

    On a Windows host with a D: drive the requested VENUS-style default is
    ``D:\\Aegis``; otherwise the reviewed Program Files location is used.
    """
    environment = os.environ if environ is None else environ
    if target is PlatformReleaseTarget.WINDOWS_X86_64:
        if Path("D:\\").exists():
            return Path("D:\\Aegis")
        program_files = Path(_env(
            environment, "ProgramFiles", r"C:\Program Files",
        ))
        return program_files / "Aegis"
    return Path("/opt/aegis")


def paths_for_install_root(
    target: PlatformReleaseTarget,
    install_root: Path | str,
    *,
    environ: Mapping[str, str] | None = None,
    desktop_directory: Path | str | None = None,
) -> GuidedPaths:
    """Derive all reviewed Platform paths from one owner-selected root."""
    if not isinstance(target, PlatformReleaseTarget):
        raise TypeError("typed release target required")
    environment = os.environ if environ is None else environ
    root = Path(install_root)
    if not root.is_absolute():
        raise GuidedDenied("INVALID_INSTALL_ROOT", "install directory must be absolute")
    root = _checked(root)
    if inside_git_worktree(root):
        raise GuidedDenied(
            "INVALID_INSTALL_ROOT",
            "install directory must be outside a Git worktree",
        )
    desktop = None if desktop_directory is None else _checked(Path(desktop_directory))
    if target is PlatformReleaseTarget.WINDOWS_X86_64:
        program_data = Path(_env(environment, "ProgramData", r"C:\ProgramData"))
        start_menu = program_data / "Microsoft/Windows/Start Menu/Programs/Aegis"
        roots = [root, program_data / "Microsoft/Windows/Start Menu/Programs"]
        if desktop is not None:
            roots.append(desktop)
        paths = GuidedPaths(
            target=target,
            destination=root / "platform",
            identity_home=root / "identity",
            local_state=root / "state" / "platform.db",
            safe_state=root / "safe",
            store_path=root / "installation" / "platform-installation.db",
            operator_bin=root / "bin",
            global_bin=None,
            start_menu=start_menu,
            desktop=desktop,
            approved_roots=tuple(roots),
            install_root=root,
        )
    else:
        global_bin = Path("/usr/local/bin") if root == Path("/opt/aegis") else None
        roots = [root]
        if global_bin is not None:
            roots.append(global_bin)
        if desktop is not None:
            roots.append(desktop)
        paths = GuidedPaths(
            target=target,
            destination=root / "platform",
            identity_home=root / "identity",
            local_state=root / "state" / "platform.db",
            safe_state=root / "safe",
            store_path=root / "installation" / "platform-installation.db",
            operator_bin=root / "bin",
            global_bin=global_bin,
            start_menu=None,
            desktop=desktop,
            approved_roots=tuple(roots),
            install_root=root,
        )
    return _validate_paths(paths)


def discover_bundle(
    bundle_root: Path | str, *, script_directory: Path | str | None = None,
) -> BundleLayout:
    """Find signed release media and the independent installer trust anchor."""
    root = Path(bundle_root).absolute()
    if not root.is_dir():
        raise GuidedDenied("BUNDLE_NOT_FOUND", "installer bundle root is unavailable")
    candidates = [root]
    release_child = root / "release"
    if release_child.is_dir():
        candidates.append(release_child)
    script = None if script_directory is None else Path(script_directory).absolute()
    if script is not None and script == root and release_child not in candidates:
        candidates.append(release_child)
    complete = [
        candidate for candidate in candidates
        if ((candidate / "release-manifest.json").is_file()
            and (candidate / "release-signature.json").is_file()
            and (candidate / "assets").is_dir())
    ]
    if not complete:
        raise GuidedDenied(
            "BUNDLE_NOT_FOUND",
            "release-manifest.json, release-signature.json and assets/ are required",
        )
    if len(complete) > 1:
        raise GuidedDenied(
            "BUNDLE_AMBIGUOUS", "more than one signed release layout was found",
        )
    release_root = complete[0]
    installer_root = root / "installer"
    trust_key = installer_root / "trusted-publisher.pem"
    trust_json = installer_root / "trust.json"
    if not trust_key.is_file() or not trust_json.is_file():
        raise GuidedDenied(
            "TRUST_ANCHOR_MISSING",
            "installer/trusted-publisher.pem and installer/trust.json are required",
        )
    # The trust anchor must never be inside signed release media. A flat bundle
    # (manifest at the bundle root) therefore refuses its own installer/ tree.
    for trusted in (trust_key, trust_json):
        if trusted == release_root or release_root in trusted.parents:
            raise GuidedDenied(
                "TRUST_NOT_INDEPENDENT",
                "installer trust anchor must be separate from release media",
            )
    return BundleLayout(
        bundle_root=root,
        release_root=release_root,
        installer_root=installer_root,
        manifest_path=release_root / "release-manifest.json",
        signature_path=release_root / "release-signature.json",
        assets_root=release_root / "assets",
        trust_key=trust_key,
        trust_json=trust_json,
    )


def _read_bounded(path: Path, limit: int) -> bytes:
    assert_no_redirected_components(path, include_leaf=True)
    info = path.stat(follow_symlinks=False)
    if not 1 <= info.st_size <= limit:
        raise GuidedDenied("INPUT_INVALID", "installer metadata is outside its size bound")
    return read_artifact_file(path, info.st_size, include_data=True)[1]


def _manifest_payload(layout: BundleLayout) -> dict[str, object]:
    try:
        payload = loads_strict_model_json(
            _read_bounded(layout.manifest_path, _MAX_METADATA_BYTES).decode("utf-8")
        )
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise GuidedDenied(
            "RELEASE_METADATA_INVALID", "signed release metadata is unreadable",
        ) from error
    if (type(payload) is not dict
            or type(payload.get("revision")) is not int
            or payload["revision"] < 1
            or type(payload.get("source_sha")) is not str
            or _HEX40.fullmatch(payload["source_sha"]) is None
            or type(payload.get("release_id")) is not str):
        raise GuidedDenied(
            "RELEASE_METADATA_INVALID", "signed release metadata is not canonical",
        )
    return payload


_TRUST_ROOT_ENV = "AEGIS_INSTALLER_TRUST_ROOT"


def _trust_record(
    directory: Path, *, missing_code: str, invalid_code: str,
) -> tuple[Path, str, str, bytes]:
    directory = Path(directory)
    key = directory / "trusted-publisher.pem"
    record = directory / "trust.json"
    if (
        key.is_symlink() or record.is_symlink()
        or not key.is_file() or not record.is_file()
    ):
        raise GuidedDenied(
            missing_code,
            "installer/trusted-publisher.pem and installer/trust.json are required",
        )
    key_bytes = _read_bounded(key, _MAX_KEY_BYTES)
    fingerprint = sha256(key_bytes).hexdigest()
    try:
        document = loads_strict_model_json(
            _read_bounded(record, _MAX_TRUST_BYTES).decode("utf-8")
        )
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise GuidedDenied(
            invalid_code, "installer trust metadata is unreadable",
        ) from error
    if type(document) is not dict:
        raise GuidedDenied(invalid_code, "installer trust metadata is not an object")
    if document.get("schema") not in (None, TRUST_SCHEMA):
        raise GuidedDenied(
            invalid_code, "installer trust metadata schema is unsupported",
        )
    if document.get("private_key_included") not in (None, False):
        raise GuidedDenied(invalid_code, "trust metadata must not embed a private key")
    pinned = None
    for name in _TRUST_KEY_NAMES:
        if name in document:
            pinned = document[name]
            break
    signer = None
    for name in _TRUST_SIGNER_NAMES:
        if name in document:
            signer = document[name]
            break
    if type(pinned) is not str or _HEX64.fullmatch(pinned) is None:
        raise GuidedDenied(invalid_code, "trusted publisher key SHA-256 is required")
    if pinned != fingerprint:
        raise GuidedDenied(invalid_code, "trusted publisher key differs from its pin")
    if type(signer) is not str or not 1 <= len(signer) <= 128:
        raise GuidedDenied(invalid_code, "trusted signer key identity is required")
    return key, pinned, signer, key_bytes


def _independent_trust_root(
    target: PlatformReleaseTarget, *, explicit: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    env = dict(os.environ if environ is None else environ)
    if explicit is not None:
        raw = Path(explicit)
    elif env.get(_TRUST_ROOT_ENV):
        raw = Path(env[_TRUST_ROOT_ENV])
    elif target is PlatformReleaseTarget.WINDOWS_X86_64:
        program_data = _env(env, "ProgramData", r"C:\ProgramData")
        raw = Path(program_data) / "Aegis" / "installer-trust"
    else:
        raw = Path("/etc/aegis/installer-trust")
    if not raw.is_absolute():
        raise GuidedDenied(
            "TRUST_ROOT_INVALID", "independent installer trust root must be absolute",
        )
    root = _checked(raw)
    if not root.is_dir():
        raise GuidedDenied(
            "TRUST_ROOT_MISSING",
            "independent owner-controlled installer trust root is not provisioned; "
            "place trusted-publisher.pem and trust.json outside the bundle first",
        )
    return root


def _trust_anchor(
    layout: BundleLayout, *, target: PlatformReleaseTarget,
    trust_root: Path | str | None = None,
) -> tuple[Path, str, str]:
    _bundle_key, bundle_pin, bundle_signer, _bundle_bytes = _trust_record(
        layout.installer_root,
        missing_code="TRUST_ANCHOR_MISSING",
        invalid_code="TRUST_ANCHOR_INVALID",
    )
    root = _independent_trust_root(target, explicit=trust_root)
    if root == layout.bundle_root or _within(root, layout.bundle_root):
        raise GuidedDenied(
            "TRUST_ROOT_NOT_INDEPENDENT",
            "independent installer trust root must be outside the installer bundle",
        )
    key, pin, signer, _key_bytes = _trust_record(
        root,
        missing_code="TRUST_ROOT_INVALID",
        invalid_code="TRUST_ROOT_INVALID",
    )
    if bundle_pin != pin or bundle_signer != signer:
        raise GuidedDenied(
            "TRUST_ANCHOR_MISMATCH",
            "bundle trust anchor does not match the independent owner trust root",
        )
    return key, pin, signer


def verify_bundle(
    layout: BundleLayout, *, target: PlatformReleaseTarget,
    expected_parent_manifest_sha256: str | None = None,
    trust_root: Path | str | None = None,
) -> tuple[SignedInstallerRelease, dict[str, object]]:
    """Verify the signed release and independently provisioned trust anchor."""
    payload = _manifest_payload(layout)
    key, fingerprint, signer = _trust_anchor(
        layout, target=target, trust_root=trust_root,
    )
    try:
        release = verify_offline_installer_bundle(
            layout.release_root,
            trusted_public_key=key,
            trusted_key_sha256=fingerprint,
            trusted_signer_key_id=signer,
            expected_source_sha=str(payload["source_sha"]),
            expected_target=target,
            minimum_revision=int(payload["revision"]),
            expected_parent_manifest_sha256=expected_parent_manifest_sha256,
            require_local_host=True,
        )
    except PlatformReleaseRejected as error:
        raise GuidedDenied("RELEASE_REJECTED", str(error)) from error
    if release.source_sha != payload["source_sha"]:
        raise GuidedDenied(
            "RELEASE_REJECTED", "signed release source SHA differs from its manifest",
        )
    return release, payload


def _release_fields(release: SignedInstallerRelease) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "revision": release.revision,
        "manifest_sha256": release.manifest_sha256,
        "source_sha": release.source_sha,
        "target": release.target,
        "signer_key_id": release.signer_key_id,
        "publisher_key_sha256": release.trust_key_sha256,
        "asset_count": release.asset_count,
    }


def _is_elevated() -> bool:
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False
    geteuid = getattr(os, "geteuid", None)
    return bool(geteuid is not None and geteuid() == 0)


def _result(operation: str, outcome: str, **fields) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": GUIDED_SCHEMA,
        "operation": operation,
        "outcome": outcome,
        "executed": False,
        "owner_approved": False,
        "owner_secret_observed": False,
        "core_activated": False,
        "fleet_enrolled": False,
        "production_authorized": False,
    }
    payload.update(fields)
    return payload


def _denied(operation: str, code: str, detail: str, **fields) -> dict[str, object]:
    return _result(
        operation, "DENIED",
        error={"code": code, "detail": detail},
        **fields,
    )


def _service_name(target: PlatformReleaseTarget) -> str:
    return (
        "AegisPlatform"
        if target is PlatformReleaseTarget.WINDOWS_X86_64
        else "aegis-platform.service"
    )


def _operator_plan(paths: GuidedPaths) -> dict[str, object]:
    if paths.target is PlatformReleaseTarget.WINDOWS_X86_64:
        files = [str(paths.operator_bin / "aegis.cmd")]
        shortcuts = [str(paths.start_menu / "Aegis Platform.lnk")] if paths.start_menu else []
        path_action = "ENSURE"
        path_scope = "machine"
    else:
        files = [str(paths.operator_bin / "aegis")]
        if paths.global_bin is not None:
            files.append(str(paths.global_bin / "aegis"))
        shortcuts = (
            [str(paths.desktop / "aegis-platform.desktop")]
            if paths.desktop else []
        )
        path_action = "NOT_APPLICABLE"
        path_scope = "user"
    return {
        "global_command": str(paths.operator_bin / (
            "aegis.cmd" if paths.target is PlatformReleaseTarget.WINDOWS_X86_64
            else "aegis")),
        "global_bin_directory": (
            None if paths.global_bin is None else str(paths.global_bin)
        ),
        "path": {"action": path_action, "scope": path_scope},
        "files": files,
        "shortcuts": shortcuts,
        "gui_executable": None,
        "tui_executable": None,
        "shortcut_note": (
            "GUI/TUI shortcuts are created only when the installed signed release "
            "provides an executable; none is present in this signed asset inventory."
        ),
    }


def build_plan(
    layout: BundleLayout, paths: GuidedPaths, release: SignedInstallerRelease,
    payload: Mapping[str, object], *, operation: str,
    elevation_required: bool, trust_root: Path | str | None = None,
) -> dict[str, object]:
    assets = payload.get("assets")
    release_files = []
    if isinstance(assets, list):
        for item in assets:
            if type(item) is not dict:
                continue
            reference = item.get("reference")
            if type(reference) is not dict:
                continue
            release_files.append({
                "kind": item.get("kind"),
                "path": reference.get("path"),
                "sha256": reference.get("sha256"),
                "size_bytes": reference.get("size_bytes"),
            })
    approvals = [
        {
            "stage": "code_publication",
            "capability": CODE_PUBLISH_CAPABILITY,
            "owner_authentication": "ATTENDED_EXISTING_SAFE_CEREMONY",
        },
        {
            "stage": "native_service",
            "capability": NATIVE_CHANNEL_CAPABILITY,
            "owner_authentication": "ATTENDED_EXISTING_SAFE_CEREMONY",
        },
        {
            "stage": "operator_apps",
            "capability": OPERATOR_APPS_CAPABILITY,
            "owner_authentication": "ATTENDED_EXISTING_SAFE_CEREMONY",
        },
    ]
    operator_plan = _operator_plan(paths)
    tui_asset = None
    if isinstance(assets, list):
        for item in assets:
            if type(item) is not dict:
                continue
            reference = item.get("reference")
            if type(reference) is not dict:
                continue
            path = str(reference.get("path", ""))
            if (item.get("role") == "aegis_tui"
                    or Path(path).name.casefold() in (
                        "aegis_tui.exe", "aegis-tui.exe",
                        "aegis_tui", "aegis-tui",
                    )):
                tui_asset = path
                break
    planned_tui = (
        None if tui_asset is None else
        str(paths.destination / "assets" / Path(tui_asset).name)
    )
    operator_plan["tui_executable"] = planned_tui
    operator_plan["planned_tui_executable"] = planned_tui
    operator_plan["tui_state"] = (
        "UNAVAILABLE" if planned_tui is None else "PLANNED_NOT_INSTALLED"
    )
    return {
        "schema": PLAN_SCHEMA,
        "mode": "PREVIEW_ONLY" if operation not in MUTATING_OPERATIONS else "PLANNED",
        "operation": operation,
        "bundle_root": str(layout.bundle_root),
        "release_root": str(layout.release_root),
        "installer_trust_root": (
            None if trust_root is None else str(trust_root)
        ),
        "bundle_installer_directory": str(layout.installer_root),
        "target": release.target,
        "source_sha": release.source_sha,
        "revision": release.revision,
        "minimum_revision": release.revision,
        "release_id": release.release_id,
        "manifest_sha256": release.manifest_sha256,
        "signer_key_id": release.signer_key_id,
        "publisher_key_sha256": release.trust_key_sha256,
        "paths": paths.as_plan(),
        "service": {
            "name": _service_name(paths.target),
            "health": "UNKNOWN",
            "registered": False,
            "core_activated": False,
        },
        "identity_retention": "RETAIN",
        "state_retention": "RETAIN",
        "purge": "SEPARATE_NOT_DEFAULT",
        "release_files": release_files,
        "operator_apps": operator_plan,
        "approvals_needed": approvals,
        "elevation_required": elevation_required,
        "executed": False,
        "owner_approved": False,
        "core_activated": False,
        "fleet_enrolled": False,
    }


def _store_exists(paths: GuidedPaths) -> bool:
    return paths.store_path.exists()


def _store(paths: GuidedPaths) -> PlatformInstallationStore | None:
    if not _store_exists(paths):
        return None
    return PlatformInstallationStore(paths.store_path)


def current_destination(paths: GuidedPaths) -> Path | None:
    """Find the canonical active receipt without guessing from empty folders."""
    store = _store(paths)
    if store is None:
        return None
    if store.receipt_for_destination(paths.destination) is not None:
        return paths.destination
    parent = paths.destination.parent
    if not parent.is_dir():
        return None
    found: list[tuple[int, Path]] = []
    try:
        children = sorted(parent.iterdir(), key=lambda item: item.name)
    except OSError:
        return None
    for child in children:
        if not child.is_dir() or child.is_symlink():
            continue
        if not _within(child, parent):
            continue
        row = store.receipt_for_destination(child)
        if row is not None:
            found.append((int(row["revision"]), child))
    if not found:
        return None
    return max(found, key=lambda item: item[0])[1]


def _update_destination(previous: Path, revision: int) -> Path:
    parent = previous.parent
    candidate = parent / f"platform-r{int(revision)}"
    if candidate == previous:
        candidate = parent / f"platform-r{int(revision)}-update"
    if candidate.exists() or candidate.is_symlink():
        candidate = parent / f"platform-r{int(revision)}-update"
    return candidate


def _rollback_destination(previous: Path, revision: int) -> Path:
    candidate = previous.parent / f"platform-r{int(revision)}"
    if candidate == previous:
        candidate = previous.parent / f"platform-r{int(revision)}-rollback"
    return candidate


def _executable(destination: Path, names: Sequence[str]) -> Path | None:
    for directory in (destination, destination / "assets", destination / "gui"):
        for name in names:
            candidate = directory / name
            try:
                if candidate.is_file() and not candidate.is_symlink():
                    return candidate
            except OSError:
                continue
    return None


def _operator_configuration(
    paths: GuidedPaths, destination: Path,
    *, start_at_login: bool = False, include_tui: bool = True,
    include_start_menu: bool = True, include_desktop: bool = False,
) -> OperatorAppsConfiguration | None:
    windows = paths.target is PlatformReleaseTarget.WINDOWS_X86_64
    runtime = destination / "runtime" / "python" / (
        "python.exe" if windows else "bin/python3.12"
    )
    code = destination / "assets"
    if not runtime.is_file() or not code.is_dir():
        return None
    gui = _executable(destination, (
        ("aegis-control-center.exe", "aegis-gui.exe")
        if windows else ("aegis-control-center", "aegis-gui")
    ))
    tui = _executable(destination, (
        ("aegis_tui.exe", "aegis-tui.exe")
        if windows else ("aegis-tui", "aegis_tui")
    )) if include_tui else None
    return OperatorAppsConfiguration(
        target=paths.target,
        runtime_python=runtime,
        code_directory=code,
        bin_directory=paths.operator_bin,
        gui_executable=gui,
        tui_executable=tui,
        start_menu_directory=(
            paths.start_menu if (windows and include_start_menu
                                and (gui is not None or tui is not None))
            else None
        ),
        desktop_directory=(
            paths.desktop if include_desktop and paths.desktop is not None else None
        ),
        global_bin_directory=(None if windows else paths.global_bin),
        approved_roots=paths.approved_roots,
        protected_paths=(paths.identity_home, paths.local_state, paths.safe_state),
        path_scope="machine" if windows else "user",
        include_powershell=windows,
        include_desktop_shortcut=bool(include_desktop),
        start_at_login=bool(start_at_login),
    )


def _operator_inputs(
    inputs: InstallerInputs, config: OperatorAppsConfiguration,
) -> InstallerInputs:
    return replace(
        inputs,
        operator_apps_requested=True,
        operator_apps_runtime_python=config.runtime_python,
        operator_apps_code_directory=config.code_directory,
        operator_apps_bin_directory=config.bin_directory,
        operator_apps_gui_executable=config.gui_executable,
        operator_apps_tui_executable=config.tui_executable,
        operator_apps_start_menu_directory=config.start_menu_directory,
        operator_apps_desktop_directory=config.desktop_directory,
        operator_apps_global_bin_directory=config.global_bin_directory,
        operator_apps_approved_roots=config.approved_roots,
        operator_apps_protected_paths=config.protected_paths,
        operator_apps_path_scope=config.path_scope,
        operator_apps_include_powershell=config.include_powershell,
        operator_apps_desktop_shortcut=config.include_desktop_shortcut,
        operator_apps_start_at_login=config.start_at_login,
    )


def _owner_approval_credential(state_path: Path | str) -> str:
    """Select the already-enrolled attended owner credential without minting one."""
    try:
        if OwnerSecretStore(state_path).enabled():
            return "owner-secret"
    except (OSError, PermissionError, RuntimeError, TypeError, ValueError,
            sqlite3.Error) as error:
        raise ApprovalUnavailable(
            "Owner approval state is unavailable or unreadable.",
            code="OWNER_CREDENTIAL_UNAVAILABLE",
        ) from error
    try:
        for kind in ("security_key", "platform"):
            credentials = enrolled_owner_credentials(state_path, kind=kind)
            if len(credentials) > 1:
                raise ApprovalUnavailable(
                    "Multiple enrolled owner credentials are available; "
                    "select one in the attended owner configuration.",
                    code="OWNER_CREDENTIAL_AMBIGUOUS",
                )
            if credentials:
                return credentials[0]
    except ApprovalUnavailable:
        raise
    except (OSError, PermissionError, RuntimeError, TypeError, ValueError,
            sqlite3.Error) as error:
        raise ApprovalUnavailable(
            "Enrolled owner credentials are unavailable or unreadable.",
            code="OWNER_CREDENTIAL_UNAVAILABLE",
        ) from error
    raise ApprovalUnavailable(
        "No owner approval credential is enrolled in the installer SAFE state. "
        "Run the attended owner enrollment ceremony on Venus first.",
        code="OWNER_ENROLLMENT_MISSING",
    )


def _approval_failure(stderr: object, returncode: object) -> ApprovalUnavailable:
    text = str(stderr or "").casefold()
    if "owner secret not enrolled" in text or "no enrolled" in text:
        return ApprovalUnavailable(
            "No owner approval credential is enrolled in the installer SAFE state. "
            "Run the attended owner enrollment ceremony on Venus first.",
            code="OWNER_ENROLLMENT_MISSING",
        )
    if "timed out" in text or "cancel" in text:
        return ApprovalUnavailable(
            "Owner approval was not completed before cancellation or timeout.",
            code="OWNER_APPROVAL_CANCELLED",
        )
    if "browser" in text or "authorization browser" in text:
        return ApprovalUnavailable(
            "The local attended owner approval browser could not be opened.",
            code="OWNER_APPROVAL_UI_UNAVAILABLE",
        )
    if "interactive terminal" in text or "console" in text:
        return ApprovalUnavailable(
            "Owner approval requires an attended interactive owner session.",
            code="OWNER_ATTENDED_SESSION_REQUIRED",
        )
    if ("local operator is not" in text or "windows sid" in text
            or "owner account binding" in text or "enrolled windows owner" in text
            or "authentication unavailable" in text
            or "credential unavailable" in text):
        return ApprovalUnavailable(
            "The current Windows session is not the enrolled owner.",
            code="OWNER_CREDENTIAL_UNAVAILABLE",
        )
    if "authentication denied" in text or "denied" in text or "invalid" in text:
        return ApprovalUnavailable(
            "Owner authentication was refused.",
            code="OWNER_AUTHENTICATION_DENIED",
        )
    return ApprovalUnavailable(
        "Owner approval subprocess failed before issuing a valid receipt.",
        code="OWNER_APPROVAL_SUBPROCESS_FAILED",
    )


class SubprocessApprovalAdapter:
    """Ask the existing attended SAFE ceremony; return only the approval id."""

    def __init__(
        self, python_executable: Path | str, state_path: Path | str, *,
        timeout_seconds: int = 900,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self.python_executable = Path(python_executable)
        self.state_path = Path(state_path)
        self.timeout_seconds = int(timeout_seconds)
        self._runner = runner

    def authorize(self, request: Mapping[str, object]) -> str:
        capability = request.get("capability")
        parameters = request.get("parameters")
        if type(capability) is not str or not capability.strip():
            raise ApprovalUnavailable(
                "Canonical owner approval request has no capability.",
                code="OWNER_APPROVAL_INVALID_REQUEST",
            )
        if type(parameters) is not dict:
            raise ApprovalUnavailable(
                "Canonical owner approval request has no parameters.",
                code="OWNER_APPROVAL_INVALID_REQUEST",
            )
        credential = _owner_approval_credential(self.state_path)
        command = [
            str(self.python_executable), "-E", "-s", "-P", "-B", "-m",
            "sofia.platform.safe.approve_execution",
            "--state-path", str(self.state_path),
            "--capability", capability,
            "--parameters-json",
            json.dumps(parameters, sort_keys=True, separators=(",", ":"),
                       allow_nan=False),
            "--credential-id", credential,
            "--ttl-seconds", "900",
        ]
        try:
            completed = self._runner(
                command, input="", capture_output=True, text=True,
                timeout=self.timeout_seconds, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ApprovalUnavailable(
                "Owner approval subprocess could not be started.",
                code="OWNER_APPROVAL_SUBPROCESS_FAILED",
            ) from error
        if completed.returncode != 0:
            raise _approval_failure(completed.stderr, completed.returncode)
        try:
            receipt = json.loads(completed.stdout)
        except (TypeError, ValueError) as error:
            raise ApprovalUnavailable(
                "Owner approval ceremony returned no valid receipt.",
                code="OWNER_APPROVAL_INVALID_RECEIPT",
            ) from error
        approval_id = receipt.get("approval_id") if type(receipt) is dict else None
        if (type(approval_id) is not str or not approval_id.strip()
                or receipt.get("capability") != capability):
            raise ApprovalUnavailable(
                "Owner approval ceremony returned an invalid receipt.",
                code="OWNER_APPROVAL_INVALID_RECEIPT",
            )
        return approval_id


def _provider(adapter: ApprovalAdapter | None):
    if adapter is None:
        return None

    def authorize(_kind: str, request: Mapping[str, object]) -> str:
        approval_id = adapter.authorize(request)
        if type(approval_id) is not str or not approval_id.strip():
            raise ApprovalUnavailable(
                "Owner approval ceremony returned no approval.",
                code="OWNER_APPROVAL_INVALID_RECEIPT",
            )
        return approval_id

    return authorize


def _bundled_python(layout: BundleLayout, target: PlatformReleaseTarget) -> Path:
    relative = (
        ("runtime", "python", "python.exe")
        if target is PlatformReleaseTarget.WINDOWS_X86_64
        else ("runtime", "python", "bin", "python3.12")
    )
    candidate = layout.release_root.joinpath(*relative)
    if candidate.is_file() and not candidate.is_symlink():
        return candidate
    raise GuidedDenied(
        "MISSING_BUNDLED_PYTHON",
        "the signed release does not contain exactly one reviewed bundled Python",
    )


def _installer_inputs(
    layout: BundleLayout, paths: GuidedPaths, release: SignedInstallerRelease,
    *, minimum_revision: int, destination: Path,
    previous_destination: Path | None = None,
    expected_parent_manifest_sha256: str | None = None,
    trust_root: Path | str | None = None,
    bootstrap_first_install_state: bool = False,
) -> InstallerInputs:
    key, fingerprint, signer = _trust_anchor(
        layout, target=paths.target, trust_root=trust_root,
    )
    return InstallerInputs(
        release_root=layout.release_root,
        publisher_key=key,
        publisher_key_sha256=fingerprint,
        publisher_signer=signer,
        expected_source_sha=release.source_sha,
        target=paths.target.value,
        minimum_revision=int(minimum_revision),
        destination=destination,
        identity_home=paths.identity_home,
        local_state=paths.local_state,
        canonical_safe_state=paths.safe_state,
        store_path=paths.store_path,
        bootstrap_first_install_state=bootstrap_first_install_state,
        previous_destination=previous_destination,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
    )


def _backend(paths: GuidedPaths):
    if paths.target is PlatformReleaseTarget.WINDOWS_X86_64:
        return WindowsScmNativeService()
    return DebianSystemdNativeService()


def _path_adapter(paths: GuidedPaths, supplied):
    if supplied is not None:
        return supplied
    if paths.target is PlatformReleaseTarget.WINDOWS_X86_64:
        return WindowsRegistryPathAdapter(scope="machine")
    return InMemoryPathAdapter()


def _shortcut_adapter(supplied):
    return PyWin32ShortcutAdapter() if supplied is None else supplied


def _mutation_layout(
    operation: str, release: SignedInstallerRelease, paths: GuidedPaths,
) -> tuple[Path, Path | None, int, str | None]:
    previous = current_destination(paths)
    store = _store(paths)
    row = None
    if previous is not None and store is not None:
        row = store.receipt_for_destination(previous)
    if operation == "install":
        return paths.destination, None, release.revision, None
    if operation == "update":
        if previous is None or row is None:
            raise GuidedDenied(
                "UPDATE_REQUIRES_INSTALLED_RELEASE",
                "update requires an existing canonical B1 installation",
            )
        return (
            _update_destination(previous, release.revision), previous,
            release.revision, str(row["manifest_sha256"]),
        )
    if operation == "rollback":
        if previous is None or row is None:
            raise GuidedDenied(
                "ROLLBACK_REQUIRES_INSTALLED_RELEASE",
                "rollback requires an existing canonical B1 installation",
            )
        floor = max(release.revision + 1, store.revision_floor() if store else 0)
        return _rollback_destination(previous, release.revision), previous, floor, None
    if operation in ("repair", "uninstall", "reinstall", "reconcile"):
        if previous is None:
            raise GuidedDenied(
                "MAINTENANCE_REQUIRES_INSTALLED_RELEASE",
                "maintenance requires an existing canonical B1 installation",
            )
        return previous, None, release.revision, None
    raise GuidedDenied("UNSUPPORTED_OPERATION", "unsupported installer operation")


def _stages(operation: str, result: Mapping[str, object]) -> list[dict[str, object]]:
    outcome = result.get("outcome")
    required = result.get("required_approval")
    stages: list[dict[str, object]] = [
        {"stage": "release_verification", "outcome": "VERIFIED"},
        {
            "stage": "code_publication",
            "outcome": (
                "REFUSED" if outcome == "DENIED" and required == "code"
                else "COMPLETED" if outcome not in ("DENIED",) else "NOT_REACHED"
            ),
        },
        {
            "stage": "native_service",
            "outcome": (
                "REFUSED" if outcome == "DENIED" and required == "native"
                else "COMPLETED" if outcome not in ("DENIED",) else "NOT_REACHED"
            ),
        },
        {
            "stage": "operator_apps",
            "outcome": (
                "REFUSED" if outcome == "DENIED" and required == "operator_apps"
                else "COMPLETED" if outcome not in ("DENIED",) else "NOT_REACHED"
            ),
        },
        {"stage": "service_status", "outcome": "REPORTED"},
    ]
    if operation not in MUTATING_OPERATIONS:
        stages = [{"stage": "release_verification", "outcome": "VERIFIED"}]
    return stages


def _read_only(
    operation: str, inputs: InstallerInputs, installer_command,
) -> dict[str, object]:
    command = "doctor" if operation == "diagnostics" else operation
    result = installer_command(command, inputs)
    return _result(
        operation, str(result.get("outcome")), executed=False, owner_approved=False,
        installer_result=result,
        **{key: value for key, value in result.items()
           if key in ("release_id", "revision", "manifest_sha256", "source_sha",
                      "target", "signer_key_id", "publisher_key_sha256",
                      "service_state", "installed_verified", "stop_active")},
    )


def run_guided(
    bundle_root: Path | str, *,
    check: bool = False,
    operation: str | None = None,
    target: PlatformReleaseTarget | None = None,
    paths: GuidedPaths | None = None,
    install_root: Path | str | None = None,
    bootstrap_first_install_state: bool = False,
    approval_adapter: ApprovalAdapter | None = None,
    native_backend=None,
    operator_apps_path_adapter=None,
    operator_apps_shortcut_adapter=None,
    operator_apps_config: OperatorAppsConfiguration | None = None,
    installer_command=None,
    operator_apps_command=None,
    elevation_check: Callable[[], bool] | None = None,
    script_directory: Path | str | None = None,
    trust_root: Path | str | None = None,
    start_at_login: bool = False,
    include_tui: bool = True,
    include_start_menu: bool = True,
    include_desktop: bool = False,
    approval_runner=None,
) -> dict[str, object]:
    """Verify, plan and (unless previewing) drive the canonical installer."""
    installer_command = installer_command or execute_command
    operator_apps_command = operator_apps_command or apply_operator_apps_command
    requested = operation or "install"
    if requested not in OPERATIONS:
        return _denied(
            requested, "UNSUPPORTED_OPERATION", "unsupported installer operation",
        )
    try:
        layout = discover_bundle(bundle_root, script_directory=script_directory)
        if target is None:
            target = host_release_target()
        if not isinstance(target, PlatformReleaseTarget):
            raise GuidedDenied("UNSUPPORTED_TARGET", "typed release target required")
        if paths is not None and install_root is not None:
            raise GuidedDenied(
                "CONFLICTING_PATH_INPUT",
                "provide either a full path set or one install root, not both",
            )
        if install_root is not None:
            resolved_paths = paths_for_install_root(
                target, install_root,
                desktop_directory=_desktop_directory(target),
            )
        else:
            resolved_paths = _validate_paths(paths or default_paths(target))
        if resolved_paths.target is not target:
            raise GuidedDenied("TARGET_MISMATCH", "path set belongs to another target")
        release, payload = verify_bundle(layout, target=target, trust_root=trust_root)
        independent_trust_root = _independent_trust_root(
            target, explicit=trust_root,
        )
        plan = build_plan(
            layout, resolved_paths, release, payload, operation=requested,
            elevation_required=requested in MUTATING_OPERATIONS,
            trust_root=independent_trust_root,
        )
        asset_kinds = set()
        for item in payload.get("assets", []):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind"))
            asset_kinds.add(kind)
            reference = item.get("reference")
            path = "" if not isinstance(reference, dict) else str(reference.get("path", ""))
            if (kind == "tui" or item.get("role") == "aegis_tui"
                    or Path(path).name.casefold() in (
                        "aegis_tui.exe", "aegis-tui.exe",
                        "aegis_tui", "aegis-tui",
                    )):
                asset_kinds.add("tui")
        plan["install_root"] = (
            None if resolved_paths.install_root is None
            else str(resolved_paths.install_root)
        )
        plan["components"] = {
            "platform_service": True,
            "terminal_tui": "tui" in asset_kinds,
            "console_launcher": True,
            "start_menu_shortcut": bool(
                include_start_menu and "tui" in asset_kinds
            ),
            "desktop_shortcut": bool(
                include_desktop and "tui" in asset_kinds
            ),
            "start_at_login": bool(start_at_login),
        }
        plan["startup_preference"] = (
            "SIGN_IN_TUI" if start_at_login else "SERVICE_START_ONLY"
        )
        operator_plan = plan.get("operator_apps")
        if isinstance(operator_plan, dict):
            command = None
            if (
                target is PlatformReleaseTarget.WINDOWS_X86_64
                and include_tui and "tui" in asset_kinds
            ):
                command = f'"{resolved_paths.operator_bin / "aegis.cmd"}" tui'
            operator_plan["startup"] = {
                "requested": bool(start_at_login),
                "supported": command is not None,
                "command": command,
                "action": "ENSURE" if start_at_login else "NO_CHANGE",
            }
    except GuidedDenied as error:
        return _denied(requested, error.code, error.detail)
    except PlatformInstallationDenied as error:
        return _denied(requested, "DENIED", str(error))
    except PermissionError:
        return _denied(
            requested, "PATH_DENIED",
            "an install path is redirected or lacks the required access",
        )
    except (OSError, ValueError, TypeError):
        return _denied(requested, "INPUT_UNAVAILABLE", "installer inputs are unavailable")

    if check:
        plan["mode"] = "PREVIEW_ONLY"
        return _result(
            requested, "PREVIEW_OK", plan=plan,
            **_release_fields(release),
        )

    if requested not in MUTATING_OPERATIONS:
        try:
            minimum = release.revision
            destination = current_destination(resolved_paths) or resolved_paths.destination
            inputs = _installer_inputs(
                layout, resolved_paths, release,
                minimum_revision=minimum, destination=destination, trust_root=trust_root,
            )
            return _read_only(requested, inputs, installer_command)
        except GuidedDenied as error:
            return _denied(requested, error.code, error.detail, plan=plan)

    elevate = elevation_check or _is_elevated
    if not elevate():
        return _result(
            requested, "ELEVATION_REQUIRED",
            elevation_required=True, plan=plan,
            error={
                "code": "ELEVATION_REQUIRED",
                "detail": "the launcher must elevate before any host change",
            },
            **_release_fields(release),
        )

    try:
        destination, previous, minimum, expected_parent = _mutation_layout(
            requested, release, resolved_paths,
        )
        _approved(destination, resolved_paths.approved_roots)
        _checked(destination)
        inputs = _installer_inputs(
            layout, resolved_paths, release, minimum_revision=minimum,
            destination=destination, previous_destination=previous,
            expected_parent_manifest_sha256=expected_parent,
            trust_root=trust_root,
            bootstrap_first_install_state=(
                bool(bootstrap_first_install_state) and requested == "install"
            ),
        )
    except GuidedDenied as error:
        return _denied(requested, error.code, error.detail, plan=plan)

    adapter = approval_adapter
    if adapter is None and requested in MUTATING_OPERATIONS:
        try:
            python = _bundled_python(layout, target)
            adapter = SubprocessApprovalAdapter(
                python, resolved_paths.safe_state, runner=(
                    subprocess.run if approval_runner is None else approval_runner
                ),
            )
        except GuidedDenied as error:
            return _denied(requested, error.code, error.detail, plan=plan)
    provider = _provider(adapter)
    backend = native_backend or _backend(resolved_paths)
    path_adapter = _path_adapter(resolved_paths, operator_apps_path_adapter)
    shortcut_adapter = _shortcut_adapter(operator_apps_shortcut_adapter)

    try:
        installer_result = installer_command(
            requested, inputs, backend=backend,
            operator_apps_path_adapter=path_adapter,
            operator_apps_shortcut_adapter=shortcut_adapter,
            approval_provider=provider,
        )
    except TypeError:
        # A test double or older adapter without the additive provider hook is
        # never allowed to silently execute without owner approval.
        return _denied(
            requested, "OWNER_APPROVAL_REQUIRED",
            "installer owner does not expose the attended approval hook",
            plan=plan,
        )

    if installer_result.get("outcome") not in SUCCESS_OUTCOMES:
        return _result(
            requested, str(installer_result.get("outcome")),
            plan=plan, installer_result=installer_result,
            stages=_stages(requested, installer_result),
            error=installer_result.get("error") or {
                "code": "INSTALLER_REFUSED",
                "detail": "the canonical installer refused the operation",
            },
            **_release_fields(release),
        )

    operator_result: dict[str, object] | None = None
    operator_operation = "update" if requested == "rollback" else requested
    if operator_operation in ("install", "update", "repair", "uninstall"):
        config = operator_apps_config or _operator_configuration(
            resolved_paths, destination, start_at_login=start_at_login,
            include_tui=include_tui, include_start_menu=include_start_menu,
            include_desktop=include_desktop,
        )
        if config is None:
            operator_result = _result(
                "operator_apps", "SKIPPED", reason="INSTALLED_RELEASE_LAYOUT_UNAVAILABLE",
            )
        else:
            app_inputs = _operator_inputs(inputs, config)
            try:
                operator_result = operator_apps_command(
                    operator_operation, app_inputs,
                    path_adapter=path_adapter,
                    shortcut_adapter=shortcut_adapter,
                    approval_provider=provider,
                )
            except TypeError:
                return _denied(
                    requested, "OWNER_APPROVAL_REQUIRED",
                    "operator apps owner does not expose the attended approval hook",
                    plan=plan, installer_result=installer_result,
                )
            except PlatformInstallationDenied as error:
                operator_result = _result(
                    "operator_apps", "DENIED",
                    error={"code": "OPERATOR_APPS_DENIED", "detail": str(error)},
                )
        if (operator_result is not None
                and operator_result.get("outcome") not in SUCCESS_OUTCOMES
                and operator_result.get("outcome") != "SKIPPED"):
            return _result(
                requested, str(operator_result.get("outcome")),
                plan=plan, installer_result=installer_result,
                operator_apps_result=operator_result,
                stages=_stages(requested, operator_result),
                error=operator_result.get("error") or {
                    "code": "OPERATOR_APPS_REFUSED",
                    "detail": "operator application launchers were not applied",
                },
                **_release_fields(release),
            )

    status_result: dict[str, object] | None = None
    try:
        status_inputs = replace(inputs, destination=destination)
        status_result = installer_command(
            "status", status_inputs, backend=backend,
            approval_provider=provider,
        )
    except Exception:
        status_result = _result(
            "status", "UNAVAILABLE",
            error={"code": "STATUS_UNAVAILABLE",
                   "detail": "service status could not be observed"},
        )

    service_health = installer_result.get("service_health", "UNKNOWN")
    return _result(
        requested, str(installer_result.get("outcome")),
        executed=True, owner_approved=True,
        plan=plan, installer_result=installer_result,
        operator_apps_result=operator_result,
        service_status=status_result,
        stages=_stages(requested, installer_result),
        service_health=service_health,
        identity_retention="RETAIN",
        state_retention="RETAIN",
        **_release_fields(release),
    )


def _load_theme(script_directory: Path | None) -> dict[str, str] | None:
    roots = [Path(__file__).resolve().parents[4]]
    if script_directory is not None:
        roots.append(Path(script_directory).absolute())
    roots.append(Path.cwd())
    for root in roots:
        candidate = root / "contracts/ui/aegis-theme-v1.json"
        try:
            if candidate.is_file():
                document = json.loads(candidate.read_text(encoding="utf-8"))
                if document.get("schema") == "aegis.ui.theme.v1":
                    tokens = document.get("tokens")
                    if type(tokens) is dict:
                        return {
                            key: value for key, value in tokens.items()
                            if type(value) is str
                        }
        except (OSError, ValueError, TypeError):
            continue
    return None


def _paint(text: str, role: str, theme: dict[str, str] | None, color: bool) -> str:
    if not color or theme is None or role not in theme:
        return text
    value = theme[role]
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None:
        return text
    red, green, blue = (
        int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16),
    )
    return f"\x1b[38;2;{red};{green};{blue}m{text}\x1b[0m"


def _print_result(
    result: Mapping[str, object], *, theme: dict[str, str] | None = None,
    color: bool = False, stream=None,
) -> None:
    out = sys.stdout if stream is None else stream
    outcome = str(result.get("outcome"))
    role = "success" if outcome in SUCCESS_OUTCOMES else "danger"
    if "danger" not in (theme or {}):
        role = "warning" if role == "danger" else role
    print(_paint(f"AEGIS PLATFORM GUIDED SETUP: {outcome}", role, theme, color), file=out)
    operation = result.get("operation")
    if operation is not None:
        print(f"OPERATION={operation}", file=out)
    error = result.get("error")
    if isinstance(error, dict):
        print(f"ERROR_CODE={error.get('code')}", file=out)
        print(f"ERROR_DETAIL={error.get('detail')}", file=out)
    plan = result.get("plan")
    if isinstance(plan, dict):
        for key in (
            "release_id", "revision", "source_sha", "target", "manifest_sha256",
            "signer_key_id", "publisher_key_sha256",
        ):
            if plan.get(key) is not None:
                print(f"{key.upper()}={plan[key]}", file=out)
        paths = plan.get("paths")
        if isinstance(paths, dict):
            for key in (
                "destination", "identity_home", "local_state", "safe_state",
                "installation_store", "operator_bin", "global_bin", "start_menu",
            ):
                if paths.get(key) is not None:
                    print(f"PATH_{key.upper()}={paths[key]}", file=out)
        service = plan.get("service")
        if isinstance(service, dict):
            print(f"SERVICE_NAME={service.get('name')}", file=out)
            print(f"SERVICE_HEALTH={service.get('health')}", file=out)
        release_files = plan.get("release_files")
        if isinstance(release_files, list):
            for item in release_files:
                if isinstance(item, dict):
                    print(
                        f"RELEASE_FILE={item.get('kind')}:{item.get('path')}",
                        file=out,
                    )
        print(f"IDENTITY_RETENTION={plan.get('identity_retention')}", file=out)
        print(f"STATE_RETENTION={plan.get('state_retention')}", file=out)
        print(f"PURGE={plan.get('purge')}", file=out)
        print(f"ELEVATION_REQUIRED={str(plan.get('elevation_required')).upper()}", file=out)
        apps = plan.get("operator_apps")
        if isinstance(apps, dict):
            print(f"OPERATOR_GLOBAL_COMMAND={apps.get('global_command')}", file=out)
            print(
                f"OPERATOR_GLOBAL_BIN={apps.get('global_bin_directory')}", file=out,
            )
            for path in apps.get("files", []):
                print(f"OPERATOR_FILE={path}", file=out)
            for path in apps.get("shortcuts", []):
                print(f"OPERATOR_SHORTCUT={path}", file=out)
        approvals = plan.get("approvals_needed")
        if isinstance(approvals, list):
            for item in approvals:
                if isinstance(item, dict):
                    print(
                        f"APPROVAL_NEEDED={item.get('stage')}:{item.get('capability')}",
                        file=out,
                    )
    stages = result.get("stages")
    if isinstance(stages, list):
        for item in stages:
            if isinstance(item, dict):
                print(f"STAGE_{item.get('stage')}={item.get('outcome')}", file=out)
    print(f"EXECUTED={str(result.get('executed')).upper()}", file=out)
    print(
        f"OWNER_APPROVED={str(result.get('owner_approved')).upper()}", file=out,
    )
    print(
        f"CORE_ACTIVATED={str(result.get('core_activated')).upper()}", file=out,
    )


def _desktop_directory(target: PlatformReleaseTarget) -> Path | None:
    if target is PlatformReleaseTarget.WINDOWS_X86_64:
        profile = os.environ.get("USERPROFILE", "").strip()
        candidate = None if not profile else Path(profile) / "Desktop"
    else:
        candidate = Path.home() / "Desktop"
    return candidate if candidate is not None and candidate.is_dir() else None


def _existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _preflight(
    bundle_root: Path | str,
    *,
    target: PlatformReleaseTarget,
    install_root: Path,
    trust_root: Path | str | None,
    script_directory: Path | None,
) -> dict[str, object]:
    """Read-only host/media checks used by the Windows TUI before prompting."""
    blockers: list[str] = []
    release_fields: dict[str, object] = {}
    asset_bytes = 0
    asset_kinds: set[str] = set()
    try:
        layout = discover_bundle(bundle_root, script_directory=script_directory)
        release, payload = verify_bundle(
            layout, target=target, trust_root=trust_root,
        )
        _bundled_python(layout, target)
        release_fields = _release_fields(release)
        for item in payload.get("assets", []):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind"))
            asset_kinds.add(kind)
            reference = item.get("reference")
            path = "" if not isinstance(reference, dict) else str(reference.get("path", ""))
            if (kind == "tui" or item.get("role") == "aegis_tui"
                    or Path(path).name.casefold() in (
                        "aegis_tui.exe", "aegis-tui.exe",
                        "aegis_tui", "aegis-tui",
                    )):
                asset_kinds.add("tui")
            if isinstance(reference, dict):
                size = reference.get("size_bytes")
                if type(size) is int and size >= 0:
                    asset_bytes += size
    except GuidedDenied as error:
        blockers.append(f"{error.code}: {error.detail}")
    except PlatformInstallationDenied as error:
        blockers.append(str(error))
    except (OSError, ValueError, TypeError):
        blockers.append("installer media or trust inputs are unavailable")

    try:
        paths = paths_for_install_root(
            target, install_root,
            desktop_directory=_desktop_directory(target),
        )
        existing = current_destination(paths)
    except (GuidedDenied, OSError, ValueError, TypeError, PermissionError) as error:
        paths = None
        existing = None
        blockers.append(
            getattr(error, "detail", str(error)) or "install directory is invalid"
        )

    ancestor = _existing_ancestor(install_root)
    try:
        usage = shutil.disk_usage(ancestor)
        free_bytes = int(usage.free)
    except OSError:
        free_bytes = 0
        blockers.append("free disk space could not be observed")
    required_bytes = asset_bytes + 512 * 1024 * 1024
    if free_bytes and free_bytes < required_bytes:
        blockers.append(
            f"insufficient disk space: need at least {required_bytes} bytes, "
            f"observed {free_bytes}"
        )

    return {
        "ok": not blockers,
        "blockers": tuple(blockers),
        "host": platform.node() or "UNKNOWN",
        "os": platform.platform(),
        "target": target.value,
        "install_root": str(install_root),
        "existing_destination": None if existing is None else str(existing),
        "paths": None if paths is None else paths.as_plan(),
        "free_bytes": free_bytes,
        "required_bytes": required_bytes,
        "asset_bytes": asset_bytes,
        "asset_kinds": tuple(sorted(asset_kinds)),
        "tui_available": "tui" in asset_kinds,
        **release_fields,
    }


def _prompt_text(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return default if not value else value


def _prompt_yes(prompt: str, *, default: bool = True) -> bool:
    marker = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{marker}]: ").strip().casefold()
    if not value:
        return default
    if value in ("y", "yes"):
        return True
    if value in ("n", "no"):
        return False
    return default


def _print_preflight(preflight: Mapping[str, object], *, theme, color: bool) -> None:
    print(_paint("SYSTEM CHECK", "primary", theme, color))
    print(f"HOST={preflight.get('host')}")
    print(f"OS={preflight.get('os')}")
    print(f"TARGET={preflight.get('target')}")
    print(f"INSTALL_ROOT={preflight.get('install_root')}")
    print(f"SIGNED_RELEASE={preflight.get('release_id', 'UNAVAILABLE')}")
    print(f"REVISION={preflight.get('revision', 'UNKNOWN')}")
    print(f"SIGNER={preflight.get('signer_key_id', 'UNAVAILABLE')}")
    existing = preflight.get("existing_destination")
    print(f"EXISTING_INSTALL={existing or 'NONE_DETECTED'}")
    print(f"FREE_BYTES={preflight.get('free_bytes')}")
    print(f"REQUIRED_BYTES={preflight.get('required_bytes')}")
    print(f"TUI_AVAILABLE={str(preflight.get('tui_available')).upper()}")
    blockers = preflight.get("blockers", ())
    if blockers:
        print(_paint("BLOCKERS:", "warning", theme, color))
        for blocker in blockers:
            print(f"  - {blocker}")
    else:
        print(_paint("SYSTEM CHECK=PASS", "success", theme, color))


def _install_wizard(
    bundle_root: Path | str, *, target: PlatformReleaseTarget,
    script_directory: Path | None, trust_root: Path | str | None,
    theme, color: bool, no_color: bool,
    install_root: Path | str | None = None,
) -> dict[str, object] | None:
    default_root = (
        default_install_root(target) if install_root is None else Path(install_root)
    )
    preflight = _preflight(
        bundle_root, target=target, install_root=default_root,
        trust_root=trust_root, script_directory=script_directory,
    )
    _print_preflight(preflight, theme=theme, color=color)
    if preflight.get("blockers"):
        return None
    selected_root = Path(_prompt_text(
        "Installation directory", str(preflight.get("install_root", default_root)),
    ))
    desktop = _desktop_directory(target)
    preflight = _preflight(
        bundle_root, target=target, install_root=selected_root,
        trust_root=trust_root, script_directory=script_directory,
    )
    _print_preflight(preflight, theme=theme, color=color)
    if preflight.get("blockers"):
        return None
    if preflight.get("existing_destination"):
        print(
            "An existing Aegis installation was detected. No files are changed "
            "until the reviewed plan is verified and owner approval succeeds."
        )

    tui_available = bool(preflight.get("tui_available"))
    include_tui = _prompt_yes(
        "Install terminal TUI launcher", default=tui_available,
    ) if tui_available else False
    include_start_menu = _prompt_yes(
        "Create Start Menu shortcut", default=include_tui,
    ) if include_tui else False
    include_desktop = _prompt_yes(
        "Create Desktop shortcut",
        default=False,
    ) if desktop is not None and include_tui else False
    start_at_login = _prompt_yes(
        "Start Aegis TUI at sign-in", default=False,
    ) if (
        target is PlatformReleaseTarget.WINDOWS_X86_64 and include_tui
    ) else False

    try:
        paths = paths_for_install_root(
            target, selected_root, desktop_directory=desktop,
        )
        plan_result = run_guided(
            bundle_root, check=True, target=target, paths=paths,
            script_directory=script_directory, trust_root=trust_root,
            start_at_login=start_at_login, include_tui=include_tui,
            include_start_menu=include_start_menu, include_desktop=include_desktop,
        )
    except Exception as error:
        print(f"Plan could not be produced: {error}")
        return None
    plan = plan_result.get("plan")
    if isinstance(plan, dict):
        print()
        _print_result(plan_result, theme=theme, color=color)
        print("COMPONENTS=" + json.dumps(
            plan.get("components", {}), sort_keys=True, separators=(",", ":"),
        ))
        print("STARTUP_PREFERENCE=" + str(plan.get("startup_preference")))
        operator_plan = plan.get("operator_apps")
        startup_plan = (
            operator_plan.get("startup")
            if isinstance(operator_plan, dict) else None
        )
        if isinstance(startup_plan, dict):
            print("STARTUP_ACTION=" + json.dumps(
                startup_plan, sort_keys=True, separators=(",", ":"),
            ))
        else:
            print("STARTUP_ACTION=UNKNOWN")
    if plan_result.get("outcome") != "PREVIEW_OK":
        return plan_result
    if not _prompt_yes(
        "Apply this exact read-only plan now? Owner approval and UAC are still required",
        default=False,
    ):
        print("Installation cancelled; no changes were made.")
        return None
    return run_guided(
        bundle_root, operation="install", target=target, paths=paths,
        script_directory=script_directory, trust_root=trust_root,
        start_at_login=start_at_login, include_tui=include_tui,
        include_start_menu=include_start_menu, include_desktop=include_desktop,
        bootstrap_first_install_state=True,
    )


def _interactive(
    bundle_root: Path | str, *, script_directory: Path | None = None,
    trust_root: Path | str | None = None, no_color: bool = False,
    install_root: Path | str | None = None,
) -> int:
    try:
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, OSError):
        interactive = False
    if not interactive:
        result = _denied(
            "menu", "INTERACTIVE_CONSOLE_REQUIRED",
            "an interactive console is required; use --check or --operation",
        )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 3
    theme = _load_theme(script_directory)
    color = not no_color
    while True:
        print()
        print(_paint("+------------------------------------------------------------+", "primary", theme, color))
        print(_paint("|                 AEGIS PLATFORM GUIDED SETUP                |", "primary", theme, color))
        print(_paint("|           ONE-STEP SIGNED INSTALL / MAINTENANCE            |", "accent", theme, color))
        print(_paint("+------------------------------------------------------------+", "primary", theme, color))
        choices = (
            ("1", "Install", "install"),
            ("2", "Update", "update"),
            ("3", "Repair", "repair"),
            ("4", "Rollback", "rollback"),
            ("5", "Uninstall", "uninstall"),
            ("6", "Status", "status"),
            ("7", "Diagnostics", "diagnostics"),
            ("0", "Exit", None),
        )
        for key, label, _op in choices:
            print(_paint(f"[{key}] {label}", "accent", theme, color))
        try:
            selection = input("Select [0-7]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        selected = {key: op for key, _label, op in choices}.get(selection, "invalid")
        if selection in ("0", "q", "Q"):
            return 0
        if selected == "invalid":
            print("Invalid selection; no operation performed.")
            continue
        try:
            target = host_release_target()
        except PlatformInstallationDenied as error:
            print(f"Unsupported host: {error}")
            continue
        if selected == "install":
            result = _install_wizard(
                bundle_root, target=target, script_directory=script_directory,
                trust_root=trust_root, theme=theme, color=color,
                no_color=no_color, install_root=install_root,
            )
            if result is None:
                continue
            _print_result(result, theme=theme, color=color)
            continue
        result = run_guided(
            bundle_root, operation=selected, check=False,
            script_directory=script_directory, trust_root=trust_root,
            install_root=install_root,
        )
        _print_result(result, theme=theme, color=color)
        if (selected not in MUTATING_OPERATIONS
                and result.get("outcome") == "PREVIEW_OK"):
            continue


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="platform_installer_guided", description=__doc__,
    )
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--operation", choices=OPERATIONS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--trust-root", type=Path)
    parser.add_argument("--install-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    script_directory = Path(__file__).resolve().parent
    no_color = bool(args.no_color or "NO_COLOR" in os.environ)
    if args.check or args.operation is not None or args.json:
        result = run_guided(
            args.bundle_root, check=bool(args.check or (
                args.json and args.operation is None
            )), operation=args.operation, script_directory=script_directory,
            trust_root=args.trust_root, install_root=args.install_root,
        )
        if args.json:
            print(json.dumps(
                result, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ))
        else:
            theme = _load_theme(script_directory)
            color = sys.stdout.isatty() and not no_color
            _print_result(result, theme=theme, color=color)
        return 0 if result.get("outcome") in SUCCESS_OUTCOMES else 3
    return _interactive(
        args.bundle_root, script_directory=script_directory,
        trust_root=args.trust_root, no_color=no_color,
        install_root=args.install_root,
    )


if __name__ == "__main__":
    sys.exit(main())
