"""Cross-platform owner-private JSON/text persistence primitives.

POSIX mode bits are not a Windows confidentiality check.  These helpers use
the native DACL on Windows and fail closed when it cannot be inspected.  They
also reject filesystem redirection before and immediately before publication.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile


def _is_redirect(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def assert_no_redirected_components(path: Path, *, include_leaf: bool) -> None:
    """Reject symlink/junction components without resolving away evidence."""
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError("private state path must be absolute")
    parts = (candidate, *candidate.parents) if include_leaf else candidate.parents
    for component in parts:
        # A broken symlink is still redirection even though exists() is false.
        if _is_redirect(component):
            raise PermissionError("private state path contains filesystem redirection")


def assert_owner_private_path(path: Path, *, directory: bool) -> None:
    """Require owner-only POSIX access or an equivalent Windows DACL.

    On Windows the descriptor owner must be the process token user or the
    token's designated default owner (``TokenOwner``); an OWNER RIGHTS ACE
    counts as an explicit grant to the verified owner.
    """
    candidate = Path(path)
    assert_no_redirected_components(candidate, include_leaf=True)
    if directory:
        if not candidate.is_dir():
            raise PermissionError("private state directory is unavailable")
    elif not candidate.is_file():
        raise PermissionError("private state file is unavailable")
    if os.name != "nt":
        if candidate.stat().st_mode & 0o077:
            raise PermissionError(
                "private state permissions are too broad (group/world accessible)"
            )
        return
    try:
        import win32api
        import win32con
        import win32security

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
        )
        owner_sid, _ = win32security.GetTokenInformation(
            token, win32security.TokenUser,
        )
        owner = win32security.ConvertSidToStringSid(owner_sid)
        default_owner_sid = win32security.GetTokenInformation(
            token, win32security.TokenOwner,
        )
        acceptable_owners = {owner}
        if default_owner_sid is not None:
            acceptable_owners.add(
                win32security.ConvertSidToStringSid(default_owner_sid)
            )
        descriptor = win32security.GetFileSecurity(
            str(candidate), win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION,
        )
        actual_owner = descriptor.GetSecurityDescriptorOwner()
        if actual_owner is None or win32security.ConvertSidToStringSid(
            actual_owner
        ) not in acceptable_owners:
            raise PermissionError("private state belongs to another Windows identity")
        dacl = descriptor.GetSecurityDescriptorDacl()
        if dacl is None:
            raise PermissionError("private state has an unrestricted NULL DACL")
        allowed = {owner, "S-1-5-18", "S-1-5-32-544", "S-1-3-4"}
        # Owner presence is not enough: READ_CONTROL, WRITE_DAC, and
        # inheritance-only ACEs do not grant data access on THIS object.
        # This is a necessary ACL permission check, not a substitute for a
        # separately witnessed Windows token effective-access audit.
        owner_read = False
        owner_write = False
        # NT file access masks: FILE_READ_DATA/FILE_LIST_DIRECTORY = 0x1,
        # FILE_WRITE_DATA/FILE_ADD_FILE = 0x2. pywin32's win32con does not
        # export these FILE_* constants on every supported Windows wheel.
        read_bits = win32con.GENERIC_ALL | win32con.GENERIC_READ | 0x0001
        write_bits = win32con.GENERIC_ALL | win32con.GENERIC_WRITE | 0x0002
        for index in range(dacl.GetAceCount()):
            ace = dacl.GetAce(index)
            ace_type, ace_flags = ace[0]
            mask = int(ace[1])
            principal = win32security.ConvertSidToStringSid(ace[2])
            owner_principal = principal in (owner, "S-1-3-4")
            if ace_type in (
                win32security.ACCESS_DENIED_ACE_TYPE,
                win32security.ACCESS_DENIED_OBJECT_ACE_TYPE,
            ) and owner_principal and not (
                ace_flags & win32security.INHERIT_ONLY_ACE
            ):
                raise PermissionError("private Windows state denies owner access")
            if ace_type in (
                win32security.ACCESS_ALLOWED_ACE_TYPE,
                win32security.ACCESS_ALLOWED_OBJECT_ACE_TYPE,
            ) and mask:
                if principal not in allowed:
                    raise PermissionError(
                        "private Windows state has an unauthorized ACL reader"
                    )
                if owner_principal and not (
                    ace_flags & win32security.INHERIT_ONLY_ACE
                ):
                    owner_read |= bool(mask & read_bits)
                    owner_write |= bool(mask & write_bits)
        if not (owner_read and owner_write):
            raise PermissionError("private Windows state has no owner ACL (read/write access required)")
    except ImportError as exc:
        raise PermissionError("Windows ACL inspection dependency unavailable") from exc
    except PermissionError:
        raise
    except Exception as exc:
        raise PermissionError("unable to verify private Windows state ACL") from exc


def restrict_new_owner_private_path(path: Path, *, directory: bool) -> None:
    if os.name != "nt":
        return
    try:
        import win32api
        import win32con
        import win32security

        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
        )
        owner_sid, _ = win32security.GetTokenInformation(
            token, win32security.TokenUser,
        )
        acl = win32security.ACL()
        inheritance = (
            win32con.CONTAINER_INHERIT_ACE | win32con.OBJECT_INHERIT_ACE
            if directory else 0
        )
        acl.AddAccessAllowedAceEx(
            win32security.ACL_REVISION, inheritance,
            win32con.GENERIC_ALL, owner_sid,
        )
        acl.AddAccessAllowedAceEx(
            win32security.ACL_REVISION, inheritance,
            win32con.GENERIC_ALL,
            win32security.ConvertStringSidToSid("S-1-5-18"),
        )
        descriptor = win32security.GetFileSecurity(
            str(path), win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION,
        )
        descriptor.SetSecurityDescriptorOwner(owner_sid, False)
        descriptor.SetSecurityDescriptorDacl(1, acl, 0)
        descriptor.SetSecurityDescriptorControl(
            win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED,
        )
        win32security.SetFileSecurity(
            str(path), win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION, descriptor,
        )
        assert_owner_private_path(path, directory=directory)
    except Exception as exc:
        raise PermissionError("cannot secure private Windows state") from exc


def ensure_owner_private_directory(path: Path) -> None:
    directory = Path(path)
    assert_no_redirected_components(directory, include_leaf=True)
    existed = directory.exists()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    assert_no_redirected_components(directory, include_leaf=True)
    if not existed:
        if os.name == "nt":
            restrict_new_owner_private_path(directory, directory=True)
        else:
            directory.chmod(0o700)
    assert_owner_private_path(directory, directory=True)


def atomic_write_private_text(
    path: Path, content: str, *, encoding: str = "utf-8",
) -> None:
    """Publish text atomically without first exposing a broad Windows temp."""
    target = Path(path)
    ensure_owner_private_directory(target.parent)
    if target.exists():
        assert_owner_private_path(target, directory=False)
    else:
        assert_no_redirected_components(target, include_leaf=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        if os.name == "nt":
            restrict_new_owner_private_path(temporary, directory=False)
        else:
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding=encoding, newline="") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        ensure_owner_private_directory(target.parent)
        if target.exists():
            assert_owner_private_path(target, directory=False)
        else:
            assert_no_redirected_components(target, include_leaf=True)
        os.replace(temporary, target)
        assert_owner_private_path(target, directory=False)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink(missing_ok=True)
