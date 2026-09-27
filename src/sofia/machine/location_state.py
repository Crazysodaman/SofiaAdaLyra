from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from sofia.machine.location import (
    MachineLocationRecord,
    MachineLocationRegistry,
)
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


class StatePlaneMachineLocationRegistry:
    """Authoritative machine-location registry with one-time JSON import."""

    NAMESPACE = "machine-location"

    def __init__(
        self,
        state_plane: StatePlane,
        *,
        legacy_path: Path | None = None,
    ) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self.state_plane = state_plane
        self.legacy_path = legacy_path
        self._import_legacy_if_needed()

    @staticmethod
    def _encode(record: MachineLocationRecord) -> bytes:
        return json.dumps(
            {
                "machine_id": record.machine_id,
                "hostname": record.hostname,
                "label": record.label,
                "timezone": record.timezone,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "updated_at": record.updated_at.isoformat(),
                "source": record.source,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def _decode(record: StateRecord) -> MachineLocationRecord:
        raw = json.loads(record.value.decode("utf-8"))
        return MachineLocationRecord(
            machine_id=raw["machine_id"],
            hostname=raw["hostname"],
            label=raw["label"],
            timezone=raw["timezone"],
            latitude=raw["latitude"],
            longitude=raw["longitude"],
            updated_at=datetime.fromisoformat(raw["updated_at"]),
            source=raw.get("source", "operator"),
        )

    def _import_legacy_if_needed(self) -> None:
        if self.state_plane.list_namespace(self.NAMESPACE):
            return
        if self.legacy_path is None or not self.legacy_path.is_file():
            return
        legacy = MachineLocationRegistry(self.legacy_path)
        for record in legacy.records():
            self.set(
                MachineLocationRecord(
                    machine_id=record.machine_id,
                    hostname=record.hostname,
                    label=record.label,
                    timezone=record.timezone,
                    latitude=record.latitude,
                    longitude=record.longitude,
                    updated_at=record.updated_at,
                    source=f"legacy-json:{record.source}",
                )
            )

    def get(self, machine_id: str) -> MachineLocationRecord | None:
        if not isinstance(machine_id, str) or not machine_id.strip():
            raise ValueError("machine_id is required")
        record = self.state_plane.read(
            StateKey(
                namespace=self.NAMESPACE,
                key=machine_id.strip(),
            )
        )
        return None if record is None else self._decode(record)

    def find_hostname(
        self,
        hostname: str,
    ) -> tuple[MachineLocationRecord, ...]:
        if not isinstance(hostname, str) or not hostname.strip():
            raise ValueError("hostname is required")
        wanted = hostname.strip().casefold()
        return tuple(
            record
            for record in self.records()
            if record.hostname.casefold() == wanted
        )

    def set(self, record: MachineLocationRecord) -> None:
        if not isinstance(record, MachineLocationRecord):
            raise TypeError("record must be MachineLocationRecord")
        key = StateKey(
            namespace=self.NAMESPACE,
            key=record.machine_id,
        )
        existing = self.state_plane.read(key)
        self.state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=1 if existing is None else existing.revision + 1,
                value=self._encode(record),
                updated_at=record.updated_at,
                source=record.source,
            ),
            expected_revision=None if existing is None else existing.revision,
        )

    def records(self) -> tuple[MachineLocationRecord, ...]:
        return tuple(
            self._decode(record)
            for record in self.state_plane.list_namespace(self.NAMESPACE)
        )
