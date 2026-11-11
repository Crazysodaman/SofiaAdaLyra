"""AG-D011 B1-owned, SAFE-fenced native service transaction coordinator.

The B1 signed installed-release store is the ONLY code installation authority.
This companion tracks exact observed OS-service effects; it does not grant
authority, create a second release store, or activate a Core.

This API is intentionally not wired to PowerShell/Bash or external IPC until
Team A freezes authenticated operation and live enrollment/revocation policy.
Native effects are always protected by an existing exact one-use owner proof.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import stat
from pathlib import Path

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
)
from sofia.platform.ops.platform_installer_native_service import (
    NativeServiceSpecification, signed_native_service_specification,
    DebianSystemdNativeService, WindowsScmNativeService,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.safe.execution_approval import (
    ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
    atomic_write_private_text,
)
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget, PlatformReleaseManifest
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.platform.state.artifact_file import read_artifact_file

_NATIVE_CAPABILITY = "platform.native_service.apply"
_JOURNAL_SCHEMA = "aegis.native-service-transaction.v1"
_JOURNAL_FILE = "native-service-transaction.json"
_OPS = frozenset(("register", "repair", "update", "rollback", "unregister"))


def _public_spec(spec: NativeServiceSpecification) -> dict[str, object]:
    return {
        "platform_id": spec.platform_id,
        "public_key_sha256": spec.public_key_sha256,
        "release_id": spec.release_id,
        "revision": spec.revision,
        "manifest_sha256": spec.manifest_sha256,
        "native_sha256": spec.executable_sha256,
        "service_name": spec.service_name,
        "target": spec.target.value,
    }


def _journal_path(store: PlatformInstallationStore) -> Path:
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical B1 installation store required")
    path = Path(store.path).absolute().parent / _JOURNAL_FILE
    assert_owner_private_path(path.parent, directory=True)
    assert_no_redirected_components(path, include_leaf=True)
    return path


def _load_journal(store: PlatformInstallationStore) -> dict[str, object] | None:
    path = _journal_path(store)
    if not path.exists():
        return None
    assert_owner_private_path(path, directory=False)
    fd = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or not 1 <= before.st_size <= 16000):
            raise PlatformInstallationDenied("native journal unsafe or oversized")
        with os.fdopen(fd, "rb", closefd=False) as reader:
            bytes_read = reader.read(16001)
        after = os.fstat(fd)
        current = os.lstat(path)
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if (len(bytes_read) != before.st_size
                or not stat.S_ISREG(current.st_mode)
                or identity != (after.st_dev, after.st_ino,
                                after.st_size, after.st_mtime_ns)
                or identity != (current.st_dev, current.st_ino,
                                current.st_size, current.st_mtime_ns)):
            raise PlatformInstallationDenied("native transaction journal changed during read")
        raw = loads_strict_model_json(bytes_read.decode("utf-8"))
    finally:
        os.close(fd)
    if (type(raw) is not dict or
            set(raw) != {"schema", "phase", "generation", "current", "last_operation", "last_receipt"}
            or raw["schema"] != _JOURNAL_SCHEMA
            or type(raw["generation"]) is not int or raw["generation"] < 1
            or raw["phase"] not in
            ("PENDING", "OUTCOME_UNKNOWN", "SERVICE_OBSERVED", "REMOVED")):
        raise PlatformInstallationDenied("native journal inconsistent, cannot recover silently")
    return raw


def _record_journal(store: PlatformInstallationStore, state: dict[str, object]) -> None:
    path = _journal_path(store)
    atomic_write_private_text(
        path, json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False),
    )


def _spec(*, store, verifier, expected_target, destination, identity_home, local_state):
    return signed_native_service_specification(
        store=store, verifier=verifier, expected_target=expected_target,
        destination=destination, identity_home=identity_home,
        local_state=local_state,
    )


def review_native_outcome_for_reconciliation(
    *,
    store: PlatformInstallationStore,
    verifier: PlatformReleaseVerifier,
    expected_target: PlatformReleaseTarget,
    destination: Path | str,
    identity_home: Path | str,
    local_state: Path | str,
    backend,
) -> dict[str, object]:
    """Read-only, signed B1 + OS observation of a fenced native outcome.

    This is NEVER an approval, a journal-clearing action or an authenticated
    RUN/READY proof. A pending/unknown OS result remains fenced, even when
    the native driver sees a matching process. Only an independent attended
    recovery workflow may later resolve it.
    """
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical B1 installation store required")
    if not isinstance(verifier, PlatformReleaseVerifier):
        raise TypeError("configured independently trusted release verifier required")
    if not isinstance(expected_target, PlatformReleaseTarget):
        raise TypeError("typed native release target required")
    driver_type = (
        WindowsScmNativeService if expected_target is PlatformReleaseTarget.WINDOWS_X86_64
        else DebianSystemdNativeService
    )
    if type(backend) is not driver_type:
        raise PlatformInstallationDenied("read-only native observer must match reviewed OS")
    if (type(backend) is DebianSystemdNativeService
            and backend.unit_path != Path("/etc/systemd/system/aegis-platform.service")):
        raise PlatformInstallationDenied("unapproved systemd unit observation target")
    before = _load_journal(store)
    signed = _spec(
        store=store, verifier=verifier, expected_target=expected_target,
        destination=destination, identity_home=identity_home,
        local_state=local_state,
    )
    signed_ref = _public_spec(signed)
    process_state = "UNKNOWN"
    observation = "UNAVAILABLE"
    same_signed_identity = False
    try:
        result = backend.observe(signed)
        if (type(result) is dict
                and result.get("schema") == "aegis.native-service-receipt.v1"
                and result.get("platform_id") == signed.platform_id
                and result.get("release_manifest_sha256") == signed.manifest_sha256
                and result.get("core_activated") is False
                and result.get("service_health") == "UNKNOWN"
                and result.get("process_state") in ("RUNNING", "NOT_RUNNING")):
            process_state = result["process_state"]
            same_signed_identity = True
            observation = "SIGNED_OS_CONFIG_OBSERVED"
        else:
            observation = "MISMATCHED_NATIVE_OBSERVATION"
    except (OSError, ValueError, RuntimeError, PermissionError):
        # A missing, foreign, stopped or unreadable unit is NOT proof that
        # the previous OS effect did or did not happen. Leave the fence.
        observation = "UNAVAILABLE"
    after = _load_journal(store)
    if before != after:
        raise PlatformInstallationDenied(
            "native journal changed during read-only recovery observation"
        )
    # Signed release bytes and protected installation identity must remain
    # stable across the observer as well. A racing release replacement is
    # never promoted into recovery evidence.
    checked = _spec(
        store=store, verifier=verifier, expected_target=expected_target,
        destination=destination, identity_home=identity_home,
        local_state=local_state,
    )
    if _public_spec(checked) != signed_ref:
        raise PlatformInstallationDenied(
            "signed B1 release changed during native recovery observation"
        )
    phase = "ABSENT" if before is None else before["phase"]
    unresolved = phase in ("PENDING", "OUTCOME_UNKNOWN")
    recorded = None if before is None else before["current"]
    return {
        "schema": "aegis.native-service-recovery-review.v1",
        "result": "RECONCILIATION_REQUIRED" if unresolved
            else "READ_ONLY_OS_OBSERVATION",
        "journal_phase": phase,
        "journal_generation": 0 if before is None else before["generation"],
        "last_operation": None if before is None else before["last_operation"],
        "signed_platform_id": signed.platform_id,
        "signed_release_manifest_sha256": signed.manifest_sha256,
        "recorded_service_matches_signed_release": recorded == signed_ref,
        "native_observation": observation,
        "observed_service_matches_signed_release": same_signed_identity,
        "process_state": process_state,
        "service_health": "UNKNOWN",
        "owner_approval_verified": False,
        "publisher_revocation_current_verified": False,
        "authenticated_platform_ready_verified": False,
        "journal_reconciled": False,
        "journal_mutated": False,
        "native_service_mutated": False,
        "core_activated": False,
        "fleet_enrolled": False,
    }


def native_service_operation_request(
    *,
    operation: str,
    store: PlatformInstallationStore,
    verifier: PlatformReleaseVerifier,
    expected_target: PlatformReleaseTarget,
    destination: Path | str,
    identity_home: Path | str,
    local_state: Path | str,
    canonical_safe_state: Path | str,
    previous_destination: Path | str | None = None,
) -> dict[str, object]:
    """Verify installed signed code + B1 checkpoint + native journal before approval."""
    if operation not in _OPS:
        raise PlatformInstallationDenied("unsupported native lifecycle operation")
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("B1 store required")
    if store.pending_attempts():
        raise PlatformInstallationDenied("unreconciled B1 attempt blocks native execution")
    current = _spec(
        store=store, verifier=verifier, expected_target=expected_target,
        destination=destination, identity_home=identity_home,
        local_state=local_state,
    )
    prev = None
    if operation in ("update", "rollback"):
        if previous_destination is None:
            raise PlatformInstallationDenied("exact current B1 release required")
        prev = _spec(
            store=store, verifier=verifier, expected_target=expected_target,
            destination=previous_destination, identity_home=identity_home,
            local_state=local_state,
        )
        if (current.platform_id != prev.platform_id
                or current.public_key_sha256 != prev.public_key_sha256):
            raise PlatformInstallationDenied("native release change cannot alter Platform identity")
        if operation == "update":
            if current.revision <= prev.revision:
                raise PlatformInstallationDenied("native update must advance signed revision")
        else:
            history = store.history()
            if (current.revision >= prev.revision or not any(
                item["release_id"] == current.release_id
                and item["manifest_sha256"] == current.manifest_sha256
                and item["result"] == "SUCCEEDED" for item in history
            )):
                raise PlatformInstallationDenied("rollback needs previously verified signed bytes")
    if operation == "update":
        # B1 confirms signature/bytes; the native swap also requires the
        # candidate to be a signed direct successor of the active release.
        manifest_path = Path(destination).absolute() / "release-manifest.json"
        size = manifest_path.stat(follow_symlinks=False).st_size
        if size > 131072:
            raise PlatformInstallationDenied("signed update manifest oversized")
        candidate_manifest = PlatformReleaseManifest.from_payload(
            loads_strict_model_json(read_artifact_file(
                manifest_path, size, include_data=True,
            )[1].decode("utf-8"))
        )
        if (candidate_manifest.digest != current.manifest_sha256
                or candidate_manifest.parent_manifest_sha256 != prev.manifest_sha256):
            raise PlatformInstallationDenied("update candidate has wrong signed predecessor")
    elif previous_destination is not None:
        raise PlatformInstallationDenied("unexpected previous release path")
    safe = Path(canonical_safe_state).absolute()
    assert_no_redirected_components(safe, include_leaf=True)
    journal = _load_journal(store)
    if journal is not None and journal["phase"] in ("PENDING", "OUTCOME_UNKNOWN"):
        raise PlatformInstallationDenied("unresolved native outcome requires reconciliation")
    registered = journal["current"] if journal else None
    if operation == "register":
        if registered is not None:
            raise PlatformInstallationDenied("existing registered service cannot be adopted")
    elif operation in ("repair", "unregister"):
        if registered != _public_spec(current):
            raise PlatformInstallationDenied("service is not owned by exact signed B1 release")
    else:
        if registered != _public_spec(prev):
            raise PlatformInstallationDenied("previous native service release identity mismatch")
    checkpoint = store.checkpoint()
    # A B1-signed historical release may be eligible only for an explicitly
    # approved rollback of an already owned native service. Ordinary first
    # registration/update must never bypass the durable revision floor.
    floor = 0 if checkpoint is None else checkpoint.minimum_accepted_revision
    if operation in ("register", "update") and current.revision < floor:
        raise PlatformInstallationDenied(
            "native registration/update below B1 signed revision floor")
    if operation == "register" and checkpoint is not None and checkpoint.active_release_id is not None:
        raise PlatformInstallationDenied(
            "existing activated B1 release requires explicit reconciliation")
    # Native target is a protected approval parameter, not a caller chosen
    # arbitrary service name or service-unit path.
    native_target = (
        "AegisPlatform" if expected_target is PlatformReleaseTarget.WINDOWS_X86_64
        else "/etc/systemd/system/aegis-platform.service"
    )
    params = {
        "operation": operation,
        "native_target": native_target,
        "candidate": _public_spec(current),
        "previous": _public_spec(prev) if prev is not None else None,
        "identity_home": str(Path(identity_home).absolute()),
        "local_state": str(Path(local_state).absolute()),
        "canonical_safe_state": str(safe),
        "destination": str(Path(destination).absolute()),
        "previous_destination": None if previous_destination is None
            else str(Path(previous_destination).absolute()),
        "b1_generation": 0 if checkpoint is None else checkpoint.generation,
        "b1_revision_floor": 0 if checkpoint is None else checkpoint.minimum_accepted_revision,
        "native_generation": 0 if journal is None else journal["generation"],
        "native_phase": "ABSENT" if journal is None else journal["phase"],
    }
    return {
        "schema": "aegis.native-service-request.v1",
        "capability": _NATIVE_CAPABILITY,
        "parameters": params,
        "fingerprint": execution_fingerprint(_NATIVE_CAPABILITY, params),
        "owner_approved": False,
        "executed": False,
    }


def apply_owner_approved_native_service(
    *,
    operation: str,
    approval_id: str,
    store: PlatformInstallationStore,
    verifier: PlatformReleaseVerifier,
    expected_target: PlatformReleaseTarget,
    destination: Path | str,
    identity_home: Path | str,
    local_state: Path | str,
    canonical_safe_state: Path | str,
    backend,
    previous_destination: Path | str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """One owner proof + one OS operation; record outcomes before/after effects.

    Real-time enrollment/revocation during an in-flight native OS call needs
    Team A's yet-to-be-frozen service boundary. A changed STOP after an OS
    effect causes OUTCOME_UNKNOWN, never a successful service-health claim.
    """
    if not isinstance(approval_id, str) or not approval_id.strip():
        raise PlatformInstallationDenied("native OS mutation requires scoped owner approval")
    if type(operation) is not str or operation not in _OPS:
        raise PlatformInstallationDenied("unknown native OS operation")
    if type(backend) not in (DebianSystemdNativeService, WindowsScmNativeService):
        raise PlatformInstallationDenied("only reviewed native OS driver is permitted")
    expected_driver = (WindowsScmNativeService if expected_target is PlatformReleaseTarget.WINDOWS_X86_64
                       else DebianSystemdNativeService)
    if type(backend) is not expected_driver:
        raise PlatformInstallationDenied("native driver and signed OS target differ")
    if (type(backend) is DebianSystemdNativeService
            and backend.unit_path != Path("/etc/systemd/system/aegis-platform.service")):
        raise PlatformInstallationDenied("unapproved systemd unit target refused")
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("timezone aware authorization time required")
    safe = Path(canonical_safe_state).absolute()
    with StateProcessLock(store.path, resource="aegis-native-install",
                          lock_directory=Path(store.path).absolute().parent):
        if OperatorStopStore(safe).current().active:
            raise PlatformInstallationDenied("STOP engaged, native operation denied")
        expected = native_service_operation_request(
            operation=operation, store=store, verifier=verifier,
            expected_target=expected_target, destination=destination,
            identity_home=identity_home, local_state=local_state,
            canonical_safe_state=safe, previous_destination=previous_destination,
        )
        # SAFE consumption provides current proof, expiration, credential
        # revocation and one-use exact action binding. No --yes/flag shortcut.
        ExecutionApprovalVerifier(safe).consume(
            approval_id=approval_id, capability=expected["capability"],
            parameters=expected["parameters"], now=moment,
        )
        if OperatorStopStore(safe).current().active:
            raise PlatformInstallationDenied("STOP engaged after approval consumption")
        observed = native_service_operation_request(
            operation=operation, store=store, verifier=verifier,
            expected_target=expected_target, destination=destination,
            identity_home=identity_home, local_state=local_state,
            canonical_safe_state=safe, previous_destination=previous_destination,
        )
        if observed["fingerprint"] != expected["fingerprint"]:
            raise PlatformInstallationDenied("B1 native service plan changed before execution")
        candidate = _spec(
            store=store, verifier=verifier, expected_target=expected_target,
            destination=destination, identity_home=identity_home,
            local_state=local_state,
        )
        previous = None if previous_destination is None else _spec(
            store=store, verifier=verifier, expected_target=expected_target,
            destination=previous_destination, identity_home=identity_home,
            local_state=local_state,
        )
        previous_journal = _load_journal(store)
        generation = 1 if previous_journal is None else previous_journal["generation"] + 1
        base = {
            "schema": _JOURNAL_SCHEMA, "phase": "PENDING",
            "generation": generation,
            "current": None if previous_journal is None else previous_journal["current"],
            "last_operation": operation, "last_receipt": None,
        }
        _record_journal(store, base)
        try:
            if operation == "register":
                result = backend.register(candidate)
                selected = _public_spec(candidate)
            elif operation == "unregister":
                result = backend.stop_and_unregister(candidate)
                selected = None
            elif operation == "repair":
                result = backend.restart_verified(candidate)
                selected = _public_spec(candidate)
            elif operation in ("update", "rollback"):
                result = backend.replace_verified(previous, candidate)
                selected = _public_spec(candidate)
            else:
                raise AssertionError("unsupported operation reached effect boundary")
            if not isinstance(result, dict) or result.get("schema") != "aegis.native-service-receipt.v1":
                raise RuntimeError("native OS adapter returned no canonical receipt")
            if result.get("core_activated") is not False:
                raise PlatformInstallationDenied(
                    "native Platform service receipt must remain Core-free"
                )
            if (result.get("platform_id") != candidate.platform_id
                    or result.get("release_manifest_sha256") != candidate.manifest_sha256
                    or result.get("service_health") != "UNKNOWN"):
                raise PlatformInstallationDenied(
                    "native receipt differs from signed installed Platform identity or release"
                )
            if not ExecutionApprovalVerifier(safe).consumed_owner_proof_remains_current(
                approval_id=approval_id, capability=expected["capability"],
                parameters=expected["parameters"],
            ):
                raise PlatformInstallationDenied(
                    "owner authentication revoked during native operation"
                )
            if OperatorStopStore(safe).current().active:
                raise PlatformInstallationDenied("STOP changed during native operation")
            verified_identity = _spec(
                store=store, verifier=verifier, expected_target=expected_target,
                destination=destination, identity_home=identity_home, local_state=local_state,
            )
            if verified_identity.platform_id != candidate.platform_id:
                raise PlatformInstallationDenied("Platform identity changed during native operation")
            if result.get("service") != candidate.service_name or (
                result.get("process_state") not in
                ("RUNNING", "REMOVED")
            ):
                raise RuntimeError("native OS effect not observed as requested")
            if operation == "unregister" and result["process_state"] != "REMOVED":
                raise RuntimeError("unregister did not remove native service")
            if operation != "unregister" and result["process_state"] != "RUNNING":
                raise RuntimeError("native service did not reach running")
            state = {**base, "phase": "REMOVED" if selected is None else "SERVICE_OBSERVED",
                     "current": selected, "last_receipt": {
                         **result,
                         "signed_release_verified": True,
                         "owner_approval_consumed": True,
                         "full_health_certified": False,
                         "protected_identity_retained": True,
                     }}
            # Exact approval can be revoked while the release verifier and
            # native receipt are being reconciled. Check again at the
            # successful journal boundary, never after claiming success.
            if (OperatorStopStore(safe).current().active
                    or not ExecutionApprovalVerifier(safe).consumed_owner_proof_remains_current(
                        approval_id=approval_id, capability=expected["capability"],
                        parameters=expected["parameters"],
                    )):
                raise PlatformInstallationDenied(
                    "owner STOP or authentication changed before native receipt commit"
                )
            _record_journal(store, state)
            return state["last_receipt"]
        except BaseException:
            # Do not auto-rollback or try another service action with consumed
            # proof. Exact native OS reconciliation required by an operator.
            _record_journal(store, {**base, "phase": "OUTCOME_UNKNOWN"})
            raise
