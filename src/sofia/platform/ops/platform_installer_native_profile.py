"""IG-001: read-only B1 provenance + live private Unix endpoint pin review.

This returns an independently CHECKABLE candidate, not a new signed
profile document, owner enrollment or external operator grant. Only Team A
can establish current SAFE/STOP/revocation and authenticated platform.status.
No shell/GUI/TUI can turn this preview into an authorization capability.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

# Linux-only NSS interfaces must never break Windows test collection.
if os.name == "posix":
    import grp
    import pwd
import stat

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
)
from sofia.platform.ops.platform_installer_native_service import (
    DebianSystemdNativeService, signed_native_service_specification,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.run.lease import LocalRunLeaseStore
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.platform_release import PlatformReleaseTarget

_RUNTIME_PATH = Path("/run/aegis-platform")
_MAX_GENERATION = 9_007_199_254_740_991


def review_private_installed_linux_service(
    *, store: PlatformInstallationStore, verifier: PlatformReleaseVerifier,
    destination: Path | str, identity_home: Path | str,
    local_state: Path | str, now: datetime | None = None,
) -> dict[str, object]:
    """Review one current B1 signed private service and its kernel socket.

    Assumes an OS host executor with local read permission and trusted B1
    verifier rooted in an independently provisioned approved public key.
    This is deliberately not an externally signed profile or a sufficient
    Team C native login token; Team A must independently validate the caller.
    """
    from sofia.platform.ops.platform_installer_bundle import host_release_target

    if os.name != "posix" or host_release_target() is not PlatformReleaseTarget.DEBIAN12_X86_64:
        raise PlatformInstallationDenied("installed-service profile requires real Debian12 host")
    if not isinstance(store, PlatformInstallationStore):
        raise TypeError("canonical B1 installation store required")
    if not isinstance(verifier, PlatformReleaseVerifier):
        raise TypeError("existing canonical publisher verifier required")
    moment = datetime.now(timezone.utc) if now is None else now
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("timezone-aware observation required")
    spec = signed_native_service_specification(
        store=store, verifier=verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        destination=destination, identity_home=identity_home,
        local_state=local_state,
    )
    driver = DebianSystemdNativeService()
    driver._require_service_identity(spec)
    observed = driver.observe(spec)
    if observed.get("process_state") != "RUNNING":
        raise PlatformInstallationDenied("native systemd process is not running")
    if OperatorStopStore(spec.local_state).current().active:
        raise PlatformInstallationDenied("STOP engaged, no current native operator pins")
    service_user = pwd.getpwnam("aegis")
    service_group = grp.getgrnam("aegis")
    if service_user.pw_gid != service_group.gr_gid:
        raise PlatformInstallationDenied("installed service UID/primary GID mismatch")
    run_store = LocalRunLeaseStore(spec.local_state, lease_key="platform-service")
    lease = run_store.current(now=moment)
    if lease is None or not 1 <= lease.epoch <= _MAX_GENERATION:
        raise PlatformInstallationDenied("no live canonical RUN generation")
    root = _RUNTIME_PATH
    socket_path = root / ("mgmt-" + str(lease.epoch) + ".sock")
    for path in (root, socket_path):
        assert_no_redirected_components(path, include_leaf=True)
    runtime = root.stat(follow_symlinks=False)
    endpoint = socket_path.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(runtime.st_mode)
            or stat.S_IMODE(runtime.st_mode) != 0o700
            or runtime.st_uid != service_user.pw_uid
            or runtime.st_gid != service_group.gr_gid
            or not stat.S_ISSOCK(endpoint.st_mode)
            or stat.S_IMODE(endpoint.st_mode) != 0o600
            or endpoint.st_uid != service_user.pw_uid
            or endpoint.st_gid != service_group.gr_gid):
        raise PlatformInstallationDenied(
            "private native endpoint ownership, mode or inode origin mismatch"
        )
    # Recheck the live lease, exact native unit, and socket inode after the
    # read-only OS observations. A racing restart never becomes a silent
    # source for C's current service identity.
    check = run_store.current(now=moment)
    second = driver.observe(spec)
    after = socket_path.stat(follow_symlinks=False)
    if (check is None or check.epoch != lease.epoch
            or check.owner_id != lease.owner_id
            or second.get("process_state") != "RUNNING"
            or second.get("process_id") != observed.get("process_id")
            or (after.st_dev, after.st_ino) != (endpoint.st_dev, endpoint.st_ino)
            or OperatorStopStore(spec.local_state).current().active):
        raise PlatformInstallationDenied("native service changed during signed B1 review")
    return {
        "schema": "aegis.platform.installed-private-operator-source.v1",
        "source": "SIGNED_B1_PLUS_OS_OBSERVATION",
        "platform_id": spec.platform_id,
        "platform_public_key_sha256": spec.public_key_sha256,
        "release_id": spec.release_id,
        "release_manifest_sha256": spec.manifest_sha256,
        "service_binary_sha256": spec.executable_sha256,
        "generation": lease.epoch,
        "socket_path": str(socket_path),
        "socket_dev": endpoint.st_dev,
        "socket_inode": endpoint.st_ino,
        "service_uid": service_user.pw_uid,
        "service_primary_gid": service_group.gr_gid,
        "socket_group_gid": None,
        # systemctl MainPID is the Rust supervisor, not the Python AF_UNIX
        # peer PID. Never falsely bind SO_PEERCRED to that different process.
        "service_pid": None,
        "supervisor_pid_observed": observed.get("process_id"),
        "socket_parent_mode": "0700",
        "socket_mode": "0600",
        "private_service_owned_endpoint": True,
        "external_operator_enrollment_verified": False,
        "safe_owner_grant_verified": False,
        "publisher_revocation_current_verified": False,
        "authenticated_platform_ready_verified": False,
        "external_tui_activation_approved": False,
        "service_mutated": False,
        "core_activated": False,
    }
