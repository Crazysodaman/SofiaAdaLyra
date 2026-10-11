"""Deferred real media builder policy tests. No ISO builds or external tools run."""
from pathlib import Path
import json
import re

import pytest

from sofia.ops.workshop_media import (
    BOOT_PARAMETERS,
    MEDIA_POLICY_VERSION,
    PreparedOfflineInstaller,
    _render_uefi_grub_config,
    render_first_boot_policy,
    render_preseed,
)

pytestmark = pytest.mark.pkg_ops
PASSWORD_HASH = "$6$abcdefgh12345678$" + "A" * 86


def test_preseed_owner_password_only_for_console_admin_not_root_or_worker():
    cfg = render_preseed(console_admin_crypted_password=PASSWORD_HASH)
    assert "d-i passwd/root-login boolean false" in cfg
    assert "d-i passwd/make-user boolean true" in cfg
    assert "d-i passwd/username string sofia-admin" in cfg
    assert (
        "d-i passwd/user-password-crypted password " + PASSWORD_HASH
    ) in cfg
    assert "passwd/root-password password" not in cfg
    assert "d-i passwd/user-password password" not in cfg
    assert "sofia-worker" not in cfg
    assert "ssh-server" not in cfg
    assert "openssh-server" not in cfg
    assert "netcfg/enable boolean false" in cfg
    assert "apt-setup/use_mirror boolean false" in cfg
    assert "d-i time/zone string America/Chicago" in cfg
    assert "d-i partman/early_command string set -- $(list-devices disk)" in cfg
    assert 'test "$#" -eq 1 || exit 1' in cfg
    assert "d-i debian-installer/exit/halt boolean true" in cfg
    assert "d-i pkgsel/include string sudo" in cfg
    assert "NOPASSWD" not in cfg


def test_guest_hardening_locks_root_and_noninteractive_worker_before_trust():
    script = render_first_boot_policy()
    assert script.startswith("#!/bin/sh\nset -eu\n")
    assert "/usr/bin/passwd --lock root" in script
    assert "/usr/sbin/usermod -aG sudo sofia-admin" in script
    assert "useradd --system --user-group --create-home" in script
    assert "--shell /usr/sbin/nologin sofia-worker" in script
    assert "/usr/bin/passwd --lock sofia-worker" in script
    assert "id -u sofia-worker" in script
    assert "grep -x sudo" in script
    assert "NOPASSWD:" in script  # rejection check, never a grant
    assert "dpkg-query -W openssh-server" in script
    assert "/usr/bin/systemctl mask ssh.service sshd.service ssh.socket" in script
    assert "useradd -p" not in script
    assert "password=" not in script


def test_grub_entry_is_first_default_and_passes_exact_offline_preseed():
    original = (
        "set timeout=20\n"
        "menuentry 'Install' {\n"
        "  linux /install.amd/vmlinuz vga=788 --- quiet\n"
        "  initrd /install.amd/initrd.gz\n"
        "}\n"
    )
    changed = _render_uefi_grub_config(original)
    assert changed.count("Hephaestus approved unattended Debian install") == 1
    assert changed.index("Hephaestus approved") < changed.index("menuentry 'Install'")
    assert changed.startswith("set default=0\nset timeout=5\n")
    assert changed.rstrip().endswith("set timeout=5")
    assert "preseed/file=/cdrom/preseed.cfg" in BOOT_PARAMETERS
    assert "netcfg/enable=false" in changed
    assert "linux /install.amd/vmlinuz auto=true priority=critical" in changed
    assert "initrd /install.amd/initrd.gz" in changed


@pytest.mark.parametrize("bad_source", [
    "",
    "menuentry 'Graphical install' { linux /install.amd/gtk/vmlinuz }",
    "linux /unknown/vmlinuz\ninitrd /unknown/initrd.gz",
    "menuentry 'shell' {\n chainloader /EFI/BOOT/BOOTX64.EFI\n}",
])
def test_unknown_grub_formats_refuse_to_claim_unattended_uefi_boot(bad_source):
    with pytest.raises(ValueError, match="Debian installer|source ISO"):
        _render_uefi_grub_config(bad_source)


@pytest.mark.parametrize("bad_hash", [
    "password123", "root", "!", "$1$weak$hash", "$6$nosalt",
    "$6$12345678$bad\ninjected",
])
def test_preseed_refuses_cleartext_weak_hashes_and_line_injection(bad_hash):
    with pytest.raises(ValueError, match="SHA-512"):
        render_preseed(console_admin_crypted_password=bad_hash)


def test_media_report_never_claims_user_admin_is_passwordless_or_guest_installed():
    result = PreparedOfflineInstaller(
        media_path="/private/iso/hephaestus-debian.iso",
        media_sha256="a" * 64,
        reviewed_debian_source_sha256="b" * 64,
        policy_version=MEDIA_POLICY_VERSION,
    )
    assert result.guest_admin == "sofia-admin"
    assert result.worker == "sofia-worker"
    assert result.initial_ssh_enabled is False
    assert result.passwordless_sudo is False
    assert result.root_login_enabled is False
    assert result.iso_contains_password_verifier is True
    assert result.os_installed is False
    assert result.hyperv_guest_verified is False
    with pytest.raises(PermissionError, match="guest trust"):
        PreparedOfflineInstaller(
            media_path="/private/iso/debian.iso",
            media_sha256="a" * 64,
            reviewed_debian_source_sha256="b" * 64,
            policy_version=MEDIA_POLICY_VERSION,
            os_installed=True,
        )


def test_password_collection_requires_hidden_local_input_and_no_cli_secret(monkeypatch):
    import sofia.ops.workshop_media as media
    responses = iter(("the same private password!", "the same private password!"))
    commands = []

    monkeypatch.setattr(media, "getpass", lambda _: next(responses))
    def fake_tool(command, *, timeout, input_text=None):
        commands.append((command, timeout, input_text))
        return PASSWORD_HASH + "\n"
    monkeypatch.setattr(media, "_run", fake_tool)
    observed = media._hash_admin_password()
    assert observed == PASSWORD_HASH
    assert len(commands) == 1
    args, timeout, stdin = commands[0]
    assert args == ["openssl", "passwd", "-6", "-stdin"]
    assert "the same private password!" not in " ".join(args)
    assert stdin == "the same private password!\n"


def test_media_build_never_autopulls_tool_or_launches_host(monkeypatch, tmp_path):
    import sofia.ops.workshop_media as media
    source = tmp_path / "debian-13.7.0-amd64-DVD-1.iso"
    source.write_bytes(b"faux fixture; tiny file")
    monkeypatch.setattr(media.platform, "system", lambda: "Linux")
    monkeypatch.setattr(media.shutil, "which", lambda _: "/usr/bin/fixture")
    output = tmp_path / "new.iso"
    with pytest.raises(ValueError, match="unexpectedly small"):
        media.prepare_offline_debian_installer(
            source_iso=source,
            expected_source_sha256=media._sha256_file(source),
            output_iso=output,
        )
    assert not output.exists()
