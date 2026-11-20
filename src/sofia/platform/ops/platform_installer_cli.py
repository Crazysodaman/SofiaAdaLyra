"""Canonical AG-D011 signed offline installer command adapter.

This module is one presentation/command adapter over the existing signed release
verifier, canonical B1 installation store, owner-approved code publication and
native service transaction owners. It does not reimplement signatures, release
selection, identity, approval, durable state or OS service behaviour.

Every mutating command consumes an existing one-use SAFE approval. A missing,
stale or revoked trust input or approval is denied. Staging is inert and is not
an installation; native OS effects remain inside the reviewed backend.

The additive ``approval_provider`` hook receives the exact canonical request
that this module already builds and may return only a one-use approval id. It
does not mint authority: the existing attended SAFE ceremony and every original
consume/revocation check remain decisive. ``apply_operator_apps_command`` is the
additive launcher-only owner used after a separately successful lifecycle step.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore, install_staged_release,
    platform_rollback_request, verify_installed, verify_staged_release_candidate,
)
from sofia.platform.ops.platform_installer_bundle import (
    SignedInstallerRelease, verify_offline_installer_bundle,
)
from sofia.platform.ops.platform_installer_code_install import (
    publish_owner_approved_code, signed_code_publication_request,
)
from sofia.platform.ops.platform_installer_native_service import (
    DebianSystemdNativeService, WindowsScmNativeService,
)
from sofia.platform.ops.platform_installer_operator_apps import (
    InMemoryPathAdapter, OperatorAppsConfiguration, OperatorAppsDenied,
    PyWin32ShortcutAdapter, WindowsRegistryPathAdapter,
    apply_owner_approved_operator_apps, operator_apps_request,
)
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.ops.platform_installer_native_transaction import (
    apply_owner_approved_native_service, native_service_operation_request,
    native_transaction_state, reconcile_owner_approved_native_service,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.ops.platform_release_staging import stage_platform_release
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.state.private_file import (
    assert_no_redirected_components, ensure_owner_private_directory,
)
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget

COMMANDS = (
    "verify", "status", "doctor", "install", "update", "repair", "rollback",
    "uninstall", "reinstall", "reconcile",
)
SUCCESS_OUTCOMES = frozenset((
    "VERIFIED", "OK", "NO_CHANGES_MADE", "INSTALLED", "UPDATED", "REPAIRED",
    "ROLLED_BACK", "UNINSTALLED", "REINSTALLED", "RECONCILED",
))
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_KEY_BYTES = 16_384
_MAX_MANIFEST_BYTES = 131_072
_MAX_SIGNATURE_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class InstallerInputs:
    release_root: Path | str | None = None
    publisher_key: Path | str | None = None
    publisher_key_sha256: str | None = None
    publisher_signer: str | None = None
    expected_source_sha: str | None = None
    target: str | None = None
    minimum_revision: int | None = None
    destination: Path | str | None = None
    identity_home: Path | str | None = None
    local_state: Path | str | None = None
    canonical_safe_state: Path | str | None = None
    store_path: Path | str | None = None
    approval_id: str | None = None
    code_approval_id: str | None = None
    bootstrap_first_install_state: bool = False
    previous_destination: Path | str | None = None
    staging_candidate: Path | str | None = None
    expected_parent_manifest_sha256: str | None = None
    operator_apps_requested: bool = False
    operator_apps_approval_id: str | None = None
    operator_apps_runtime_python: Path | str | None = None
    operator_apps_code_directory: Path | str | None = None
    operator_apps_bin_directory: Path | str | None = None
    operator_apps_gui_executable: Path | str | None = None
    operator_apps_tui_executable: Path | str | None = None
    operator_apps_start_menu_directory: Path | str | None = None
    operator_apps_desktop_directory: Path | str | None = None
    operator_apps_global_bin_directory: Path | str | None = None
    operator_apps_approved_roots: tuple[Path | str, ...] = ()
    operator_apps_protected_paths: tuple[Path | str, ...] = ()
    operator_apps_path_scope: str = "user"
    operator_apps_include_powershell: bool = False
    operator_apps_desktop_shortcut: bool = False
    operator_apps_start_at_login: bool = False


def _result(command: str, outcome: str, *, executed: bool = False,
            owner_approved: bool = False, **fields) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "aegis.installer.cli-result.v1",
        "command": command,
        "outcome": outcome,
        "executed": bool(executed),
        "owner_approved": bool(owner_approved),
        "core_activated": False,
        "fleet_enrolled": False,
        "production_authorized": False,
    }
    payload.update(fields)
    return payload


def _denied(command: str, code: str, *, executed: bool = False,
            detail: str = "signed installer contract refused the request",
            **fields) -> dict[str, object]:
    return _result(
        command, "DENIED", executed=executed,
        error={"code": code, "detail": detail},
        **fields,
    )


def _require(value, name: str):
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PlatformInstallationDenied(f"missing trusted installer input: {name}")
    return value


def _require_hex(value, name: str, pattern) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise PlatformInstallationDenied(f"invalid trusted installer input: {name}")
    return value


def _target(value) -> PlatformReleaseTarget:
    try:
        return PlatformReleaseTarget(_require(value, "target"))
    except ValueError as error:
        raise PlatformInstallationDenied("unsupported signed release target") from error


def _positive_floor(value) -> int:
    if type(value) is not int or value < 1:
        raise PlatformInstallationDenied("positive durable revision floor required")
    return value


def _read_bounded_json(path: Path, limit: int):
    assert_no_redirected_components(path, include_leaf=True)
    info = path.stat(follow_symlinks=False)
    if not 1 <= info.st_size <= limit:
        raise PlatformInstallationDenied("installer metadata outside bounded size")
    return loads_strict_model_json(
        read_artifact_file(path, info.st_size, include_data=True)[1].decode("utf-8")
    )


def _pinned_verifier(inputs: InstallerInputs) -> PlatformReleaseVerifier:
    root = Path(_require(inputs.release_root, "release root")).absolute()
    key = Path(_require(inputs.publisher_key, "publisher key")).absolute()
    fingerprint = _require_hex(
        inputs.publisher_key_sha256, "publisher key SHA-256", _HEX64,
    )
    signer = _require(inputs.publisher_signer, "publisher signer")
    assert_no_redirected_components(root, include_leaf=True)
    assert_no_redirected_components(key, include_leaf=True)
    if not root.is_dir() or key == root or root in key.parents:
        raise PlatformInstallationDenied(
            "publisher trust must be provisioned independently of release media"
        )
    info = key.stat(follow_symlinks=False)
    if not 1 <= info.st_size <= _MAX_KEY_BYTES:
        raise PlatformInstallationDenied("publisher key outside bounded size")
    data = read_artifact_file(key, info.st_size, include_data=True)[1]
    if sha256(data).hexdigest() != fingerprint:
        raise PlatformInstallationDenied("publisher key differs from independent pin")
    return PlatformReleaseVerifier({signer: data})


def _verify_release(inputs: InstallerInputs, *, floor: int,
                    expected_parent: str | None = None) -> SignedInstallerRelease:
    root = Path(_require(inputs.release_root, "release root")).absolute()
    key = Path(_require(inputs.publisher_key, "publisher key")).absolute()
    fingerprint = _require_hex(
        inputs.publisher_key_sha256, "publisher key SHA-256", _HEX64,
    )
    signer = _require(inputs.publisher_signer, "publisher signer")
    source = _require_hex(
        inputs.expected_source_sha, "expected source SHA", _HEX40,
    )
    target = _target(inputs.target)
    released = verify_offline_installer_bundle(
        root,
        trusted_public_key=key,
        trusted_key_sha256=fingerprint,
        trusted_signer_key_id=signer,
        expected_source_sha=source,
        expected_target=target,
        minimum_revision=_positive_floor(floor),
        expected_parent_manifest_sha256=expected_parent,
        require_local_host=True,
    )
    return released


def _store(inputs: InstallerInputs, *, create: bool) -> PlatformInstallationStore:
    path = Path(_require(inputs.store_path, "local installation state")).absolute()
    if not create and not path.exists():
        raise FileNotFoundError("installation state is absent")
    return PlatformInstallationStore(path)


def _stop_active(inputs: InstallerInputs) -> bool:
    safe = Path(_require(inputs.canonical_safe_state, "canonical SAFE state")).absolute()
    if not safe.exists():
        raise FileNotFoundError("canonical SAFE state is absent")
    return OperatorStopStore(safe).current().active


def _bootstrap_first_install_state(inputs: InstallerInputs) -> None:
    """Provision empty identity, SAFE and local state for an authorized install.

    The attended guided installer sets this explicit input after the owner
    approves the preview. An existing destination or installation store never
    permits this initialization; partial state is validated, never repaired.
    """
    if not inputs.bootstrap_first_install_state:
        return
    destination = Path(_require(inputs.destination, "destination")).absolute()
    identity_home = Path(_require(inputs.identity_home, "identity home")).absolute()
    local_state = Path(_require(
        inputs.local_state, "local Platform state",
    )).absolute()
    safe = Path(_require(
        inputs.canonical_safe_state, "canonical SAFE state",
    )).absolute()
    store_path = Path(_require(
        inputs.store_path, "local installation state",
    )).absolute()
    if safe.exists() and identity_home.exists() and local_state.exists():
        return
    if destination.exists():
        raise PlatformInstallationDenied(
            "first-install state bootstrap is unavailable for an existing installation"
        )
    if store_path.exists():
        store = PlatformInstallationStore(store_path)
        checkpoint = store.checkpoint()
        if (store.history() or store.pending_attempts()
                or (checkpoint is not None
                    and checkpoint.active_release_id is not None)):
            raise PlatformInstallationDenied(
                "first-install state bootstrap is unavailable for an existing installation"
            )
    ensure_owner_private_directory(safe.parent)
    if not safe.exists():
        bootstrap_canonical_sqlite(safe)
    identity = InstallationIdentityStore(identity_home).initialize()
    roles = PlatformRoleConfiguration((PlatformRole.MODULE_HOST,))
    PlatformLocalStore(
        local_state, roles=roles,
        host_identity=identity.identity.canonical_uuid,
        create=not local_state.exists(),
    )


def _assert_not_stopped(inputs: InstallerInputs) -> None:
    if _stop_active(inputs):
        raise PlatformInstallationDenied("operator STOP is engaged")


def _paths(inputs: InstallerInputs) -> tuple[Path, Path, Path, Path]:
    destination = Path(_require(inputs.destination, "destination")).absolute()
    identity = Path(_require(inputs.identity_home, "identity home")).absolute()
    local_state = Path(_require(inputs.local_state, "local Platform state")).absolute()
    safe = Path(_require(inputs.canonical_safe_state, "canonical SAFE state")).absolute()
    for path in (destination, identity, local_state, safe):
        assert_no_redirected_components(path, include_leaf=True)
    return destination, identity, local_state, safe


def _default_backend(target: PlatformReleaseTarget):
    if target is PlatformReleaseTarget.WINDOWS_X86_64:
        return WindowsScmNativeService()
    return DebianSystemdNativeService()


def _operator_apps_config(inputs: InstallerInputs) -> OperatorAppsConfiguration | None:
    if not inputs.operator_apps_requested:
        return None
    protected = list(inputs.operator_apps_protected_paths)
    for value in (inputs.identity_home, inputs.local_state,
                  inputs.canonical_safe_state):
        if value is not None:
            protected.append(value)
    return OperatorAppsConfiguration(
        target=_target(inputs.target),
        runtime_python=Path(_require(
            inputs.operator_apps_runtime_python, "operator app runtime Python")),
        code_directory=Path(_require(
            inputs.operator_apps_code_directory, "operator app code directory")),
        bin_directory=Path(_require(
            inputs.operator_apps_bin_directory, "operator app bin directory")),
        gui_executable=(None if inputs.operator_apps_gui_executable is None
                        else Path(inputs.operator_apps_gui_executable)),
        tui_executable=(None if inputs.operator_apps_tui_executable is None
                        else Path(inputs.operator_apps_tui_executable)),
        start_menu_directory=(None if inputs.operator_apps_start_menu_directory is None
                              else Path(inputs.operator_apps_start_menu_directory)),
        desktop_directory=(None if inputs.operator_apps_desktop_directory is None
                           else Path(inputs.operator_apps_desktop_directory)),
        global_bin_directory=(None if inputs.operator_apps_global_bin_directory is None
                              else Path(inputs.operator_apps_global_bin_directory)),
        approved_roots=tuple(Path(item) for item in inputs.operator_apps_approved_roots),
        protected_paths=tuple(Path(item) for item in protected),
        path_scope=inputs.operator_apps_path_scope,
        include_powershell=inputs.operator_apps_include_powershell,
        include_desktop_shortcut=inputs.operator_apps_desktop_shortcut,
        start_at_login=inputs.operator_apps_start_at_login,
    )


def _operator_apps_preflight(
    command: str, inputs: InstallerInputs,
) -> OperatorAppsConfiguration | None:
    """Require the separate exact approval before any Platform effect."""
    config = _operator_apps_config(inputs)
    if config is None:
        return None
    request = operator_apps_request(command, config)
    state = Path(_require(inputs.canonical_safe_state, "canonical SAFE state")).absolute()
    approval_id = inputs.operator_apps_approval_id
    now = datetime.now(timezone.utc)
    if (not approval_id
            or not ExecutionApprovalVerifier(state).matches_unconsumed(
                approval_id=approval_id,
                capability=request["capability"],
                parameters=request["parameters"],
                now=now,
            )):
        raise _ApprovalRequired(
            "operator_apps", request, command=command,
        )
    return config


def _apply_operator_apps(
    *, command: str, inputs: InstallerInputs, store: PlatformInstallationStore,
    config: OperatorAppsConfiguration | None, path_adapter=None,
    shortcut_adapter=None,
) -> dict[str, object] | None:
    if config is None:
        return None
    target = _target(inputs.target)
    if path_adapter is None:
        path_adapter = (
            WindowsRegistryPathAdapter(scope=config.path_scope)
            if target is PlatformReleaseTarget.WINDOWS_X86_64
            else InMemoryPathAdapter()
        )
    if shortcut_adapter is None:
        shortcut_adapter = PyWin32ShortcutAdapter()
    try:
        return apply_owner_approved_operator_apps(
            approval_id=inputs.operator_apps_approval_id,
            operation=command,
            config=config,
            state_path=Path(_require(
                inputs.canonical_safe_state, "canonical SAFE state")),
            store=store,
            path_adapter=path_adapter,
            shortcut_adapter=shortcut_adapter,
            now=datetime.now(timezone.utc),
        )
    except OperatorAppsDenied:
        raise
    except Exception as error:
        raise PlatformInstallationDenied(
            "operator application launcher effect failed; receipt recorded"
        ) from error


def _operator_apps_fields(receipt: dict[str, object] | None) -> dict[str, object]:
    if receipt is None:
        return {}
    return {
        "operator_apps_receipt": receipt,
        "operator_apps_plan_digest": receipt["plan_digest"],
        "operator_apps_path_action": receipt["path_action"],
        "operator_apps_shortcut_actions": receipt["shortcut_actions"],
    }


def staging_candidate_path(store_path: Path | str, release_id: str,
                           revision: int) -> Path:
    base = Path(store_path).absolute().parent / "installer-staging"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", release_id)[:80] or "release"
    return base / f"{safe_name}-r{int(revision)}"


def _staging_candidate(inputs: InstallerInputs, release: SignedInstallerRelease,
                       store: PlatformInstallationStore) -> Path:
    if inputs.staging_candidate is not None:
        return Path(inputs.staging_candidate).absolute()
    return staging_candidate_path(store.path, release.release_id, release.revision)


def _ensure_staging(inputs: InstallerInputs, release: SignedInstallerRelease,
                    store: PlatformInstallationStore,
                    verifier: PlatformReleaseVerifier, *, floor: int) -> Path:
    root = Path(inputs.release_root).absolute()
    stage = _staging_candidate(inputs, release, store)
    assert_no_redirected_components(stage, include_leaf=True)
    if (stage == root or root in stage.parents or stage in root.parents
            or store.path == stage or store.path in stage.parents):
        raise PlatformInstallationDenied(
            "staging candidate must remain separate from release media and B1 state"
        )
    if stage.exists() or stage.is_symlink():
        candidate = verify_staged_release_candidate(
            stage, verifier=verifier, minimum_revision=1,
        )
        if (candidate.release_id != release.release_id
                or candidate.manifest_sha256 != release.manifest_sha256
                or candidate.revision != release.revision):
            raise PlatformInstallationDenied(
                "existing staging candidate belongs to another signed release"
            )
        return stage
    ensure_owner_private_directory(stage.parent)
    payload = _read_bounded_json(root / "release-manifest.json", _MAX_MANIFEST_BYTES)
    envelope = _read_bounded_json(
        root / "release-signature.json", _MAX_SIGNATURE_BYTES,
    )
    if (type(envelope) is not dict
            or set(envelope) != {"signer_key_id", "signature_b64"}):
        raise PlatformInstallationDenied("release signature envelope is not canonical")
    signed_parent = payload.get("parent_manifest_sha256")
    if (inputs.expected_parent_manifest_sha256 is not None
            and signed_parent != inputs.expected_parent_manifest_sha256):
        raise PlatformInstallationDenied(
            "signed release predecessor differs from the trusted expectation"
        )
    stage_platform_release(
        verifier=verifier, payload=payload,
        signature_b64=envelope["signature_b64"],
        signer_key_id=envelope["signer_key_id"],
        assets_root=root / "assets", destination=stage,
        expected_source_sha=inputs.expected_source_sha,
        expected_target=_target(inputs.target),
        minimum_revision=_positive_floor(floor),
        expected_parent_manifest_sha256=signed_parent,
    )
    candidate = verify_staged_release_candidate(
        stage, verifier=verifier, minimum_revision=1,
    )
    if (candidate.release_id != release.release_id
            or candidate.manifest_sha256 != release.manifest_sha256):
        raise PlatformInstallationDenied("staged release differs from verified media")
    return stage


def _release_fields(release: SignedInstallerRelease) -> dict[str, object]:
    return {
        "release_id": release.release_id,
        "revision": release.revision,
        "manifest_sha256": release.manifest_sha256,
        "source_sha": release.source_sha,
        "target": release.target,
        "signer_key_id": release.signer_key_id,
        "publisher_key_sha256": release.trust_key_sha256,
    }


def _status_payload(inputs: InstallerInputs) -> dict[str, object]:
    payload: dict[str, object] = {
        "service_state": "NOT_OBSERVED",
        "installed_verified": False,
        "history_entries": 0,
        "pending_attempts": 0,
        "pending_native_attempts": 0,
        "native_journal_phase": "ABSENT",
        "native_journal_generation": 0,
        "native_service_registered": False,
        "active_release_id": None,
        "checkpoint_generation": 0,
        "minimum_accepted_revision": 0,
        "stop_active": None,
    }
    safe = inputs.canonical_safe_state
    if safe is not None and Path(safe).exists():
        payload["stop_active"] = OperatorStopStore(Path(safe)).current().active
    path = inputs.store_path
    if path is None or not Path(path).exists():
        return payload
    store = PlatformInstallationStore(Path(path))
    checkpoint = store.checkpoint()
    payload["history_entries"] = len(store.history())
    payload["pending_attempts"] = len(store.pending_attempts())
    try:
        journal = native_transaction_state(store)
    except (OSError, ValueError, TypeError, PermissionError):
        # An unreadable or inconsistent journal is an unresolved recovery
        # fence, never a clean status.
        payload["native_journal_phase"] = "INCONSISTENT"
        payload["pending_native_attempts"] = 1
    else:
        if journal is not None:
            phase = journal["phase"]
            payload["native_journal_phase"] = phase
            payload["native_journal_generation"] = journal["generation"]
            payload["native_service_registered"] = journal["current"] is not None
            if phase in ("PENDING", "OUTCOME_UNKNOWN"):
                payload["pending_native_attempts"] = 1
    if checkpoint is not None:
        payload["checkpoint_generation"] = checkpoint.generation
        payload["minimum_accepted_revision"] = checkpoint.minimum_accepted_revision
        payload["active_release_id"] = checkpoint.active_release_id
    if inputs.destination is not None:
        destination = Path(inputs.destination).absolute()
        row = store.receipt_for_destination(destination)
        if row is not None:
            payload["release_id"] = row["release_id"]
            payload["revision"] = int(row["revision"])
            payload["manifest_sha256"] = row["manifest_sha256"]
            if (inputs.publisher_key is not None
                    and inputs.publisher_key_sha256 is not None
                    and inputs.publisher_signer is not None
                    and inputs.release_root is not None):
                verifier = _pinned_verifier(inputs)
                try:
                    verified = verify_installed(
                        destination, store=store, verifier=verifier,
                        minimum_revision=int(row["revision"]),
                    )
                except (OSError, ValueError, TypeError, PermissionError):
                    payload["installed_verified"] = False
                else:
                    payload["installed_verified"] = (
                        verified["manifest_sha256"] == row["manifest_sha256"]
                    )
    return payload


def _command_verify(inputs: InstallerInputs) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    release = _verify_release(
        inputs, floor=floor,
        expected_parent=inputs.expected_parent_manifest_sha256,
    )
    return _result(
        "verify", "VERIFIED", executed=False, owner_approved=False,
        **_release_fields(release),
    )


def _command_status(inputs: InstallerInputs) -> dict[str, object]:
    payload = _status_payload(inputs)
    outcome = ("RECONCILIATION_REQUIRED"
               if payload["pending_attempts"] or payload["pending_native_attempts"]
               else "OK")
    return _result("status", outcome, **payload)


def _command_doctor(inputs: InstallerInputs) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    release = _verify_release(inputs, floor=floor)
    payload = _status_payload(inputs)
    payload.update(_release_fields(release))
    outcome = ("RECONCILIATION_REQUIRED"
               if payload["pending_attempts"] or payload["pending_native_attempts"]
               else "OK")
    return _result("doctor", outcome, **payload)


def _published_receipt(store: PlatformInstallationStore, destination: Path):
    return store.receipt_for_destination(destination)


def _ensure_code_published(*, command: str, inputs: InstallerInputs,
                           release: SignedInstallerRelease,
                           store: PlatformInstallationStore,
                           verifier: PlatformReleaseVerifier,
                           destination: Path, identity: Path, safe: Path,
                           floor: int, now: datetime,
                           previous_destination: Path | None) -> dict[str, object]:
    row = _published_receipt(store, destination)
    if row is not None:
        verified = verify_installed(
            destination, store=store, verifier=verifier,
            minimum_revision=max(1, int(row["revision"])),
        )
        if (verified["release_id"] != release.release_id
                or verified["manifest_sha256"] != release.manifest_sha256):
            raise PlatformInstallationDenied(
                "published B1 release differs from verified offline release"
            )
        return {"code_published": True, "code_reused": True}
    stage = _ensure_staging(inputs, release, store, verifier, floor=floor)
    request = signed_code_publication_request(
        staged_candidate=stage, destination=destination,
        identity_home=identity, state_path=safe, store=store, verifier=verifier,
        expected_target=_target(inputs.target),
        previous_destination=previous_destination,
    )
    approval = inputs.code_approval_id
    if not approval:
        raise _ApprovalRequired(
            "code", request, command=command,
        )
    published = publish_owner_approved_code(
        approval_id=approval, staged_candidate=stage, destination=destination,
        identity_home=identity, state_path=safe, store=store, verifier=verifier,
        expected_target=_target(inputs.target), now=now,
        previous_destination=previous_destination,
    )
    if (published.get("result") != "PLATFORM_RELEASE_INSTALLED"
            or published.get("os_service_registered") is not False):
        raise PlatformInstallationDenied("canonical B1 code publication differs")
    return {"code_published": True, "code_reused": False}


class _ApprovalRequired(PlatformInstallationDenied):
    def __init__(self, kind: str, request: dict[str, object], *, command: str):
        super().__init__(f"{kind} owner approval required")
        self.kind = kind
        self.request = request
        self.fingerprint = request["fingerprint"]
        self.command = command


def _native_arguments(*, operation: str, inputs: InstallerInputs,
                      store: PlatformInstallationStore,
                      verifier: PlatformReleaseVerifier,
                      destination: Path, identity: Path, local_state: Path,
                      safe: Path,
                      previous_destination: Path | None) -> dict[str, object]:
    return dict(
        operation=operation, store=store, verifier=verifier,
        expected_target=_target(inputs.target), destination=destination,
        identity_home=identity, local_state=local_state,
        canonical_safe_state=safe,
        previous_destination=previous_destination if operation in
        ("update", "rollback") else None,
    )


def _apply_native(*, command: str, inputs: InstallerInputs, operation: str,
                  store: PlatformInstallationStore,
                  verifier: PlatformReleaseVerifier, destination: Path,
                  identity: Path, local_state: Path, safe: Path,
                  previous_destination: Path | None, backend,
                  now: datetime) -> dict[str, object]:
    arguments = _native_arguments(
        operation=operation, inputs=inputs, store=store, verifier=verifier,
        destination=destination, identity=identity, local_state=local_state,
        safe=safe, previous_destination=previous_destination,
    )
    if not inputs.approval_id:
        request = native_service_operation_request(**arguments)
        raise _ApprovalRequired(
            "native", request, command=command,
        )
    receipt = apply_owner_approved_native_service(
        **arguments, approval_id=inputs.approval_id, backend=backend, now=now,
    )
    if receipt.get("owner_approval_consumed") is not True:
        raise PlatformInstallationDenied("native owner approval was not consumed")
    return receipt


def _command_install(inputs: InstallerInputs, backend=None,
                     operator_apps_path_adapter=None,
                     operator_apps_shortcut_adapter=None) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    _bootstrap_first_install_state(inputs)
    _assert_not_stopped(inputs)
    release = _verify_release(
        inputs, floor=floor,
        expected_parent=inputs.expected_parent_manifest_sha256,
    )
    operator_apps = _operator_apps_preflight("install", inputs)
    store = _store(inputs, create=True)
    if store.pending_attempts():
        raise PlatformInstallationDenied("unreconciled B1 attempt blocks install")
    verifier = _pinned_verifier(inputs)
    destination, identity, local_state, safe = _paths(inputs)
    now = datetime.now(timezone.utc)
    publication = _ensure_code_published(
        command="install", inputs=inputs, release=release, store=store,
        verifier=verifier, destination=destination, identity=identity, safe=safe,
        floor=floor, now=now, previous_destination=None,
    )
    backend = backend or _default_backend(_target(inputs.target))
    receipt = _apply_native(
        command="install", inputs=inputs, operation="register", store=store,
        verifier=verifier, destination=destination, identity=identity,
        local_state=local_state, safe=safe, previous_destination=None,
        backend=backend, now=now,
    )
    operator_receipt = _apply_operator_apps(
        command="install", inputs=inputs, store=store, config=operator_apps,
        path_adapter=operator_apps_path_adapter,
        shortcut_adapter=operator_apps_shortcut_adapter,
    )
    return _result(
        "install", "INSTALLED", executed=True, owner_approved=True,
        **_release_fields(release), **publication,
        native_process_state=receipt.get("process_state"),
        service_health=receipt.get("service_health"),
        **_operator_apps_fields(operator_receipt),
    )


def _command_update(inputs: InstallerInputs, backend=None,
                    operator_apps_path_adapter=None,
                    operator_apps_shortcut_adapter=None) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    _assert_not_stopped(inputs)
    store = _store(inputs, create=True)
    if store.pending_attempts():
        raise PlatformInstallationDenied("unreconciled B1 attempt blocks update")
    previous = Path(_require(inputs.previous_destination, "previous destination")).absolute()
    previous_row = store.receipt_for_destination(previous)
    if previous_row is None:
        raise PlatformInstallationDenied("update requires existing canonical B1 release")
    release = _verify_release(
        inputs, floor=floor,
        expected_parent=previous_row["manifest_sha256"],
    )
    operator_apps = _operator_apps_preflight("update", inputs)
    verifier = _pinned_verifier(inputs)
    destination, identity, local_state, safe = _paths(inputs)
    if destination == previous:
        raise PlatformInstallationDenied("update destination must differ from active release")
    now = datetime.now(timezone.utc)
    publication = _ensure_code_published(
        command="update", inputs=inputs, release=release, store=store,
        verifier=verifier, destination=destination, identity=identity, safe=safe,
        floor=floor, now=now, previous_destination=previous,
    )
    backend = backend or _default_backend(_target(inputs.target))
    receipt = _apply_native(
        command="update", inputs=inputs, operation="update", store=store,
        verifier=verifier, destination=destination, identity=identity,
        local_state=local_state, safe=safe, previous_destination=previous,
        backend=backend, now=now,
    )
    operator_receipt = _apply_operator_apps(
        command="update", inputs=inputs, store=store, config=operator_apps,
        path_adapter=operator_apps_path_adapter,
        shortcut_adapter=operator_apps_shortcut_adapter,
    )
    return _result(
        "update", "UPDATED", executed=True, owner_approved=True,
        **_release_fields(release), **publication,
        native_process_state=receipt.get("process_state"),
        service_health=receipt.get("service_health"),
        **_operator_apps_fields(operator_receipt),
    )


def _command_rollback(inputs: InstallerInputs, backend=None) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    _assert_not_stopped(inputs)
    store = _store(inputs, create=True)
    if store.pending_attempts():
        raise PlatformInstallationDenied("unreconciled B1 attempt blocks rollback")
    previous = Path(_require(inputs.previous_destination, "previous destination")).absolute()
    previous_row = store.receipt_for_destination(previous)
    if previous_row is None:
        raise PlatformInstallationDenied("rollback requires existing active B1 release")
    release = _verify_release(inputs, floor=1)
    if release.revision >= int(previous_row["revision"]):
        raise PlatformInstallationDenied("rollback must target an older signed release")
    if floor < release.revision + 1:
        raise PlatformInstallationDenied("rollback revision floor fence is inconsistent")
    verifier = _pinned_verifier(inputs)
    destination, identity, local_state, safe = _paths(inputs)
    if destination == previous:
        raise PlatformInstallationDenied("rollback destination must differ from active release")
    now = datetime.now(timezone.utc)
    row = store.receipt_for_destination(destination)
    code_published = row is not None
    if row is not None:
        verified = verify_installed(
            destination, store=store, verifier=verifier,
            minimum_revision=max(1, int(row["revision"])),
        )
        if (verified["release_id"] != release.release_id
                or verified["manifest_sha256"] != release.manifest_sha256):
            raise PlatformInstallationDenied(
                "rollback target differs from previously installed signed bytes"
            )
    else:
        stage = _ensure_staging(inputs, release, store, verifier, floor=1)
        request = platform_rollback_request(
            stage, destination, safe, store=store, verifier=verifier,
        )
        if not inputs.code_approval_id:
            raise _ApprovalRequired(
                "code", request, command="rollback",
            )
        receipt = install_staged_release(
            stage, destination, store=store, verifier=verifier,
            operation="rollback", state_path=safe,
            approval_id=inputs.code_approval_id, now=now,
        )
        if receipt.get("result") != "PLATFORM_RELEASE_INSTALLED":
            raise PlatformInstallationDenied("canonical B1 rollback did not install")
    backend = backend or _default_backend(_target(inputs.target))
    receipt = _apply_native(
        command="rollback", inputs=inputs, operation="rollback", store=store,
        verifier=verifier, destination=destination, identity=identity,
        local_state=local_state, safe=safe, previous_destination=previous,
        backend=backend, now=now,
    )
    return _result(
        "rollback", "ROLLED_BACK", executed=True, owner_approved=True,
        **_release_fields(release), code_published=code_published,
        native_process_state=receipt.get("process_state"),
        service_health=receipt.get("service_health"),
    )


def _installed_parent_manifest_sha256(destination: Path) -> str | None:
    """Read the signed predecessor from already-verified installed bytes."""
    path = destination / "release-manifest.json"
    info = path.stat(follow_symlinks=False)
    if not 1 <= info.st_size <= 131_072:
        raise PlatformInstallationDenied("installed release manifest outside bound")
    try:
        payload = json.loads(
            read_artifact_file(path, info.st_size, include_data=True)[1].decode("utf-8")
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise PlatformInstallationDenied(
            "installed signed release manifest is unavailable"
        ) from error
    parent = payload.get("parent_manifest_sha256")
    if parent is not None and (
        not isinstance(parent, str) or _HEX64.fullmatch(parent) is None
    ):
        raise PlatformInstallationDenied("installed release predecessor is invalid")
    return parent


def _verify_installed_release(inputs: InstallerInputs, *, operation: str,
                              floor: int) -> tuple[
                                  SignedInstallerRelease, PlatformInstallationStore,
                                  PlatformReleaseVerifier, Path, Path, Path, Path]:
    store = _store(inputs, create=True)
    if store.pending_attempts():
        raise PlatformInstallationDenied("unreconciled B1 attempt blocks maintenance")
    verifier = _pinned_verifier(inputs)
    destination, identity, local_state, safe = _paths(inputs)
    row = store.receipt_for_destination(destination)
    if row is None:
        raise PlatformInstallationDenied("destination has no canonical B1 receipt")
    verified = verify_installed(
        destination, store=store, verifier=verifier,
        minimum_revision=max(1, int(row["revision"])),
    )
    # The installed signed manifest establishes the exact predecessor. Media
    # verification must bind to it instead of assuming a parentless release;
    # otherwise repair/reinstall after an approved update is impossible.
    release = _verify_release(
        inputs, floor=floor,
        expected_parent=_installed_parent_manifest_sha256(destination),
    )
    if (verified["release_id"] != release.release_id
            or verified["manifest_sha256"] != release.manifest_sha256):
        raise PlatformInstallationDenied(
            f"{operation} cannot switch signed releases"
        )
    return release, store, verifier, destination, identity, local_state, safe


def _command_repair(inputs: InstallerInputs, backend=None,
                    operator_apps_path_adapter=None,
                    operator_apps_shortcut_adapter=None) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    _assert_not_stopped(inputs)
    release, store, verifier, destination, identity, local_state, safe = (
        _verify_installed_release(inputs, operation="repair", floor=floor)
    )
    operator_apps = _operator_apps_preflight("repair", inputs)
    backend = backend or _default_backend(_target(inputs.target))
    receipt = _apply_native(
        command="repair", inputs=inputs, operation="repair", store=store,
        verifier=verifier, destination=destination, identity=identity,
        local_state=local_state, safe=safe, previous_destination=None,
        backend=backend, now=datetime.now(timezone.utc),
    )
    operator_receipt = _apply_operator_apps(
        command="repair", inputs=inputs, store=store, config=operator_apps,
        path_adapter=operator_apps_path_adapter,
        shortcut_adapter=operator_apps_shortcut_adapter,
    )
    return _result(
        "repair", "REPAIRED", executed=True, owner_approved=True,
        **_release_fields(release),
        native_process_state=receipt.get("process_state"),
        service_health=receipt.get("service_health"),
        **_operator_apps_fields(operator_receipt),
    )


def _command_uninstall(inputs: InstallerInputs, backend=None,
                       operator_apps_path_adapter=None,
                       operator_apps_shortcut_adapter=None) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    _assert_not_stopped(inputs)
    release, store, verifier, destination, identity, local_state, safe = (
        _verify_installed_release(inputs, operation="uninstall", floor=floor)
    )
    operator_apps = _operator_apps_preflight("uninstall", inputs)
    backend = backend or _default_backend(_target(inputs.target))
    receipt = _apply_native(
        command="uninstall", inputs=inputs, operation="unregister", store=store,
        verifier=verifier, destination=destination, identity=identity,
        local_state=local_state, safe=safe, previous_destination=None,
        backend=backend, now=datetime.now(timezone.utc),
    )
    operator_receipt = _apply_operator_apps(
        command="uninstall", inputs=inputs, store=store, config=operator_apps,
        path_adapter=operator_apps_path_adapter,
        shortcut_adapter=operator_apps_shortcut_adapter,
    )
    return _result(
        "uninstall", "UNINSTALLED", executed=True, owner_approved=True,
        **_release_fields(release),
        protected_identity_policy="RETAIN",
        protected_state_policy="RETAIN",
        native_process_state=receipt.get("process_state"),
        service_health=receipt.get("service_health"),
        **_operator_apps_fields(operator_receipt),
    )


def _command_reinstall(inputs: InstallerInputs, backend=None) -> dict[str, object]:
    floor = _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    _assert_not_stopped(inputs)
    release, store, verifier, destination, identity, local_state, safe = (
        _verify_installed_release(inputs, operation="reinstall", floor=floor)
    )
    backend = backend or _default_backend(_target(inputs.target))
    receipt = _apply_native(
        command="reinstall", inputs=inputs, operation="register", store=store,
        verifier=verifier, destination=destination, identity=identity,
        local_state=local_state, safe=safe, previous_destination=None,
        backend=backend, now=datetime.now(timezone.utc),
    )
    return _result(
        "reinstall", "REINSTALLED", executed=True, owner_approved=True,
        **_release_fields(release), identity_policy="REUSE_EXACT",
        native_process_state=receipt.get("process_state"),
        service_health=receipt.get("service_health"),
    )


def _command_reconcile(inputs: InstallerInputs, backend=None) -> dict[str, object]:
    _positive_floor(_require(inputs.minimum_revision, "revision floor"))
    _require_hex(inputs.expected_source_sha, "expected source SHA", _HEX40)
    _assert_not_stopped(inputs)
    release = _verify_release(inputs, floor=1)
    store = _store(inputs, create=True)
    verifier = _pinned_verifier(inputs)
    destination, identity, local_state, safe = _paths(inputs)
    row = store.receipt_for_destination(destination)
    if row is None or row["manifest_sha256"] != release.manifest_sha256:
        raise PlatformInstallationDenied(
            "reconciliation requires the exact installed signed release"
        )
    backend = backend or _default_backend(_target(inputs.target))
    arguments = dict(
        store=store, verifier=verifier, expected_target=_target(inputs.target),
        destination=destination, identity_home=identity, local_state=local_state,
        canonical_safe_state=safe, backend=backend,
    )
    if not inputs.approval_id:
        from sofia.platform.ops.platform_installer_native_transaction import (
            native_service_reconciliation_request,
        )
        request = native_service_reconciliation_request(**arguments)
        raise _ApprovalRequired(
            "native", request, command="reconcile",
        )
    receipt = reconcile_owner_approved_native_service(
        **arguments, approval_id=inputs.approval_id,
        now=datetime.now(timezone.utc),
    )
    return _result(
        "reconcile", "RECONCILED", executed=True, owner_approved=True,
        journal_reconciled=receipt.get("journal_reconciled") is True,
        native_service_mutated=receipt.get("native_service_mutated"),
        service_health=receipt.get("service_health"),
    )


def apply_operator_apps_command(
    operation: str, inputs: InstallerInputs, *, path_adapter=None,
    shortcut_adapter=None, approval_provider=None,
) -> dict[str, object]:
    """Additive owner: apply only operator applications after an installed step.

    It uses the same exact one-use SAFE approval, plan digest and adapters as the
    lifecycle commands. It never changes a release or an OS service.
    """
    if operation not in ("install", "update", "repair", "uninstall"):
        return _denied(operation, "UNSUPPORTED_COMMAND")
    try:
        config = _operator_apps_config(inputs)
        if config is None:
            return _result(operation, "NO_CHANGES_MADE")
        if not inputs.operator_apps_approval_id:
            request = operator_apps_request(operation, config)
            if approval_provider is None:
                return _denied(
                    operation, "OWNER_APPROVAL_REQUIRED",
                    required_approval="operator_apps",
                    approval_fingerprint=request["fingerprint"],
                )
            approval_id = approval_provider("operator_apps", request)
            inputs = replace(inputs, operator_apps_approval_id=approval_id)
        _assert_not_stopped(inputs)
        _operator_apps_preflight(operation, inputs)
        store = _store(inputs, create=True)
        receipt = _apply_operator_apps(
            command=operation, inputs=inputs, store=store, config=config,
            path_adapter=path_adapter, shortcut_adapter=shortcut_adapter,
        )
        return _result(
            operation, "OK", executed=True, owner_approved=True,
            operator_apps_operation=operation,
            **_operator_apps_fields(receipt),
        )
    except _ApprovalRequired as required:
        return _denied(
            operation, "OWNER_APPROVAL_REQUIRED",
            required_approval=required.kind,
            approval_fingerprint=required.fingerprint,
        )
    except PlatformInstallationDenied:
        return _denied(operation, "DENIED")
    except PermissionError:
        return _denied(operation, "DENIED")
    except FileExistsError:
        return _denied(operation, "OCCUPIED_TARGET")
    except (FileNotFoundError, NotADirectoryError):
        return _denied(operation, "MISSING_INPUT")
    except OSError:
        return _denied(operation, "INPUT_UNAVAILABLE")
    except (ValueError, TypeError):
        return _denied(operation, "INVALID_INPUT")
    except Exception:
        return _denied(operation, "REFUSED")


def _dispatch_command(
    command: str, inputs: InstallerInputs, *, backend=None,
    operator_apps_path_adapter=None, operator_apps_shortcut_adapter=None,
) -> dict[str, object]:
    if command == "verify":
        return _command_verify(inputs)
    if command == "status":
        return _command_status(inputs)
    if command == "doctor":
        return _command_doctor(inputs)
    if command == "install":
        return _command_install(
            inputs, backend, operator_apps_path_adapter,
            operator_apps_shortcut_adapter,
        )
    if command == "update":
        return _command_update(
            inputs, backend, operator_apps_path_adapter,
            operator_apps_shortcut_adapter,
        )
    if command == "rollback":
        return _command_rollback(inputs, backend)
    if command == "repair":
        return _command_repair(
            inputs, backend, operator_apps_path_adapter,
            operator_apps_shortcut_adapter,
        )
    if command == "uninstall":
        return _command_uninstall(
            inputs, backend, operator_apps_path_adapter,
            operator_apps_shortcut_adapter,
        )
    if command == "reinstall":
        return _command_reinstall(inputs, backend)
    return _command_reconcile(inputs, backend)


def execute_command(
    command: str, inputs: InstallerInputs, *, backend=None,
    operator_apps_path_adapter=None, operator_apps_shortcut_adapter=None,
    approval_provider=None,
) -> dict[str, object]:
    """Run one canonical command, optionally asking an attended approval owner.

    The additive ``approval_provider`` hook receives the exact canonical request
    object that the existing owner builders already produced. It may return only
    a one-use approval id. The canonical command is then retried with that id,
    and every approval is still consumed by the original owner.
    """
    if command not in COMMANDS:
        return _denied(command, "UNSUPPORTED_COMMAND")
    attempts = 0
    while True:
        try:
            return _dispatch_command(
                command, inputs, backend=backend,
                operator_apps_path_adapter=operator_apps_path_adapter,
                operator_apps_shortcut_adapter=operator_apps_shortcut_adapter,
            )
        except _ApprovalRequired as required:
            if approval_provider is None or attempts >= 8:
                return _denied(
                    command, "OWNER_APPROVAL_REQUIRED",
                    required_approval=required.kind,
                    approval_fingerprint=required.fingerprint,
                )
            attempts += 1
            try:
                approval_id = approval_provider(required.kind, required.request)
            except Exception as error:
                code = getattr(error, "code", None)
                detail = getattr(error, "detail", None)
                if type(code) is str and type(detail) is str:
                    return _denied(
                        command, code, detail=detail,
                        required_approval=required.kind,
                        approval_fingerprint=required.fingerprint,
                    )
                return _denied(
                    command, "OWNER_APPROVAL_UNAVAILABLE",
                    detail="Owner approval ceremony was unavailable.",
                    required_approval=required.kind,
                    approval_fingerprint=required.fingerprint,
                )
            if type(approval_id) is not str or not approval_id.strip():
                return _denied(
                    command, "OWNER_APPROVAL_UNAVAILABLE",
                    required_approval=required.kind,
                    approval_fingerprint=required.fingerprint,
                )
            if required.kind == "code":
                inputs = replace(inputs, code_approval_id=approval_id)
            elif required.kind == "native":
                inputs = replace(inputs, approval_id=approval_id)
            elif required.kind == "operator_apps":
                inputs = replace(inputs, operator_apps_approval_id=approval_id)
            else:
                return _denied(
                    command, "OWNER_APPROVAL_REQUIRED",
                    required_approval=required.kind,
                    approval_fingerprint=required.fingerprint,
                )
        except PlatformInstallationDenied:
            return _denied(command, "DENIED")
        except PermissionError:
            return _denied(command, "DENIED")
        except FileExistsError:
            return _denied(command, "OCCUPIED_TARGET")
        except (FileNotFoundError, NotADirectoryError):
            return _denied(command, "MISSING_INPUT")
        except OSError:
            return _denied(command, "INPUT_UNAVAILABLE")
        except (ValueError, TypeError):
            return _denied(command, "INVALID_INPUT")
        except Exception:
            return _denied(command, "REFUSED")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="platform_installer_cli", description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--release-root", type=Path)
    common.add_argument("--publisher-key", type=Path)
    common.add_argument("--publisher-key-sha256")
    common.add_argument("--publisher-signer")
    common.add_argument("--expected-source-sha")
    common.add_argument("--target", choices=[item.value for item in PlatformReleaseTarget])
    common.add_argument("--minimum-revision", type=int)
    common.add_argument("--destination", type=Path)
    common.add_argument("--identity-home", type=Path)
    common.add_argument("--local-state", type=Path)
    common.add_argument("--safe-state", dest="canonical_safe_state", type=Path)
    common.add_argument("--local-installation-state", dest="store_path", type=Path)
    common.add_argument("--approval-id")
    common.add_argument("--code-approval-id")
    common.add_argument("--previous-destination", type=Path)
    common.add_argument("--staging-candidate", type=Path)
    common.add_argument("--expected-parent-manifest-sha256")
    common.add_argument("--operator-apps", dest="operator_apps_requested",
                        action="store_true")
    common.add_argument("--operator-apps-approval-id")
    common.add_argument("--operator-apps-runtime-python", type=Path)
    common.add_argument("--operator-apps-code-directory", type=Path)
    common.add_argument("--operator-apps-bin-directory", type=Path)
    common.add_argument("--operator-apps-gui-executable", type=Path)
    common.add_argument("--operator-apps-tui-executable", type=Path)
    common.add_argument("--operator-apps-start-menu-directory", type=Path)
    common.add_argument("--operator-apps-desktop-directory", type=Path)
    common.add_argument("--operator-apps-global-bin-directory", type=Path)
    common.add_argument("--operator-apps-approved-root", type=Path,
                        dest="operator_apps_approved_roots", action="append",
                        default=[])
    common.add_argument("--operator-apps-protected-path", type=Path,
                        dest="operator_apps_protected_paths", action="append",
                        default=[])
    common.add_argument("--operator-apps-path-scope",
                        choices=("user", "machine"), default="user")
    common.add_argument("--operator-apps-include-powershell",
                        action="store_true")
    common.add_argument("--operator-apps-desktop-shortcut",
                        action="store_true")
    common.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparsers.add_parser(command, parents=[common])
    return parser


def _inputs(args: argparse.Namespace) -> InstallerInputs:
    return InstallerInputs(
        release_root=args.release_root,
        publisher_key=args.publisher_key,
        publisher_key_sha256=args.publisher_key_sha256,
        publisher_signer=args.publisher_signer,
        expected_source_sha=args.expected_source_sha,
        target=args.target,
        minimum_revision=args.minimum_revision,
        destination=args.destination,
        identity_home=args.identity_home,
        local_state=args.local_state,
        canonical_safe_state=args.canonical_safe_state,
        store_path=args.store_path,
        approval_id=args.approval_id,
        code_approval_id=args.code_approval_id,
        previous_destination=args.previous_destination,
        staging_candidate=args.staging_candidate,
        expected_parent_manifest_sha256=args.expected_parent_manifest_sha256,
        operator_apps_requested=args.operator_apps_requested,
        operator_apps_approval_id=args.operator_apps_approval_id,
        operator_apps_runtime_python=args.operator_apps_runtime_python,
        operator_apps_code_directory=args.operator_apps_code_directory,
        operator_apps_bin_directory=args.operator_apps_bin_directory,
        operator_apps_gui_executable=args.operator_apps_gui_executable,
        operator_apps_tui_executable=args.operator_apps_tui_executable,
        operator_apps_start_menu_directory=args.operator_apps_start_menu_directory,
        operator_apps_desktop_directory=args.operator_apps_desktop_directory,
        operator_apps_global_bin_directory=args.operator_apps_global_bin_directory,
        operator_apps_approved_roots=tuple(args.operator_apps_approved_roots),
        operator_apps_protected_paths=tuple(args.operator_apps_protected_paths),
        operator_apps_path_scope=args.operator_apps_path_scope,
        operator_apps_include_powershell=args.operator_apps_include_powershell,
        operator_apps_desktop_shortcut=args.operator_apps_desktop_shortcut,
    )


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    result = execute_command(args.command, _inputs(args))
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result["outcome"] in SUCCESS_OUTCOMES else 3


if __name__ == "__main__":
    sys.exit(main())
