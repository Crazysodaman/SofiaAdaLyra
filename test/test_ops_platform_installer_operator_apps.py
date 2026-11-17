"""Owner-approved installed-host launcher, PATH and shortcut plan tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.ops.platform_installer_operator_apps import (
    InMemoryPathAdapter, OperatorAppsApprovalRequired, OperatorAppsConfiguration,
    OperatorAppsDenied, OWNERSHIP_MARKER, apply_owner_approved_operator_apps,
    build_operator_apps_plan, operator_apps_request,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier,
)
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.owner_auth_fixture import record_verified_owner_approval

pytestmark = pytest.mark.pkg_ops
WINDOWS = PlatformReleaseTarget.WINDOWS_X86_64
DEBIAN = PlatformReleaseTarget.DEBIAN12_X86_64


class FakeShortcuts:
    def __init__(self) -> None:
        self.created = []
        self.removed = []

    def create(self, spec) -> None:
        self.created.append(spec)
        spec.path.parent.mkdir(parents=True, exist_ok=True)
        spec.path.write_bytes(b"mock-shortcut")

    def remove(self, spec) -> None:
        self.removed.append(spec)
        spec.path.unlink(missing_ok=True)


def _approve(store_path, request, approval_id):
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=approval_id,
        capability=request["capability"],
        request_fingerprint=request["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(store_path), approval,
    )
    return approval_id


@pytest.fixture
def windows_scope(tmp_path, canonical_state_path):
    runtime = tmp_path / "runtime/python.exe"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"installed-runtime")
    code = tmp_path / "code"
    code.mkdir()
    gui = tmp_path / "gui/aegis-control-center.exe"
    gui.parent.mkdir()
    gui.write_bytes(b"installed-gui")
    tui = tmp_path / "gui/aegis_tui.exe"
    tui.write_bytes(b"installed-tui")
    identity = tmp_path / "identity/identity.json"
    identity.parent.mkdir()
    identity.write_text("identity", encoding="utf-8")
    local_state = tmp_path / "state/platform.db"
    local_state.parent.mkdir()
    local_state.write_text("platform", encoding="utf-8")
    config = OperatorAppsConfiguration(
        target=WINDOWS,
        runtime_python=runtime,
        code_directory=code,
        bin_directory=tmp_path / "bin",
        gui_executable=gui,
        tui_executable=tui,
        start_menu_directory=tmp_path / "Start Menu/Programs/Aegis",
        desktop_directory=tmp_path / "Desktop",
        approved_roots=(tmp_path,),
        protected_paths=(identity, local_state, canonical_state_path),
        include_powershell=True,
        include_desktop_shortcut=True,
    )
    store = PlatformInstallationStore(tmp_path / "b1/install.db")
    return SimpleNamespace(
        tmp_path=tmp_path, config=config, store=store,
        safe=canonical_state_path, paths=InMemoryPathAdapter(value=r"C:\Windows;C:\Tools"),
        shortcuts=FakeShortcuts(), identity=identity, local_state=local_state,
    )


def _apply(scope, operation, *, approval_id="approval:operator-apps"):
    request = operator_apps_request(operation, scope.config)
    _approve(scope.safe, request, approval_id)
    return apply_owner_approved_operator_apps(
        approval_id=approval_id, operation=operation, config=scope.config,
        state_path=scope.safe, store=scope.store, path_adapter=scope.paths,
        shortcut_adapter=scope.shortcuts,
    )


def test_windows_fresh_install_creates_owned_shim_path_and_shortcuts(windows_scope):
    receipt = _apply(windows_scope, "install")
    assert receipt["outcome"] == "SUCCEEDED"
    assert receipt["core_activated"] is False
    assert receipt["protected_state_touched"] is False
    shim = windows_scope.tmp_path / "bin/aegis.cmd"
    content = shim.read_text(encoding="utf-8")
    assert OWNERSHIP_MARKER in content
    runtime_sha = sha256(b"installed-runtime").hexdigest()
    assert f"AEGIS_SOURCE_SHA256={runtime_sha}" in content
    assert "AEGIS_TARGET_SHA256=" in content
    assert '"%*"' not in content and "%*" in content
    assert (windows_scope.tmp_path / "bin/aegis.ps1").is_file()
    assert str(windows_scope.tmp_path / "bin") in windows_scope.paths.value
    assert windows_scope.paths.value.count(str(windows_scope.tmp_path / "bin")) == 1
    assert len(windows_scope.shortcuts.created) == 2
    for spec in windows_scope.shortcuts.created:
        sidecar = json.loads(spec.sidecar.read_text(encoding="utf-8"))
        assert sidecar["ownership_marker"] == OWNERSHIP_MARKER
        assert sidecar["source_sha256"] and sidecar["target_sha256"]
        assert sidecar["link_sha256"]
    assert receipt["path_action"]["action"] == "ADD"
    assert {item["action"] for item in receipt["shortcut_actions"]} == {"CREATE"}
    durable = json.loads(
        (windows_scope.tmp_path / "b1/operator-apps-receipt.json").read_text(
            encoding="utf-8")
    )
    assert durable["plan_digest"] == receipt["plan_digest"]
    assert durable["outcome"] == "SUCCEEDED"


def test_idempotent_reinstall_does_not_duplicate_path_or_shortcuts(windows_scope):
    _apply(windows_scope, "install", approval_id="approval:first")
    created = len(windows_scope.shortcuts.created)
    receipt = _apply(windows_scope, "install", approval_id="approval:second")
    assert receipt["outcome"] == "SUCCEEDED"
    assert receipt["path_action"]["action"] == "NO_CHANGE"
    assert {item["action"] for item in receipt["shortcut_actions"]} == {"NO_CHANGE"}
    assert len(windows_scope.shortcuts.created) == created
    assert windows_scope.paths.value.count(str(windows_scope.tmp_path / "bin")) == 1


def test_foreign_launcher_is_refused_without_overwrite(windows_scope):
    foreign = windows_scope.tmp_path / "bin/aegis.cmd"
    foreign.parent.mkdir()
    foreign.write_text("foreign launcher", encoding="utf-8")
    with pytest.raises(OperatorAppsDenied):
        _apply(windows_scope, "install")
    assert foreign.read_text(encoding="utf-8") == "foreign launcher"
    assert windows_scope.shortcuts.created == []
    assert windows_scope.paths.value == r"C:\Windows;C:\Tools"
    receipt = json.loads(
        (windows_scope.tmp_path / "b1/operator-apps-receipt.json").read_text(
            encoding="utf-8")
    )
    assert receipt["outcome"] == "FAILED"


def test_symlinked_launcher_target_is_refused(windows_scope):
    target = windows_scope.tmp_path / "outside.cmd"
    target.write_text("outside", encoding="utf-8")
    link = windows_scope.tmp_path / "bin/aegis.cmd"
    link.parent.mkdir()
    try:
        link.symlink_to(target)
    except OSError as exc:
        if getattr(exc, "winerror", None) != 1314:
            raise
        pytest.skip("symlink creation privilege unavailable")
    with pytest.raises(OperatorAppsDenied):
        _apply(windows_scope, "install")
    assert target.read_text(encoding="utf-8") == "outside"
    assert windows_scope.shortcuts.created == []


def test_uninstall_preserves_protected_state_and_foreign_path_entries(windows_scope):
    identity_before = windows_scope.identity.read_bytes()
    state_before = windows_scope.local_state.read_bytes()
    _apply(windows_scope, "install", approval_id="approval:install")
    windows_scope.paths.value += r";C:\Foreign"
    receipt = _apply(windows_scope, "uninstall", approval_id="approval:uninstall")
    assert receipt["outcome"] == "SUCCEEDED"
    assert receipt["path_action"]["action"] == "REMOVE"
    assert windows_scope.paths.value == r"C:\Windows;C:\Tools;C:\Foreign"
    assert not (windows_scope.tmp_path / "bin/aegis.cmd").exists()
    assert not (windows_scope.tmp_path / "bin/aegis.ps1").exists()
    assert windows_scope.shortcuts.created
    assert len(windows_scope.shortcuts.removed) == 2
    assert windows_scope.identity.read_bytes() == identity_before
    assert windows_scope.local_state.read_bytes() == state_before


def test_repair_recreates_owned_launcher(windows_scope):
    _apply(windows_scope, "install", approval_id="approval:install")
    shim = windows_scope.tmp_path / "bin/aegis.cmd"
    shim.unlink()
    receipt = _apply(windows_scope, "repair", approval_id="approval:repair")
    assert receipt["outcome"] == "SUCCEEDED"
    assert shim.is_file()
    assert OWNERSHIP_MARKER in shim.read_text(encoding="utf-8")


def test_missing_operator_apps_approval_has_no_effect(windows_scope):
    with pytest.raises(OperatorAppsApprovalRequired):
        apply_owner_approved_operator_apps(
            approval_id=None, operation="install", config=windows_scope.config,
            state_path=windows_scope.safe, store=windows_scope.store,
            path_adapter=windows_scope.paths,
            shortcut_adapter=windows_scope.shortcuts,
        )
    assert not (windows_scope.tmp_path / "bin").exists()
    assert windows_scope.shortcuts.created == []
    assert windows_scope.paths.value == r"C:\Windows;C:\Tools"


def test_competing_foreign_launcher_is_refused_before_approval(windows_scope):
    competing = windows_scope.tmp_path / "bin/aegis.exe"
    competing.parent.mkdir()
    competing.write_bytes(b"foreign exe")
    with pytest.raises(OperatorAppsDenied):
        operator_apps_request("install", windows_scope.config)
    assert competing.read_bytes() == b"foreign exe"


def test_plan_is_deterministic_and_binds_exact_hashes(windows_scope):
    first = build_operator_apps_plan(windows_scope.config)
    second = build_operator_apps_plan(windows_scope.config)
    assert first["plan_digest"] == second["plan_digest"]
    for item in first["files"]:
        assert item["ownership_marker"] == OWNERSHIP_MARKER
        assert len(item["source_sha256"]) == 64
        assert len(item["target_sha256"]) == 64
        assert len(item["content_sha256"]) == 64
    assert first["applications"]["gui"]["sha256"] == sha256(b"installed-gui").hexdigest()


def test_debian_plan_builds_owned_scripts_and_desktop_entry(tmp_path):
    runtime = tmp_path / "runtime/python/bin/python3.12"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"debian-runtime")
    code = tmp_path / "opt/aegis/release"
    code.mkdir(parents=True)
    gui = tmp_path / "opt/aegis/bin/aegis-control-center"
    gui.parent.mkdir(parents=True)
    gui.write_bytes(b"debian-gui")
    config = OperatorAppsConfiguration(
        target=DEBIAN,
        runtime_python=runtime,
        code_directory=code,
        bin_directory=tmp_path / "opt/aegis/bin",
        gui_executable=gui,
        global_bin_directory=tmp_path / "usr/local/bin",
        desktop_directory=tmp_path / "usr/share/applications",
        approved_roots=(tmp_path,),
        protected_paths=(),
    )
    plan = build_operator_apps_plan(config)
    modes = {Path(item["path"]).name: item["mode"] for item in plan["files"]}
    assert modes["aegis"] == "0755"
    assert modes["aegis-platform.desktop"] == "0644"
    assert plan["path"]["action"] == "NOT_APPLICABLE"

    store = PlatformInstallationStore(tmp_path / "b1/install.db")
    state = tmp_path / "safe/sofia.db"
    state.parent.mkdir()
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    bootstrap_canonical_sqlite(state)
    request = operator_apps_request("install", config)
    _approve(state, request, "approval:debian-install")
    paths = InMemoryPathAdapter(value="/usr/bin:/bin")
    shortcuts = FakeShortcuts()
    receipt = apply_owner_approved_operator_apps(
        approval_id="approval:debian-install", operation="install", config=config,
        state_path=state, store=store, path_adapter=paths,
        shortcut_adapter=shortcuts,
    )
    assert receipt["outcome"] == "SUCCEEDED"
    primary = plan["files"][0]["path"]
    script = Path(primary).read_text(encoding="utf-8")
    assert script.startswith("#!/bin/sh\n")
    assert OWNERSHIP_MARKER in script
    assert "sofia.platform.cli" in script
    wrapper = tmp_path / "usr/local/bin/aegis"
    assert OWNERSHIP_MARKER in wrapper.read_text(encoding="utf-8")
    desktop = tmp_path / "usr/share/applications/aegis-platform.desktop"
    assert OWNERSHIP_MARKER in desktop.read_text(encoding="utf-8")
    assert paths.value == "/usr/bin:/bin"
    assert receipt["path_action"]["action"] == "NO_CHANGE"
