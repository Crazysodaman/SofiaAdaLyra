"""Artemis-host independent Sofia VM observation and tamper-evident journal.

The controller does not import the canonical application, touch sofia.db,
restart services, stop VMs or mint writer epochs. It runs on the Hyper-V HOST,
under an independently configured non-administrator Windows service identity.
Its receipts are useful for supervised preflight, NEVER writer-fence proof.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sys
from threading import Event
from typing import Any, Callable, Iterator, Mapping
from uuid import UUID


_MAX_JOURNAL_BYTES = 64 * 1024 * 1024
_MAX_RECEIPT_BYTES = 8192
_GENESIS = "0" * 64


class ArtemisControllerError(RuntimeError):
    """Independent host admission, observation or journal integrity failure."""


def _safe_existing_directory(path: Path) -> None:
    if not isinstance(path, Path) or not path.is_absolute():
        raise ArtemisControllerError("controller audit directory must be absolute")
    if not path.is_dir():
        raise ArtemisControllerError("controller audit directory must exist without redirection")
    if os.name == "nt" and str(path).startswith("\\\\"):
        raise ArtemisControllerError("controller audit directory must be host-local, not UNC")
    junction = getattr(os.path, "isjunction", None)
    # A junction/symlink in ANY ancestor can redirect an ostensibly local log.
    for entry in (path, *path.parents):
        if entry.is_symlink() or (callable(junction) and junction(entry)):
            raise ArtemisControllerError("controller audit path redirection is forbidden")


@dataclass(frozen=True, slots=True)
class ArtemisControllerConfig:
    """Root-controlled configuration for *one* exact Sofia Hyper-V guest."""

    expected_vm_id: UUID
    audit_directory: Path
    poll_seconds: int = 60
    expected_host: str = "Artemis"
    vm_name: str = "Sofia"

    def __post_init__(self) -> None:
        if not isinstance(self.expected_vm_id, UUID):
            raise TypeError("exact independently inventoried VM UUID is required")
        if self.expected_host.casefold() != "artemis" or self.vm_name != "Sofia":
            raise ArtemisControllerError("controller is restricted to Artemis / Sofia")
        if type(self.poll_seconds) is not int or not 30 <= self.poll_seconds <= 3600:
            raise ValueError("controller poll interval must be 30..3600 seconds")
        _safe_existing_directory(self.audit_directory)

    @classmethod
    def load(cls, path: Path) -> "ArtemisControllerConfig":
        if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
            raise ArtemisControllerError("existing non-redirected controller config required")
        if path.stat().st_size > 8192:
            raise ArtemisControllerError("controller configuration exceeds allowed size")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ArtemisControllerError("controller configuration is invalid") from exc
        if not isinstance(raw, dict) or set(raw) != {
            "schema", "expected_host", "vm_name", "expected_vm_id",
            "audit_directory", "poll_seconds",
        }:
            raise ArtemisControllerError("exact controller schema required; no implicit authority")
        if type(raw["schema"]) is not int or raw["schema"] != 1:
            raise ArtemisControllerError("unsupported controller schema")
        if not isinstance(raw["expected_host"], str) or not isinstance(raw["vm_name"], str):
            raise ArtemisControllerError("invalid host or VM identity")
        try:
            vm_id = UUID(raw["expected_vm_id"])
        except (ValueError, TypeError, AttributeError) as exc:
            raise ArtemisControllerError("independently verified VM UUID required") from exc
        if not isinstance(raw["audit_directory"], str):
            raise ArtemisControllerError("audit directory must be text")
        return cls(
            expected_vm_id=vm_id,
            expected_host=raw["expected_host"],
            vm_name=raw["vm_name"],
            audit_directory=Path(raw["audit_directory"]),
            poll_seconds=raw["poll_seconds"],
        )


@dataclass(frozen=True, slots=True)
class ControllerObservation:
    """Host metadata ONLY. These fields convey no database-writer authority."""

    outcome: str
    observed_vm_id: str | None
    vm_state: str | None
    blockers: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.outcome not in {"observed", "requires_review", "unavailable"}:
            raise ValueError("unrecognized controller observation outcome")
        if self.observed_at.tzinfo is None:
            raise ValueError("timestamp must be timezone aware")

    def payload(self) -> dict[str, Any]:
        return {
            "event": "hyperv.sofia.observe",
            "outcome": self.outcome,
            "vm_id": self.observed_vm_id,
            "vm_state": self.vm_state,
            "blockers": list(self.blockers),
            "observed_at": self.observed_at.astimezone(timezone.utc).isoformat(),
            "canonical_writer_verified": False,
            "guest_os_verified": False,
            "old_writer_fenced": False,
            "migration_authorized": False,
            "host_change_performed": False,
        }


def _hyperv_failure_code(exc: Exception) -> str:
    """Expose bounded diagnostic categories, never raw host stderr/secrets."""
    message = str(exc).casefold()[:4096]
    if any(fragment in message for fragment in (
        "access is denied", "access denied", "permission denied",
        "unauthorizedaccess", "0x80070005", "e_accessdenied",
    )):
        category = "permission_denied"
    elif any(fragment in message for fragment in (
        "not recognized as the name", "commandnotfoundexception",
        "module could not be loaded", "cannot find module",
    )):
        category = "powershell_hyperv_cmdlet_unavailable"
    elif any(fragment in message for fragment in (
        "rpc server is unavailable", "0x800706ba",
        "virtual machine management service is not running",
    )):
        category = "hyperv_management_service_unavailable"
    elif "cannot find" in message or "not found" in message:
        category = "hyperv_object_unavailable"
    else:
        category = "hyperv_inventory_failed"
    # Cmdlet tags identify the failing stage only if PowerShell reported it.
    stages = (
        ("get-vmharddiskdrive", "disk_inventory"),
        ("get-vhd", "vhd_metadata"),
        ("get-vmnetworkadapter", "vm_network"),
        ("get-vmswitch", "switch_metadata"),
        ("get-vmdvddrive", "dvd_metadata"),
        ("get-vm", "vm_inventory"),
    )
    stage = next((tag for cmdlet, tag in stages if cmdlet in message), "unspecified")
    return f"{stage}_{category}"


def observe_exact_sofia(
    config: ArtemisControllerConfig,
    *,
    inventory: Callable[[], Mapping[str, Any]],
    hostname: Callable[[], str] = socket.gethostname,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> ControllerObservation:
    """Inspect only on Artemis; never infer VM trust from its display name."""
    if hostname().casefold().split(".")[0] != config.expected_host.casefold():
        raise ArtemisControllerError("controller refuses a host other than Artemis")
    moment = now()
    try:
        report = inventory()
    except Exception as exc:
        # Hyper-V subprocess error details can contain paths, account names or
        # other sensitive host data. Only a bounded reason is journaled.
        return ControllerObservation(
            "unavailable", None, None, (_hyperv_failure_code(exc),), moment,
        )
    try:
        if not isinstance(report, Mapping):
            raise ArtemisControllerError("Hyper-V inventory returned invalid object")
        vm = report.get("host_inventory")
        review = report.get("read_only_review")
        if not isinstance(vm, Mapping) or not isinstance(review, Mapping):
            raise ArtemisControllerError("required reviewed Hyper-V metadata missing")
        actual_id = str(UUID(str(vm.get("VmId"))))
        if vm.get("Name") != config.vm_name or actual_id != str(config.expected_vm_id):
            raise ArtemisControllerError("Hyper-V Sofia VM GUID/name changed; refuse")
        if (
            report.get("activation_authorized") is not False
            or report.get("canonical_writer_active") != "unverified"
            or review.get("may_activate_canonical_writer") is not False
        ):
            raise ArtemisControllerError("untrusted inventory claims activation authority")
        reasons = review.get("host_blockers", ())
        if not isinstance(reasons, (tuple, list)) or not all(
            isinstance(x, str) and 0 < len(x) <= 128 for x in reasons
        ) or len(reasons) > 32:
            raise ArtemisControllerError("Hyper-V review blockers are invalid")
        eligible = review.get("inventory_eligible_for_review")
        if type(eligible) is not bool:
            raise ArtemisControllerError("Hyper-V review status is invalid")
        state = vm.get("State")
        if not isinstance(state, str) or len(state) > 32:
            raise ArtemisControllerError("Hyper-V VM state is unavailable")
        outcome = "observed" if eligible else "requires_review"
        return ControllerObservation(
            outcome, actual_id, state, tuple(reasons), moment,
        )
    except (RuntimeError, ValueError, TypeError, OSError, KeyError):
        return ControllerObservation(
            "unavailable", None, None, ("host_inventory_not_trusted",), moment,
        )


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@contextmanager
def _exclusive_file_lock(path: Path) -> Iterator[None]:
    """Serialize all local writer processes; SCM service is not a DB lease."""
    if path.is_symlink():
        raise ArtemisControllerError("controller lock redirection refused")
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ArtemisControllerJournal:
    """Fail-closed local hash chain, not remotely witnessed immutable evidence."""

    def __init__(self, audit_directory: Path) -> None:
        _safe_existing_directory(audit_directory)
        self.path = audit_directory / "artemis-controller.jsonl"
        self.lock_path = audit_directory / ".artemis-controller.lock"

    def _last(self) -> tuple[int, str]:
        if self.path.is_symlink():
            raise ArtemisControllerError("controller journal symlink refused")
        if not self.path.exists():
            return (0, _GENESIS)
        if not self.path.is_file() or self.path.stat().st_size > _MAX_JOURNAL_BYTES:
            raise ArtemisControllerError("controller journal exceeds safe bounds")
        index, previous = 0, _GENESIS
        with self.path.open("rb") as journal:
            for line in journal:
                if len(line) > _MAX_RECEIPT_BYTES or not line.endswith(b"\n"):
                    raise ArtemisControllerError("partial or oversized journal receipt")
                try:
                    entry = json.loads(line)
                    if not isinstance(entry, dict):
                        raise ValueError("journal entry must be an object")
                    digest = entry.pop("sha256")
                    if (
                        type(entry.get("sequence")) is not int
                        or entry["sequence"] != index + 1
                        or entry.get("previous_sha256") != previous
                        or not isinstance(digest, str)
                        or sha256(_canonical_bytes(entry)).hexdigest() != digest
                    ):
                        raise ValueError("invalid chain")
                except (UnicodeError, TypeError, ValueError, KeyError) as exc:
                    raise ArtemisControllerError("controller audit chain failed verification") from exc
                index += 1
                previous = digest
        return index, previous

    def append(self, observation: ControllerObservation) -> dict[str, Any]:
        if not isinstance(observation, ControllerObservation):
            raise TypeError("controller observation required")
        with _exclusive_file_lock(self.lock_path):
            sequence, prior = self._last()
            entry = {
                "sequence": sequence + 1,
                "previous_sha256": prior,
                **observation.payload(),
            }
            digest = sha256(_canonical_bytes(entry)).hexdigest()
            result = {**entry, "sha256": digest}
            line = _canonical_bytes(result) + b"\n"
            if len(line) > _MAX_RECEIPT_BYTES:
                raise ArtemisControllerError("controller receipt exceeds bounds")
            if self.path.exists() and self.path.stat().st_size + len(line) > _MAX_JOURNAL_BYTES:
                raise ArtemisControllerError("controller journal at capacity; rotate under supervision")
            with self.path.open("ab") as journal:
                journal.write(line)
                journal.flush()
                os.fsync(journal.fileno())
            return result

    def inspect(self) -> tuple[int, str]:
        with _exclusive_file_lock(self.lock_path):
            return self._last()


def controller_once(
    config: ArtemisControllerConfig,
    *,
    inventory: Callable[[], Mapping[str, Any]] | None = None,
    hostname: Callable[[], str] = socket.gethostname,
) -> dict[str, Any]:
    if hostname().casefold().split(".")[0] != config.expected_host.casefold():
        raise ArtemisControllerError("controller cannot run outside Artemis")
    if inventory is None:
        # The independently restricted SCM account can access this exact
        # read-only CIM class, not the wider Get-VM / Get-VMSwitch commands.
        # This path provides identity + EnabledState only, never full host
        # preflight, operational readiness or canonical writer authority.
        from sofia.ops.artemis_wmi import ArtemisWmiObserver
        inventory = ArtemisWmiObserver(expected_vm_id=config.expected_vm_id)
    return ArtemisControllerJournal(config.audit_directory).append(
        observe_exact_sofia(config, inventory=inventory, hostname=hostname)
    )


def controller_run(
    config: ArtemisControllerConfig,
    *,
    stop: Event,
    inventory: Callable[[], Mapping[str, Any]] | None = None,
    hostname: Callable[[], str] = socket.gethostname,
) -> None:
    if not isinstance(stop, Event):
        raise TypeError("thread stop event required")
    if hostname().casefold().split(".")[0] != config.expected_host.casefold():
        raise ArtemisControllerError("controller cannot run outside Artemis")
    while not stop.is_set():
        controller_once(config, inventory=inventory, hostname=hostname)
        stop.wait(config.poll_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Artemis-only independent controller observation")
    parser.add_argument("action", choices=("once", "watch", "verify-journal"))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if sys.platform != "win32":
            raise ArtemisControllerError("controller is restricted to Windows host Artemis")
        config = ArtemisControllerConfig.load(args.config)
        if socket.gethostname().casefold().split(".")[0] != "artemis":
            raise ArtemisControllerError("this is not Artemis")
        if args.action == "verify-journal":
            sequence, digest = ArtemisControllerJournal(config.audit_directory).inspect()
            print(json.dumps({"records": sequence, "chain_head": digest}))
        elif args.action == "once":
            print(json.dumps(controller_once(config), sort_keys=True))
        else:
            stop = Event()
            try:
                controller_run(config, stop=stop)
            except KeyboardInterrupt:
                stop.set()
        return 0
    except (OSError, ValueError, TypeError, ArtemisControllerError) as exc:
        print(f"Artemis controller refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
