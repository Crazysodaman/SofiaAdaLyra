"""Owner-signed offline Hephaestus ISO policy attestation.

Signature authenticates the reviewed local media-builder policy and its
specific SHA-256, not the quality of its boot or OS install. Artemis pins an
independent owner Ed25519 public key. No model/admin root can substitute an
unattested interactive ISO for the protected offline installer.
"""
from __future__ import annotations

import argparse
from base64 import b64decode, b64encode
from getpass import getpass
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SCHEMA = "sofia-workshop-offline-media-ed25519-v1"
POLICY = "hephaestus-debian13-console-admin-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _json_bytes(obj: dict) -> bytes:
    return json.dumps(
        obj,sort_keys=True,separators=(",", ":"),
        ensure_ascii=True,allow_nan=False,
    ).encode("ascii")


def _content_hash(path: Path) -> str:
    h=sha256()
    with path.open("rb") as src:
        while chunk:=src.read(1024*1024):
            h.update(chunk)
    return h.hexdigest()


def _assert_owner_private_path(path: Path, *, directory: bool) -> None:
    """Check actual OS ACLs instead of trusting synthetic Windows chmod bits.

    On POSIX require an owner-only 0700/0600 boundary. Windows has a DACL:
    reject inherited Everyone/Users/readers, NULL DACLs and foreign owners.
    The local token user, SYSTEM and built-in Administrators are the only
    permitted allow ACE principals. Missing pywin32 means DENY, never allow.
    """
    if os.name != "nt":
        if path.stat().st_mode & 0o077:
            raise PermissionError(
                "key directory must not be group/world accessible" if directory
                else "owner signing key file permissions are too broad"
            )
        return
    try:
        import win32api
        import win32con
        import win32security

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
        )
        user_sid, _ = win32security.GetTokenInformation(
            token, win32security.TokenUser,
        )
        own = win32security.ConvertSidToStringSid(user_sid)
        descriptor = win32security.GetFileSecurity(
            str(path), win32security.OWNER_SECURITY_INFORMATION |
            win32security.DACL_SECURITY_INFORMATION,
        )
        actual_owner = descriptor.GetSecurityDescriptorOwner()
        if actual_owner is None or (
            win32security.ConvertSidToStringSid(actual_owner) != own
        ):
            raise PermissionError("owner signing path belongs to another Windows identity")
        dacl = descriptor.GetSecurityDescriptorDacl()
        if dacl is None:
            raise PermissionError("owner signing path has an unrestricted NULL DACL")
        allowed = {own, "S-1-5-18", "S-1-5-32-544"}
        saw_owner_allow = False
        for i in range(dacl.GetAceCount()):
            ace = dacl.GetAce(i)
            ace_type = ace[0][0]
            mask = int(ace[1])
            principal = win32security.ConvertSidToStringSid(ace[2])
            if ace_type in (
                win32security.ACCESS_ALLOWED_ACE_TYPE,
                win32security.ACCESS_ALLOWED_OBJECT_ACE_TYPE,
            ) and mask:
                if principal not in allowed:
                    raise PermissionError(
                        "Windows owner signing key path has unauthorized ACL reader"
                    )
                if principal == own:
                    saw_owner_allow = True
        if not saw_owner_allow:
            raise PermissionError("owner signing path has no approved owner ACL")
    except ImportError as exc:
        raise PermissionError("Windows ACL inspection dependency unavailable") from exc
    except PermissionError:
        raise
    except Exception as exc:
        raise PermissionError("unable to verify private Windows owner ACL") from exc


def _restrict_new_windows_file(path: Path) -> None:
    """Tighten a newly created EMPTY file before writing private key bytes."""
    if os.name != "nt":
        return
    try:
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
        acl.AddAccessAllowedAce(
            win32security.ACL_REVISION, win32con.GENERIC_ALL, sid,
        )
        acl.AddAccessAllowedAce(
            win32security.ACL_REVISION, win32con.GENERIC_ALL,
            win32security.ConvertStringSidToSid("S-1-5-18"),
        )
        sd = win32security.GetFileSecurity(
            str(path), win32security.DACL_SECURITY_INFORMATION,
        )
        sd.SetSecurityDescriptorDacl(1, acl, 0)
        win32security.SetFileSecurity(
            str(path), win32security.DACL_SECURITY_INFORMATION, sd,
        )
        _assert_owner_private_path(path, directory=False)
    except Exception as exc:
        raise PermissionError("cannot secure new private Windows owner key") from exc


