"""Deferred offline Ed25519 attestation, immutable installer account policy.

No ISO remastering, network, Hyper-V invocation, key publication or CI run.
"""
from pathlib import Path
import json
import os

import pytest

from sofia.ops.workshop_media_attestation import (
    POLICY,
    create_owner_signing_keypair,
    media_manifest_payload,
    sign_prepared_media,
    verify_prepared_media,
)
from sofia.ops.workshop_media import MEDIA_POLICY_VERSION

pytestmark=pytest.mark.pkg_ops


def _restrict_owner_test_folder(path):
    """Use the native ACL, not chmod emulation, on Windows test runners."""
    if os.name != "nt":
        path.chmod(0o700)
        return
    import win32api
    import win32con
    import win32security
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
    )
    sid, _ = win32security.GetTokenInformation(
        token, win32security.TokenUser,
    )
    acl = win32security.ACL()
    inherit = win32con.CONTAINER_INHERIT_ACE | win32con.OBJECT_INHERIT_ACE
    acl.AddAccessAllowedAceEx(
        win32security.ACL_REVISION, inherit, win32con.GENERIC_ALL, sid,
    )
    acl.AddAccessAllowedAceEx(
        win32security.ACL_REVISION, inherit, win32con.GENERIC_ALL,
        win32security.ConvertStringSidToSid("S-1-5-18"),
    )
    sd = win32security.GetFileSecurity(
        str(path), win32security.OWNER_SECURITY_INFORMATION |
        win32security.DACL_SECURITY_INFORMATION,
    )
    sd.SetSecurityDescriptorOwner(sid, False)
    sd.SetSecurityDescriptorDacl(1, acl, 0)
    sd.SetSecurityDescriptorControl(
        win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED,
    )
    win32security.SetFileSecurity(
        str(path), win32security.OWNER_SECURITY_INFORMATION |
        win32security.DACL_SECURITY_INFORMATION, sd,
    )


def _owner_key(tmp_path,monkeypatch):
    private_dir=tmp_path/"owner-private"
    private_dir.mkdir(mode=0o700)
    _restrict_owner_test_folder(private_dir)
    monkeypatch.setattr(
        "sofia.ops.workshop_media_attestation.getpass",
        lambda _: "test-owner-local-passphrase-only",
    )
    keys=create_owner_signing_keypair(private_dir)
    return Path(keys["private_key_path"]),Path(keys["public_key_path"])


def test_owner_signed_media_policy_binds_exact_iso_sha_and_non_root_guest(tmp_path,monkeypatch):
    private,public=_owner_key(tmp_path,monkeypatch)
    installer=tmp_path/"hephaestus-debian13-offline.iso"
    installer.write_bytes(b"dummy nonbootable media fixture")
    signed=sign_prepared_media(
        iso_path=installer,
        base_sha256="f"*64,
        signing_key_file=private,
    )
    assert signed["signed"] is True
    assert signed["policy"]==POLICY==MEDIA_POLICY_VERSION
    inspected=verify_prepared_media(
        iso_path=installer,trusted_public_key_file=public,
    )
    assert inspected["sha256"]==signed["media_sha256"]
    assert inspected["policy_version"]==POLICY
    assert inspected["owner_signed"] is True
    assert inspected["guest_installed"] is False
    envelope=json.loads(Path(signed["manifest_path"]).read_text())
    payload=envelope["payload"]
    assert payload["root_login_enabled"] is False
    assert payload["console_admin_requires_password"] is True
    assert payload["local_admin"]=="sofia-admin"
    assert payload["worker"]=="sofia-worker"
    assert payload["worker_has_sudo"] is False
    assert payload["worker_interactive_login_enabled"] is False
    assert payload["passwordless_sudo"] is False
    assert payload["openssh_server_installed"] is False
    assert payload["ssh_service_enabled"] is False
    assert payload["networked_installer_enabled"] is False
    assert payload["host_authority"]=="NONE"
    assert payload["fleet_enrollment"]=="SEPARATE_OWNER_APPROVAL"
    assert "passwd" not in json.dumps(payload).casefold()


def test_iso_tampering_breaks_pinned_manifest_even_if_owner_verified_original(tmp_path,monkeypatch):
    private,public=_owner_key(tmp_path,monkeypatch)
    installer=tmp_path/"hephaestus-debian13-offline.iso"
    installer.write_bytes(b"original media contents")
    sign_prepared_media(
        iso_path=installer,base_sha256="b"*64,signing_key_file=private,
    )
    installer.write_bytes(b"substituted interactive ISO")
    with pytest.raises(PermissionError,match="ISO content differs"):
        verify_prepared_media(
            iso_path=installer,trusted_public_key_file=public,
        )


