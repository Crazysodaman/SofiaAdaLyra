"""A service singleton lock must not follow attacker-created temp-file links."""
import os
from uuid import uuid4

import pytest

from sofia.platform.run.process_lock import StateProcessLock


def test_redirected_lock_is_refused_without_modifying_target(tmp_path):
    lock = StateProcessLock(tmp_path/str(uuid4()), resource='platform-service')
    target = tmp_path/'untouched'
    target.write_bytes(b'')
    if os.name == 'nt':
        os.link(target, lock.path)
    else:
        lock.path.symlink_to(target)
    try:
        with pytest.raises((PermissionError, OSError)):
            lock.acquire()
        assert target.read_bytes() == b''
    finally:
        lock.release()
        lock.path.unlink()


def test_foreign_readable_existing_lock_is_refused(tmp_path):
    lock = StateProcessLock(tmp_path/str(uuid4()), resource='platform-service')
    lock.path.write_bytes(b'0')
    if os.name == 'nt':
        import win32con
        import win32security
        from sofia.platform.state.private_file import restrict_new_owner_private_path
        restrict_new_owner_private_path(lock.path, directory=False)
        descriptor = win32security.GetFileSecurity(str(lock.path), win32security.DACL_SECURITY_INFORMATION)
        acl = descriptor.GetSecurityDescriptorDacl()
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_READ,
            win32security.CreateWellKnownSid(win32security.WinWorldSid, None))
        descriptor.SetSecurityDescriptorDacl(1, acl, 0)
        win32security.SetFileSecurity(str(lock.path), win32security.DACL_SECURITY_INFORMATION, descriptor)
    else:
        lock.path.chmod(0o644)
    try:
        with pytest.raises(PermissionError):
            lock.acquire()
    finally:
        lock.release()
        lock.path.unlink()
