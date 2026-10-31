"""LINK-02 protected Core Link binding registry acceptance."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess

import pytest

from sofia.platform import launcher
from sofia.platform.core_link import (
    CoreLinkBinding, CoreLinkBindingState, CoreLinkBindingStore,
)
from sofia.platform.state.private_file import assert_owner_private_path
from sofia.sdk.contracts import ProtocolVersion


NOW = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)


def binding(**changes) -> CoreLinkBinding:
    base = CoreLinkBinding(
        binding_id="binding:sofia-primary",
        local_platform_id="platform:venus-client",
        remote_platform_id="platform:canonical-vm",
        remote_core_identity_id="core:sofia",
        remote_core_generation=7,
        endpoint_id="endpoint:canonical-core-link",
        credential_ref="os-keystore:sofia/core-link/client-7",
        trust_anchor_ref="sha256:" + "a" * 64,
        audience_id="audience:sparks-private",
        granted_scopes=("conversation.read", "conversation.write", "status.read"),
        protocol_version=ProtocolVersion(1, 0),
        state=CoreLinkBindingState.PENDING_APPROVAL,
        revision=1,
        created_at=NOW,
        updated_at=NOW,
    )
    return replace(base, **changes)


def store(tmp_path: Path) -> CoreLinkBindingStore:
    root = tmp_path / "private-client"
    root.mkdir(mode=0o700)
    return CoreLinkBindingStore((root / "core-links.json").resolve())


def activate(registry: CoreLinkBindingStore):
    created = registry.add_pending(binding(), expected_store_revision=0)
    verifying = registry.transition(
        "binding:sofia-primary", expected_binding_revision=1,
        expected_store_revision=created.revision,
        state=CoreLinkBindingState.VERIFYING, at=NOW + timedelta(seconds=1),
    )
    active = registry.reconcile_contact(
        "binding:sofia-primary", expected_binding_revision=2,
        expected_store_revision=verifying.revision,
        remote_platform_id="platform:canonical-vm",
        remote_core_identity_id="core:sofia", remote_core_generation=7,
        endpoint_id="endpoint:canonical-core-link",
        trust_anchor_ref="sha256:" + "a" * 64,
        at=NOW + timedelta(seconds=2),
    )
    return active


def test_binding_store_is_core_free_json_not_sqlite_and_survives_restart(tmp_path):
    registry = store(tmp_path)
    active = activate(registry)
    selected = registry.select(
        "binding:sofia-primary", expected_store_revision=active.revision,
    )
    assert selected.selected().state is CoreLinkBindingState.ACTIVE
    assert not any(path.suffix == ".db" for path in registry.path.parent.iterdir())
    restarted = CoreLinkBindingStore(registry.path).load()
    assert restarted == selected
    assert_owner_private_path(registry.path, directory=False)


def test_cas_prevents_concurrent_silent_overwrite(tmp_path):
    registry = store(tmp_path)
    first = registry.add_pending(binding(), expected_store_revision=0)
    registry.transition(
        "binding:sofia-primary", expected_binding_revision=1,
        expected_store_revision=first.revision,
        state=CoreLinkBindingState.VERIFYING, at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(RuntimeError, match="store revision conflict"):
        registry.transition(
            "binding:sofia-primary", expected_binding_revision=1,
            expected_store_revision=first.revision,
            state=CoreLinkBindingState.REVOKED, at=NOW + timedelta(seconds=2),
        )


@pytest.mark.parametrize("field,value", [
    ("remote_platform_id", "platform:impostor"),
    ("remote_core_identity_id", "core:roland"),
    ("remote_core_generation", 8),
    ("endpoint_id", "endpoint:changed"),
    ("trust_anchor_ref", "sha256:" + "b" * 64),
])
def test_authenticated_contact_mismatch_quarantines_and_deselects(
    tmp_path, field, value,
):
    registry = store(tmp_path)
    selected = registry.select(
        "binding:sofia-primary", expected_store_revision=activate(registry).revision,
    )
    observed = {
        "remote_platform_id": "platform:canonical-vm",
        "remote_core_identity_id": "core:sofia",
        "remote_core_generation": 7,
        "endpoint_id": "endpoint:canonical-core-link",
        "trust_anchor_ref": "sha256:" + "a" * 64,
    }
    observed[field] = value
    result = registry.reconcile_contact(
        "binding:sofia-primary", expected_binding_revision=3,
        expected_store_revision=selected.revision,
        at=NOW + timedelta(seconds=3), **observed,
    )
    assert result.selected_binding_id is None
    assert result.bindings[0].state is CoreLinkBindingState.QUARANTINED
    assert result.bindings[0].remote_core_identity_id == "core:sofia"


def test_offline_selected_core_remains_selected_and_no_substitute_is_chosen(tmp_path):
    registry = store(tmp_path)
    selected = registry.select(
        "binding:sofia-primary", expected_store_revision=activate(registry).revision,
    )
    offline = registry.transition(
        "binding:sofia-primary", expected_binding_revision=3,
        expected_store_revision=selected.revision,
        state=CoreLinkBindingState.OFFLINE, at=NOW + timedelta(seconds=3),
    )
    second = replace(
        binding(), binding_id="binding:roland", remote_core_identity_id="core:roland",
        revision=1, updated_at=NOW + timedelta(seconds=4),
    )
    after_discovery = registry.add_pending(
        second, expected_store_revision=offline.revision,
    )
    assert after_discovery.selected_binding_id == "binding:sofia-primary"
    assert after_discovery.selected().state is CoreLinkBindingState.OFFLINE


def test_store_rejects_corruption_unknown_fields_and_symlink(tmp_path):
    registry = store(tmp_path)
    registry.path.write_text("not json", encoding="utf-8")
    registry.path.chmod(0o600)
    with pytest.raises(RuntimeError, match="corrupt"):
        registry.load()

    registry.path.write_text(json.dumps({
        "schema": "companion.platform.core_link_store.v1", "revision": 0,
        "selected_binding_id": None, "bindings": [], "surprise": True,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="malformed"):
        registry.load()

    registry.path.unlink()
    target = registry.path.parent / "other.json"
    target.write_text("{}", encoding="utf-8")
    _symlink_or_skip(registry.path.symlink_to, target)
    with pytest.raises(PermissionError, match="redirection|regular"):
        registry.load()


def test_binding_store_rejects_redirected_parent(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    redirected = tmp_path / "redirected"
    _symlink_or_skip(redirected.symlink_to, outside, target_is_directory=True)
    registry = CoreLinkBindingStore((redirected / "bindings.json").absolute())
    with pytest.raises(PermissionError, match="redirection"):
        registry.add_pending(binding(), expected_store_revision=0)

    broken = tmp_path / "broken-redirect"
    broken.symlink_to(tmp_path / "missing", target_is_directory=True)
    broken_registry = CoreLinkBindingStore(
        (broken / "bindings.json").absolute()
    )
    with pytest.raises(PermissionError, match="redirection"):
        broken_registry.add_pending(binding(), expected_store_revision=0)


def test_binding_store_rejects_unsafe_native_permissions(tmp_path):
    registry = store(tmp_path)
    registry.add_pending(binding(), expected_store_revision=0)
    if os.name == "nt":
        import win32con
        import win32security

        descriptor = win32security.GetFileSecurity(
            str(registry.path), win32security.DACL_SECURITY_INFORMATION,
        )
        dacl = descriptor.GetSecurityDescriptorDacl()
        assert dacl is not None
        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION, win32con.GENERIC_READ,
            win32security.ConvertStringSidToSid("S-1-1-0"),
        )
        descriptor.SetSecurityDescriptorDacl(1, dacl, 0)
        win32security.SetFileSecurity(
            str(registry.path), win32security.DACL_SECURITY_INFORMATION,
            descriptor,
        )
    else:
        registry.path.chmod(0o644)
    with pytest.raises(PermissionError, match="ACL reader|group/world"):
        registry.load()


def _windows_privilege_enabled(name: str) -> bool:
    import win32api
    import win32security

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(),
        win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY,
    )
    privileges = {
        win32security.LookupPrivilegeName(None, luid): attributes
        for luid, attributes in win32security.GetTokenInformation(
            token, win32security.TokenPrivileges,
        )
    }
    if privileges.get(name, 0) & win32security.SE_PRIVILEGE_ENABLED:
        return True
    try:
        luid = win32security.LookupPrivilegeValue(None, name)
        win32security.AdjustTokenPrivileges(
            token, 0, [(luid, win32security.SE_PRIVILEGE_ENABLED)],
        )
    except Exception:
        return False
    privileges = {
        win32security.LookupPrivilegeName(None, luid): attributes
        for luid, attributes in win32security.GetTokenInformation(
            token, win32security.TokenPrivileges,
        )
    }
    return bool(privileges.get(name, 0) & win32security.SE_PRIVILEGE_ENABLED)


def _symlink_or_skip(symlink_to, target, **kwargs) -> None:
    try:
        symlink_to(target, **kwargs)
    except OSError as exc:
        if getattr(exc, "winerror", None) != 1314:
            raise
        pytest.skip("symlink creation privilege unavailable")


@pytest.mark.skipif(os.name != "nt", reason="Windows native DACL validation")
def test_windows_owner_rights_dacl_is_owner_private(tmp_path):
    import win32security

    root = tmp_path / "private-client"
    root.mkdir(mode=0o700)
    descriptor = win32security.GetFileSecurity(
        str(root), win32security.DACL_SECURITY_INFORMATION,
    )
    dacl = descriptor.GetSecurityDescriptorDacl()
    assert dacl is not None
    principals = {
        win32security.ConvertSidToStringSid(dacl.GetAce(index)[2])
        for index in range(dacl.GetAceCount())
    }
    assert "S-1-3-4" in principals
    registry = CoreLinkBindingStore((root / "core-links.json").resolve())
    activate(registry)
    assert_owner_private_path(root, directory=True)
    assert_owner_private_path(registry.path, directory=False)


@pytest.mark.skipif(os.name != "nt", reason="Windows native DACL validation")
def test_windows_accepts_token_owner_and_rejects_foreign_owner(tmp_path):
    import win32api
    import win32security

    if not _windows_privilege_enabled("SeRestorePrivilege"):
        pytest.skip("SeRestorePrivilege unavailable for owner reconstruction")

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
    )
    user_sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
    root = tmp_path / "private-client"
    root.mkdir(mode=0o700)
    target = root / "state.json"
    target.write_text("{}", encoding="utf-8")

    def set_owner(sid) -> None:
        descriptor = win32security.GetFileSecurity(
            str(target),
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION,
        )
        descriptor.SetSecurityDescriptorOwner(sid, False)
        win32security.SetFileSecurity(
            str(target), win32security.OWNER_SECURITY_INFORMATION, descriptor,
        )

    set_owner(win32security.ConvertStringSidToSid("S-1-5-32-546"))
    with pytest.raises(PermissionError, match="another Windows identity"):
        assert_owner_private_path(target, directory=False)

    set_owner(win32security.GetTokenInformation(token, win32security.TokenOwner))
    assert_owner_private_path(target, directory=False)
    set_owner(user_sid)
    assert_owner_private_path(target, directory=False)


@pytest.mark.skipif(os.name != "nt", reason="Windows native DACL validation")
def test_windows_owner_rights_does_not_admit_unauthorized_readers(tmp_path):
    import win32con
    import win32security

    root = tmp_path / "private-client"
    root.mkdir(mode=0o700)
    target = root / "state.json"
    target.write_text("{}", encoding="utf-8")

    def replace_dacl(acl) -> None:
        descriptor = win32security.GetFileSecurity(
            str(target), win32security.DACL_SECURITY_INFORMATION,
        )
        descriptor.SetSecurityDescriptorDacl(1, acl, 0)
        win32security.SetFileSecurity(
            str(target), win32security.DACL_SECURITY_INFORMATION, descriptor,
        )

    unauthorized = win32security.ACL()
    unauthorized.AddAccessAllowedAce(
        win32security.ACL_REVISION, win32con.GENERIC_READ,
        win32security.ConvertStringSidToSid("S-1-5-11"),
    )
    replace_dacl(unauthorized)
    with pytest.raises(PermissionError, match="unauthorized ACL reader"):
        assert_owner_private_path(target, directory=False)

    ownerless = win32security.ACL()
    for sid in ("S-1-5-18", "S-1-5-32-544"):
        ownerless.AddAccessAllowedAce(
            win32security.ACL_REVISION, win32con.GENERIC_ALL,
            win32security.ConvertStringSidToSid(sid),
        )
    replace_dacl(ownerless)
    with pytest.raises(PermissionError, match="no owner ACL"):
        assert_owner_private_path(target, directory=False)


@pytest.mark.skipif(os.name != "nt", reason="Windows native DACL validation")
@pytest.mark.parametrize("owner_grant", ("READ_CONTROL", "GENERIC_READ", "GENERIC_WRITE"))
def test_windows_private_state_owner_ace_requires_read_and_write(tmp_path, owner_grant):
    """An owner ACE with an unrelated or one-way bit cannot authorize state."""
    import win32api
    import win32con
    import win32security

    target = tmp_path / "state.json"
    target.write_text("{}", encoding="utf-8")
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
    )
    owner_sid, _ = win32security.GetTokenInformation(
        token, win32security.TokenUser,
    )
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION, getattr(win32con, owner_grant), owner_sid,
    )
    descriptor = win32security.GetFileSecurity(
        str(target), win32security.DACL_SECURITY_INFORMATION,
    )
    descriptor.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(
        str(target), win32security.DACL_SECURITY_INFORMATION, descriptor,
    )
    with pytest.raises(PermissionError, match="no read/write owner ACL"):
        assert_owner_private_path(target, directory=False)


@pytest.mark.skipif(os.name != "nt", reason="Windows native DACL validation")
def test_windows_private_state_explicit_owner_deny_fails_closed(tmp_path):
    import win32api
    import win32con
    import win32security

    target = tmp_path / "state.json"
    target.write_text("{}", encoding="utf-8")
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
    )
    owner_sid, _ = win32security.GetTokenInformation(
        token, win32security.TokenUser,
    )
    dacl = win32security.ACL()
    dacl.AddAccessDeniedAce(
        win32security.ACL_REVISION, win32con.GENERIC_WRITE, owner_sid,
    )
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION, win32con.GENERIC_ALL, owner_sid,
    )
    descriptor = win32security.GetFileSecurity(
        str(target), win32security.DACL_SECURITY_INFORMATION,
    )
    descriptor.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(
        str(target), win32security.DACL_SECURITY_INFORMATION, descriptor,
    )
    with pytest.raises(PermissionError, match="denies owner access"):
        assert_owner_private_path(target, directory=False)


@pytest.mark.skipif(os.name != "nt", reason="Windows native DACL validation")
def test_windows_private_state_inherit_only_ace_not_effective_on_directory(tmp_path):
    import win32api
    import win32con
    import win32security

    directory = tmp_path / "private-client"
    directory.mkdir()
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
    )
    owner_sid, _ = win32security.GetTokenInformation(
        token, win32security.TokenUser,
    )
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAceEx(
        win32security.ACL_REVISION,
        win32security.INHERIT_ONLY_ACE | win32con.CONTAINER_INHERIT_ACE,
        win32con.GENERIC_ALL,
        owner_sid,
    )
    descriptor = win32security.GetFileSecurity(
        str(directory), win32security.DACL_SECURITY_INFORMATION,
    )
    descriptor.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(
        str(directory), win32security.DACL_SECURITY_INFORMATION, descriptor,
    )
    with pytest.raises(PermissionError, match="no read/write owner ACL"):
        assert_owner_private_path(directory, directory=True)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction redirection")
def test_windows_private_state_rejects_junction_parent(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    junction = tmp_path / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True, capture_output=True,
    )
    registry = CoreLinkBindingStore((junction / "bindings.json").absolute())
    with pytest.raises(PermissionError, match="redirection"):
        registry.add_pending(binding(), expected_store_revision=0)


def test_plaintext_credentials_and_invalid_fingerprints_are_rejected():
    with pytest.raises(ValueError, match="secret-store reference"):
        binding(credential_ref="actual-secret-token")
    with pytest.raises(ValueError, match="SHA-256 fingerprint"):
        binding(trust_anchor_ref="trust-me")


def test_active_state_requires_exact_authenticated_contact(tmp_path):
    registry = store(tmp_path)
    created = registry.add_pending(binding(), expected_store_revision=0)
    verifying = registry.transition(
        "binding:sofia-primary", expected_binding_revision=1,
        expected_store_revision=created.revision,
        state=CoreLinkBindingState.VERIFYING, at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="invalid Core Link transition"):
        registry.transition(
            "binding:sofia-primary", expected_binding_revision=2,
            expected_store_revision=verifying.revision,
            state=CoreLinkBindingState.ACTIVE, at=NOW + timedelta(seconds=2),
        )


def test_revoked_binding_cannot_be_reactivated_by_contact(tmp_path):
    registry = store(tmp_path)
    created = registry.add_pending(binding(), expected_store_revision=0)
    revoked = registry.transition(
        "binding:sofia-primary", expected_binding_revision=1,
        expected_store_revision=created.revision,
        state=CoreLinkBindingState.REVOKED, at=NOW + timedelta(seconds=1),
    )
    with pytest.raises(PermissionError, match="contact reconciliation"):
        registry.reconcile_contact(
            "binding:sofia-primary", expected_binding_revision=2,
            expected_store_revision=revoked.revision,
            remote_platform_id="platform:canonical-vm",
            remote_core_identity_id="core:sofia", remote_core_generation=7,
            endpoint_id="endpoint:canonical-core-link",
            trust_anchor_ref="sha256:" + "a" * 64,
            at=NOW + timedelta(seconds=2),
        )


def test_launcher_status_projects_selected_binding_without_secret_refs(
    tmp_path, monkeypatch, capsys,
):
    registry = store(tmp_path)
    selected = registry.select(
        "binding:sofia-primary", expected_store_revision=activate(registry).revision,
    )
    monkeypatch.setenv("SOFIA_PLATFORM_ROLES", "CORE_LINK,MODULE_HOST")
    monkeypatch.setenv("SOFIA_CORE_LINK_BINDING_STORE", str(registry.path))
    assert launcher.main(["status"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["core_link"]["store_revision"] == selected.revision
    projection = payload["core_link"]["selected"]
    assert projection["remote_core_identity_id"] == "core:sofia"
    assert "credential_ref" not in projection
    assert "trust_anchor_ref" not in projection

