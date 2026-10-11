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


def _owner_key(tmp_path,monkeypatch):
    private_dir=tmp_path/"owner-private"
    private_dir.mkdir(mode=0o700)
    private_dir.chmod(0o700)
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
    other_dir.chmod(0o700)
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
    assert private.stat().st_mode & 0o077 == 0
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
