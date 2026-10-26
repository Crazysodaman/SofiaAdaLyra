"""Profile-scoped UI ownership using RUN's shared OS-backed process lock."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.state.atomic_file import atomic_write_text


class TrayProcessAlreadyRunning(RuntimeError):
    pass


class DesktopProcessAlreadyRunning(RuntimeError):
    pass


class SettingsProcessAlreadyRunning(RuntimeError):
    pass


def core_link_profile_anchor(
    binding_store_path: str | Path, binding_id: str,
) -> Path:
    """Return a stable local lock anchor without opening canonical state."""
    if not isinstance(binding_id, str) or not binding_id.strip() or len(binding_id) > 160:
        raise ValueError("binding_id must be bounded text")
    store = Path(binding_store_path)
    if not store.is_absolute():
        raise ValueError("binding store path must be absolute")
    from hashlib import sha256

    suffix = sha256(binding_id.encode("utf-8")).hexdigest()[:24]
    return store.parent / f"client-profile-{suffix}"


class TrayProcessLock(StateProcessLock):
    def __init__(self, profile_anchor):
        super().__init__(
            profile_anchor, resource="tray", owner_label="tray agent",
            duplicate_error=TrayProcessAlreadyRunning,
        )


class DesktopProcessLock(StateProcessLock):
    def __init__(self, profile_anchor):
        super().__init__(
            profile_anchor, resource="desktop", owner_label="desktop client",
            duplicate_error=DesktopProcessAlreadyRunning,
        )


class SettingsProcessLock(StateProcessLock):
    def __init__(self, profile_anchor):
        super().__init__(
            profile_anchor, resource="settings", owner_label="settings client",
            duplicate_error=SettingsProcessAlreadyRunning,
        )


class DesktopAttentionMailbox:
    """Inert same-user request asking an existing desktop to show itself."""

    def __init__(self, lock: DesktopProcessLock) -> None:
        if not isinstance(lock, DesktopProcessLock):
            raise TypeError("DesktopProcessLock required")
        self.path = lock.path.with_suffix(".attention.json")

    def request(self, *, at: datetime | None = None) -> None:
        moment = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        atomic_write_text(self.path, json.dumps({
            "schema": "companion.ui.desktop_attention.v1",
            "requester_pid": os.getpid(),
            "requested_at": moment.isoformat(),
        }, sort_keys=True) + "\n")
        if os.name != "nt":
            self.path.chmod(0o600)

    def consume(self, *, now: datetime | None = None) -> bool:
        if not self.path.exists():
            return False
        if self.path.is_symlink() or not self.path.is_file():
            raise PermissionError("desktop attention mailbox must be a regular file")
        if os.name != "nt" and self.path.stat().st_mode & 0o077:
            raise PermissionError("desktop attention mailbox permissions are unsafe")
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) != {
                "schema", "requester_pid", "requested_at",
            }:
                raise ValueError("attention request has unexpected fields")
            if payload["schema"] != "companion.ui.desktop_attention.v1":
                raise ValueError("attention request schema is unsupported")
            if type(payload["requester_pid"]) is not int or payload["requester_pid"] < 1:
                raise ValueError("attention requester PID is invalid")
            requested = datetime.fromisoformat(payload["requested_at"])
            if requested.tzinfo is None:
                raise ValueError("attention request timestamp must be aware")
            age = (moment - requested.astimezone(timezone.utc)).total_seconds()
            return 0 <= age <= 60
        finally:
            self.path.unlink(missing_ok=True)