def test_manifest_tamper_or_wrong_owner_key_never_admits_boot(tmp_path,monkeypatch):
    private,public=_owner_key(tmp_path,monkeypatch)
    installer=tmp_path/"hephaestus-debian13-offline.iso"
    installer.write_bytes(b"some bytes")
    sign_prepared_media(
        iso_path=installer,base_sha256="c"*64,signing_key_file=private,
    )
    other_dir=tmp_path/"other-owner"
    other_dir.mkdir(mode=0o700)
    _restrict_owner_test_folder(other_dir)
    unrelated=create_owner_signing_keypair(other_dir)
    with pytest.raises(PermissionError,match="pin changed"):
        verify_prepared_media(
            iso_path=installer,
            trusted_public_key_file=unrelated["public_key_path"],
        )
    manifest=Path(str(installer)+".manifest.json")
    data=json.loads(manifest.read_text())
    data["payload"]["passwordless_sudo"]=True
    manifest.write_text(json.dumps(data))
    with pytest.raises(PermissionError,match="signature invalid"):
        verify_prepared_media(
            iso_path=installer,trusted_public_key_file=public,
        )


def test_no_unsigned_interactive_iso_or_missing_owner_pin_passes():
    tmp_path=None
    assert MEDIA_POLICY_VERSION==POLICY
    with pytest.raises(ValueError,match="SHA-256"):
        media_manifest_payload(
            media_name="interactive.iso",
            media_sha256="unsigned",base_sha256="a"*64,
        )


def test_generation_requires_private_owner_key_dir(tmp_path,monkeypatch):
    folder=tmp_path/"world-accessible"
    folder.mkdir(mode=0o777)
    if os.name == "nt":
        import win32api
        import win32con
        import win32security
        # Windows chmod(0777) does NOT grant Everyone access. Use a real
        # permissive DACL to prove the production key guard rejects it.
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
        )
        user, _ = win32security.GetTokenInformation(
            token, win32security.TokenUser,
        )
        acl = win32security.ACL()
        acl.AddAccessAllowedAce(
            win32security.ACL_REVISION, win32con.GENERIC_ALL, user,
        )
        acl.AddAccessAllowedAce(
            win32security.ACL_REVISION, win32con.GENERIC_READ,
            win32security.ConvertStringSidToSid("S-1-1-0"),
        )
        sd = win32security.GetFileSecurity(
            str(folder), win32security.OWNER_SECURITY_INFORMATION |
            win32security.DACL_SECURITY_INFORMATION,
        )
        sd.SetSecurityDescriptorOwner(user, False)
        sd.SetSecurityDescriptorDacl(1, acl, 0)
        sd.SetSecurityDescriptorControl(
            win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED,
        )
        win32security.SetFileSecurity(
            str(folder), win32security.OWNER_SECURITY_INFORMATION |
            win32security.DACL_SECURITY_INFORMATION, sd,
        )
    else:
        folder.chmod(0o777)
    monkeypatch.setattr(
        "sofia.ops.workshop_media_attestation.getpass",
        lambda _: "not-a-real-user-secret",
    )
    with pytest.raises(PermissionError,match="group/world"):
        create_owner_signing_keypair(folder)


def test_key_pair_is_explicitly_owner_private_and_not_regenerated(tmp_path,monkeypatch):
    private,public=_owner_key(tmp_path,monkeypatch)
    assert private.exists() and public.exists()
    from sofia.ops.workshop_media_attestation import _assert_owner_private_path
    _assert_owner_private_path(private, directory=False)
    with pytest.raises(FileExistsError,match="overwrite"):
        create_owner_signing_keypair(private.parent)

def test_owner_signed_media_contract_explicitly_requires_guest_firewall():
    from sofia.ops.workshop_media_attestation import media_manifest_payload
    p=media_manifest_payload(
        media_name="hephaestus-debian13-offline.iso",
        media_sha256="a"*64,base_sha256="b"*64,
    )
    assert p["network_mode"]=="internal_host_guest_no_lan"
    assert p["guest_ipv4"]=="172.30.250.2/30"
    assert p["gateway"] is None
    assert p["dns_servers"]==[]
    assert p["guest_firewall"]=="nftables:default_drop_input_output_forward"
    assert p["guest_firewall_other_outbound"]=="DENIED"
    assert p["host_guest_agent_allowed_tcp_port"]==7443
    assert p["ipv4_forwarding_enabled"] is False
    assert p["ipv6_forwarding_enabled"] is False