def _private_file(path: Path, content: bytes) -> None:
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        _restrict_new_windows_file(path)
        with os.fdopen(fd,"wb") as stream:
            fd=None
            stream.write(content)
    except Exception:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise


def _reject_repository_storage(path: Path) -> None:
    if any((parent/".git").exists() for parent in (
        path.parent,*path.parents,
    )):
        raise PermissionError("secret-bearing keys and media must not be in Git")
    if not path.parent.exists() or not path.parent.is_dir():
        raise ValueError("existing dedicated private local folder required")


def create_owner_signing_keypair(directory: Path | str) -> dict:
    """Explicit local-only owner initialization; never generate on Artemis."""
    folder=Path(directory).resolve(strict=False)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("provide an existing private local key directory")
    _reject_repository_storage(folder/"hephaestus-owner-private.pem")
    _assert_owner_private_path(folder, directory=True)
    private_file=folder/"hephaestus-owner-private.pem"
    public_file=folder/"hephaestus-owner-public.pem"
    if private_file.exists() or public_file.exists():
        raise FileExistsError("never overwrite or silently rotate owner key identity")
    password=getpass("Local Hephaestus signing-key passphrase: ")
    again=getpass("Repeat signing-key passphrase: ")
    if password!=again or len(password)<16:
        raise ValueError("matching passphrase of at least 16 characters required")
    try:
        key=Ed25519PrivateKey.generate()
        secret=key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode("utf-8"),
            ),
        )
        pub=key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        _private_file(private_file,secret)
        _private_file(public_file,pub)
        return {
            "private_key_path":str(private_file),
            "public_key_path":str(public_file),
            "public_key_sha256":sha256(pub).hexdigest(),
            "public_key_is_secret":False,
            "private_key_must_never_leave_owner":True,
        }
    finally:
        del password,again


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    if not path.is_file() or path.is_symlink() or path.stat().st_size>10_000:
        raise PermissionError("reviewed local encrypted owner signing key required")
    _assert_owner_private_path(path, directory=False)
    passphrase=getpass("Local owner media-signing passphrase: ")
    try:
        key=serialization.load_pem_private_key(
            path.read_bytes(),password=passphrase.encode("utf-8"),
        )
    finally:
        del passphrase
    if not isinstance(key,Ed25519PrivateKey):
        raise ValueError("owner media key must be Ed25519")
    return key


