"""Host-privileged, fixed-purpose Hyper-V VM observation via protected local snapshot.

Architecture: a separately installed SYSTEM scheduled task performs exactly one
read-only Sofia VM inventory and atomically publishes a bounded snapshot into
an administrator-owned directory. The always-running LocalService controller
may READ this file but must not receive Hyper-V Administrators membership.

Filesystem integrity depends on independent administrator/SYSTEM-only write
ACLs on the directory and code. This is *monitoring only*, never migration,
writer fencing, guest attestation, or VM mutation authority.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from typing import Any, Callable, Mapping
from uuid import UUID

from sofia.ops.artemis_controller import (
    ArtemisControllerConfig, ArtemisControllerError, observe_exact_sofia,
    _safe_existing_directory,
)

_SNAPSHOT_NAME = "sofia-host-vm-observation.json"
_MAX_BYTES = 8192
_MAX_AGE = timedelta(seconds=180)
_FUTURE_TOLERANCE = timedelta(seconds=15)
_SOURCE = "artemis_pinned_hyperv_readonly_export"


def _snapshot_path(config: ArtemisControllerConfig) -> Path:
    root = config.audit_directory.parent
    _safe_existing_directory(root)
    if root.name.casefold() != "artemiscontroller":
        raise ArtemisControllerError("unexpected Artemis controller root")
    return root / _SNAPSHOT_NAME


def _verify_system_account() -> None:
    """Only fixed-task LocalSystem may produce an authoritative host snapshot."""
    if sys.platform != "win32":
        raise ArtemisControllerError("host observer requires Windows")
    try:
        result = subprocess.run(
            ["whoami.exe", "/user", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        rows = list(csv.reader(result.stdout.splitlines()))
    except (OSError, subprocess.SubprocessError, UnicodeError, csv.Error) as exc:
        raise ArtemisControllerError("SYSTEM identity could not be established") from exc
    if len(rows) != 1 or len(rows[0]) < 2 or rows[0][1].casefold() != "s-1-5-18":
        raise ArtemisControllerError("only NT AUTHORITY SYSTEM may export host snapshot")


def export_snapshot(
    config: ArtemisControllerConfig,
    *,
    inventory: Callable[[], Mapping[str, Any]] | None = None,
    hostname: Callable[[], str] = socket.gethostname,
    require_system: Callable[[], None] = _verify_system_account,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, Any]:
    if hostname().casefold().split(".")[0] != "artemis":
        raise ArtemisControllerError("host export only permitted on Artemis")
    require_system()
    if inventory is None:
        from sofia.integrations.hyperv import HyperVAdapter
        inventory = HyperVAdapter().sofia_guest_inventory
    observed = now()
    if observed.tzinfo is None:
        raise ArtemisControllerError("host timestamp must be timezone-aware")
    # Verify full host inventory before publishing any VM state evidence.
    report = inventory()
    check = observe_exact_sofia(
        config, inventory=lambda: report, hostname=hostname, now=lambda: observed
    )
    if check.outcome == "unavailable" or check.observed_vm_id is None:
        raise ArtemisControllerError("pinned host Hyper-V inventory failed verification")
    path = _snapshot_path(config)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ArtemisControllerError("host snapshot path redirection refused")
    payload: dict[str, Any] = {
        "schema": 1, "source": _SOURCE, "host": "Artemis",
        "vm_id": check.observed_vm_id,
        "name": config.vm_name, "state": check.vm_state,
        "observed_at": observed.astimezone(timezone.utc).isoformat(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > _MAX_BYTES:
        raise ArtemisControllerError("host snapshot exceeds bound")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".sofia-host-vm-", suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return payload


class ArtemisHostSnapshotObserver:
    """LocalService read-only consumer, never a privileged Hyper-V actor."""

    def __init__(
        self, *, config: ArtemisControllerConfig,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.config = config
        self.now = now

    def __call__(self) -> Mapping[str, Any]:
        path = _snapshot_path(self.config)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
            raise ArtemisControllerError("host_snapshot_missing_or_untrusted")
        raw = path.read_bytes()
        if len(raw) > _MAX_BYTES:
            raise ArtemisControllerError("host_snapshot_oversized")
        try:
            snapshot = json.loads(raw)
        except (UnicodeError, TypeError, ValueError) as exc:
            raise ArtemisControllerError("host_snapshot_unparseable") from exc
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "schema", "source", "host", "vm_id", "name", "state", "observed_at",
        }:
            raise ArtemisControllerError("host_snapshot_schema_invalid")
        if (
            type(snapshot["schema"]) is not int or snapshot["schema"] != 1
            or snapshot["source"] != _SOURCE
            or snapshot["host"] != "Artemis"
            or snapshot["name"] != self.config.vm_name
        ):
            raise ArtemisControllerError("host_snapshot_source_untrusted")
        try:
            pinned = str(UUID(snapshot["vm_id"]))
            observed = datetime.fromisoformat(snapshot["observed_at"])
        except (ValueError, TypeError, AttributeError) as exc:
            raise ArtemisControllerError("host_snapshot_identity_or_time_invalid") from exc
        if pinned != str(self.config.expected_vm_id):
            raise ArtemisControllerError("host_snapshot_wrong_vm")
        current = self.now()
        if current.tzinfo is None or observed.tzinfo is None:
            raise ArtemisControllerError("host_snapshot_time_zone_missing")
        age = current.astimezone(timezone.utc) - observed.astimezone(timezone.utc)
        if age > _MAX_AGE or age < -_FUTURE_TOLERANCE:
            raise ArtemisControllerError("host_snapshot_stale_or_future")
        state = snapshot["state"]
        if not isinstance(state, str) or not 0 < len(state) <= 32:
            raise ArtemisControllerError("host_snapshot_vm_state_invalid")
        return {
            "host_inventory": {"VmId": pinned, "Name": self.config.vm_name, "State": state},
            "read_only_review": {
                "inventory_eligible_for_review": False,
                "host_blockers": [
                    "privileged_snapshot_only",
                    "live_guest_os_and_writer_state_unverified",
                ],
                "may_activate_canonical_writer": False,
            },
            "canonical_writer_active": "unverified",
            "guest_os_installed": "unverified",
            "activation_authorized": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Artemis SYSTEM-only fixed Hyper-V read-only observation")
    parser.add_argument("action", choices=("export",))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if sys.platform != "win32":
            raise ArtemisControllerError("Windows Artemis host required")
        config = ArtemisControllerConfig.load(args.config)
        result = export_snapshot(config)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, ArtemisControllerError) as exc:
        print(f"Artemis snapshot refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
