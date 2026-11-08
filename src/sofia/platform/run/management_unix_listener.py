"""Explicit, service-owned Linux AF_UNIX management listener.

A listener is never started by importing this module. The owning Platform
service must explicitly construct it with its current, SAFE-backed dispatcher;
OS credentials establish peer provenance, NOT enrollment or permission.
No Core startup, settings mutation, privileged management, or remote access.
Windows fails closed until a reviewed named-pipe token implementation exists.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import stat
import sys
from threading import Event

from sofia.platform.run.local_peer import dispatch_one_kernel_peer_read
from sofia.platform.state.private_file import assert_owner_private_path


class ManagementUnixListener:
    """One OS-owned socket, one bounded authenticated read per connection.

    The injected dispatcher is not a user option. Production composition MUST
    use current Platform identity/lease/STOP and live enrollment both before
    and after each read. A kernel UID alone never authorizes an observation.
    """

    def __init__(
        self,
        path: Path,
        *,
        dispatch: Callable[..., Mapping[str, object]],
    ) -> None:
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("absolute management socket Path required")
        if not callable(dispatch):
            raise TypeError("service-owned dispatcher required")
        self.path = path
        self._dispatch = dispatch
        self._listener: socket.socket | None = None
        self._owned_inode: tuple[int, int] | None = None

    def open(self) -> "ManagementUnixListener":
        if self._listener is not None:
            raise RuntimeError("management listener already open")
        if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
            raise PermissionError("Linux kernel-authenticated management required")
        if len(os.fsencode(str(self.path))) > 100:
            raise ValueError("management socket path exceeds safe AF_UNIX bound")
        assert_owner_private_path(self.path.parent, directory=True)
        if self.path.parent.stat().st_uid != os.geteuid():
            raise PermissionError("management socket directory belongs to another user")
        if os.path.lexists(self.path):
            raise PermissionError("management socket path already occupied")

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        bound_identity: tuple[int, int] | None = None
        # The parent is 0700 as well. The restrictive umask prevents a
        # bind-to-chmod exposure window; do not touch an existing endpoint.
        prior_umask = os.umask(0o077)
        try:
            listener.bind(str(self.path))
            info = os.lstat(self.path)
            bound_identity = (info.st_dev, info.st_ino)
            os.chmod(self.path, 0o600)
            info = os.lstat(self.path)
            if (
                not stat.S_ISSOCK(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
            ):
                raise PermissionError("management socket mode or owner unsafe")
            listener.listen(8)
            listener.settimeout(0.2)
            self._owned_inode = (info.st_dev, info.st_ino)
            self._listener = listener
            return self
        except BaseException:
            listener.close()
            if bound_identity is not None:
                # Only this bind's inode may be cleaned up. A substituted
                # socket from another service must never be unlinked.
                try:
                    info = os.lstat(self.path)
                    if (stat.S_ISSOCK(info.st_mode)
                            and (info.st_dev, info.st_ino) == bound_identity):
                        os.unlink(self.path)
                except FileNotFoundError:
                    pass
            raise
        finally:
            os.umask(prior_umask)

    def _require_owned_endpoint(self) -> None:
        if self._listener is None or self._owned_inode is None:
            raise RuntimeError("management listener not active")
        info = os.lstat(self.path)
        if (
            not stat.S_ISSOCK(info.st_mode)
            or (info.st_dev, info.st_ino) != self._owned_inode
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
        ):
            raise PermissionError("management endpoint replaced or unsafe")

    def serve_once(self) -> bool:
        """Process at most one client; refusals never disclose exception text."""
        self._require_owned_endpoint()
        assert self._listener is not None
        try:
            connection, _ = self._listener.accept()
        except socket.timeout:
            return False
        with connection:
            try:
                self._require_owned_endpoint()
                # Resolve time AFTER bounded intake, not at accept; caller
                # supplied request deadlines cannot outlive the actual read.
                dispatch_one_kernel_peer_read(
                    connection, dispatch=self._dispatch,
                    now=lambda: datetime.now(timezone.utc),
                )
            except (PermissionError, ValueError, TimeoutError, OSError):
                return False
        return True

    def serve_until(self, stop: Event) -> None:
        """Explicit caller-owned loop; a STOP must also be read by dispatch."""
        if not isinstance(stop, Event):
            raise TypeError("threading.Event required")
        while not stop.is_set():
            try:
                self.serve_once()
            except OSError:
                if stop.is_set() or self._listener is None:
                    return
                raise

    def close(self) -> None:
        listener, owned = self._listener, self._owned_inode
        self._listener = None
        self._owned_inode = None
        if listener is not None:
            listener.close()
        if owned is not None:
            try:
                info = os.lstat(self.path)
            except FileNotFoundError:
                return
            if stat.S_ISSOCK(info.st_mode) and (info.st_dev, info.st_ino) == owned:
                os.unlink(self.path)

    def __enter__(self) -> "ManagementUnixListener":
        return self.open()

    def __exit__(self, *_: object) -> None:
        self.close()