def media_manifest_payload(
    *,media_name:str,media_sha256:str,base_sha256:str,
) -> dict:
    if (
        not isinstance(media_name,str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{8,160}\.iso",media_name)
        or "/" in media_name or "\\" in media_name
        or not isinstance(media_sha256,str)
        or not _SHA.fullmatch(media_sha256)
        or not isinstance(base_sha256,str)
        or not _SHA.fullmatch(base_sha256)
    ):
        raise ValueError("bounded reviewed media and exact SHA-256 required")
    return {
        "schema":SCHEMA,
        "policy":POLICY,
        "media_name":media_name,
        "media_sha256":media_sha256,
        "debian_source_sha256":base_sha256,
        "source_family":"Debian 13 amd64 DVD-1",
        "boot_mode":"Hyper-V Generation-2 UEFI",
        "preseed":"/cdrom/preseed.cfg",
        "local_admin":"sofia-admin",
        "console_admin_requires_password":True,
        "root_login_enabled":False,
        "openssh_server_installed":False,
        "ssh_service_enabled":False,
        "worker":"sofia-worker",
        "worker_interactive_login_enabled":False,
        "worker_password_auth_enabled":False,
        "worker_has_sudo":False,
        "passwordless_sudo":False,
        "networked_installer_enabled":False,
        "network_mode":"internal_host_guest_no_lan",
        "guest_ipv4":"172.30.250.2/30",
        "gateway":None,
        "dns_servers":[],
        "host_guest_agent_allowed_tcp_port":7443,
        "guest_firewall":"nftables:default_drop_input_output_forward",
        "guest_firewall_host_only_source":"172.30.250.1/32",
        "guest_firewall_other_outbound":"DENIED",
        "ipv4_forwarding_enabled":False,
        "ipv6_forwarding_enabled":False,
        "post_install_action":"halt_without_trusting_guest",
        "media_contains_salted_password_verifier":True,
        "host_authority":"NONE",
        "fleet_enrollment":"SEPARATE_OWNER_APPROVAL",
    }


def sign_prepared_media(
    *,iso_path:Path|str,base_sha256:str,
    signing_key_file:Path|str,
) -> dict:
    """Sign a fully built local ISO, never any source-controlled secret."""
    iso=Path(iso_path).resolve(strict=True)
    key_path=Path(signing_key_file).resolve(strict=True)
    _reject_repository_storage(iso)
    if not iso.is_file() or iso.suffix.casefold()!=".iso":
        raise ValueError("actual new UEFI installer ISO required")
    manifest=Path(str(iso)+".manifest.json")
    if manifest.exists():
        raise FileExistsError("media manifest already exists; no overwrite")
    payload=media_manifest_payload(
        media_name=iso.name,
        media_sha256=_content_hash(iso),
        base_sha256=base_sha256,
    )
    key=_load_private_key(key_path)
    signature=key.sign(_json_bytes(payload))
    public_der=key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    envelope={
        "payload":payload,
        "signature_base64":b64encode(signature).decode("ascii"),
        "signer_public_key_der_sha256":sha256(public_der).hexdigest(),
    }
    raw=_json_bytes(envelope)
    if len(raw)>8192:
        raise ValueError("media policy attestation exceeds size bound")
    _private_file(manifest,raw+b"\n")
    return {
        "media_path":str(iso),
        "manifest_path":str(manifest),
        "media_sha256":payload["media_sha256"],
        "policy":payload["policy"],
        "signer_public_key_der_sha256":envelope["signer_public_key_der_sha256"],
        "signed":True,
        "guest_os_installed":False,
    }


def verify_prepared_media(
    *,iso_path:Path|str, trusted_public_key_file:Path|str,
    verify_full_iso:bool=True,
) -> dict:
    """Artemis-side content-and-policy attestation, independently pinned key."""
    iso=Path(iso_path).resolve(strict=True)
    public=Path(trusted_public_key_file).resolve(strict=True)
    manifest=Path(str(iso)+".manifest.json")
    if (
        not iso.is_file() or iso.suffix.casefold()!=".iso"
        or not manifest.is_file() or manifest.is_symlink()
        or manifest.stat().st_size>8192
        or not public.is_file() or public.stat().st_size>10_000
    ):
        raise PermissionError("host-side signed offline media attestation missing")
    key=serialization.load_pem_public_key(public.read_bytes())
    if not isinstance(key,Ed25519PublicKey):
        raise ValueError("independently pinned Ed25519 owner key required")
    try:
        wrapper=json.loads(manifest.read_text(encoding="ascii"))
        if not isinstance(wrapper,dict) or set(wrapper)!={
            "payload","signature_base64","signer_public_key_der_sha256",
        }:
            raise ValueError("unexpected owner media attestation document")
        payload=wrapper["payload"]
        if not isinstance(payload,dict):
            raise ValueError("typed signed media policy required")
        signature=b64decode(wrapper["signature_base64"],validate=True)
        if len(signature)!=64:
            raise ValueError("invalid Ed25519 signature size")
        public_der=key.public_bytes(
            serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        if sha256(public_der).hexdigest()!=wrapper["signer_public_key_der_sha256"]:
            raise PermissionError("media owner key pin changed")
        key.verify(signature,_json_bytes(payload))
        expected=media_manifest_payload(
            media_name=iso.name,
            media_sha256=payload["media_sha256"],
            base_sha256=payload["debian_source_sha256"],
        )
        if payload!=expected:
            raise PermissionError("signed installer account/network policy not approved")
        if verify_full_iso and _content_hash(iso)!=payload["media_sha256"]:
            raise PermissionError("ISO content differs from signed reviewed media")
    except InvalidSignature as exc:
        raise PermissionError("offline installer owner signature invalid") from exc
    return {
        "sha256":payload["media_sha256"],
        "kind":".iso",
        "policy_version":payload["policy"],
        "owner_signed":True,
        "signer_key_sha256":wrapper["signer_public_key_der_sha256"],
        "signed_manifest_path":str(manifest),
        "guest_installed":False,
        "fleet_enrolled":False,
    }


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-owner-key-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    result=create_owner_signing_keypair(args.create_owner_key_dir)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
