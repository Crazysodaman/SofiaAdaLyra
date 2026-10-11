"""Local, owner-operated Debian 13 unattended install-media preparation.

An offline Linux or WSL machine with xorriso and openssl builds a new
UEFI-bootable ISO from the owner's independently hash-verified Debian DVD-1.
The root account stays locked; a password-required local 'sofia-admin' can
use sudo; 'sofia-worker' has no password, login shell or sudo. No SSH server,
network mirror, model download, VM action or Fleet enrollment is requested.

No secret, password, hash, preseed file or output ISO belongs in source control.
The resulting ISO contains a salted password verifier: control access, destroy
media after successful install and rotate the console password if exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from getpass import getpass
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile

_DEBIAN_DVD_NAME = re.compile(
    r"^debian-13\.[0-9]+\.[0-9]+-amd64-DVD-1\.iso$", re.IGNORECASE
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SHA512_CRYPT = re.compile(r"^\$6\$[A-Za-z0-9./]{8,16}\$[A-Za-z0-9./]{80,90}$")
_GRUB_LINUX = re.compile(r"(?m)^\s*linux\s+/install\.amd/vmlinuz(?:\s|$)")
_GRUB_INITRD = re.compile(r"(?m)^\s*initrd\s+/install\.amd/initrd\.gz(?:\s|$)")
BOOT_PARAMETERS = (
    "auto=true priority=critical "
    "preseed/file=/cdrom/preseed.cfg netcfg/enable=false --- quiet"
)
MEDIA_POLICY_VERSION = "hephaestus-debian13-console-admin-v1"


@dataclass(frozen=True, slots=True)
class PreparedOfflineInstaller:
    media_path: str
    media_sha256: str
    reviewed_debian_source_sha256: str
    policy_version: str
    guest_admin: str = "sofia-admin"
    worker: str = "sofia-worker"
    initial_ssh_enabled: bool = False
    passwordless_sudo: bool = False
    root_login_enabled: bool = False
    offline_install_only: bool = True
    iso_contains_password_verifier: bool = True
    os_installed: bool = False
    hyperv_guest_verified: bool = False
    owner_signed: bool = False
    manifest_path: str | None = None

    def __post_init__(self) -> None:
        if self.policy_version != MEDIA_POLICY_VERSION:
            raise ValueError("unrecognized unattended installer policy")
        if not _DIGEST.fullmatch(self.media_sha256):
            raise ValueError("output media SHA-256 must be observed")
        if not _DIGEST.fullmatch(self.reviewed_debian_source_sha256):
            raise ValueError("original Debian source digest must be pinned")
        if self.owner_signed and not self.manifest_path:
            raise ValueError("signed ISO must carry its owner attestation manifest")
        if any((
            self.initial_ssh_enabled,
            self.passwordless_sudo,
            self.root_login_enabled,
            not self.offline_install_only,
            not self.iso_contains_password_verifier,
            self.os_installed,
            self.hyperv_guest_verified,
        )):
            raise PermissionError("media artifact does not grant guest trust")


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def _run(command: list[str], *, timeout: int, input_text: str | None = None) -> str:
    """No shell, never place password material in argv or environment."""
    result = subprocess.run(
        command, input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        timeout=timeout,
    )
    if result.returncode:
        # xorriso and openssl diagnostic output can include workspace paths;
        # do not echo arbitrary command output or secret-bearing preseed.
        raise RuntimeError(
            f"offline installer tool failed: {Path(command[0]).name} "
            f"(exit code {result.returncode})"
        )
    return result.stdout


def _hash_admin_password() -> str:
    """Only a hidden local terminal prompt; never accept CLI/environment secrets."""
    first = getpass("Hephaestus console admin password (local input only): ")
    repeat = getpass("Repeat console admin password: ")
    try:
        if first != repeat or len(first) < 16 or len(first) > 256:
            raise ValueError("console password must match and be 16-256 characters")
        if "\n" in first or "\r" in first or "\x00" in first:
            raise ValueError("newline and NUL characters prohibited")
        hashed = _run(
            ["openssl", "passwd", "-6", "-stdin"],
            timeout=30, input_text=first + "\n",
        ).strip()
        if not _SHA512_CRYPT.fullmatch(hashed):
            raise RuntimeError("OpenSSL did not produce a supported SHA-512 crypt verifier")
        return hashed
    finally:
        # Python strings cannot be securely zeroized; keep the operation
        # local/offline and do not save raw password to disk, env or CLI.
        del first, repeat


def render_preseed(*, console_admin_crypted_password: str) -> str:
    """Debian Installer preseed; one reviewed disk, locked root and SSH off."""
    if (
        not isinstance(console_admin_crypted_password, str)
        or not _SHA512_CRYPT.fullmatch(console_admin_crypted_password)
    ):
        raise ValueError("salted SHA-512 crypt password verifier required")
    return "\n".join((
        "# SOFIA-WORKSHOP: reviewed offline Debian 13 Gen2 installer",
        "# CAUTION: this hashed administrator password remains in the ISO",
        "d-i debian-installer/locale string en_US.UTF-8",
        "d-i keyboard-configuration/xkb-keymap select us",
        "d-i netcfg/enable boolean false",
        "d-i netcfg/get_hostname string hephaestus",
        "d-i netcfg/get_domain string localdomain",
        "d-i mirror/http/proxy string",
        "d-i apt-setup/use_mirror boolean false",
        "d-i apt-setup/cdrom/set-first boolean true",
        "d-i clock-setup/utc boolean true",
        "d-i clock-setup/ntp boolean false",
        "d-i time/zone string America/Chicago",
        "d-i passwd/root-login boolean false",
        "d-i passwd/make-user boolean true",
        "d-i passwd/user-fullname string Hephaestus Console Administrator",
        "d-i passwd/username string sofia-admin",
        f"d-i passwd/user-password-crypted password {console_admin_crypted_password}",
        "d-i user-setup/allow-password-weak boolean false",
        "# Abort rather than choose an arbitrary disk if more than one exists.",
        "d-i partman/early_command string set -- $(list-devices disk); "
        'test "$#" -eq 1 || exit 1; debconf-set partman-auto/disk "$1"',
        "d-i partman-auto/method string regular",
        "d-i partman-auto/choose_recipe select atomic",
        "d-i partman-partitioning/default_label string gpt",
        "d-i partman-partitioning/choose_label select gpt",
        "d-i partman-lvm/device_remove_lvm boolean false",
        "d-i partman-md/device_remove_md boolean false",
        "d-i partman/confirm_write_new_label boolean true",
        "d-i partman/choose_partition select finish",
        "d-i partman/confirm boolean true",
        "d-i partman/confirm_nooverwrite boolean true",
        "d-i base-installer/kernel/image string linux-image-amd64",
        "tasksel tasksel/first multiselect standard",
        "d-i pkgsel/include string sudo",
        "d-i pkgsel/upgrade select none",
        "popularity-contest popularity-contest/participate boolean false",
        "d-i grub-installer/only_debian boolean true",
        "d-i grub-installer/with_other_os boolean false",
        "d-i grub-installer/bootdev string default",
        "d-i preseed/late_command string set -e; "
        "cp /cdrom/sofia-setup.sh /target/tmp/sofia-setup.sh; "
        "chmod 0700 /target/tmp/sofia-setup.sh; "
        "in-target /bin/sh /tmp/sofia-setup.sh; "
        "rm -f /target/tmp/sofia-setup.sh",
        "# Halt, do not automatically boot the still-mounted installer DVD again.",
        "d-i debian-installer/exit/halt boolean true",
        "d-i finish-install/reboot_in_progress note",
        "",
    ))


def render_first_boot_policy() -> str:
    """Fixed, password-free guest-hardening script, executed by d-i in-target."""
    return "\n".join((
        "#!/bin/sh",
        "set -eu",
        "test \"$(id -u sofia-admin)\" -ne 0",
        "test -x /usr/sbin/useradd",
        "test -x /usr/sbin/usermod",
        "test -x /usr/bin/passwd",
        "test -x /usr/bin/sudo",
        "test -x /usr/bin/systemctl",
        "# Root may not provide an alternate remote authentication path.",
        "/usr/bin/passwd --lock root",
        "/usr/sbin/usermod -aG sudo sofia-admin",
        "test \"$(id -u sofia-admin)\" -ne 0",
        "test -z \"$(id -nG sofia-admin | tr ' ' '\\n' | grep -x root || :)\"",
        "if id sofia-worker >/dev/null 2>&1; then exit 1; fi",
        "/usr/sbin/useradd --system --user-group --create-home "
        "--home-dir /var/lib/sofia-worker --shell /usr/sbin/nologin sofia-worker",
        "/usr/bin/passwd --lock sofia-worker",
        "/bin/chmod 0700 /var/lib/sofia-worker",
        "test \"$(id -u sofia-worker)\" -ne 0",
        "test -z \"$(id -nG sofia-worker | tr ' ' '\\n' | grep -x sudo || :)\"",
        "# Any passwordless sudo rule means this guest failed secure bootstrap.",
        "if grep -ER 'NOPASSWD:' /etc/sudoers /etc/sudoers.d "
        ">/dev/null 2>&1; then exit 1; fi",
        "# Not installed at all, and masked if a future package adds it.",
        "if dpkg-query -W openssh-server >/dev/null 2>&1; then exit 1; fi",
        "/usr/bin/systemctl mask ssh.service sshd.service ssh.socket",
        "exit 0",
        "",
    ))


def _render_uefi_grub_config(original: str) -> str:
    if not isinstance(original, str) or not 100 <= len(original) <= 64_000:
        raise ValueError("unsupported Debian installer GRUB configuration")
    if not (_GRUB_LINUX.search(original) and _GRUB_INITRD.search(original)):
        raise ValueError(
            "source ISO lacks expected Debian Installer amd64 kernel/initrd; "
            "refusing a guess at UEFI boot configuration"
        )
    entry = "\n".join((
        "# Dedicated one-time reviewed offline unattended boot; always first.",
        "menuentry 'Hephaestus approved unattended Debian install' {",
        f"    linux /install.amd/vmlinuz {BOOT_PARAMETERS}",
        "    initrd /install.amd/initrd.gz",
        "}",
    ))
    return (
        "set default=0\nset timeout=5\n" + entry + "\n"
        + original + "\nset default=0\nset timeout=5\n"
    )


def _private_write(path: Path, data: str) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(data)


def prepare_offline_debian_installer(
    *, source_iso: Path | str, expected_source_sha256: str,
    output_iso: Path | str,
    signing_key_file: Path | str,
) -> PreparedOfflineInstaller:
    """Owner-invoked ISO builder; never initiates Hyper-V/guest actions."""
    if platform.system() != "Linux":
        raise EnvironmentError(
            "use a local Linux or WSL environment with xorriso and openssl"
        )
    from sofia.ops.workshop_media_attestation import sign_prepared_media
    if not isinstance(signing_key_file,(str,Path)) or not str(signing_key_file):
        raise PermissionError("local encrypted owner signing key is required")
    source = Path(source_iso).resolve(strict=True)
    output = Path(output_iso).resolve(strict=False)
    if (
        not source.is_file()
        or not _DEBIAN_DVD_NAME.fullmatch(source.name)
        or not _DIGEST.fullmatch(expected_source_sha256)
    ):
        raise ValueError(
            "independently SHA-256 reviewed Debian 13 amd64 DVD-1 is required"
        )
    if source == output or output.exists():
        raise FileExistsError("output must be a fresh ISO, never replace source/media")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("reviewed existing local output directory required")
    if any((parent / ".git").exists() for parent in (output.parent, *output.parents)):
        raise PermissionError("never save credential-bearing media inside a Git checkout")
    if not shutil.which("xorriso") or not shutil.which("openssl"):
        raise EnvironmentError("xorriso and openssl required; never download tools automatically")
    if source.stat().st_size < 1_000_000_000:
        raise ValueError("offline DVD-1 source unexpectedly small; netinst media denied")
    if _sha256_file(source) != expected_source_sha256:
        raise PermissionError("source Debian DVD content differs from reviewed SHA-256")

    previous_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix=".hephaestus-iso-", dir=output.parent) as tdir:
            workspace=Path(tdir)
            grub=workspace / "original.grub.cfg"
            _run(
                ["xorriso", "-osirrox", "on", "-indev", str(source),
                 "-extract", "/boot/grub/grub.cfg", str(grub)],
                timeout=120,
            )
            original=grub.read_text(encoding="utf-8")
            modified=_render_uefi_grub_config(original)
            _private_write(workspace/"grub.cfg", modified)
            # Only now ask for the password, after source validation passed.
            password_hash=_hash_admin_password()
            _private_write(
                workspace/"preseed.cfg",
                render_preseed(console_admin_crypted_password=password_hash),
            )
            _private_write(workspace/"sofia-setup.sh", render_first_boot_policy())
            generated=workspace/"prepared.iso"
            _run(
                ["xorriso", "-indev", str(source), "-outdev", str(generated),
                 "-map", str(workspace/"preseed.cfg"), "/preseed.cfg",
                 "-map", str(workspace/"sofia-setup.sh"), "/sofia-setup.sh",
                 "-map", str(workspace/"grub.cfg"), "/boot/grub/grub.cfg",
                 "-boot_image", "any", "replay"],
                timeout=900,
            )
            # Verify the output's UEFI boot descriptor and embedded preseed.
            boot_report=_run(
                ["xorriso", "-indev", str(generated),
                 "-report_el_torito", "plain"], timeout=120,
            )
            if not re.search(r"UEFI|EFI", boot_report, flags=re.IGNORECASE):
                raise RuntimeError("remastered Debian ISO has no verified EFI boot image")
            extracted=workspace/"verify-preseed.cfg"
            _run(
                ["xorriso", "-osirrox", "on", "-indev", str(generated),
                 "-extract", "/preseed.cfg", str(extracted)], timeout=120,
            )
            if _sha256_file(extracted) != _sha256_file(workspace/"preseed.cfg"):
                raise RuntimeError("remastered installer preseed did not verify")
            confirmed=workspace/"verify-grub.cfg"
            _run(
                ["xorriso", "-osirrox", "on", "-indev", str(generated),
                 "-extract", "/boot/grub/grub.cfg", str(confirmed)], timeout=120,
            )
            if confirmed.read_text(encoding="utf-8") != modified:
                raise RuntimeError("UEFI GRUB automatic-install entry changed")
            media_digest=_sha256_file(generated)
            os.chmod(generated, 0o600)
            # Same-filesystem exclusive link does not overwrite existing output.
            os.link(generated, output)
            try:
                signed=sign_prepared_media(
                    iso_path=output,
                    base_sha256=expected_source_sha256,
                    signing_key_file=signing_key_file,
                )
            except Exception:
                # Unattested output must not be mistaken for boot-ready media.
                output.unlink(missing_ok=True)
                raise
            return PreparedOfflineInstaller(
                media_path=str(output),
                media_sha256=media_digest,
                reviewed_debian_source_sha256=expected_source_sha256,
                policy_version=MEDIA_POLICY_VERSION,
                owner_signed=True,
                manifest_path=signed["manifest_path"],
            )
    finally:
        os.umask(previous_umask)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-iso",required=True,type=Path)
    parser.add_argument("--source-sha256",required=True)
    parser.add_argument("--output-iso",required=True,type=Path)
    parser.add_argument("--signing-key-file",required=True,type=Path,
                        help="Local owner encrypted Ed25519 private key; never copy to Artemis")
    args=parser.parse_args(argv)
    result=prepare_offline_debian_installer(
        source_iso=args.source_iso,
        expected_source_sha256=args.source_sha256,
        output_iso=args.output_iso,
        signing_key_file=args.signing_key_file,
    )
    print(json.dumps({
        "media_path":result.media_path,
        "media_sha256":result.media_sha256,
        "source_sha256":result.reviewed_debian_source_sha256,
        "policy":result.policy_version,
        "owner_signed":result.owner_signed,
        "signed_manifest_path":result.manifest_path,
        "guest_admin":result.guest_admin,
        "guest_worker":result.worker,
        "initial_ssh_enabled":False,
        "passwordless_sudo":False,
        "root_login_enabled":False,
        "contains_password_verifier":True,
        "guest_os_installed":False,
        "note":"Private ISO contains a salted administrator password hash. "
               "Never commit/upload this media. Copy under Artemis' "
               "host-approved offline media root and review its SHA-256.",
    },sort_keys=True,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
