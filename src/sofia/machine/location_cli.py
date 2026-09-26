"""Operator CLI for durable machine-location configuration.

Examples:
    python -m sofia.machine.location_cli set-local --label "Home Lab" \
        --timezone America/Chicago --latitude 32.5 --longitude -97.1

    python -m sofia.machine.location_cli list
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .discovery import create_machine_discovery
from .location import (
    MachineLocationRegistry,
    new_machine_location,
)
from .persistence import MachineInventoryPersistence


def _state_directory() -> Path:
    return Path(__file__).resolve().parents[3] / "state"


def _registry(state_directory: Path) -> MachineLocationRegistry:
    return MachineLocationRegistry(
        state_directory / "machine-locations.json"
    )


def _known_identity(
    state_directory: Path,
    *,
    machine_id: str | None,
    hostname: str | None,
) -> tuple[str, str]:
    if machine_id:
        inventory_path = state_directory / "machine-inventory.json"
        if inventory_path.exists():
            inventory = MachineInventoryPersistence(
                inventory_path
            ).load()
            observation = inventory.get(machine_id)
            if observation is not None:
                return (
                    observation.machine_id,
                    observation.hostname,
                )
        if not hostname:
            raise ValueError(
                "hostname is required when machine_id is not present "
                "in machine-inventory.json"
            )
        return machine_id, hostname

    if not hostname:
        raise ValueError(
            "one of --machine-id or --hostname is required"
        )

    inventory_path = state_directory / "machine-inventory.json"
    if not inventory_path.exists():
        raise ValueError(
            "machine-inventory.json does not exist; use --machine-id "
            "with --hostname or configure the machine locally"
        )
    inventory = MachineInventoryPersistence(
        inventory_path
    ).load()
    matches = [
        observation
        for machine_id_value in inventory.machine_ids()
        if (
            (observation := inventory.get(machine_id_value))
            is not None
            and observation.hostname.casefold()
            == hostname.casefold()
        )
    ]
    if not matches:
        raise ValueError(
            f"no known machine has hostname {hostname!r}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"hostname {hostname!r} matches multiple machines; "
            "use --machine-id"
        )
    return matches[0].machine_id, matches[0].hostname


def _configure(
    registry: MachineLocationRegistry,
    *,
    machine_id: str,
    hostname: str,
    args,
) -> None:
    record = new_machine_location(
        machine_id=machine_id,
        hostname=hostname,
        label=args.label,
        timezone_name=args.timezone,
        latitude=args.latitude,
        longitude=args.longitude,
    )
    registry.set(record)
    print(
        f"Saved {record.hostname} ({record.machine_id}) "
        f"location as {record.label} in {record.timezone}."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.machine.location_cli",
        description=(
            "Configure durable machine locations used by "
            "PKG-ENVIRONMENT."
        ),
    )
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=_state_directory(),
        help="Sofía state directory (default: repository state/).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    local = sub.add_parser(
        "set-local",
        help="Configure the machine on which this command is running.",
    )
    known = sub.add_parser(
        "set-known",
        help="Configure a machine already known to Sofía.",
    )
    sub.add_parser(
        "list",
        help="List configured machine locations without coordinates.",
    )

    for target in (local, known):
        target.add_argument("--label", required=True)
        target.add_argument("--timezone", required=True)
        target.add_argument("--latitude", required=True, type=float)
        target.add_argument("--longitude", required=True, type=float)

    known.add_argument("--machine-id")
    known.add_argument("--hostname")
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    state_directory = args.state_directory.resolve()
    registry = _registry(state_directory)

    if args.command == "set-local":
        identity = create_machine_discovery().discover().identity
        _configure(
            registry,
            machine_id=identity.machine_id,
            hostname=identity.hostname,
            args=args,
        )
        return 0

    if args.command == "set-known":
        try:
            machine_id, hostname = _known_identity(
                state_directory,
                machine_id=args.machine_id,
                hostname=args.hostname,
            )
        except ValueError as exc:
            parser.error(str(exc))
        _configure(
            registry,
            machine_id=machine_id,
            hostname=hostname,
            args=args,
        )
        return 0

    if args.command == "list":
        records = registry.records()
        if not records:
            print("No configured machine locations.")
            return 0
        for record in records:
            print(
                f"{record.hostname} ({record.machine_id}): "
                f"{record.label} [{record.timezone}]"
            )
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
