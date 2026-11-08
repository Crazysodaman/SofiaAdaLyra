"""IG-001 internal read-only service pin REVIEW, not a native owner grant.

Uses a genuine AF_UNIX inode but mocked installed B1/RUN metadata. A live
signed host, canonical Team A current SAFE grant and Team C native client
remain separate required integration acceptance.
"""
from __future__ import annotations

from datetime import datetime, timezone
import grp
import os
from pathlib import Path
import pwd
import socket
from types import SimpleNamespace

import pytest

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
)
from sofia.platform.ops.platform_release import PlatformReleaseVerifier
from sofia.platform.ops.platform_installer_native_profile import (
    review_private_installed_linux_service,
)
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.test_ops_platform_installer_native_service import native_spec

pytestmark = [
    pytest.mark.pkg_ops,
    pytest.mark.skipif(os.name == "nt", reason="real AF_UNIX kernel socket fixture"),
]


@pytest.fixture
def installed_private_pins(tmp_path, native_spec, monkeypatch):
    import sofia.platform.ops.platform_installer_native_profile as mod
    import sofia.platform.ops.platform_installer_bundle as bundle

    home = tmp_path / "runtime"
    home.mkdir(mode=0o700)
    path = home / "mgmt-7.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    path.chmod(0o600)
    monkeypatch.setattr(mod, "_RUNTIME_PATH", home)
    monkeypatch.setattr(
        bundle, "host_release_target",
        lambda: PlatformReleaseTarget.DEBIAN12_X86_64,
    )
    monkeypatch.setattr(mod, "signed_native_service_specification", lambda **_kw: native_spec)
    monkeypatch.setattr(mod, "DebianSystemdNativeService", lambda: SimpleNamespace(
        _require_service_identity=lambda spec: None,
        observe=lambda spec: {
            "process_state": "RUNNING", "process_id": 50127,
        },
    ))
    monkeypatch.setattr(mod, "LocalRunLeaseStore", lambda *_a, **_kw: SimpleNamespace(
        current=lambda *, now: SimpleNamespace(epoch=7, owner_id="platform-run"),
    ))
    monkeypatch.setattr(mod, "OperatorStopStore", lambda *_a, **_kw: SimpleNamespace(
        current=lambda: SimpleNamespace(active=False),
    ))
    monkeypatch.setattr(pwd, "getpwnam", lambda _: SimpleNamespace(
        pw_uid=os.geteuid(), pw_gid=os.getegid(),
    ))
    monkeypatch.setattr(grp, "getgrnam", lambda _: SimpleNamespace(
        gr_gid=os.getegid(),
    ))
    store = PlatformInstallationStore(tmp_path / "b1.db")
    verifier = object.__new__(PlatformReleaseVerifier)
    args = dict(
        store=store, verifier=verifier,
        destination=native_spec.executable.parent.parent,
        identity_home=native_spec.identity_home,
        local_state=native_spec.local_state,
        now=datetime.now(timezone.utc),
    )
    try:
        yield args, path, listener, mod
    finally:
        listener.close()


def test_private_profile_uses_live_kernel_inode_and_never_grants_operator(
        installed_private_pins):
    args, path, listener, _mod = installed_private_pins
    value = review_private_installed_linux_service(**args)
    assert value["source"] == "SIGNED_B1_PLUS_OS_OBSERVATION"
    assert value["socket_path"] == str(path)
    assert value["socket_inode"] == path.stat().st_ino
    assert value["socket_dev"] == path.stat().st_dev
    assert value["generation"] == 7
    assert value["platform_id"]
    assert value["service_uid"] == os.geteuid()
    assert value["service_primary_gid"] == os.getegid()
    assert value["socket_group_gid"] is None
    assert value["supervisor_pid_observed"] == 50127
    # Rust supervisor PID != kernel peer PID of A's Python AF_UNIX listener.
    assert value["service_pid"] is None
    for key in (
        "safe_owner_grant_verified", "external_operator_enrollment_verified",
        "publisher_revocation_current_verified",
        "authenticated_platform_ready_verified",
        "external_tui_activation_approved",
        "service_mutated", "core_activated",
    ):
        assert value[key] is False


@pytest.mark.parametrize("failure", (
    "group-readable-socket", "nonprivate-parent", "stale-generation",
    "STOP", "not-running", "changed-supervisor",
))
def test_private_profile_never_adopts_unsafe_or_stale_operator_endpoints(
        installed_private_pins, monkeypatch, failure):
    args, path, listener, mod = installed_private_pins
    if failure == "group-readable-socket":
        path.chmod(0o660)
    elif failure == "nonprivate-parent":
        path.parent.chmod(0o750)
    elif failure == "stale-generation":
        monkeypatch.setattr(mod, "LocalRunLeaseStore", lambda *_a, **_kw: SimpleNamespace(
            current=lambda *, now: None,
        ))
    elif failure == "STOP":
        monkeypatch.setattr(mod, "OperatorStopStore", lambda *_a, **_kw: SimpleNamespace(
            current=lambda: SimpleNamespace(active=True),
        ))
    elif failure == "not-running":
        monkeypatch.setattr(mod, "DebianSystemdNativeService", lambda: SimpleNamespace(
            _require_service_identity=lambda spec: None,
            observe=lambda spec: {"process_state": "NOT_RUNNING", "process_id": None},
        ))
    elif failure == "changed-supervisor":
        calls = iter((50127, 50128))
        monkeypatch.setattr(mod, "DebianSystemdNativeService", lambda: SimpleNamespace(
            _require_service_identity=lambda spec: None,
            observe=lambda spec: {
                "process_state": "RUNNING", "process_id": next(calls),
            },
        ))
    with pytest.raises(PlatformInstallationDenied):
        review_private_installed_linux_service(**args)
