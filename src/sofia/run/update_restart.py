"""Detect an activated release change and apply the owner's restart policy."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.run.active_release import ActiveRelease
from sofia.ui.notifications import DesktopNotificationStore


class UpdateRestartAction(str, Enum):
    NONE = "none"
    AUTOMATIC_RESTART = "automatic_restart"
    ASK_OWNER = "ask_owner"


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    release_id: str
    manifest_sha256: str

    @classmethod
    def from_release(cls, release: ActiveRelease | None):
        if release is None:
            return None
        return cls(release.release_id, release.manifest_sha256)


class ActiveReleaseChangeMonitor:
    """Compare authoritative release identity without treating mtime as proof."""

    def __init__(self, current: ActiveRelease | None) -> None:
        self.current = ReleaseIdentity.from_release(current)
        self._requested: set[ReleaseIdentity] = set()

    def evaluate(
        self,
        observed: ActiveRelease | None,
        *,
        mode: str,
    ) -> UpdateRestartAction:
        if mode not in {"automatic", "ask"}:
            raise ValueError("update restart mode must be automatic or ask")
        identity = ReleaseIdentity.from_release(observed)
        if identity is None or identity == self.current:
            return UpdateRestartAction.NONE
        if mode == "automatic":
            return UpdateRestartAction.AUTOMATIC_RESTART
        if identity in self._requested:
            return UpdateRestartAction.NONE
        self._requested.add(identity)
        return UpdateRestartAction.ASK_OWNER


def configured_update_restart_mode(state_path: Path) -> str:
    return RuntimeUserSettingsStore(state_path).load().update_restart_mode


def queue_update_restart_request(
    state_path: Path,
    release: ActiveRelease,
    *,
    now: datetime,
) -> None:
    DesktopNotificationStore(state_path).enqueue(
        notification_id=(
            f"runtime-update:{release.release_id}:{release.manifest_sha256}"
        ),
        title="Sofía update ready",
        content=(
            f"Update {release.release_id} is installed and ready. "
            "Restart Sofía from the tray when you’re ready."
        ),
        created_at=now,
    )
